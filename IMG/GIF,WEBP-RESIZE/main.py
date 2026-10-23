from PIL import Image, ImageSequence
import os
from pathlib import Path

SUPPORTED_EXTENSIONS = {'.gif', '.webp'}


def extract_frames(img):
    """
    애니메이션 이미지(GIF/WEBP)에서 프레임, 지속시간, 반복횟수를 추출합니다.
    """
    frames = []
    durations = []

    for frame in ImageSequence.Iterator(img):
        frames.append(frame.convert('RGBA'))
        durations.append(frame.info.get('duration', 100))

    loop = img.info.get('loop', 0)
    return frames, durations, loop


def calc_target_size(width, height, target_width):
    """
    가로세로 비율을 유지하면서 목표 가로 크기에 맞는 (너비, 높이)를 계산합니다.
    target_width가 0이거나 원본과 같으면 리사이즈하지 않습니다.
    """
    if not target_width or target_width <= 0 or target_width == width:
        return width, height

    ratio = target_width / width
    new_height = max(1, round(height * ratio))
    return target_width, new_height


def build_gif_palette(frames, colors):
    """
    애니메이션 전체에서 일관된 색상을 쓰도록, 프레임 일부를 샘플링해
    공용 팔레트를 생성합니다. (프레임마다 따로 팔레트를 만들면 색이 흔들림)
    """
    n = len(frames)
    sample_count = min(8, n)
    if sample_count > 1:
        indices = sorted({round(i * (n - 1) / (sample_count - 1)) for i in range(sample_count)})
    else:
        indices = [0]

    width, height = frames[0].size
    sample = Image.new('RGB', (width * len(indices), height))
    for i, idx in enumerate(indices):
        sample.paste(frames[idx].convert('RGB'), (i * width, 0))

    return sample.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)


def quality_to_gif_colors(quality):
    """
    품질(1-100)을 GIF 팔레트 색상 수(2-256)로 변환합니다.
    GIF는 JPEG/WEBP처럼 품질 수치가 없어서, 색상 수를 줄여 압축률을 조절합니다.
    """
    colors = round(32 + (quality / 100) * 224)
    return max(2, min(256, colors))


def compress_and_resize(input_path, output_path, target_width=0, quality=80, method=5):
    """
    GIF/WEBP 애니메이션을 리사이즈하고 압축하여 저장합니다.

    Args:
        input_path: 입력 파일 경로 (.gif 또는 .webp)
        output_path: 출력 파일 경로 (입력과 동일한 확장자 사용)
        target_width: 목표 가로 크기 (px). 0이면 원본 크기 유지, 세로는 비율에 맞춰 자동 계산
        quality: 압축 품질 (1-100, WEBP는 직접 적용 / GIF는 색상 수로 환산)
        method: WEBP 압축 방법 (0 빠름 - 6 압축률 높음)
    """
    try:
        ext = Path(input_path).suffix.lower()
        img = Image.open(input_path)
        original_size = os.path.getsize(input_path)

        frames, durations, loop = extract_frames(img)
        width, height = frames[0].size
        new_width, new_height = calc_target_size(width, height, target_width)

        if (new_width, new_height) != (width, height):
            frames = [f.resize((new_width, new_height), Image.Resampling.LANCZOS) for f in frames]
            print(f"  리사이즈: {width}x{height} → {new_width}x{new_height}")

        if ext == '.gif':
            colors = quality_to_gif_colors(quality)
            palette_img = build_gif_palette(frames, colors)
            pal_frames = [
                f.convert('RGB').quantize(palette=palette_img, dither=Image.Dither.FLOYDSTEINBERG)
                for f in frames
            ]
            pal_frames[0].save(
                output_path,
                format='GIF',
                save_all=True,
                append_images=pal_frames[1:],
                duration=durations,
                loop=loop,
                optimize=True,
                disposal=2,
            )
        else:  # .webp
            frames[0].save(
                output_path,
                format='WEBP',
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                loop=loop,
                quality=quality,
                method=method,
            )

        compressed_size = os.path.getsize(output_path)
        reduction = (1 - compressed_size / original_size) * 100

        print(f"  프레임 수: {len(frames)}개")
        print(f"  원본: {original_size / 1024:.1f}KB → 압축: {compressed_size / 1024:.1f}KB")
        print(f"  압축률: {reduction:+.1f}%")

        return True, original_size, compressed_size

    except Exception as e:
        print(f"  ❌ 오류: {e}")
        return False, 0, 0


def process_folder(input_folder='input', output_folder='output', target_width=0, quality=80, method=5):
    """
    폴더 내 모든 GIF/WEBP 애니메이션 파일을 리사이즈 + 압축합니다.
    """
    Path(output_folder).mkdir(exist_ok=True)

    input_path = Path(input_folder)
    if not input_path.exists():
        print(f"❌ '{input_folder}' 폴더가 존재하지 않습니다.")
        return

    target_files = [f for f in input_path.iterdir()
                     if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS]

    if not target_files:
        print(f"'{input_folder}' 폴더에 GIF/WEBP 파일이 없습니다.")
        return

    print(f"\n{'='*60}")
    resize_desc = f"가로 {target_width}px로 리사이즈" if target_width else "리사이즈 없음"
    print(f"GIF/WEBP 압축 + 리사이징 시작 (품질 {quality}, {resize_desc})")
    print(f"{'='*60}\n")

    success_count = 0
    total_original_size = 0
    total_compressed_size = 0

    for idx, file in enumerate(target_files, 1):
        print(f"[{idx}/{len(target_files)}] {file.name}")

        output_file = Path(output_folder) / file.name
        ok, original_size, compressed_size = compress_and_resize(
            str(file), str(output_file), target_width, quality, method
        )

        if ok:
            success_count += 1
            total_original_size += original_size
            total_compressed_size += compressed_size

        print()

    print(f"{'='*60}")
    print(f"압축 완료: {success_count}/{len(target_files)}개 성공")

    if total_original_size > 0:
        total_reduction = (1 - total_compressed_size / total_original_size) * 100
        print(f"전체 원본: {total_original_size / 1024 / 1024:.2f}MB")
        print(f"전체 압축: {total_compressed_size / 1024 / 1024:.2f}MB")
        print(f"전체 압축률: {total_reduction:+.1f}%")

    print(f"{'='*60}\n")


def ask_int(prompt, default, min_value=None, max_value=None):
    """
    사용자에게 정수를 입력받습니다. 빈 입력이면 기본값을 사용합니다.
    """
    raw = input(prompt).strip()
    if not raw:
        return default

    try:
        value = int(raw)
    except ValueError:
        print(f"  숫자가 아닙니다. 기본값({default})을 사용합니다.")
        return default

    if min_value is not None and value < min_value:
        value = min_value
    if max_value is not None and value > max_value:
        value = max_value

    return value


if __name__ == '__main__':
    print("=== GIF / 애니메이션 WEBP 압축 + 리사이징 도구 ===\n")

    TARGET_WIDTH = ask_int(
        "목표 가로 크기(px)를 입력하세요 (가로세로 비율 유지, 변경 안 하려면 Enter): ",
        default=0,
        min_value=0,
    )
    QUALITY = ask_int(
        "압축 품질을 입력하세요 (1-100, 낮을수록 용량 작음, 기본 80): ",
        default=80,
        min_value=1,
        max_value=100,
    )

    process_folder(
        input_folder='input',
        output_folder='output',
        target_width=TARGET_WIDTH,
        quality=QUALITY,
        method=5,
    )
