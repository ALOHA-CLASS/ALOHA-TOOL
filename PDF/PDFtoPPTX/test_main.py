import tempfile
import unittest
from pathlib import Path

import pymupdf
from pptx import Presentation
from pptx.opc.constants import RELATIONSHIP_TYPE as RT

from main import convert_pdf


class ConvertPdfTests(unittest.TestCase):
    def test_converts_every_page_and_preserves_web_and_page_links(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "linked.pdf"
            destination = root / "out" / "linked.pptx"

            document = pymupdf.open()
            first = document.new_page(width=300, height=200)
            first.insert_text((20, 40), "First page")
            first.insert_link({
                "kind": pymupdf.LINK_URI,
                "from": pymupdf.Rect(20, 50, 180, 90),
                "uri": "https://example.com",
            })
            second = document.new_page(width=300, height=200)
            second.insert_text((20, 40), "Second page")
            second.insert_link({
                "kind": pymupdf.LINK_GOTO,
                "from": pymupdf.Rect(20, 50, 180, 90),
                "page": 0,
                "to": pymupdf.Point(0, 0),
            })
            document.save(source)
            document.close()

            page_count, link_count, unsupported_count = convert_pdf(
                source, destination, dpi=72
            )

            self.assertEqual((page_count, link_count, unsupported_count), (2, 2, 0))
            presentation = Presentation(destination)
            self.assertEqual(len(presentation.slides), 2)
            first_slide = presentation.slides[0]
            self.assertEqual(len(first_slide.shapes), 2)
            self.assertEqual(
                first_slide.shapes[1].click_action.hyperlink.address,
                "https://example.com",
            )
            second_slide_rels = presentation.slides[1].part.rels
            slide_targets = [
                rel.target_part
                for rel in second_slide_rels.values()
                if rel.reltype == RT.SLIDE
            ]
            self.assertEqual(len(slide_targets), 1)
            self.assertIs(slide_targets[0], first_slide.part)


if __name__ == "__main__":
    unittest.main()
