# -*- coding: utf-8 -*-
r"""
이미지 -> PDF 병합 프로그램
--------------------
input 폴더에 있는 이미지 파일들을 파일명 순서대로 한 장씩 PDF 페이지로 만들어
하나의 PDF 파일로 병합합니다.

지원 확장자: jpg/jpeg, png, webp, bmp, tiff, gif(첫 프레임만)

사용법
  1) 대화형 실행
       python main.py
     실행 후 PDF 파일명을 입력하면 input 폴더의 모든 이미지를 순서대로 병합합니다.

  2) 커맨드라인 인자로 실행
       python main.py --name 제목
       python main.py --input "C:\path\to\folder" --output "C:\path\to\out" --name 제목
       python main.py img1.jpg img2.png img3.jpg --name 제목   (지정한 파일만, 입력 순서대로 병합)
"""

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageOps

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".gif"}

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = SCRIPT_DIR / "input"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "output"
DEFAULT_NAME = "병합"
DEFAULT_DPI = 200


def iter_image_files(folder: Path):
    """폴더 내에서 지원하는 확장자를 가진 이미지 파일들을 이름순으로 반환한다."""
    return [
        path for path in sorted(folder.iterdir())
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]


def load_page_image(path: Path) -> Image.Image:
    """이미지를 열어 PDF 페이지로 쓸 수 있도록 RGB로 변환한다(EXIF 회전 반영, 투명 배경은 흰색 처리)."""
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        if getattr(img, "is_animated", False):
            img.seek(0)
        if img.mode in ("RGBA", "LA", "P"):
            rgba = img.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.split()[-1])
            return background
        return img.convert("RGB")


def merge_images_to_pdf(files, dst: Path, dpi: int) -> int:
    """이미지 파일 목록을 순서대로 하나의 PDF로 병합한다. 병합된 페이지 수를 반환한다."""
    pages = [load_page_image(path) for path in files]
    first, rest = pages[0], pages[1:]
    first.save(
        dst,
        format="PDF",
        save_all=True,
        append_images=rest,
        resolution=dpi,
    )
    return len(pages)


def resolve_output_path(output_dir: Path, name: str) -> Path:
    stem = name.strip() or DEFAULT_NAME
    if stem.lower().endswith(".pdf"):
        stem = stem[: -len(".pdf")]
    return output_dir / f"{stem}.pdf"


def prompt_name() -> str:
    answer = input(f"저장할 PDF 파일명을 입력하세요 (기본값: {DEFAULT_NAME}): ").strip()
    return answer or DEFAULT_NAME


def main():
    parser = argparse.ArgumentParser(description="이미지들을 하나의 PDF로 병합하는 프로그램")
    parser.add_argument("files", nargs="*", help="병합할 이미지 파일 경로들 (입력 순서대로 병합, 생략 시 input 폴더 전체를 이름순으로 병합)")
    parser.add_argument("--name", dest="name", help="저장할 PDF 파일명 (확장자 제외, 기본값: 병합)")
    parser.add_argument("--input", dest="input_dir", default=str(DEFAULT_INPUT_DIR), help="입력 폴더 경로 (기본: input)")
    parser.add_argument("--output", dest="output_dir", default=str(DEFAULT_OUTPUT_DIR), help="출력 폴더 경로 (기본: output)")
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI, help=f"PDF 페이지 해상도 DPI (기본: {DEFAULT_DPI})")
    args = parser.parse_args()

    if args.dpi <= 0:
        print("[오류] DPI는 1 이상이어야 합니다.")
        sys.exit(1)

    if args.files:
        files = []
        for raw in args.files:
            path = Path(raw)
            if not path.exists():
                print(f"[오류] 파일이 존재하지 않습니다: {path}")
                sys.exit(1)
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                print(f"[오류] 지원하지 않는 확장자입니다: {path}")
                print(f"       지원 확장자: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
                sys.exit(1)
            files.append(path)
    else:
        input_dir = Path(args.input_dir)
        if not input_dir.exists():
            print(f"[오류] 입력 폴더가 존재하지 않습니다: {input_dir}")
            sys.exit(1)
        files = iter_image_files(input_dir)
        if not files:
            print(f"[알림] '{input_dir}' 폴더에서 병합할 수 있는 이미지 파일을 찾지 못했습니다.")
            print(f"       지원 확장자: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
            sys.exit(1)

    name = args.name if args.name else prompt_name()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    dst = resolve_output_path(output_dir, name)

    print(f"\n{'='*60}")
    print(f"이미지 -> PDF 병합 시작 (총 {len(files)}개 이미지, {args.dpi}DPI)")
    print(f"{'='*60}\n")
    for i, f in enumerate(files, 1):
        print(f"  [{i}/{len(files)}] {f.name}")

    try:
        page_count = merge_images_to_pdf(files, dst, args.dpi)
    except Exception as exc:
        print(f"\n[실패] PDF 병합 중 오류가 발생했습니다: {exc}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"[완료] {page_count}개 이미지를 '{dst.name}'로 병합했습니다.")
    print(f"저장 위치: {dst}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
