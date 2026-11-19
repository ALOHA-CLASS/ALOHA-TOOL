"""Enlarge images using resampling or an AI super-resolution model."""

import argparse
import hashlib
import math
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps


BASE_DIR = Path(__file__).resolve().parent
EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".gif", ".avif",
}
MAX_OUTPUT_PIXELS = 80_000_000
MODEL_URL = "https://raw.githubusercontent.com/Saafke/FSRCNN_Tensorflow/master/models/FSRCNN_x4.pb"
MODEL_SHA256 = "5c68d18db561aed8ead4ffedf1b897ea615baaf60ebf6c35f8e641f8fa4a21bf"
MODEL_PATH = Path.home() / ".cache" / "aloha-image-upscale" / "FSRCNN_x4.pb"
AI_SCALE = 4
TILE_SIZE = 128
TILE_PADDING = 16


def scale_factor(value: str) -> float:
    try:
        factor = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("배율은 1 이상의 숫자로 입력하세요.") from exc
    if not math.isfinite(factor) or factor < 1:
        raise argparse.ArgumentTypeError("배율은 1 이상의 유한한 숫자여야 합니다.")
    return factor


def output_size(size: tuple[int, int], factor: float) -> tuple[int, int]:
    if not math.isfinite(factor) or factor < 1:
        raise ValueError("배율은 1 이상의 유한한 숫자여야 합니다.")
    width, height = size
    if factor > MAX_OUTPUT_PIXELS / max(width, height):
        raise ValueError("출력 이미지가 최대 8,000만 픽셀을 초과합니다.")
    result = (max(1, round(width * factor)), max(1, round(height * factor)))
    if result[0] * result[1] > MAX_OUTPUT_PIXELS:
        raise ValueError("출력 이미지가 최대 8,000만 픽셀을 초과합니다.")
    return result


def save_new_image(image: Image.Image, destination: Path, image_format: str) -> Path:
    options = {}
    if image_format == "JPEG":
        options.update(quality=95, subsampling=0)
    elif image_format == "WEBP":
        options["lossless"] = True
    for metadata in ("icc_profile", "exif"):
        if image.info.get(metadata):
            options[metadata] = image.info[metadata]

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
                image.save(stream, format=image_format, **options)
        except (OSError, ValueError, KeyError, MemoryError):
            candidate.unlink()
            raise
        return candidate


class FSRCNNModel:
    def __init__(self, data: bytes):
        import cv2
        import numpy as np

        # The super-resolution module registers the model's DepthToSpace layer.
        self._layers = cv2.dnn_superres.DnnSuperResImpl_create()
        self._net = cv2.dnn.readNetFromTensorflow(np.frombuffer(data, dtype=np.uint8))

    def upsample(self, bgr):
        import cv2
        import numpy as np

        ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb).astype(np.float32) / 255.0
        self._net.setInput(cv2.dnn.blobFromImage(ycrcb[:, :, 0]))
        luminance = self._net.forward()[0, 0]
        size = (bgr.shape[1] * AI_SCALE, bgr.shape[0] * AI_SCALE)
        chroma = cv2.resize(ycrcb[:, :, 1:], size, interpolation=cv2.INTER_LINEAR)
        merged = np.dstack((luminance, chroma))
        ycrcb_8bit = np.clip(np.rint(merged * 255), 0, 255).astype(np.uint8)
        return cv2.cvtColor(ycrcb_8bit, cv2.COLOR_YCrCb2BGR)


def load_ai_model(model_path: Path):
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("AI 모드에 필요한 패키지가 없습니다. pip install -r requirements.txt 를 실행하세요.") from exc
    if not hasattr(cv2, "dnn_superres"):
        raise RuntimeError("OpenCV 초해상도 모듈이 없습니다. opencv-contrib-python을 설치하세요.")

    try:
        if not model_path.exists():
            if model_path != MODEL_PATH:
                raise ValueError(f"모델 파일이 없습니다: {model_path}")
            print("AI 모델을 다운로드합니다...")
            model_path.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(MODEL_URL, timeout=60) as response:
                data = response.read(1_000_001)
            if hashlib.sha256(data).hexdigest() != MODEL_SHA256:
                raise ValueError("다운로드한 AI 모델의 검증에 실패했습니다.")
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=model_path.parent, delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(data)
                os.replace(temporary, model_path)
            finally:
                if temporary is not None and temporary.exists():
                    temporary.unlink()
        data = model_path.read_bytes()
        if hashlib.sha256(data).hexdigest() != MODEL_SHA256:
            raise ValueError(f"AI 모델 검증에 실패했습니다: {model_path}")
        return FSRCNNModel(data)
    except (OSError, ValueError, urllib.error.URLError, cv2.error) as exc:
        raise RuntimeError(f"AI 모델을 준비하지 못했습니다: {exc}") from exc


def ai_enlarge(image: Image.Image, size: tuple[int, int], model) -> Image.Image:
    import cv2
    import numpy as np

    intermediate_size = output_size(image.size, AI_SCALE)
    with image.convert("RGBA") as rgba:
        with rgba.convert("RGB") as rgb:
            pixels = np.asarray(rgb)
            with Image.new("RGB", intermediate_size) as enhanced:
                for y in range(0, image.height, TILE_SIZE):
                    for x in range(0, image.width, TILE_SIZE):
                        left, top = max(0, x - TILE_PADDING), max(0, y - TILE_PADDING)
                        right = min(image.width, x + TILE_SIZE + TILE_PADDING)
                        bottom = min(image.height, y + TILE_SIZE + TILE_PADDING)
                        tile = pixels[top:bottom, left:right]
                        try:
                            result = model.upsample(cv2.cvtColor(tile, cv2.COLOR_RGB2BGR))
                            result = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
                        except cv2.error as exc:
                            raise RuntimeError(f"AI 이미지 처리에 실패했습니다: {exc}") from exc
                        x0, y0 = (x - left) * AI_SCALE, (y - top) * AI_SCALE
                        width = min(TILE_SIZE, image.width - x) * AI_SCALE
                        height = min(TILE_SIZE, image.height - y) * AI_SCALE
                        with Image.fromarray(result[y0:y0 + height, x0:x0 + width]) as part:
                            enhanced.paste(part, (x * AI_SCALE, y * AI_SCALE))
                result_image = enhanced.resize(size, Image.Resampling.LANCZOS)
        if "A" in image.getbands() or "transparency" in image.info:
            with rgba.getchannel("A") as alpha:
                with alpha.resize(size, Image.Resampling.LANCZOS) as resized_alpha:
                    result_image.putalpha(resized_alpha)
        result_image.info.update(image.info)
        if image.mode not in ("RGB", "RGBA", "P"):
            result_image.info.pop("icc_profile", None)
        return result_image


def process_image(
    source: Path, destination: Path, factor: float, model=None,
) -> tuple[Path, tuple[int, int]]:
    with Image.open(source) as original:
        if getattr(original, "n_frames", 1) > 1:
            raise ValueError("애니메이션/다중 페이지 이미지는 지원하지 않습니다.")
        image_format = original.format
        if image_format is None:
            raise ValueError("이미지 형식을 확인할 수 없습니다.")
        with ImageOps.exif_transpose(original) as oriented:
            size = output_size(oriented.size, factor)
            if model is not None:
                with ai_enlarge(oriented, size, model) as enhanced:
                    return save_new_image(enhanced, destination, image_format), size
            # Palette and 1-bit images otherwise use nearest-neighbor resampling.
            if oriented.mode in ("P", "1"):
                mode = "RGBA" if "transparency" in oriented.info else "RGB"
                with oriented.convert(mode) as converted:
                    with converted.resize(size, Image.Resampling.LANCZOS) as resized:
                        return save_new_image(resized, destination, image_format), size
            with oriented.resize(size, Image.Resampling.LANCZOS) as resized:
                return save_new_image(resized, destination, image_format), size


def prompt_factor() -> float:
    while True:
        try:
            return scale_factor(input("해상도 확대 배율 (예: 2 또는 1.5): ").strip())
        except argparse.ArgumentTypeError as exc:
            print(exc)


def prompt_mode() -> str:
    print("1. 단순 해상도 확장 (Lanczos)")
    print("2. AI 디테일 복원 (FSRCNN)")
    while True:
        choice = input("처리 방식 선택 [1/2]: ").strip()
        if choice == "1":
            return "simple"
        if choice == "2":
            return "ai"
        print("1 또는 2를 입력하세요.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="input 폴더의 이미지를 지정한 배율로 확대하여 output 폴더에 저장합니다."
    )
    parser.add_argument("--scale", type=scale_factor, help="가로와 세로 확대 배율 (1 이상)")
    parser.add_argument("--mode", choices=("simple", "ai"), help="처리 방식 (simple 또는 ai)")
    parser.add_argument("--model", type=Path, help="FSRCNN x4 모델 파일 경로 (AI 모드)")
    parser.add_argument("--input", type=Path, default=BASE_DIR / "input")
    parser.add_argument("--output", type=Path, default=BASE_DIR / "output")
    args = parser.parse_args(argv)
    if args.model is not None and args.mode != "ai":
        parser.error("--model은 --mode ai와 함께 사용하세요.")
    try:
        if args.mode is None:
            args.mode = prompt_mode() if args.scale is None else "simple"
        if args.scale is None:
            args.scale = prompt_factor()
    except (EOFError, KeyboardInterrupt):
        print("\n입력이 취소되었습니다.", file=sys.stderr)
        return 1

    try:
        input_dir = args.input.resolve()
        output_dir = args.output.resolve()
        if input_dir == output_dir:
            raise ValueError("원본 보호를 위해 input과 output은 서로 달라야 합니다.")
        if not input_dir.is_dir():
            raise ValueError(f"입력 폴더가 없습니다: {input_dir}")
        sources = sorted(
            (path for path in input_dir.iterdir()
             if path.is_file() and path.suffix.lower() in EXTENSIONS),
            key=lambda path: (path.name.casefold(), path.name),
        )
        if not sources:
            raise ValueError(f"처리할 이미지가 없습니다: {input_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, ValueError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1

    model = None
    if args.mode == "ai":
        try:
            model = load_ai_model(args.model if args.model is not None else MODEL_PATH)
        except RuntimeError as exc:
            print(f"오류: {exc}", file=sys.stderr)
            return 1

    failures = 0
    for source in sources:
        try:
            saved_path, size = process_image(source, output_dir / source.name, args.scale, model)
            print(f"완료: {source.name} -> {saved_path.name} ({size[0]} x {size[1]})")
        except (OSError, ValueError, KeyError, MemoryError, RuntimeError,
                Image.DecompressionBombError) as exc:
            failures += 1
            print(f"실패: {source.name}: {exc}", file=sys.stderr)
    print(f"처리 결과: 성공 {len(sources) - failures}개 / 실패 {failures}개")
    print(f"저장 위치: {output_dir}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())