"""Resize images in input/ and save new files in output/."""

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageOps


BASE_DIR = Path(__file__).resolve().parent
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".gif"}


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("크기는 양의 정수로 입력하세요.") from exc
    if number <= 0:
        raise argparse.ArgumentTypeError("크기는 1 이상이어야 합니다.")
    return number


def resize_image(
    image: Image.Image,
    width: int | None,
    height: int | None,
    mode: str | None = None,
) -> Image.Image:
    if width is None and height is None:
        raise ValueError("가로 또는 세로 크기를 지정하세요.")
    if (width is not None and width <= 0) or (height is not None and height <= 0):
        raise ValueError("크기는 1 이상이어야 합니다.")
    if width is not None and height is not None:
        if mode == "cover":
            return ImageOps.fit(
                image, (width, height), method=Image.Resampling.LANCZOS
            )
        if mode == "contain":
            scale = min(width / image.width, height / image.height)
            size = (
                max(1, round(image.width * scale)),
                max(1, round(image.height * scale)),
            )
            return image.resize(size, Image.Resampling.LANCZOS)
        raise ValueError("가로와 세로를 함께 지정할 때는 cover 또는 contain이 필요합니다.")
    if mode is not None:
        raise ValueError("cover/contain 모드는 가로와 세로 크기가 모두 필요합니다.")
    if width is not None:
        size = (width, max(1, round(image.height * width / image.width)))
    else:
        assert height is not None
        size = (max(1, round(image.width * height / image.height)), height)
    return image.resize(size, Image.Resampling.LANCZOS)


def save_new_image(image: Image.Image, destination: Path, image_format: str) -> Path:
    index = 0
    while True:
        candidate = destination if index == 0 else destination.with_name(
            f"{destination.stem}_{index}{destination.suffix}"
        )
        try:
            stream = candidate.open("xb")
        except FileExistsError:
            index += 1
            continue
        try:
            with stream:
                options = {"quality": 95} if image_format in {"JPEG", "WEBP"} else {}
                image.save(stream, format=image_format, **options)
        except (OSError, ValueError):
            candidate.unlink()
            raise
        return candidate


def process_image(
    source: Path,
    destination: Path,
    width: int | None,
    height: int | None,
    mode: str | None,
) -> tuple[Path, tuple[int, int]]:
    with Image.open(source) as original:
        if getattr(original, "n_frames", 1) > 1:
            raise ValueError("애니메이션/다중 페이지 이미지는 지원하지 않습니다.")
        image_format = original.format
        if image_format is None:
            raise ValueError("이미지 형식을 확인할 수 없습니다.")
        with ImageOps.exif_transpose(original) as oriented:
            with resize_image(oriented, width, height, mode) as resized:
                saved_path = save_new_image(resized, destination, image_format)
                return saved_path, resized.size


def prompt_options() -> tuple[int | None, int | None, str | None]:
    print("이미지 리사이즈 (원본 비율 유지)")
    print("1. 가로 크기 지정")
    print("2. 세로 크기 지정")
    print("3. cover: 지정 크기를 채우고 넘치는 부분 중앙 자르기")
    print("4. contain: 지정 영역 안에 잘림 없이 맞추기 (여백 추가 없음)")
    while True:
        choice = input("모드 선택 [1/2/3/4]: ").strip()
        if choice in {"1", "2", "3", "4"}:
            break
        print("1, 2, 3, 4 중 하나를 입력하세요.")

    def read_size(label: str) -> int:
        while True:
            try:
                return positive_int(input(f"{label} 크기(px): ").strip())
            except argparse.ArgumentTypeError as exc:
                print(exc)

    width = read_size("가로") if choice != "2" else None
    height = read_size("세로") if choice != "1" else None
    mode = {"3": "cover", "4": "contain"}.get(choice)
    return width, height, mode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="input 폴더의 이미지를 비율 유지하여 output 폴더에 저장합니다."
    )
    parser.add_argument("--width", type=positive_int, help="가로 크기(px)")
    parser.add_argument("--height", type=positive_int, help="세로 크기(px)")
    parser.add_argument("--mode", choices=("cover", "contain"))
    parser.add_argument("--input", type=Path, default=BASE_DIR / "input")
    parser.add_argument("--output", type=Path, default=BASE_DIR / "output")
    args = parser.parse_args(argv)
    if args.width is None and args.height is None:
        if args.mode is not None:
            parser.error("--mode는 --width와 --height가 모두 필요합니다.")
        try:
            args.width, args.height, args.mode = prompt_options()
        except (EOFError, KeyboardInterrupt):
            print("\n입력이 취소되었습니다.", file=sys.stderr)
            return 1
    if args.width is not None and args.height is not None:
        if args.mode is None:
            parser.error("가로와 세로를 함께 지정할 때 --mode cover 또는 contain이 필요합니다.")
    elif args.mode is not None:
        parser.error("--mode는 --width와 --height가 모두 필요합니다.")

    try:
        input_dir = args.input.resolve()
        output_dir = args.output.resolve()
        if input_dir == output_dir:
            raise ValueError("원본 보호를 위해 input과 output은 서로 달라야 합니다.")
        if not input_dir.is_dir():
            raise ValueError(f"입력 폴더가 없습니다: {input_dir}")
        sources = sorted(
            path for path in input_dir.iterdir()
            if path.is_file() and path.suffix.lower() in EXTENSIONS
        )
        if not sources:
            raise ValueError(f"처리할 이미지가 없습니다: {input_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, ValueError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1

    failures = 0
    for source in sources:
        try:
            saved_path, size = process_image(
                source, output_dir / source.name, args.width, args.height, args.mode
            )
            print(f"완료: {source.name} -> {saved_path.name} ({size[0]} x {size[1]})")
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            failures += 1
            print(f"실패: {source.name}: {exc}", file=sys.stderr)
    print(f"처리 결과: 성공 {len(sources) - failures}개 / 실패 {failures}개")
    print(f"저장 위치: {output_dir}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
