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
        self.source = self.input_dir / "sample.avif"
        with Image.new("RGBA", (16, 16), (255, 0, 0, 0)) as image:
            image.save(self.source, format="AVIF", lossless=True)
        self.input_patch = patch.object(main, "INPUT_DIR", self.input_dir)
        self.output_patch = patch.object(main, "OUTPUT_DIR", self.output_dir)
        self.input_patch.start()
        self.output_patch.start()
        self.addCleanup(self.input_patch.stop)
        self.addCleanup(self.output_patch.stop)

    def run_main(self, args, answers=()):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("builtins.input", side_effect=answers), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = main.main(args)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_interactive_default_jpg_and_transparency(self):
        result, _, _ = self.run_main([], ["photo", ""])
        self.assertEqual(result, 0)
        with Image.open(self.output_dir / "photo.jpg") as image:
            self.assertEqual(image.format, "JPEG")
            self.assertEqual(image.getpixel((0, 0)), (255, 255, 255))

    def test_formats_and_default_command_line(self):
        for extension, expected in (
            ("png", "PNG"), (".GIF", "GIF"), ("webp", "WEBP"),
            ("bmp", "BMP"), ("tiff", "TIFF"), ("jpeg", "JPEG"),
        ):
            with self.subTest(extension=extension):
                result, _, _ = self.run_main(["photo", "--to", extension])
                self.assertEqual(result, 0)
                path = self.output_dir / ("photo." + extension.lower().lstrip("."))
                with Image.open(path) as image:
                    self.assertEqual(image.format, expected)
                    self.assertEqual(image.size, (16, 16))
                    if expected in ("PNG", "WEBP"):
                        self.assertEqual(image.convert("RGBA").getpixel((0, 0))[3], 0)
        self.assertEqual(self.run_main(["photo"])[0], 0)
        self.assertTrue((self.output_dir / "photo.jpg").exists())

    def test_batch_naming_order_and_ignores_other_files(self):
        with Image.new("RGB", (16, 16), "blue") as image:
            image.save(self.input_dir / "a.AVIF", format="AVIF", lossless=True)
        (self.input_dir / "ignored.txt").write_text("ignored")
        (self.input_dir / "folder.avif").mkdir()
        result, output, _ = self.run_main([], ["결과", "png"])
        self.assertEqual(result, 0)
        self.assertIn("a.AVIF ->", output)
        self.assertLess(output.index("a.AVIF ->"), output.index("sample.avif ->"))
        with Image.open(self.output_dir / "결과_1.png") as first:
            self.assertGreater(first.convert("RGB").getpixel((0, 0))[2], 200)
        with Image.open(self.output_dir / "결과_2.png") as second:
            self.assertEqual(second.convert("RGBA").getpixel((0, 0))[3], 0)
        self.assertEqual(len(list(self.output_dir.iterdir())), 2)

    def test_failures_do_not_overwrite_and_continue(self):
        self.output_dir.mkdir()
        with Image.new("RGB", (16, 16), "blue") as image:
            image.save(self.input_dir / "other.avif", format="AVIF")
        existing = self.output_dir / "photo_1.jpg"
        existing.write_bytes(b"existing")
        result, output, error = self.run_main(["photo"])
        self.assertEqual(result, 1)
        self.assertIn("[실패]", error)
        self.assertIn("성공 1개, 실패 1개", output)
        self.assertEqual(existing.read_bytes(), b"existing")
        self.assertTrue((self.output_dir / "photo_2.jpg").exists())

    def test_invalid_names_formats_and_empty_input(self):
        for args in (
            ["photo", "--to", "exe"], [""], ["../photo"],
            ["nested\\photo"], ["C:photo"], ["CON"], ["photo."],
        ):
            with self.subTest(args=args):
                result, _, error = self.run_main(args)
                self.assertEqual(result, 1)
                self.assertIn("[오류]", error)
        self.source.unlink()
        result, _, error = self.run_main(["photo"])
        self.assertEqual(result, 1)
        self.assertIn("변환할 AVIF 파일이 없습니다", error)

    def test_rejects_non_avif_and_removes_failed_output(self):
        self.source.unlink()
        with Image.new("RGB", (4, 4)) as image:
            image.save(self.input_dir / "fake.avif", format="PNG")
        self.assertEqual(self.run_main(["photo"])[0], 1)
        self.assertFalse((self.output_dir / "photo.jpg").exists())
        (self.input_dir / "fake.avif").unlink()
        with Image.new("RGB", (4, 4)) as image:
            image.save(self.source, format="AVIF")
        with patch.object(Image.Image, "save", side_effect=OSError("save failed")):
            self.assertEqual(self.run_main(["photo"])[0], 1)
        self.assertFalse((self.output_dir / "photo.jpg").exists())

    def test_animated_avif_uses_first_frame(self):
        self.source.unlink()
        source = self.input_dir / "animated.avif"
        with Image.new("RGB", (16, 16), "red") as first, \
                Image.new("RGB", (16, 16), "blue") as second:
            first.save(source, format="AVIF", save_all=True, append_images=[second],
                       duration=[100, 100], lossless=True)
        self.assertEqual(self.run_main(["photo", "--to", "png"])[0], 0)
        with Image.open(self.output_dir / "photo.png") as image:
            self.assertEqual(getattr(image, "n_frames", 1), 1)
            red, _, blue = image.convert("RGB").getpixel((0, 0))
            self.assertGreater(red, blue)


if __name__ == "__main__":
    unittest.main()
