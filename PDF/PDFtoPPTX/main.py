# -*- coding: utf-8 -*-
"""Convert PDF files to PowerPoint presentations, preserving page appearance and links."""

import argparse
from io import BytesIO
from pathlib import Path
import sys

import pymupdf
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = SCRIPT_DIR / "input"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "output"
DEFAULT_DPI = 180
MAX_SLIDE_INCHES = 56


def iter_pdf_files(folder: Path):
    """Return PDF files in a folder in alphabetical order."""
    return sorted(
        path for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() == ".pdf"
    )


def convert_pdf(src: Path, dst: Path, dpi: int) -> tuple[int, int, int]:
    """Render every PDF page and recreate supported PDF links in a PPTX."""
    with pymupdf.open(src) as document:
        if document.page_count == 0:
            raise ValueError("PDF에 페이지가 없습니다.")
        page_count = document.page_count

        first_page = document[0]
        canvas_width = first_page.rect.width
        canvas_height = first_page.rect.height
        max_dimension = max(canvas_width, canvas_height)
        if max_dimension > MAX_SLIDE_INCHES * 72:
            scale = MAX_SLIDE_INCHES * 72 / max_dimension
            canvas_width *= scale
            canvas_height *= scale

        presentation = Presentation()
        presentation.slide_width = Inches(canvas_width / 72)
        presentation.slide_height = Inches(canvas_height / 72)
        blank_layout = presentation.slide_layouts[6]
        slides = []
        pending_links = []
        unsupported_links = 0

        for page_index, page in enumerate(document):
            slide = presentation.slides.add_slide(blank_layout)
            slides.append(slide)

            page_rect = page.rect
            if page_rect.width <= 0 or page_rect.height <= 0:
                raise ValueError(f"{page_index + 1}페이지의 크기가 올바르지 않습니다.")
            fit_scale = min(
                canvas_width / page_rect.width,
                canvas_height / page_rect.height,
            )
            image_width = page_rect.width * fit_scale
            image_height = page_rect.height * fit_scale
            image_left = (canvas_width - image_width) / 2
            image_top = (canvas_height - image_height) / 2

            zoom = dpi / 72
            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(zoom, zoom),
                alpha=False,
            )
            slide.shapes.add_picture(
                BytesIO(pixmap.tobytes("png")),
                Inches(image_left / 72),
                Inches(image_top / 72),
                width=Inches(image_width / 72),
                height=Inches(image_height / 72),
            )

            for link in page.get_links():
                link_kind = link.get("kind")
                if link_kind == pymupdf.LINK_URI:
                    destination = link.get("uri")
                    if not isinstance(destination, str) or not destination:
                        unsupported_links += 1
                        continue
                elif link_kind == pymupdf.LINK_GOTO:
                    destination = link.get("page")
                    if (
                        not isinstance(destination, int)
                        or not 0 <= destination < document.page_count
                    ):
                        unsupported_links += 1
                        continue
                else:
                    unsupported_links += 1
                    continue

                link_rect = pymupdf.Rect(link["from"]) * page.rotation_matrix
                link_rect &= page_rect
                if link_rect.is_empty or link_rect.is_infinite:
                    continue

                left = image_left + (link_rect.x0 - page_rect.x0) * fit_scale
                top = image_top + (link_rect.y0 - page_rect.y0) * fit_scale
                width = link_rect.width * fit_scale
                height = link_rect.height * fit_scale
                if width <= 0 or height <= 0:
                    continue
                pending_links.append(
                    (slide, left, top, width, height, link_kind, destination)
                )

        for slide, left, top, width, height, link_kind, destination in pending_links:
            hotspot = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE,
                Inches(left / 72),
                Inches(top / 72),
                Inches(width / 72),
                Inches(height / 72),
            )
            hotspot.fill.background()
            hotspot.line.fill.background()
            if link_kind == pymupdf.LINK_URI:
                hotspot.click_action.hyperlink.address = destination
            else:
                hotspot.click_action.target_slide = slides[destination]

        dst.parent.mkdir(parents=True, exist_ok=True)
        presentation.save(dst)

    return page_count, len(pending_links), unsupported_links


def run_conversion(src: Path, output_dir: Path, dpi: int) -> bool:
    dst = output_dir / f"{src.stem}.pptx"
    try:
        page_count, link_count, unsupported_links = convert_pdf(src, dst, dpi)
    except Exception as exc:
        print(f"[실패] {src.name}: {exc}")
        return False

    print(f"[완료] {src.name} -> {dst.name} ({page_count}페이지, 링크 {link_count}개)")
    if unsupported_links:
        print(f"[안내] 지원하지 않는 링크 {unsupported_links}개는 PPTX에 포함되지 않았습니다.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PDF의 모든 페이지를 PowerPoint로 변환하고 링크를 보존합니다."
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="변환할 PDF 파일 (생략하면 input 폴더의 모든 PDF 변환)",
    )
    parser.add_argument(
        "--input",
        dest="input_dir",
        default=str(DEFAULT_INPUT_DIR),
        help="입력 폴더 경로 (기본: input)",
    )
    parser.add_argument(
        "--output",
        dest="output_dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="출력 폴더 경로 (기본: output)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=DEFAULT_DPI,
        help=f"페이지 렌더링 해상도 (기본: {DEFAULT_DPI})",
    )
    args = parser.parse_args()

    if not 1 <= args.dpi <= 1200:
        parser.error("--dpi는 1에서 1200 사이여야 합니다.")

    output_dir = Path(args.output_dir)
    if args.file:
        src = Path(args.file)
        if not src.is_file():
            print(f"[오류] 파일이 존재하지 않습니다: {src}")
            sys.exit(1)
        if src.suffix.lower() != ".pdf":
            print(f"[오류] PDF 파일이 아닙니다: {src}")
            sys.exit(1)
        output_dir.mkdir(parents=True, exist_ok=True)
        if not run_conversion(src, output_dir, args.dpi):
            sys.exit(1)
        return

    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        print(f"[오류] 입력 폴더가 존재하지 않습니다: {input_dir}")
        sys.exit(1)
    files = iter_pdf_files(input_dir)
    if not files:
        print(f"[알림] '{input_dir}' 폴더에서 PDF 파일을 찾지 못했습니다.")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    succeeded = sum(run_conversion(src, output_dir, args.dpi) for src in files)
    print(f"\n총 {len(files)}개 중 성공 {succeeded}개, 실패 {len(files) - succeeded}개")
    print(f"결과 저장 위치: {output_dir}")
    if succeeded != len(files):
        sys.exit(1)


if __name__ == "__main__":
    main()