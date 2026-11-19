import argparse
import sys
from pathlib import Path

from PIL import Image, ImageOps


SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_DIR = SCRIPT_DIR / "input"
OUTPUT_DIR = SCRIPT_DIR / "output"
FORMATS = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "png": "PNG",
    "gif": "GIF",
    "webp": "WEBP",
    "bmp": "BMP",
    "tif": "TIFF",
    "tiff": "TIFF",
}


def output_name(name: str) -> str:
    name = name.strip()
    if (not name or name in (".", "..") or name.endswith(".")
            or any(c in name for c in '<>:"/\\|?*')
            or any(ord(c) < 32 for c in name)):
        raise ValueError("출력 파일명은 경로나 확장자 없이 입력해주세요.")
    reserved = {"CON", "PRN", "AUX", "NUL"}
    reserved.update(f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(1, 10))
    if name.split(".")[0].upper() in reserved:
        raise ValueError(f"사용할 수 없는 출력 파일명입니다: {name}")
    return name


def normalize_format(extension: str) -> str:
    extension = extension.strip().lower().removeprefix(".") or "jpg"
    if extension not in FORMATS:
        raise ValueError(
            f"지원하지 않는 확장자입니다: {extension} "
            f"(지원: {', '.join(FORMATS)})"
        )
    return extension


def convert_image(source: Path, destination: Path, extension: str) -> None:
    target_format = FORMATS[extension]
    with Image.open(source) as image:
        if image.format != "AVIF":
            raise ValueError("입력 파일이 올바른 AVIF 이미지가 아닙니다.")
        image.seek(0)
        frame = ImageOps.exif_transpose(image)
        if target_format == "JPEG":
            rgba = frame.convert("RGBA")
            frame = Image.new("RGB", rgba.size, "white")
            frame.paste(rgba, mask=rgba.getchannel("A"))

        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as output:
            try:
                frame.save(output, format=target_format)
            except Exception:
                output.close()
                destination.unlink()
                raise


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="input 폴더의 모든 AVIF 이미지를 변환합니다.")
    parser.add_argument("name", nargs="?", help="출력 파일명 (확장자 제외)")
    parser.add_argument("--to", help="출력 확장자 (기본: jpg)")
    args = parser.parse_args(argv)

    try:
        sources = sorted(
            (path for path in INPUT_DIR.iterdir()
             if path.is_file() and path.suffix.lower() == ".avif"),
            key=lambda path: (path.name.casefold(), path.name),
        )
        if not sources:
            raise ValueError(f"변환할 AVIF 파일이 없습니다: {INPUT_DIR}")
        name = output_name(
            args.name if args.name is not None else input("출력 파일명 (확장자 제외): ")
        )
        if args.to is not None:
            extension = args.to
        elif args.name is None:
            extension = input("출력 확장자 (기본: jpg): ")
        else:
            extension = "jpg"
        extension = normalize_format(extension)
    except (OSError, ValueError, EOFError) as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        return 1

    failed = 0
    for index, source in enumerate(sources, 1):
        suffix = f"_{index}" if len(sources) > 1 else ""
        destination = OUTPUT_DIR / f"{name}{suffix}.{extension}"
        try:
            convert_image(source, destination, extension)
            print(f"[완료] {source.name} -> {destination}")
        except (OSError, ValueError) as exc:
            print(f"[실패] {source.name}: {exc}", file=sys.stderr)
            failed += 1
    print(f"총 {len(sources)}개 중 성공 {len(sources) - failed}개, 실패 {failed}개")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())