# -*- coding: utf-8 -*-
r"""
PDF -> 이미지 변환 프로그램
--------------------
input 폴더에 있는 PDF 파일들을 페이지별로 이미지로 변환하여 output 폴더에 저장합니다.
파일명은 "{PDF 파일명}-{페이지번호}.{확장자}" 형식으로 저장됩니다. (예: 보고서-001.jpg)

지원 확장자: jpg/jpeg, png, webp, gif, bmp, tiff

사용법
  1) 대화형 실행
       python main.py
     실행 후 변환할 확장자를 입력하면 input 폴더의 모든 PDF를 변환합니다.

  2) 커맨드라인 인자로 실행
       python main.py --to jpg
       python main.py --to png --dpi 300
       python main.py --input "C:\path\to\folder" --output "C:\path\to\out" --to jpg
       python main.py report.pdf --to png   (단일 파일 변환)
"""

import argparse
import sys
from pathlib import Path

import pymupdf as fitz  # PyMuPDF
from PIL import Image

# Pillow가 인식하는 지원 확장자 -> 저장 포맷 이름 매핑
SUPPORTED_EXTENSIONS = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
    "gif": "GIF",
    "bmp": "BMP",
    "tiff": "TIFF",
    "tif": "TIFF",
}

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = SCRIPT_DIR / "input"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "output"
DEFAULT_DPI = 200


def normalize_ext(ext: str) -> str:
    """사용자 입력 확장자를 정규화한다 (".JPG" -> "jpg")."""
    return ext.strip().lower().lstrip(".")


def iter_pdf_files(folder: Path):
    """폴더 내에서 PDF 파일들을 반환한다."""
    for path in sorted(folder.iterdir()):
        if path.is_file() and path.suffix.lower() == ".pdf":
            yield path


def render_page_to_image(page: "fitz.Page", dpi: int) -> Image.Image:
    """PDF 페이지를 지정한 DPI로 렌더링하여 PIL 이미지로 반환한다."""
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def save_page_image(image: Image.Image, dst: Path, target_format: str, quality: int) -> None:
    """렌더링된 페이지 이미지를 target_format으로 저장한다."""
    frame = image
    save_kwargs = {}
    if target_format in ("JPEG", "WEBP"):
        save_kwargs["quality"] = quality
    elif target_format == "PNG":
        save_kwargs["optimize"] = True
    elif target_format == "GIF":
        # GIF는 팔레트(최대 256색) 이미지이므로 변환해서 저장한다.
        frame = frame.convert("P", palette=Image.ADAPTIVE)

    frame.save(dst, format=target_format, **save_kwargs)


def convert_pdf(src: Path, output_dir: Path, target_ext: str, dpi: int, quality: int) -> int:
    """PDF 파일을 페이지별 이미지로 변환한다. 변환된 페이지 수를 반환한다."""
    target_format = SUPPORTED_EXTENSIONS[target_ext]

    with fitz.open(src) as doc:
        total_pages = doc.page_count
        if total_pages == 0:
            return 0
        digits = max(3, len(str(total_pages)))

        for index, page in enumerate(doc, start=1):
            image = render_page_to_image(page, dpi)
            dst = output_dir / f"{src.stem}-{index:0{digits}d}.{target_ext}"
            save_page_image(image, dst, target_format, quality)

        return total_pages


def run_batch(input_dir: Path, output_dir: Path, target_ext: str, dpi: int, quality: int) -> None:
    files = list(iter_pdf_files(input_dir))
    if not files:
        print(f"[알림] '{input_dir}' 폴더에서 변환할 수 있는 PDF 파일을 찾지 못했습니다.")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    success, failed, total_pages = 0, 0, 0
    for src in files:
        try:
            pages = convert_pdf(src, output_dir, target_ext, dpi, quality)
            print(f"[완료] {src.name} -> {pages}페이지 변환 (예: {src.stem}-001.{target_ext})")
            success += 1
            total_pages += pages
        except Exception as exc:
            print(f"[실패] {src.name}: {exc}")
            failed += 1

    print("\n--------------------------------------")
    print(f"총 {len(files)}개 PDF 중 성공 {success}개, 실패 {failed}개 (총 {total_pages}페이지 변환)")
    print(f"결과 저장 위치: {output_dir}")


def run_single(src: Path, output_dir: Path, target_ext: str, dpi: int, quality: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        pages = convert_pdf(src, output_dir, target_ext, dpi, quality)
        print(f"[완료] {src.name} -> {pages}페이지 변환 (예: {src.stem}-001.{target_ext})")
        print(f"결과 저장 위치: {output_dir}")
    except Exception as exc:
        print(f"[실패] {src.name}: {exc}")
        sys.exit(1)


def prompt_target_ext() -> str:
    valid = sorted(set(SUPPORTED_EXTENSIONS))
    while True:
        answer = input(f"변환할 확장자를 입력하세요 ({', '.join(valid)}): ")
        ext = normalize_ext(answer)
        if ext in SUPPORTED_EXTENSIONS:
            return ext
        print(f"'{answer}'는 지원하지 않는 확장자입니다. 다시 입력해주세요.")


def main():
    parser = argparse.ArgumentParser(description="PDF를 페이지별 이미지로 변환하는 프로그램")
    parser.add_argument("file", nargs="?", help="단일 PDF 파일을 변환할 경우 파일 경로 (생략 시 input 폴더 전체 변환)")
    parser.add_argument("--to", dest="target_ext", help="변환할 확장자 (예: jpg, png, webp, gif)")
    parser.add_argument("--input", dest="input_dir", default=str(DEFAULT_INPUT_DIR), help="입력 폴더 경로 (기본: input)")
    parser.add_argument("--output", dest="output_dir", default=str(DEFAULT_OUTPUT_DIR), help="출력 폴더 경로 (기본: output)")
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI, help=f"변환 해상도 DPI (기본: {DEFAULT_DPI}, 높을수록 선명하지만 용량 커짐)")
    parser.add_argument("--quality", type=int, default=95, help="JPEG/WEBP 저장 품질 (1-100, 기본 95)")
    args = parser.parse_args()

    target_ext = normalize_ext(args.target_ext) if args.target_ext else None
    if target_ext and target_ext not in SUPPORTED_EXTENSIONS:
        print(f"[오류] 지원하지 않는 확장자입니다: {args.target_ext}")
        print(f"       지원 확장자: {', '.join(sorted(set(SUPPORTED_EXTENSIONS)))}")
        sys.exit(1)

    if not target_ext:
        target_ext = prompt_target_ext()

    if args.dpi <= 0:
        print("[오류] DPI는 1 이상이어야 합니다.")
        sys.exit(1)

    output_dir = Path(args.output_dir)

    if args.file:
        src = Path(args.file)
        if not src.exists():
            print(f"[오류] 파일이 존재하지 않습니다: {src}")
            sys.exit(1)
        if src.suffix.lower() != ".pdf":
            print(f"[오류] PDF 파일이 아닙니다: {src}")
            sys.exit(1)
        run_single(src, output_dir, target_ext, args.dpi, args.quality)
    else:
        input_dir = Path(args.input_dir)
        if not input_dir.exists():
            print(f"[오류] 입력 폴더가 존재하지 않습니다: {input_dir}")
            sys.exit(1)
        run_batch(input_dir, output_dir, target_ext, args.dpi, args.quality)


if __name__ == "__main__":
    main()
