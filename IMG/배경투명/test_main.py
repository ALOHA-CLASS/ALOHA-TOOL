import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

import main


class BackgroundRemovalTests(unittest.TestCase):
    def test_white_background_and_enclosed_regions(self):
        with Image.new("RGB", (9, 9), "white") as image:
            draw = ImageDraw.Draw(image)
            draw.rectangle((2, 2, 6, 6), fill="black")
            draw.rectangle((3, 3, 5, 5), fill="white")
            with main.remove_background(image, main.RemovalOptions()) as result:
                self.assertEqual(result.mode, "RGBA")
                self.assertEqual(result.size, image.size)
                self.assertEqual(result.getpixel((0, 0))[3], 0)
                self.assertEqual(result.getpixel((2, 2)), (0, 0, 0, 255))
                self.assertEqual(result.getpixel((4, 4))[3], 0)
            with main.remove_background(
                image, main.RemovalOptions(scope="edges")
            ) as result:
                self.assertEqual(result.getpixel((0, 0))[3], 0)
                self.assertEqual(result.getpixel((4, 4))[3], 255)
            self.assertEqual(image.getpixel((0, 0)), (255, 255, 255))

    def test_tolerance_softness_and_strength(self):
        with Image.new("RGB", (5, 1)) as image:
            image.putdata([
                (255, 255, 255), (245, 245, 245), (235, 235, 235),
                (225, 225, 225), (0, 0, 0),
            ])
            for options, expected in (
                (main.RemovalOptions("white", 10, 0), [0, 0, 255, 255, 255]),
                (main.RemovalOptions("white", 10, 20), [0, 0, 127, 255, 255]),
                (main.RemovalOptions("white", 10, 0, 50), [127, 127, 255, 255, 255]),
                (main.RemovalOptions("white", 255, 0), [0, 0, 0, 0, 0]),
            ):
                with self.subTest(options=options):
                    with main.remove_background(image, options) as result:
                        self.assertEqual(list(result.getchannel("A").tobytes()), expected)

    def test_alpha_is_never_increased(self):
        with Image.new("RGBA", (4, 1)) as image:
            image.putdata([
                (255, 255, 255, 0), (255, 255, 255, 128),
                (0, 0, 0, 80), (255, 0, 0, 0),
            ])
            with main.remove_background(
                image, main.RemovalOptions("white", strength=50)
            ) as result:
                self.assertEqual(list(result.getchannel("A").tobytes()), [0, 63, 80, 0])
            with main.remove_background(
                image, main.RemovalOptions(strength=0)
            ) as result:
                self.assertEqual(result.tobytes(), image.tobytes())

    def test_auto_ignores_transparent_border_pixels(self):
        with Image.new("RGBA", (3, 3), (255, 0, 0, 0)) as image:
            image.putpixel((1, 0), (0, 0, 255, 255))
            image.putpixel((1, 1), (0, 0, 255, 255))
            self.assertEqual(main.detect_background(image), (0, 0, 255))
            with main.remove_background(image, main.RemovalOptions()) as result:
                self.assertEqual(result.getpixel((1, 1))[3], 0)
            image.putpixel((1, 0), (0, 0, 255, 0))
            with self.assertRaisesRegex(ValueError, "--background"):
                main.remove_background(image, main.RemovalOptions())
            with main.remove_background(
                image, main.RemovalOptions("#0000ff")
            ) as result:
                self.assertEqual(result.getpixel((1, 1))[3], 0)

    def test_black_and_custom_backgrounds(self):
        for color in ("black", "#00ff00"):
            normalized = main.background_color(color)
            with self.subTest(color=color), Image.new("RGB", (2, 1), normalized) as image:
                image.putpixel((1, 0), (255, 0, 0))
                with main.remove_background(
                    image, main.RemovalOptions(color, 0, 0)
                ) as result:
                    self.assertEqual(result.getpixel((0, 0))[3], 0)
                    self.assertEqual(result.getpixel((1, 0)), (255, 0, 0, 255))

    def test_edge_connectivity_is_four_way(self):
        with Image.new("RGB", (5, 5), "black") as image:
            image.putpixel((0, 0), (255, 255, 255))
            image.putpixel((1, 1), (255, 255, 255))
            with main.remove_background(
                image, main.RemovalOptions("white", scope="edges")
            ) as result:
                self.assertEqual(result.getpixel((0, 0))[3], 0)
                self.assertEqual(result.getpixel((1, 1))[3], 255)

    def test_transparent_pixels_connect_background(self):
        with Image.new("RGBA", (5, 5), "black") as image:
            image.putpixel((2, 0), (255, 0, 0, 0))
            image.putpixel((2, 1), (255, 0, 0, 0))
            image.putpixel((2, 2), (255, 255, 255, 255))
            with main.remove_background(
                image, main.RemovalOptions("white", scope="edges")
            ) as result:
                self.assertEqual(result.getpixel((2, 2))[3], 0)

    def test_feather_softens_mask_without_increasing_existing_alpha(self):
        with Image.new("RGBA", (21, 21), "white") as image:
            ImageDraw.Draw(image).rectangle((7, 7, 13, 13), fill=(0, 0, 0, 100))
            with main.remove_background(
                image, main.RemovalOptions("white", feather=1)
            ) as result:
                self.assertLess(result.getpixel((7, 10))[3], 100)
                self.assertGreater(result.getpixel((6, 10))[3], 0)
                self.assertGreater(result.getpixel((10, 10))[3], 90)
                self.assertEqual(result.getpixel((0, 0))[3], 0)

    def test_narrow_images(self):
        for size in ((1, 1), (1, 5), (5, 1)):
            for scope in ("all", "edges"):
                with self.subTest(size=size, scope=scope):
                    with Image.new("RGB", size, "white") as image:
                        with main.remove_background(
                            image, main.RemovalOptions(scope=scope)
                        ) as result:
                            self.assertEqual(result.getchannel("A").getextrema(), (0, 0))

    def test_palette_transparency(self):
        with Image.new("P", (2, 1)) as image:
            image.putpalette([255, 255, 255, 0, 0, 0] + [0] * 762)
            image.putdata([0, 1])
            image.info["transparency"] = 1
            with main.remove_background(
                image, main.RemovalOptions("white")
            ) as result:
                self.assertEqual(list(result.getchannel("A").tobytes()), [0, 0])

    def test_invalid_options(self):
        for kwargs in (
            {"background": "#zzzzzz"}, {"background": "blue"},
            {"tolerance": -1}, {"tolerance": 256}, {"softness": -1},
            {"softness": 256}, {"strength": 101}, {"strength": -1},
            {"scope": "unknown"}, {"feather": 21}, {"feather": -1},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                main.RemovalOptions(**kwargs)


class FileAndCliTests(unittest.TestCase):
    def run_quietly(self, args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return main.main(args)

    def test_batch_formats_collisions_and_original_preservation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input"
            destination = root / "output"
            source.mkdir()
            original = source / "로고.PNG"
            with Image.new("RGBA", (7, 7), "white") as image:
                image.putpixel((3, 3), (0, 0, 0, 90))
                image.save(original)
            original_bytes = original.read_bytes()
            for target in ("png", "webp"):
                args = [
                    "--to", target, "--background", "white",
                    "--input", str(source), "--output", str(destination),
                ]
                self.assertEqual(self.run_quietly(args), 0)
                self.assertEqual(self.run_quietly(args), 0)
                self.assertTrue((destination / f"로고_transparent_1.{target}").exists())
                with Image.open(destination / f"로고_transparent.{target}") as result:
                    self.assertEqual(result.format, target.upper())
                    self.assertEqual(result.size, (7, 7))
                    self.assertEqual(result.getpixel((0, 0))[3], 0)
                    self.assertEqual(result.getpixel((3, 3)), (0, 0, 0, 90))
            self.assertEqual(original.read_bytes(), original_bytes)

    def test_all_supported_input_formats(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for suffix in main.EXTENSIONS:
                with self.subTest(suffix=suffix):
                    source = root / f"source{suffix}"
                    with Image.new("RGB", (5, 5), "white") as image:
                        image.save(source)
                    destination = root / f"result_{suffix[1:]}.png"
                    main.process_image(
                        source, destination, main.RemovalOptions("white"), "png"
                    )
                    with Image.open(destination) as result:
                        self.assertEqual(result.getchannel("A").getextrema(), (0, 0))

    def test_corrupt_file_does_not_stop_batch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input"
            destination = root / "output"
            source.mkdir()
            (source / "broken.png").write_bytes(b"not an image")
            with Image.new("RGB", (3, 3), "white") as image:
                image.save(source / "valid.png")
            errors = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                code = main.main([
                    "--to", "png", "--input", str(source), "--output", str(destination),
                ])
            self.assertEqual(code, 1)
            self.assertIn("broken.png", errors.getvalue())
            self.assertTrue((destination / "valid_transparent.png").exists())
            self.assertFalse((destination / "broken_transparent.png").exists())

    def test_single_file_and_lossy_webp(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "logo.png"
            with Image.new("RGB", (5, 5), "white") as image:
                image.putpixel((2, 2), (0, 0, 0))
                image.save(source)
            self.assertEqual(self.run_quietly([
                str(source), "--to", "webp", "--lossy", "--quality", "80",
                "--output", str(root / "output"),
            ]), 0)
            with Image.open(root / "output" / "logo_transparent.webp") as result:
                self.assertEqual(result.getpixel((0, 0))[3], 0)
                self.assertEqual(result.getpixel((2, 2))[3], 255)

    def test_missing_empty_same_and_unsupported_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "text.txt").write_text("not an image", encoding="utf-8")
            for args in (
                ["--input", str(root / "missing")],
                ["--input", str(root)],
                ["--input", str(root), "--output", str(root)],
                [str(root / "text.txt")],
                [str(root / "missing.png")],
            ):
                with self.subTest(args=args):
                    self.assertEqual(self.run_quietly(["--to", "png"] + args), 1)

    def test_exif_orientation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, destination = root / "rotated.jpg", root / "result.png"
            with Image.new("RGB", (7, 3), "white") as image:
                exif = Image.Exif()
                exif[274] = 6
                image.save(source, exif=exif)
            main.process_image(source, destination, main.RemovalOptions("white"), "png")
            with Image.open(destination) as result:
                self.assertEqual(result.size, (3, 7))
                self.assertNotIn(274, result.getexif())

    def test_animated_and_multipage_images_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for suffix in ("gif", "webp", "tiff"):
                source, destination = root / f"animated.{suffix}", root / f"{suffix}.png"
                with Image.new("RGB", (5, 5), "white") as first:
                    with Image.new("RGB", (5, 5), "black") as second:
                        first.save(source, save_all=True, append_images=[second])
                with self.subTest(suffix=suffix):
                    with self.assertRaisesRegex(ValueError, "애니메이션"):
                        main.process_image(source, destination, main.RemovalOptions(), "png")
                    self.assertFalse(destination.exists())

    def test_partial_save_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "result.png"
            with Image.new("RGBA", (2, 2)) as image:
                with patch.object(image, "save", side_effect=OSError("disk full")):
                    with self.assertRaisesRegex(OSError, "disk full"):
                        main.save_new_image(image, destination, "png")
            self.assertFalse(destination.exists())

    def test_cli_rejects_invalid_options(self):
        for args in (
            ["--to", "jpg"], ["--to", "png", "--lossy"],
            ["--tolerance", "-1"], ["--tolerance", "256"],
            ["--softness", "abc"], ["--strength", "101"], ["--feather", "21"],
            ["--quality", "0"], ["--background", "#xyzxyz"],
            ["--scope", "other"],
        ):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    main.main(args)
                self.assertEqual(raised.exception.code, 2)

    def test_interactive_defaults_validation_and_cancellation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, destination = root / "input", root / "output"
            source.mkdir()
            with Image.new("RGB", (3, 3), "white") as image:
                image.save(source / "logo.png")
            args = ["--input", str(source), "--output", str(destination)]
            answers = ["jpg", "", "invalid", "white", "-1", "", "", "101", "", "", "", ""]
            with patch("builtins.input", side_effect=answers):
                self.assertEqual(self.run_quietly(args), 0)
            with patch("builtins.input", side_effect=["webp"] + [""] * 9):
                self.assertEqual(self.run_quietly(args), 0)
            with patch("builtins.input", side_effect=EOFError):
                self.assertEqual(self.run_quietly(args), 1)
            with patch("builtins.input", side_effect=KeyboardInterrupt):
                self.assertEqual(self.run_quietly(args), 1)

    def test_output_name_validation(self):
        for value in ("", "..", "../escape", r"..\escape", "C:logo", "a?", "a\x00",
                      "CON", "nul.png", "LPT1.txt", "COM¹", ".png", "logo.", "a" * 241):
            with self.subTest(value=value), self.assertRaises(ValueError):
                main.output_name(value)
        for value, expected in (
            ("내 로고", "내 로고"), ("logo.PNG", "logo"), ("logo.webp", "logo"),
            ("logo.v2", "logo.v2"),
        ):
            self.assertEqual(main.output_name(value), expected)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            main.main(["--to", "png", "--name", "../escape"])
        self.assertEqual(raised.exception.code, 2)

    def test_custom_output_names_and_collisions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, destination = root / "input", root / "output"
            source.mkdir()
            with Image.new("RGB", (3, 3), "white") as image:
                image.save(source / "one.png")
                image.save(source / "two.png")
            args = ["--input", str(source), "--output", str(destination)]
            with patch("builtins.input", side_effect=[""] * 7 + ["../bad", "첫 로고", "둘째.PNG"]):
                self.assertEqual(self.run_quietly(args), 0)
            self.assertTrue((destination / "첫 로고.png").exists())
            self.assertTrue((destination / "둘째.png").exists())
            with patch("builtins.input", side_effect=AssertionError("unexpected prompt")):
                self.assertEqual(self.run_quietly(
                    args + ["--to", "webp", "--name", "새 로고.png"]
                ), 0)
            for name in ("새 로고.webp", "새 로고_1.webp"):
                with Image.open(destination / name) as result:
                    self.assertEqual(result.format, "WEBP")
                    self.assertEqual(result.getchannel("A").getextrema(), (0, 0))
            with patch("builtins.input", side_effect=[""] * 7 + [EOFError]):
                self.assertEqual(self.run_quietly(args), 1)
            with patch("builtins.input", side_effect=[""] * 7):
                self.assertEqual(self.run_quietly(args + ["--name", "지정됨"]), 0)
            self.assertTrue((destination / "지정됨.png").exists())
            self.assertTrue((destination / "지정됨_1.png").exists())

    def test_webp_support_error_is_explicit(self):
        with patch.object(main.features, "check", return_value=False):
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                self.assertEqual(main.main(["--to", "webp"]), 1)
            self.assertIn("WebP", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
