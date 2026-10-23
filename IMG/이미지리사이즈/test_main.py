import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import main


class ResizeTests(unittest.TestCase):
    def test_dimensions(self):
        with Image.new("RGB", (400, 200)) as image:
            for width, height, mode, expected in (
                (100, None, None, (100, 50)),
                (None, 100, None, (200, 100)),
                (100, 100, "cover", (100, 100)),
                (100, 100, "contain", (100, 50)),
                (800, None, None, (800, 400)),
            ):
                with self.subTest(width=width, height=height, mode=mode):
                    with main.resize_image(image, width, height, mode) as result:
                        self.assertEqual(result.size, expected)

    def test_portrait_and_rounding(self):
        with Image.new("RGB", (1, 1000)) as image:
            with main.resize_image(image, None, 1) as result:
                self.assertEqual(result.size, (1, 1))
            with main.resize_image(image, 100, 100, "contain") as result:
                self.assertEqual(result.size, (1, 100))
        with Image.new("RGB", (200, 400)) as image:
            with main.resize_image(image, 100, 100, "contain") as result:
                self.assertEqual(result.size, (50, 100))
            with main.resize_image(image, 100, None) as result:
                self.assertEqual(result.size, (100, 200))

    def test_cover_crops_center(self):
        with Image.new("RGB", (300, 100), "red") as image:
            image.paste("blue", (100, 0, 200, 100))
            with main.resize_image(image, 100, 100, "cover") as result:
                self.assertEqual(result.getpixel((0, 50)), (0, 0, 255))
                self.assertEqual(result.getpixel((99, 50)), (0, 0, 255))

    def test_invalid_options(self):
        with Image.new("RGB", (10, 10)) as image:
            for width, height, mode in (
                (None, None, None), (0, None, None), (None, -1, None),
                (10, 10, None), (10, None, "cover"),
            ):
                with self.subTest(width=width, height=height, mode=mode):
                    with self.assertRaises(ValueError):
                        main.resize_image(image, width, height, mode)

    def test_batch_transparency_collision_and_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input"
            destination = root / "output"
            source.mkdir()
            original = source / "사진.PNG"
            with Image.new("RGBA", (40, 20), (255, 0, 0, 80)) as image:
                image.save(original)
            original_bytes = original.read_bytes()
            args = ["--width", "10", "--input", str(source), "--output", str(destination)]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main.main(args), 0)
                self.assertEqual(main.main(args), 0)
            self.assertEqual(original.read_bytes(), original_bytes)
            self.assertTrue((destination / "사진_1.PNG").exists())
            with Image.open(destination / original.name) as result:
                self.assertEqual(result.size, (10, 5))
                self.assertEqual(result.getpixel((0, 0)), (255, 0, 0, 80))
            (source / "broken.png").write_bytes(b"not an image")
            errors = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                self.assertEqual(main.main(args), 1)
            self.assertIn("broken.png", errors.getvalue())
            self.assertTrue((destination / "사진_2.PNG").exists())
            self.assertFalse((destination / "broken.png").exists())

    def test_exif_orientation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "rotated.jpg"
            with Image.new("RGB", (40, 20), "red") as image:
                exif = Image.Exif()
                exif[274] = 6
                image.save(source, exif=exif)
            _, size = main.process_image(source, root / "result.jpg", 10, None, None)
            self.assertEqual(size, (10, 20))
            with Image.open(root / "result.jpg") as result:
                self.assertNotIn(274, result.getexif())

    def test_animation_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "animated.gif"
            with Image.new("RGB", (10, 10), "red") as first:
                with Image.new("RGB", (10, 10), "blue") as second:
                    first.save(source, save_all=True, append_images=[second])
            with self.assertRaisesRegex(ValueError, "애니메이션"):
                main.process_image(source, root / "result.gif", 5, None, None)
            self.assertFalse((root / "result.gif").exists())

    def test_supported_formats(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for extension, image_format in (
                ("jpg", "JPEG"), ("png", "PNG"), ("webp", "WEBP"),
                ("bmp", "BMP"), ("tiff", "TIFF"), ("gif", "GIF"),
            ):
                with self.subTest(image_format=image_format):
                    source = root / f"source.{extension}"
                    destination = root / f"result.{extension}"
                    with Image.new("RGB", (40, 20), "red") as image:
                        image.save(source)
                    main.process_image(source, destination, 10, 10, "cover")
                    with Image.open(destination) as result:
                        self.assertEqual(result.size, (10, 10))
                        self.assertEqual(result.format, image_format)

    def test_failed_save_removes_partial_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "result.png"
            with Image.new("RGB", (10, 10)) as image:
                with patch.object(image, "save", side_effect=OSError("disk full")):
                    with self.assertRaisesRegex(OSError, "disk full"):
                        main.save_new_image(image, destination, "PNG")
            self.assertFalse(destination.exists())

    def test_cli_rejects_invalid_arguments(self):
        for args in (
            ["--width", "0"], ["--height", "-1"], ["--width", "abc"],
            ["--width", "10", "--height", "10"], ["--mode", "cover"],
            ["--width", "10", "--mode", "contain"],
        ):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    main.main(args)
                self.assertEqual(raised.exception.code, 2)

    def test_interactive_input_validation(self):
        with patch("builtins.input", side_effect=["invalid", "4", "0", "100", "50"]):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main.prompt_options(), (100, 50, "contain"))

    def test_missing_empty_and_same_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for source, destination in (
                (root / "missing", root / "out"), (root, root / "out"), (root, root),
            ):
                with self.subTest(source=source, destination=destination):
                    with contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(main.main([
                            "--width", "10", "--input", str(source),
                            "--output", str(destination),
                        ]), 1)


if __name__ == "__main__":
    unittest.main()
