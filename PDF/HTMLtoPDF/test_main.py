import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pymupdf
from playwright.sync_api import sync_playwright

import main


class ConversionOptionsTests(unittest.TestCase):
    def test_default_is_paged_a4(self):
        args = main.build_parser().parse_args([])
        self.assertEqual(args.mode, "paged")
        self.assertEqual(args.format, "A4")
        self.assertIsNone(args.margin)
        self.assertEqual(main.DEFAULT_MARGIN, 10)
        self.assertFalse(args.print_css)

    def test_margin_prompt_accepts_default_and_numbers(self):
        for value, expected in (("", 10), ("  ", 10), ("3.5", 3.5), ("0", 0)):
            with self.subTest(value=value), patch("builtins.input", return_value=value):
                self.assertEqual(main.prompt_margin(), expected)

    def test_margin_prompt_retries_invalid_input(self):
        with patch("builtins.input", side_effect=["abc", "-1", "nan", "inf", "10"]), patch(
            "builtins.print"
        ) as output:
            self.assertEqual(main.prompt_margin(), 10)
            self.assertEqual(output.call_count, 4)

    def test_margin_prompt_reports_eof_default(self):
        with patch("builtins.input", side_effect=EOFError), patch("builtins.print") as output:
            self.assertEqual(main.prompt_margin(), 10)
            output.assert_called_once()

    def test_cli_margin_bypasses_prompt(self):
        with patch.object(main, "prompt_margin") as prompt, patch.object(
            main, "collect_sources", return_value=[]
        ), patch("sys.argv", ["main.py", "--margin", "7.5"]), patch("builtins.print"):
            self.assertEqual(main.main(), 1)
            prompt.assert_not_called()
        self.assertEqual(main.build_parser().parse_args(["--margin", "7.5"]).margin, 7.5)

    def test_cli_prompts_once_for_paged_only(self):
        for options, calls in (([], 1), (["--mode", "single"], 0)):
            with self.subTest(options=options), patch.object(
                main, "prompt_margin", return_value=10
            ) as prompt, patch.object(main, "collect_sources", return_value=[]), patch(
                "sys.argv", ["main.py", *options]
            ), patch("builtins.print"):
                self.assertEqual(main.main(), 1)
                self.assertEqual(prompt.call_count, calls)

    def test_paged_options_and_context_cleanup(self):
        args = main.build_parser().parse_args(
            ["--format", "Letter", "--landscape", "--margin", "10", "--print-css"]
        )
        browser = Mock()
        context = browser.new_context.return_value
        page = context.new_page.return_value
        with patch.object(main, "prepare_page"):
            mode = main.convert(browser, Path("input.html"), Path("output.pdf"), args)
        self.assertEqual(mode, "paged")
        page.emulate_media.assert_called_once_with(media="print")
        page.pdf.assert_called_once_with(
            path="output.pdf", format="Letter", landscape=True,
            print_background=True,
            margin=dict.fromkeys(("top", "right", "bottom", "left"), "10.0mm"),
            prefer_css_page_size=True,
        )
        context.close.assert_called_once_with()

    def test_oversized_single_falls_back_to_paged(self):
        args = main.build_parser().parse_args(["--mode", "single"])
        browser = Mock()
        page = browser.new_context.return_value.new_page.return_value
        with patch.object(main, "prepare_page"), patch.object(
            main, "measure_height", return_value=main.MAX_PAGE_HEIGHT_PX + 1
        ):
            mode = main.convert(browser, Path("input.html"), Path("output.pdf"), args)
        self.assertEqual(mode, "paged")
        self.assertEqual(page.pdf.call_args.kwargs["format"], "A4")
        self.assertNotIn("page_ranges", page.pdf.call_args.kwargs)

    def test_context_closes_on_pdf_failure(self):
        args = main.build_parser().parse_args([])
        browser = Mock()
        context = browser.new_context.return_value
        context.new_page.return_value.pdf.side_effect = RuntimeError("PDF failed")
        with patch.object(main, "prepare_page"):
            with self.assertRaisesRegex(RuntimeError, "PDF failed"):
                main.convert(browser, Path("input.html"), Path("output.pdf"), args)
        context.close.assert_called_once_with()


class PdfPaginationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = main.launch_browser(cls.playwright)
        except Exception:
            cls.playwright.stop()
            raise

    @classmethod
    def tearDownClass(cls):
        try:
            cls.browser.close()
        finally:
            cls.playwright.stop()

    def convert_html(self, html, options=()):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input.html"
            destination = root / "output.pdf"
            source.write_text(html, encoding="utf-8")
            args = main.build_parser().parse_args(["--wait", "0", *options])
            mode = main.convert(self.browser, source, destination, args)
            with pymupdf.open(destination) as pdf:
                pages = [(page.rect.width, page.rect.height, page.get_text()) for page in pdf]
            return mode, pages

    def assert_a4(self, pages):
        for width, height, _ in pages:
            self.assertAlmostEqual(width, 210 / 25.4 * 72, delta=1)
            self.assertAlmostEqual(height, 297 / 25.4 * 72, delta=1)

    def test_default_automatically_paginates_all_content(self):
        markers = [f"CONTENT_{index:03d}_END" for index in range(80)]
        html = "<style>p {margin:0; height:60px}</style>" + "".join(
            f"<p>{marker}</p>" for marker in markers
        )
        mode, pages = self.convert_html(html)
        self.assertEqual(mode, "paged")
        self.assertGreaterEqual(len(pages), 2)
        self.assert_a4(pages)
        text = "".join(page[2] for page in pages)
        for marker in markers:
            self.assertEqual(text.count(marker), 1)
        self.assertIn(markers[-1], pages[-1][2])

    def test_forced_page_breaks_preserve_every_page(self):
        for options in ((), ("--print-css",), ("--mode", "single")):
            with self.subTest(options=options):
                _, pages = self.convert_html(
                    "<style>section + section {break-before:page}</style>"
                    "<section>FIRST_PAGE</section>"
                    "<section>SECOND_PAGE</section>"
                    "<section>LAST_PAGE</section>",
                    options,
                )
                self.assertEqual(len(pages), 3)
                for page, marker in zip(pages, ("FIRST_PAGE", "SECOND_PAGE", "LAST_PAGE")):
                    self.assertIn(marker, page[2])
                if "--mode" not in options:
                    self.assert_a4(pages)

    def test_short_document_remains_one_a4_page(self):
        _, pages = self.convert_html("<p>SHORT_DOCUMENT</p>")
        self.assertEqual(len(pages), 1)
        self.assert_a4(pages)
        self.assertIn("SHORT_DOCUMENT", pages[0][2])

    def test_single_mode_retains_long_page(self):
        mode, pages = self.convert_html(
            "<div style='height:3000px'>FIRST_LINE</div><p>LAST_LINE</p>",
            ("--mode", "single"),
        )
        self.assertEqual(mode, "single")
        self.assertEqual(len(pages), 1)
        self.assertGreater(pages[0][1], 2000)
        self.assertIn("FIRST_LINE", pages[0][2])
        self.assertIn("LAST_LINE", pages[0][2])

    def test_wide_scroll_table_wraps_last_column_and_keeps_rows_together(self):
        markers = [f"LAST_COLUMN_BADGE_{index:03d}_" + "X" * 60 for index in range(30)]
        html = """
            <style>
                @page { margin: 30mm; }
                .page { margin: 40px auto; padding: 24px; max-width: 1080px; }
                .table-wrap { overflow: hidden; break-inside: avoid; }
                table { width: 1400px; min-width: 1400px; }
                td { padding: 12px; }
                .badge { display: inline-block; padding: 4px; white-space: nowrap; }
            </style>
            <main class="page"><div class="table-wrap"><table>
        """ + "".join(
            f"<tr><td>ROW_{index:03d}</td><td>Description</td>"
            f"<td><span class='badge'>{marker}</span></td></tr>"
            for index, marker in enumerate(markers)
        ) + "</table></div></main>"
        for options in ((), ("--print-css",)):
            with self.subTest(options=options):
                _, pages = self.convert_html(html, options)
                self.assertGreaterEqual(len(pages), 2)
                self.assert_a4(pages)
                for index, marker in enumerate(markers):
                    matches = [
                        page for page in pages
                        if f"ROW_{index:03d}" in page[2]
                    ]
                    self.assertEqual(len(matches), 1)
                    self.assertIn(marker, "".join(matches[0][2].split()))

    def test_page_margin_overrides_html_and_removes_outer_spacing(self):
        html = """
            <style>
                @page { margin: 30mm; }
                body { margin: 20px; padding: 20px; }
                .page { margin: 40px; padding: 24px; max-width: 300px; }
            </style>
            <main class="page">MARGIN_MARKER</main>
        """
        for options, expected_left in (
            ((), 10 / 25.4 * 72), (("--print-css",), 10 / 25.4 * 72),
            (("--margin", "3"), 3 / 25.4 * 72), (("--margin", "0"), 0),
        ):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / "margin.html"
                destination = root / "margin.pdf"
                source.write_text(html, encoding="utf-8")
                args = main.build_parser().parse_args(["--wait", "0", *options])
                main.convert(self.browser, source, destination, args)
                with pymupdf.open(destination) as pdf:
                    block = pdf[0].get_text("blocks")[0]
                    self.assertAlmostEqual(block[0], expected_left, delta=1)
                    self.assertLess(block[1], expected_left + 5)

    def test_badge_fragments_fit_inside_last_cell(self):
        page = self.browser.new_page(viewport={"width": 794, "height": 1123})
        try:
            page.set_content("""
                <style>
                    table { min-width: 1400px; }
                    td { padding: 8px; }
                    .badge { display: inline-block; white-space: nowrap; padding: 6px; }
                </style>
                <div style="overflow:auto"><table><tr>
                    <td>First</td><td>Second</td>
                    <td><span class="badge">LONG_BADGE_ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789</span></td>
                </tr></table></div>
            """)
            main.prepare_paged_layout(page, 0)
            layout = page.evaluate("""() => {
                const cell = document.querySelector('td:last-child').getBoundingClientRect();
                const badge = document.querySelector('.badge');
                const rect = badge.getBoundingClientRect();
                const range = document.createRange();
                range.selectNodeContents(badge);
                return {
                    cellRight: cell.right, badgeRight: rect.right,
                    fragments: [...range.getClientRects()].map(r => ({
                        left: r.left, right: r.right
                    })),
                    badgeLeft: rect.left,
                    tableWidth: document.querySelector('table').getBoundingClientRect().width,
                    viewportWidth: window.innerWidth
                };
            }""")
            self.assertLessEqual(layout["tableWidth"], layout["viewportWidth"])
            self.assertLessEqual(layout["badgeRight"], layout["cellRight"])
            self.assertGreater(len(layout["fragments"]), 1)
            for fragment in layout["fragments"]:
                self.assertGreaterEqual(fragment["left"], layout["badgeLeft"] - 1)
                self.assertLessEqual(fragment["right"], layout["badgeRight"] + 1)
        finally:
            page.close()


if __name__ == "__main__":
    unittest.main()
