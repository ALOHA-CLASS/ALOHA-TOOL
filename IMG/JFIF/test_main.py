import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import main


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.input_dir = root / "input"
        self.output_dir = root / "output"
        self.input_dir.mkdir()
        self.source = self.input_dir / "sample.jfif"
        with Image.new("RGB", (16, 8), "red") as image:
            image.save(self.source, format="JPEG")
        input_patch = patch.object(main, "INPUT_DIR", self.input_dir)
        output_patch = patch.object(main, "OUTPUT_DIR", self.output_dir)
        input_patch.start()
        output_patch.start()
        self.addCleanup(input_patch.stop)
        self.addCleanup(output_patch.stop)

    def run_main(self, args, answers=()):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("builtins.input", side_effect=answers), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = main.main(args)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_interactive_default_and_formats(self):
        self.assertEqual(self.run_main([], ["photo", ""])[0], 0)
        for extension, expected in (
            ("jpg", "JPEG"), ("jpeg", "JPEG"), ("png", "PNG"),
            (".GIF", "GIF"), ("webp", "WEBP"), ("bmp", "BMP"),
            ("tif", "TIFF"), ("tiff", "TIFF"),
        ):
            with self.subTest(extension=extension):
                if extension != "jpg":
                    self.assertEqual(self.run_main(["photo", "--to", extension])[0], 0)
                path = self.output_dir / ("photo." + extension.lower().lstrip("."))
                with Image.open(path) as image:
                    self.assertEqual(image.format, expected)
                    self.assertEqual(image.size, (16, 8))

    def test_batch_order_and_existing_output(self):
        with Image.new("RGB", (16, 8), "blue") as image:
            image.save(self.input_dir / "a.JFIF", format="JPEG")
        (self.input_dir / "ignored.txt").write_text("ignored")
        (self.input_dir / "folder.jfif").mkdir()
        self.output_dir.mkdir()
        existing = self.output_dir / "photo_1.png"
        existing.write_bytes(b"existing")
        result, output, error = self.run_main(["photo", "--to", "png"])
        self.assertEqual(result, 1)
        self.assertIn("[실패] a.JFIF", error)
        self.assertIn("sample.jfif ->", output)
        self.assertIn("성공 1개, 실패 1개", output)
        self.assertEqual(existing.read_bytes(), b"existing")
        with Image.open(self.output_dir / "photo_2.png") as image:
            self.assertGreater(image.getpixel((0, 0))[0], 200)

    def test_invalid_input_and_failed_save(self):
        for args in (["photo", "--to", "exe"], [""], ["../photo"], ["CON"]):
            with self.subTest(args=args):
                result, _, error = self.run_main(args)
                self.assertEqual(result, 1)
                self.assertIn("[오류]", error)
        with Image.new("RGB", (4, 4)) as image:
            image.save(self.source, format="PNG")
        self.assertEqual(self.run_main(["photo"])[0], 1)
        self.assertFalse((self.output_dir / "photo.jpg").exists())
        with Image.new("RGB", (4, 4)) as image:
            image.save(self.source, format="JPEG")
        with patch.object(Image.Image, "save", side_effect=OSError("save failed")):
            self.assertEqual(self.run_main(["photo"])[0], 1)
        self.assertFalse((self.output_dir / "photo.jpg").exists())
        self.source.unlink()
        result, _, error = self.run_main(["photo"])
        self.assertEqual(result, 1)
        self.assertIn("변환할 JFIF 파일이 없습니다", error)

    def test_cmyk_and_exif_orientation(self):
        with Image.new("CMYK", (16, 8), (0, 255, 255, 0)) as image:
            exif = image.getexif()
            exif[274] = 6
            image.save(self.source, format="JPEG", exif=exif)
        self.assertEqual(self.run_main(["photo", "--to", "png"])[0], 0)
        with Image.open(self.output_dir / "photo.png") as image:
            self.assertEqual(image.mode, "RGB")
            self.assertEqual(image.size, (8, 16))


if __name__ == "__main__":
    unittest.main()
