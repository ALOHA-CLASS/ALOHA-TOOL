import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, features

import main


class EnhancementTests(unittest.TestCase):
    def test_scale_and_limits(self):
        self.assertEqual(main.output_size((40, 20), 2), (80, 40))
        self.assertEqual(main.output_size((20, 10), 1.5), (30, 15))
        self.assertEqual(main.output_size((8000, 10000), 1), (8000, 10000))
        with self.assertRaisesRegex(ValueError, "8,000만"):
            main.output_size((8000, 10000), 1.01)
        for value in ("0", "-1", "nan", "inf", "abc"):
            with self.subTest(value=value), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    main.main(["--scale", value])
                self.assertEqual(raised.exception.code, 2)

    def test_batch_and_collisions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input"
            destination = root / "output"
            source.mkdir()
            with Image.new("RGBA", (20, 10), (255, 0, 0, 80)) as image:
                image.save(source / "사진.PNG")
            with Image.new("RGB", (10, 4), "blue") as image:
                image.save(source / "photo.jpg")
            (source / "broken.png").write_bytes(b"not an image")
            (source / "ignored.txt").write_text("not an image")
            before = (source / "사진.PNG").read_bytes()
            args = ["--scale", "1.5", "--input", str(source), "--output", str(destination)]
            errors = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                self.assertEqual(main.main(args), 1)
                self.assertEqual(main.main(args), 1)
            self.assertIn("broken.png", errors.getvalue())
            self.assertFalse((destination / "broken.png").exists())
            self.assertEqual((source / "사진.PNG").read_bytes(), before)
            with Image.open(destination / "사진.PNG") as image:
                self.assertEqual(image.size, (30, 15))
                self.assertEqual(image.getpixel((0, 0)), (255, 0, 0, 80))
            with Image.open(destination / "photo_1.jpg") as image:
                self.assertEqual(image.size, (15, 6))
            self.assertTrue((destination / "사진_1.PNG").exists())

    def test_formats_and_palette_transparency(self):
        formats = [("png", "PNG"), ("jpg", "JPEG"), ("bmp", "BMP"),
                   ("tiff", "TIFF"), ("gif", "GIF")]
        if features.check("webp"):
            formats.append(("webp", "WEBP"))
        if features.check("avif"):
            formats.append(("avif", "AVIF"))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for extension, image_format in formats:
                with self.subTest(format=image_format):
                    source = root / f"source.{extension}"
                    destination = root / f"result.{extension}"
                    with Image.new("RGB", (8, 4), "red") as image:
                        image.save(source, format=image_format)
                    main.process_image(source, destination, 2)
                    with Image.open(destination) as result:
                        self.assertEqual(result.format, image_format)
                        self.assertEqual(result.size, (16, 8))
            source = root / "palette.png"
            with Image.new("P", (2, 1)) as image:
                image.putpalette([255, 0, 0, 0, 0, 255] + [0] * 762)
                image.putdata([0, 1])
                image.save(source, transparency=0)
            main.process_image(source, root / "palette-result.png", 4)
            with Image.open(root / "palette-result.png") as result:
                self.assertEqual(result.mode, "RGBA")
                self.assertEqual(result.getpixel((0, 0))[3], 0)
                self.assertEqual(result.getpixel((7, 0))[3], 255)
                self.assertTrue(any(0 < result.getpixel((x, 0))[3] < 255 for x in range(8)))

    def test_orientation_and_animation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with Image.new("RGB", (20, 10), "red") as image:
                exif = Image.Exif()
                exif[274] = 6
                image.save(root / "rotated.jpg", exif=exif)
            _, size = main.process_image(root / "rotated.jpg", root / "out.jpg", 2)
            self.assertEqual(size, (20, 40))
            with Image.open(root / "out.jpg") as result:
                self.assertNotIn(274, result.getexif())
            with Image.new("RGB", (5, 5), "red") as first:
                with Image.new("RGB", (5, 5), "blue") as second:
                    first.save(root / "animated.gif", save_all=True, append_images=[second])
            with self.assertRaisesRegex(ValueError, "애니메이션"):
                main.process_image(root / "animated.gif", root / "out.gif", 2)
            self.assertFalse((root / "out.gif").exists())

    def test_failed_save_removes_partial_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "result.png"
            with Image.new("RGB", (2, 2)) as image:
                with patch.object(image, "save", side_effect=OSError("disk full")):
                    with self.assertRaises(OSError):
                        main.save_new_image(image, destination, "PNG")
            self.assertFalse(destination.exists())

    def test_interactive_and_directory_errors(self):
        with patch("builtins.input", side_effect=["x", "0", "2"]):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main.prompt_factor(), 2)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for source, destination in ((root, root), (root, root / "out"),
                                        (root / "missing", root / "out")):
                with self.subTest(source=source, destination=destination):
                    with contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(main.main([
                            "--scale", "2", "--input", str(source),
                            "--output", str(destination),
                        ]), 1)

    def test_mode_prompt_and_model_errors(self):
        with patch("builtins.input", side_effect=["3", "2"]):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main.prompt_mode(), "ai")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input"
            source.mkdir()
            with Image.new("RGB", (4, 4), "red") as image:
                image.save(source / "one.png")
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                result = main.main(["--mode", "ai", "--scale", "2",
                                    "--model", str(root / "missing.pb"),
                                    "--input", str(source), "--output", str(root / "out")])
            self.assertEqual(result, 1)
            self.assertIn("모델", errors.getvalue())
            self.assertFalse((root / "out" / "one.png").exists())
            corrupt = root / "corrupt.pb"
            corrupt.write_bytes(b"not a model")
            with self.assertRaisesRegex(RuntimeError, "검증"):
                main.load_ai_model(corrupt)

    @unittest.skipUnless(os.environ.get("FSRCNN_TEST_MODEL"), "실제 AI 모델 경로가 필요합니다.")
    def test_real_model_ai_batch(self):
        import cv2
        import numpy as np

        model_path = Path(os.environ["FSRCNN_TEST_MODEL"])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / "input", root / "output"
            source.mkdir()
            with Image.new("RGBA", (130, 10), (200, 30, 70, 90)) as image:
                image.putpixel((50, 5), (0, 0, 255, 0))
                image.save(source / "alpha.png")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main.main([
                    "--mode", "ai", "--scale", "1.5", "--model", str(model_path),
                    "--input", str(source), "--output", str(output),
                ]), 0)
            with Image.open(output / "alpha.png") as image:
                self.assertEqual(image.size, (195, 15))
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.getpixel((0, 0))[3], 90)
            model = main.load_ai_model(model_path)
            reference = cv2.dnn_superres.DnnSuperResImpl_create()
            reference.readModel(str(model_path))
            reference.setModel("fsrcnn", 4)
            pixels = np.random.default_rng(42).integers(0, 256, (16, 20, 3), dtype=np.uint8)
            actual = model.upsample(pixels)
            expected = reference.upsample(pixels)
            self.assertLessEqual(np.abs(actual.astype(int) - expected.astype(int)).max(), 2)
            with Image.open(source / "alpha.png") as original:
                with main.ai_enlarge(original, (195, 15), model) as result:
                    with original.convert("RGB") as rgb:
                        with rgb.resize(result.size, Image.Resampling.LANCZOS) as simple:
                            self.assertNotEqual(result.convert("RGB").tobytes(), simple.tobytes())


if __name__ == "__main__":
    unittest.main()
