# -*- coding: utf-8 -*-
r"""
이미지 변환 프로그램
--------------------
input 폴더에 있는 이미지 파일들을 원하는 확장자로 변환하여 output 폴더에 저장합니다.
지원 확장자: jpg/jpeg, png, webp, gif, bmp, tiff, ico

사용법
  1) 대화형 실행
       python main.py
     실행 후 변환할 확장자를 입력하면 input 폴더의 모든 이미지를 변환합니다.

  2) 커맨드라인 인자로 실행
       python main.py --to webp
       python main.py --to jpg --quality 90
       python main.py --input "C:\path\to\folder" --output "C:\path\to\out" --to png
       python main.py photo.png --to webp   (단일 파일 변환)
"""

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageSequence

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
    "ico": "ICO",
}

# 여러 프레임(애니메이션)을 지원하는 포맷
ANIMATABLE_FORMATS = {"GIF", "WEBP"}

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = SCRIPT_DIR / "input"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "output"


def normalize_ext(ext: str) -> str:
    """사용자 입력 확장자를 정규화한다 (".JPG" -> "jpg")."""
    return ext.strip().lower().lstrip(".")


def iter_image_files(folder: Path):
    """폴더 내에서 지원하는 확장자를 가진 이미지 파일들을 반환한다."""
    for path in sorted(folder.iterdir()):
        if path.is_file() and normalize_ext(path.suffix) in SUPPORTED_EXTENSIONS:
            yield path


def convert_image(src: Path, dst: Path, target_ext: str, quality: int = 95) -> None:
    """src 이미지를 target_ext 포맷으로 변환하여 dst 경로에 저장한다."""
    target_format = SUPPORTED_EXTENSIONS[target_ext]

    with Image.open(src) as img:
        is_animated = getattr(img, "is_animated", False)

        save_kwargs = {}
        if target_format == "JPEG":
            save_kwargs["quality"] = quality
        elif target_format == "WEBP":
            save_kwargs["quality"] = quality
        elif target_format == "PNG":
            save_kwargs["optimize"] = True

        if is_animated and target_format in ANIMATABLE_FORMATS:
            # 애니메이션 프레임을 모두 보존하여 저장 (GIF <-> WEBP 등)
            frames = []
            durations = []
            for frame in ImageSequence.Iterator(img):
                mode = "RGBA" if target_format == "WEBP" else frame.mode
                frames.append(frame.convert(mode).copy())
                durations.append(frame.info.get("duration", 100))

            first, rest = frames[0], frames[1:]
            save_kwargs["save_all"] = True
            save_kwargs["append_images"] = rest
            save_kwargs["duration"] = durations
            save_kwargs["loop"] = img.info.get("loop", 0)
            first.save(dst, format=target_format, **save_kwargs)
            return

        # 단일 프레임 변환
        frame = img
        if target_format == "JPEG" and frame.mode in ("RGBA", "LA", "P"):
            # JPEG은 투명 채널을 지원하지 않으므로 흰색 배경으로 합성한다.
            converted = Image.new("RGB", frame.size, (255, 255, 255))
            rgba = frame.convert("RGBA")
            converted.paste(rgba, mask=rgba.split()[-1])
            frame = converted
        elif target_format in ("PNG", "WEBP", "GIF") and frame.mode == "CMYK":
            frame = frame.convert("RGB")
        elif target_format == "ICO" and frame.mode not in ("RGBA", "RGB"):
            frame = frame.convert("RGBA")

        frame.save(dst, format=target_format, **save_kwargs)


def run_batch(input_dir: Path, output_dir: Path, target_ext: str, quality: int) -> None:
    files = list(iter_image_files(input_dir))
    if not files:
        print(f"[알림] '{input_dir}' 폴더에서 변환할 수 있는 이미지 파일을 찾지 못했습니다.")
        print(f"       지원 확장자: {', '.join(sorted(set(SUPPORTED_EXTENSIONS)))}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    success, skipped, failed = 0, 0, 0
    for src in files:
        current_ext = normalize_ext(src.suffix)
        if current_ext == target_ext:
            print(f"[건너뜀] {src.name} (이미 .{target_ext} 파일)")
            skipped += 1
            continue

        dst = output_dir / f"{src.stem}.{target_ext}"
        try:
            convert_image(src, dst, target_ext, quality)
            print(f"[완료] {src.name} -> {dst.name}")
            success += 1
        except Exception as exc:
            print(f"[실패] {src.name}: {exc}")
            failed += 1

    print("\n--------------------------------------")
    print(f"총 {len(files)}개 중 성공 {success}개, 건너뜀 {skipped}개, 실패 {failed}개")
    print(f"결과 저장 위치: {output_dir}")


def run_single(src: Path, output_dir: Path, target_ext: str, quality: int) -> None:
    current_ext = normalize_ext(src.suffix)
    if current_ext not in SUPPORTED_EXTENSIONS:
        print(f"[오류] 지원하지 않는 확장자입니다: {src.suffix}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    dst = output_dir / f"{src.stem}.{target_ext}"
    try:
        convert_image(src, dst, target_ext, quality)
        print(f"[완료] {src.name} -> {dst}")
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
    parser = argparse.ArgumentParser(description="이미지 확장자 변환 프로그램")
    parser.add_argument("file", nargs="?", help="단일 파일을 변환할 경우 파일 경로 (생략 시 input 폴더 전체 변환)")
    parser.add_argument("--to", dest="target_ext", help="변환할 확장자 (예: jpg, png, webp, gif)")
    parser.add_argument("--input", dest="input_dir", default=str(DEFAULT_INPUT_DIR), help="입력 폴더 경로 (기본: input)")
    parser.add_argument("--output", dest="output_dir", default=str(DEFAULT_OUTPUT_DIR), help="출력 폴더 경로 (기본: output)")
    parser.add_argument("--quality", type=int, default=95, help="JPEG/WEBP 저장 품질 (1-100, 기본 95)")
    args = parser.parse_args()

    target_ext = normalize_ext(args.target_ext) if args.target_ext else None
    if target_ext and target_ext not in SUPPORTED_EXTENSIONS:
        print(f"[오류] 지원하지 않는 확장자입니다: {args.target_ext}")
        print(f"       지원 확장자: {', '.join(sorted(set(SUPPORTED_EXTENSIONS)))}")
        sys.exit(1)

    if not target_ext:
        target_ext = prompt_target_ext()

    output_dir = Path(args.output_dir)

    if args.file:
        run_single(Path(args.file), output_dir, target_ext, args.quality)
    else:
        input_dir = Path(args.input_dir)
        if not input_dir.exists():
            print(f"[오류] 입력 폴더가 존재하지 않습니다: {input_dir}")
            sys.exit(1)
        run_batch(input_dir, output_dir, target_ext, args.quality)


if __name__ == "__main__":
    main()
