"""Remove a solid-color background and save transparent PNG/WebP images."""

import argparse
import sys
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps, features


BASE_DIR = Path(__file__).resolve().parent
EXTENSIONS = {".png", ".webp", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".gif"}


def background_color(value: str) -> str:
    value = value.strip().lower()
    value = {"white": "#ffffff", "black": "#000000"}.get(value, value)
    if value == "auto":
        return value
    if len(value) == 7 and value.startswith("#"):
        try:
            int(value[1:], 16)
        except ValueError:
            pass
        else:
            if all(character in "0123456789abcdef" for character in value[1:]):
                return value
    raise ValueError("배경색은 auto, white, black 또는 #RRGGBB 형식으로 입력하세요.")


def bounded_int(minimum: int, maximum: int):
    def parse(value: str) -> int:
        try:
            result = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("정수를 입력하세요.") from exc
        if not minimum <= result <= maximum:
            raise argparse.ArgumentTypeError(f"{minimum}~{maximum} 사이로 입력하세요.")
        return result
    return parse


@dataclass(frozen=True)
class RemovalOptions:
    background: str = "auto"
    tolerance: int = 30
    softness: int = 20
    strength: int = 100
    scope: str = "all"
    feather: int = 0

    def __post_init__(self):
        background_color(self.background)
        for name, value, maximum in (
            ("tolerance", self.tolerance, 255),
            ("softness", self.softness, 255),
            ("strength", self.strength, 100),
            ("feather", self.feather, 20),
        ):
            if not isinstance(value, int) or not 0 <= value <= maximum:
                raise ValueError(f"{name}: 0~{maximum} 사이의 정수가 필요합니다.")
        if self.scope not in {"all", "edges"}:
            raise ValueError("scope는 all 또는 edges여야 합니다.")


def detect_background(image: Image.Image) -> tuple[int, int, int]:
    pixels = image.load()
    width, height = image.size
    border = [(x, 0) for x in range(width)]
    if height > 1:
        border.extend((x, height - 1) for x in range(width))
    for y in range(1, height - 1):
        border.append((0, y))
        if width > 1:
            border.append((width - 1, y))
    colors = Counter(
        pixels[x, y][:3] for x, y in border if pixels[x, y][3] > 0
    )
    if not colors:
        raise ValueError("테두리가 이미 투명합니다. --background로 배경색을 지정하세요.")
    return colors.most_common(1)[0][0]


def edge_connected_mask(mask: Image.Image, alpha: Image.Image) -> Image.Image:
    width, height = mask.size
    candidates = mask.tobytes()
    original_alpha = alpha.tobytes()
    visited = bytearray(width * height)
    result = bytearray(width * height)
    queue = deque()

    def enqueue(index: int):
        # Already-transparent pixels can connect separated background regions.
        if not visited[index] and (candidates[index] or original_alpha[index] == 0):
            visited[index] = 1
            result[index] = candidates[index]
            queue.append(index)

    for x in range(width):
        enqueue(x)
        enqueue((height - 1) * width + x)
    for y in range(1, height - 1):
        enqueue(y * width)
        enqueue(y * width + width - 1)
    while queue:
        index = queue.popleft()
        x, y = index % width, index // width
        if x > 0:
            enqueue(index - 1)
        if x + 1 < width:
            enqueue(index + 1)
        if y > 0:
            enqueue(index - width)
        if y + 1 < height:
            enqueue(index + width)
    return Image.frombytes("L", mask.size, bytes(result))


def remove_background(image: Image.Image, options: RemovalOptions) -> Image.Image:
    rgba = image.convert("RGBA")
    if options.strength == 0:
        return rgba
    color = background_color(options.background)
    background = detect_background(rgba) if color == "auto" else tuple(
        int(color[index:index + 2], 16) for index in (1, 3, 5)
    )
    rgb = rgba.convert("RGB")
    red, green, blue = ImageChops.difference(
        rgb, Image.new("RGB", rgba.size, background)
    ).split()
    distance = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    lookup = []
    for value in range(256):
        if value <= options.tolerance:
            removal = 255
        elif options.softness:
            removal = round(255 * max(
                0, 1 - (value - options.tolerance) / options.softness
            ))
        else:
            removal = 0
        lookup.append(removal)
    mask = distance.point(lookup)
    alpha = rgba.getchannel("A")
    if options.scope == "edges":
        mask = edge_connected_mask(mask, alpha)
    if options.feather:
        mask = mask.filter(ImageFilter.GaussianBlur(options.feather))
    retained = mask.point([
        255 - round(value * options.strength / 100) for value in range(256)
    ])
    rgba.putalpha(ImageChops.multiply(alpha, retained))
    return rgba


def save_new_image(
    image: Image.Image, destination: Path, target: str,
    lossless: bool = True, quality: int = 95,
) -> Path:
    if target not in {"png", "webp"}:
        raise ValueError("출력 형식은 png 또는 webp여야 합니다.")
    if not 1 <= quality <= 100:
        raise ValueError("품질은 1~100 사이여야 합니다.")
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
                if target == "webp":
                    image.save(
                        stream, format="WEBP", lossless=lossless,
                        quality=quality, method=6,
                    )
                else:
                    image.save(stream, format="PNG", optimize=True)
        except (OSError, ValueError):
            candidate.unlink()
            raise
        return candidate


def process_image(
    source: Path, destination: Path, options: RemovalOptions,
    target: str, lossless: bool = True, quality: int = 95,
) -> Path:
    with Image.open(source) as original:
        if getattr(original, "n_frames", 1) > 1:
            raise ValueError("애니메이션/다중 페이지 이미지는 지원하지 않습니다.")
        with ImageOps.exif_transpose(original) as oriented:
            with remove_background(oriented, options) as result:
                return save_new_image(result, destination, target, lossless, quality)


def output_name(value: str) -> str:
    value = value.strip()
    if not value or any(
        character in '<>:"/\\|?*' or ord(character) < 32 for character in value
    ) or value.endswith("."):
        raise ValueError("폴더 경로나 특수문자 없이 파일명만 입력하세요.")
    if value.lower().endswith((".png", ".webp")):
        value = value[:value.rfind(".")]
    reserved = {"CON", "PRN", "AUX", "NUL"}
    reserved.update(f"{prefix}{number}" for prefix in ("COM", "LPT") for number in "123456789¹²³")
    if not value or value.endswith((" ", ".")) or value.split(".")[0].upper() in reserved:
        raise ValueError("사용할 수 없는 파일명입니다. 다른 이름을 입력하세요.")
    if len(value.encode("utf-16-le")) // 2 > 240:
        raise ValueError("파일명이 너무 깁니다. 240자 이내로 입력하세요.")
    return value


def prompt_output_name(source: Path, target: str) -> str:
    default = f"{source.stem}_transparent"
    while True:
        answer = input(
            f"{source.name} 출력 파일명 (확장자 자동 적용) [{default}.{target}]: "
        ).strip()
        try:
            return output_name(answer or default)
        except ValueError as exc:
            print(exc)


def prompt_options(args: argparse.Namespace) -> None:
    print("단색 배경 투명화 (원본 보존)")
    print("Enter를 누르면 [기본값]을 사용합니다.")

    def read(label, default, parse):
        while True:
            answer = input(f"{label} [{default}]: ").strip()
            try:
                return parse(answer if answer else str(default))
            except (ValueError, argparse.ArgumentTypeError) as exc:
                print(exc)

    def choice(*values):
        def parse(value):
            value = value.lower().lstrip(".")
            if value not in values:
                raise ValueError(f"{', '.join(values)} 중 선택하세요.")
            return value
        return parse

    args.to = read("출력 확장자 (png/webp)", "png", choice("png", "webp"))
    args.background = read(
        "배경색 (auto/white/black/#RRGGBB)", args.background, background_color
    )
    args.tolerance = read("색상 허용 오차 (0~255)", args.tolerance, bounded_int(0, 255))
    args.softness = read("색상 경계 부드러움 (0~255)", args.softness, bounded_int(0, 255))
    args.strength = read("제거 강도 (0~100%)", args.strength, bounded_int(0, 100))
    args.scope = read(
        "제거 범위 (all: 내부 포함 / edges: 테두리 연결만)",
        args.scope, choice("all", "edges"),
    )
    args.feather = read("가장자리 흐림 (0~20px)", args.feather, bounded_int(0, 20))
    if args.to == "webp":
        compression = read(
            "WebP 압축 (lossless: 무손실 / lossy: 손실)",
            "lossy" if args.lossy else "lossless", choice("lossless", "lossy"),
        )
        args.lossy = compression == "lossy"
        args.quality = read(
            "WebP 품질/무손실 압축 노력 (1~100)", args.quality, bounded_int(1, 100)
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="단색 배경을 투명하게 바꾸어 PNG/WebP로 저장합니다. --to 생략 시 대화형 실행."
    )
    parser.add_argument("file", nargs="?", type=Path, help="단일 이미지 (생략 시 input 폴더)")
    parser.add_argument("--input", type=Path, default=BASE_DIR / "input", help="입력 폴더")
    parser.add_argument("--output", type=Path, default=BASE_DIR / "output", help="출력 폴더")
    parser.add_argument("--name", type=output_name, help="출력 파일명 (확장자 자동 적용, 중복 시 번호 추가)")
    parser.add_argument("--to", type=str.lower, choices=("png", "webp"), help="출력 확장자")
    parser.add_argument("--background", type=background_color, default="auto", help="auto/white/black/#RRGGBB")
    parser.add_argument("--tolerance", type=bounded_int(0, 255), default=30, help="색상 허용 오차 (기본 30)")
    parser.add_argument("--softness", type=bounded_int(0, 255), default=20, help="색상 경계 부드러움 (기본 20)")
    parser.add_argument("--strength", type=bounded_int(0, 100), default=100, help="제거 강도 %% (기본 100)")
    parser.add_argument("--scope", choices=("all", "edges"), default="all", help="내부 포함 / 테두리 연결만")
    parser.add_argument("--feather", type=bounded_int(0, 20), default=0, help="마스크 흐림 반경 px (기본 0)")
    parser.add_argument("--lossy", action="store_true", help="WebP 손실 압축 (기본 무손실)")
    parser.add_argument("--quality", type=bounded_int(1, 100), default=95, help="WebP 품질/무손실 압축 노력 (기본 95)")
    args = parser.parse_args(argv)
    interactive = args.to is None
    if interactive:
        try:
            prompt_options(args)
        except (EOFError, KeyboardInterrupt):
            print("\n입력이 취소되었습니다. 자동 실행 시 --to png 또는 --to webp를 지정하세요.", file=sys.stderr)
            return 1
    if args.to == "png" and args.lossy:
        parser.error("--lossy는 --to webp에서만 사용할 수 있습니다.")

    try:
        options = RemovalOptions(
            args.background, args.tolerance, args.softness,
            args.strength, args.scope, args.feather,
        )
        if args.to == "webp" and not features.check("webp"):
            raise ValueError("현재 Pillow에 WebP 지원이 없습니다. WebP 지원 Pillow를 설치하세요.")
        input_path = (args.file if args.file is not None else args.input).resolve()
        output_dir = args.output.resolve()
        source_dir = input_path.parent if input_path.is_file() else input_path
        if source_dir == output_dir:
            raise ValueError("원본 보호를 위해 입력 폴더와 출력 폴더는 서로 달라야 합니다.")
        if args.file is not None:
            if not input_path.is_file() or input_path.suffix.lower() not in EXTENSIONS:
                raise ValueError(f"지원하는 이미지 파일이 아닙니다: {input_path}")
            sources = [input_path]
        else:
            if not input_path.is_dir():
                raise ValueError(f"입력 폴더가 없습니다: {input_path}")
            sources = sorted(
                path for path in input_path.iterdir()
                if path.is_file() and path.suffix.lower() in EXTENSIONS
            )
        if not sources:
            raise ValueError(f"처리할 이미지가 없습니다: {input_path}")
        output_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, ValueError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1

    failures = 0
    for source in sources:
        try:
            name = args.name
            if name is None:
                name = prompt_output_name(source, args.to) if interactive else f"{source.stem}_transparent"
            saved = process_image(
                source, output_dir / f"{name}.{args.to}",
                options, args.to, not args.lossy, args.quality,
            )
            print(f"완료: {source.name} -> {saved.name}")
        except (EOFError, KeyboardInterrupt):
            print("\n파일명 입력이 취소되었습니다.", file=sys.stderr)
            return 1
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            failures += 1
            print(f"실패: {source.name}: {exc}", file=sys.stderr)
    print(f"처리 결과: 성공 {len(sources) - failures}개 / 실패 {failures}개")
    print(f"저장 위치: {output_dir}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())