from PIL import Image, ImageSequence
import os
from pathlib import Path


def convert_gif_to_webp(input_path, output_path, quality=80, lossless=False, method=6):
    """
    GIF를 애니메이션 WEBP로 변환합니다.

    Args:
        input_path: 입력 GIF 경로
        output_path: 출력 WEBP 경로
        quality: WEBP 품질 (0-100, lossless=False일 때만 적용)
        lossless: 무손실 압축 여부 (True면 품질 손실 없이 변환, 용량은 커질 수 있음)
        method: 압축 방법 (0-6, 높을수록 압축률은 좋지만 느림)
    """
    try:
        img = Image.open(input_path)

        # 원본 크기
        original_size = os.path.getsize(input_path)

        # 각 프레임과 지속 시간(duration) 추출
        frames = []
        durations = []

        for frame in ImageSequence.Iterator(img):
            frames.append(frame.convert('RGBA'))
            durations.append(frame.info.get('duration', 100))

        loop = img.info.get('loop', 0)

        # 애니메이션 WEBP로 저장
        frames[0].save(
            output_path,
            format='WEBP',
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=loop,
            quality=quality,
            lossless=lossless,
            method=method,
        )

        # 결과 출력
        compressed_size = os.path.getsize(output_path)
        reduction = (1 - compressed_size / original_size) * 100

        print(f"  프레임 수: {len(frames)}개")
        print(f"  원본: {original_size / 1024:.1f}KB → 변환: {compressed_size / 1024:.1f}KB")
        print(f"  용량 변화: {reduction:+.1f}%")

        return True

    except Exception as e:
        print(f"  ❌ 오류: {e}")
        return False


def convert_gifs_in_folder(input_folder='input', output_folder='output',
                            quality=80, lossless=False, method=6):
    """
    폴더 내 모든 GIF 파일을 애니메이션 WEBP로 변환합니다.

    Args:
        input_folder: 입력 폴더 경로
        output_folder: 출력 폴더 경로
        quality: WEBP 품질 (0-100)
        lossless: 무손실 압축 여부
        method: 압축 방법 (0-6)
    """
    # 출력 폴더 생성
    Path(output_folder).mkdir(exist_ok=True)

    input_path = Path(input_folder)

    if not input_path.exists():
        print(f"❌ '{input_folder}' 폴더가 존재하지 않습니다.")
        return

    gif_files = [f for f in input_path.iterdir()
                 if f.is_file() and f.suffix.lower() == '.gif']

    if not gif_files:
        print(f"'{input_folder}' 폴더에 GIF 파일이 없습니다.")
        return

    print(f"\n{'='*60}")
    mode = "무손실" if lossless else f"품질 {quality}"
    print(f"GIF → 애니메이션 WEBP 변환 시작 ({mode})")
    print(f"{'='*60}\n")

    success_count = 0
    total_original_size = 0
    total_converted_size = 0

    for idx, gif_file in enumerate(gif_files, 1):
        print(f"[{idx}/{len(gif_files)}] {gif_file.name}")

        output_file = Path(output_folder) / f"{gif_file.stem}.webp"
        original_size = os.path.getsize(gif_file)

        if convert_gif_to_webp(str(gif_file), str(output_file), quality, lossless, method):
            success_count += 1
            converted_size = os.path.getsize(output_file)
            total_original_size += original_size
            total_converted_size += converted_size

        print()

    # 전체 결과 출력
    print(f"{'='*60}")
    print(f"변환 완료: {success_count}/{len(gif_files)}개 성공")

    if total_original_size > 0:
        total_reduction = (1 - total_converted_size / total_original_size) * 100
        print(f"전체 원본: {total_original_size / 1024 / 1024:.2f}MB")
        print(f"전체 변환: {total_converted_size / 1024 / 1024:.2f}MB")
        print(f"전체 용량 변화: {total_reduction:+.1f}%")

    print(f"{'='*60}\n")


if __name__ == '__main__':
    # 설정값 (필요에 따라 조정)
    QUALITY = 80      # 품질: 0-100 (권장: 75-90), lossless=False일 때만 적용
    LOSSLESS = False  # True면 무손실 변환 (용량은 커질 수 있음)
    METHOD = 6        # 압축 방법: 0(빠름)-6(압축률 높음)

    convert_gifs_in_folder(
        input_folder='input',
        output_folder='output',
        quality=QUALITY,
        lossless=LOSSLESS,
        method=METHOD
    )
