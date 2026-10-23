# -*- coding: utf-8 -*-
r"""
이미지 분할 프로그램
--------------------
input 폴더에 있는 이미지를 지정한 방향/등분 수/분할 크기에 따라 조각으로 나누어
output 폴더에 저장합니다. (상세페이지처럼 긴 이미지를 나눌 때 유용합니다)

진행 순서
  1) 분할 방향 선택
       1. 가로  : 가로선으로 잘라 위->아래로 여러 조각을 만듦 (세로 길이를 분할)
       2. 세로  : 세로선으로 잘라 왼쪽->오른쪽으로 여러 조각을 만듦 (가로 길이를 분할)
       3. 가로, 세로 : 가로/세로 모두 잘라 격자(그리드) 형태로 조각을 만듦
  2) 몇 등분 할지 입력 (가로,세로 선택 시에는 각각 입력)
  3) 균등 분할 여부 선택
       - 균등분할: 전체 길이를 등분 수만큼 가능한 균등하게 나눔 (나머지 픽셀은 앞쪽 조각에 1px씩 배분)
       - 균등분할 아님: 각 조각의 픽셀 크기를 직접 입력 (합계가 전체 크기와 일치해야 함)

사용법
  python main.py            # 대화형 실행 (위 순서대로 질문)
  python main.py --input "경로" --output "경로"   # input/output 폴더 변경
"""

import argparse
import sys
from pathlib import Path

from PIL import Image

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".gif"}

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = SCRIPT_DIR / "input"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "output"


# ----------------------------------------------------------------------
# 입력(파일 목록) 관련
# ----------------------------------------------------------------------
def list_image_files(folder: Path):
    return [p for p in sorted(folder.iterdir()) if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]


# ----------------------------------------------------------------------
# 분할 크기 계산
# ----------------------------------------------------------------------
def equal_sizes(total: int, n: int):
    """total을 n조각으로 최대한 균등하게 나눈다. 나머지는 앞쪽 조각부터 1px씩 더 배분."""
    base, remainder = divmod(total, n)
    sizes = []
    for i in range(n):
        sizes.append(base + 1 if i < remainder else base)
    return sizes


def sizes_to_offsets(sizes):
    offsets = [0]
    for s in sizes:
        offsets.append(offsets[-1] + s)
    return offsets


def parse_manual_sizes(text: str, n: int, total: int):
    """쉼표로 구분된 픽셀 값 문자열을 파싱하고 검증한다. 실패 시 ValueError 발생."""
    parts = [p.strip() for p in text.split(",") if p.strip() != ""]
    if len(parts) != n:
        raise ValueError(f"{n}개의 값을 입력해야 하는데 {len(parts)}개가 입력되었습니다.")
    try:
        sizes = [int(p) for p in parts]
    except ValueError:
        raise ValueError("모든 값은 정수(픽셀)여야 합니다.")
    if any(s <= 0 for s in sizes):
        raise ValueError("모든 값은 1 이상이어야 합니다.")
    if sum(sizes) != total:
        raise ValueError(f"입력한 값의 합({sum(sizes)}px)이 전체 크기({total}px)와 일치하지 않습니다.")
    return sizes


# ----------------------------------------------------------------------
# 대화형 프롬프트
# ----------------------------------------------------------------------
def prompt_choice(message: str, choices: dict) -> str:
    """choices: {"1": "가로", "2": "세로", ...} 형태. 입력받은 key를 반환."""
    while True:
        print(message)
        for key, label in choices.items():
            print(f"  {key}. {label}")
        answer = input("번호를 입력하세요: ").strip()
        if answer in choices:
            return answer
        print(f"[오류] '{answer}'는 올바른 선택이 아닙니다. 다시 입력해주세요.\n")


def prompt_count(label: str) -> int:
    while True:
        answer = input(f"{label} 몇 등분 하시겠습니까? (숫자 입력, 2 이상): ").strip()
        if answer.isdigit() and int(answer) >= 2:
            return int(answer)
        print("[오류] 2 이상의 정수를 입력해주세요.\n")


def prompt_equal() -> bool:
    while True:
        answer = input("균등 분할 하시겠습니까? (y/n): ").strip().lower()
        if answer in ("y", "yes", "ㅇ"):
            return True
        if answer in ("n", "no", "ㄴ"):
            return False
        print("[오류] y 또는 n을 입력해주세요.\n")


def prompt_manual_sizes(label: str, n: int, total: int):
    print(f"{label} 각 조각의 크기(px)를 쉼표로 구분하여 입력하세요. (총 {n}개, 합계는 {total}px)")
    print(f"  예시: {', '.join(str(s) for s in equal_sizes(total, n))}")
    while True:
        text = input("입력: ")
        try:
            return parse_manual_sizes(text, n, total)
        except ValueError as exc:
            print(f"[오류] {exc}\n")


def resolve_direction_and_sizes(width: int, height: int):
    """사용자에게 분할 방향/등분 수/균등 여부를 물어보고 (row_sizes, col_sizes)를 반환한다.
    row_sizes: 높이를 나누는 크기 목록 (None이면 분할 없음 -> [height])
    col_sizes: 너비를 나누는 크기 목록 (None이면 분할 없음 -> [width])
    """
    direction = prompt_choice(
        "\n[1단계] 분할 방향을 선택하세요.",
        {"1": "가로 (상하로 분할)", "2": "세로 (좌우로 분할)", "3": "가로, 세로 (격자로 분할)"},
    )

    if direction == "1":
        n = prompt_count("\n[2단계] 가로")
        equal = prompt_equal()
        row_sizes = equal_sizes(height, n) if equal else prompt_manual_sizes("\n[3단계] 가로 분할 -", n, height)
        col_sizes = [width]
    elif direction == "2":
        n = prompt_count("\n[2단계] 세로")
        equal = prompt_equal()
        col_sizes = equal_sizes(width, n) if equal else prompt_manual_sizes("\n[3단계] 세로 분할 -", n, width)
        row_sizes = [height]
    else:
        print("\n[2단계] 가로, 세로 각각 몇 등분 할지 입력하세요.")
        n_row = prompt_count("가로 방향(상하)으로")
        n_col = prompt_count("세로 방향(좌우)으로")
        equal = prompt_equal()
        if equal:
            row_sizes = equal_sizes(height, n_row)
            col_sizes = equal_sizes(width, n_col)
        else:
            row_sizes = prompt_manual_sizes("\n[3단계] 가로 방향(상하) 분할 -", n_row, height)
            col_sizes = prompt_manual_sizes("\n[3단계] 세로 방향(좌우) 분할 -", n_col, width)

    return row_sizes, col_sizes


# ----------------------------------------------------------------------
# 이미지 분할 실행
# ----------------------------------------------------------------------
def split_image(src: Path, output_dir: Path, row_sizes, col_sizes):
    with Image.open(src) as img:
        width, height = img.size
        row_offsets = sizes_to_offsets(row_sizes)
        col_offsets = sizes_to_offsets(col_sizes)

        n_rows = len(row_sizes)
        n_cols = len(col_sizes)
        row_digits = max(2, len(str(n_rows)))
        col_digits = max(2, len(str(n_cols)))

        saved = []
        for r in range(n_rows):
            for c in range(n_cols):
                box = (col_offsets[c], row_offsets[r], col_offsets[c + 1], row_offsets[r + 1])
                piece = img.crop(box)

                if n_rows == 1:
                    suffix = f"_{c + 1:0{col_digits}d}"
                elif n_cols == 1:
                    suffix = f"_{r + 1:0{row_digits}d}"
                else:
                    suffix = f"_r{r + 1:0{row_digits}d}_c{c + 1:0{col_digits}d}"

                dst = output_dir / f"{src.stem}{suffix}{src.suffix}"

                ext = src.suffix.lower()
                if ext in (".jpg", ".jpeg") and piece.mode in ("RGBA", "LA", "P"):
                    # JPEG은 투명 채널을 지원하지 않으므로 흰색 배경으로 합성한다.
                    rgba = piece.convert("RGBA")
                    flattened = Image.new("RGB", rgba.size, (255, 255, 255))
                    flattened.paste(rgba, mask=rgba.split()[-1])
                    piece = flattened

                piece.save(dst)
                saved.append(dst)

        return width, height, saved


# ----------------------------------------------------------------------
# 메인
# ----------------------------------------------------------------------
def choose_source_file(input_dir: Path) -> Path:
    files = list_image_files(input_dir)
    if not files:
        print(f"[오류] '{input_dir}' 폴더에서 이미지 파일을 찾지 못했습니다.")
        print(f"       지원 확장자: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
        sys.exit(1)

    if len(files) == 1:
        print(f"[알림] 분할할 이미지: {files[0].name}")
        return files[0]

    print("\n분할할 이미지를 선택하세요.")
    for i, f in enumerate(files, start=1):
        print(f"  {i}. {f.name}")
    while True:
        answer = input("번호를 입력하세요: ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(files):
            return files[int(answer) - 1]
        print("[오류] 올바른 번호를 입력해주세요.\n")


def main():
    parser = argparse.ArgumentParser(description="이미지 분할 프로그램")
    parser.add_argument("file", nargs="?", help="분할할 이미지 파일 경로 (생략 시 input 폴더에서 선택)")
    parser.add_argument("--input", dest="input_dir", default=str(DEFAULT_INPUT_DIR), help="입력 폴더 경로 (기본: input)")
    parser.add_argument("--output", dest="output_dir", default=str(DEFAULT_OUTPUT_DIR), help="출력 폴더 경로 (기본: output)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    if args.file:
        src = Path(args.file)
        if not src.exists():
            print(f"[오류] 파일이 존재하지 않습니다: {src}")
            sys.exit(1)
    else:
        input_dir = Path(args.input_dir)
        if not input_dir.exists():
            print(f"[오류] 입력 폴더가 존재하지 않습니다: {input_dir}")
            sys.exit(1)
        src = choose_source_file(input_dir)

    with Image.open(src) as probe:
        width, height = probe.size
    print(f"이미지 크기: {width} x {height} px")

    row_sizes, col_sizes = resolve_direction_and_sizes(width, height)

    output_dir.mkdir(parents=True, exist_ok=True)
    _, _, saved = split_image(src, output_dir, row_sizes, col_sizes)

    print("\n--------------------------------------")
    print(f"총 {len(saved)}개 조각으로 분할 완료:")
    for p in saved:
        print(f"  - {p.name}")
    print(f"결과 저장 위치: {output_dir}")


if __name__ == "__main__":
    main()
