# -*- coding: utf-8 -*-
r"""
HTML -> PDF 변환 프로그램 (보이는 그대로)
--------------------------------------
브라우저(Chromium)로 HTML을 실제 렌더링한 뒤 PDF로 저장합니다.
화면(screen) 스타일과 배경색/배경 이미지를 그대로 유지합니다.

모드
  single (기본) : 페이지 나눔 없이 화면에 보이는 모습 전체를 한 장의 긴 PDF 페이지로 저장
  paged         : A4 등 일반 용지 크기로 페이지를 나누어 저장

사용법
  1) 기본 실행
       python main.py
     input 폴더의 모든 .html/.htm 파일을 output 폴더에 PDF로 변환합니다.

  2) 커맨드라인 인자로 실행
       python main.py page.html
       python main.py a.html b.html --output "C:\path\to\out"
       python main.py https://example.com --width 1440
       python main.py --mode paged --format A4 --margin 10
"""

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

SUPPORTED_EXTENSIONS = {".html", ".htm", ".xhtml"}

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = SCRIPT_DIR / "input"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "output"
DEFAULT_WIDTH = 1280
# Chromium PDF 페이지 최대 높이(200인치)를 CSS px로 환산한 값
MAX_PAGE_HEIGHT_PX = 200 * 96 - 2


def is_url(value: str) -> bool:
    return urlparse(value).scheme in ("http", "https", "file")


def iter_html_files(folder: Path):
    """폴더 내의 HTML 파일들을 이름순으로 반환한다."""
    return [
        path for path in sorted(folder.iterdir())
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]


def collect_sources(inputs, input_dir: Path):
    """변환 대상(파일 경로 또는 URL) 목록을 (원본, 출력 파일명) 튜플로 만든다."""
    sources = []
    if inputs:
        for item in inputs:
            if is_url(item):
                parsed = urlparse(item)
                stem = Path(parsed.path).stem or parsed.netloc or "page"
                sources.append((item, stem))
                continue
            path = Path(item)
            if path.is_dir():
                sources.extend((p, p.stem) for p in iter_html_files(path))
            elif path.is_file():
                sources.append((path, path.stem))
            else:
                print(f"[건너뜀] 찾을 수 없음: {item}")
    else:
        if not input_dir.is_dir():
            print(f"[오류] 입력 폴더가 없습니다: {input_dir}")
            return []
        sources.extend((p, p.stem) for p in iter_html_files(input_dir))
    return sources


def launch_browser(playwright):
    """설치된 Edge/Chrome을 우선 사용하고, 없으면 Playwright 내장 Chromium을 사용한다."""
    errors = []
    for channel in ("msedge", "chrome", None):
        try:
            if channel:
                return playwright.chromium.launch(channel=channel)
            return playwright.chromium.launch()
        except Exception as exc:  # 브라우저 미설치 등
            errors.append(f"{channel or 'chromium'}: {str(exc).splitlines()[0]}")
    raise RuntimeError(
        "사용 가능한 브라우저를 찾지 못했습니다.\n  " + "\n  ".join(errors)
        + "\n  해결: python -m playwright install chromium"
    )


def prepare_page(page, source, wait_ms: int):
    """페이지를 로드하고 폰트/이미지/지연 로딩 콘텐츠가 모두 그려질 때까지 기다린다."""
    url = source if isinstance(source, str) else source.resolve().as_uri()
    page.goto(url, wait_until="load")
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass  # 계속 통신하는 페이지는 무시하고 진행

    # 끝까지 스크롤하여 lazy-load 이미지/애니메이션을 트리거
    page.evaluate(
        """async () => {
            const step = Math.max(window.innerHeight, 400);
            for (let y = 0; y < document.documentElement.scrollHeight; y += step) {
                window.scrollTo(0, y);
                await new Promise(r => setTimeout(r, 80));
            }
            window.scrollTo(0, 0);
            if (document.fonts && document.fonts.ready) await document.fonts.ready;
            await Promise.all(Array.from(document.images).map(img =>
                img.complete ? null : new Promise(r => { img.onload = img.onerror = r; })));
        }"""
    )
    if wait_ms:
        page.wait_for_timeout(wait_ms)


def measure_height(page) -> int:
    return int(page.evaluate(
        """() => Math.ceil(Math.max(
            document.documentElement.scrollHeight,
            document.body ? document.body.scrollHeight : 0,
            document.documentElement.getBoundingClientRect().height))"""
    ))


def convert(browser, source, dst: Path, args) -> str:
    """하나의 HTML을 PDF로 변환한다. 실제 사용된 모드를 반환한다."""
    context = browser.new_context(
        viewport={"width": args.width, "height": args.viewport_height},
        device_scale_factor=1,
    )
    try:
        page = context.new_page()
        page.emulate_media(media="print" if args.print_css else "screen")
        prepare_page(page, source, args.wait)

        mode = args.mode
        if mode == "single":
            height = measure_height(page)
            if height > MAX_PAGE_HEIGHT_PX:
                print(f"  [안내] 페이지가 너무 길어(>{MAX_PAGE_HEIGHT_PX}px) paged 모드로 전환합니다.")
                mode = "paged"
            else:
                page.add_style_tag(
                    content="@page{margin:0;size:%dpx %dpx}html,body{margin:0}" % (args.width, height)
                )
                page.pdf(
                    path=str(dst),
                    width=f"{args.width}px",
                    height=f"{height}px",
                    print_background=True,
                    margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                    page_ranges="1",
                )
                return mode

        margin = f"{args.margin}mm"
        page.pdf(
            path=str(dst),
            format=args.format,
            landscape=args.landscape,
            print_background=True,
            margin={"top": margin, "right": margin, "bottom": margin, "left": margin},
            prefer_css_page_size=args.print_css,
        )
        return mode
    finally:
        context.close()


def build_parser():
    parser = argparse.ArgumentParser(description="HTML을 보이는 그대로 PDF로 변환합니다.")
    parser.add_argument("inputs", nargs="*", help="HTML 파일/폴더/URL (생략 시 input 폴더 전체)")
    parser.add_argument("--input", dest="input_dir", type=Path, default=DEFAULT_INPUT_DIR,
                        help="입력 폴더 (기본: ./input)")
    parser.add_argument("--output", dest="output_dir", type=Path, default=DEFAULT_OUTPUT_DIR,
                        help="출력 폴더 (기본: ./output)")
    parser.add_argument("--mode", choices=("single", "paged"), default="single",
                        help="single: 한 장의 긴 페이지 / paged: 용지 크기로 분할 (기본: single)")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH,
                        help=f"렌더링 화면 폭(px) (기본: {DEFAULT_WIDTH})")
    parser.add_argument("--viewport-height", type=int, default=900, help="렌더링 화면 높이(px) (기본: 900)")
    parser.add_argument("--format", default="A4", help="paged 모드 용지 (A4, A3, Letter 등. 기본: A4)")
    parser.add_argument("--landscape", action="store_true", help="paged 모드 가로 방향")
    parser.add_argument("--margin", type=float, default=0, help="paged 모드 여백(mm) (기본: 0)")
    parser.add_argument("--print-css", action="store_true",
                        help="화면 스타일 대신 인쇄(@media print) 스타일 사용")
    parser.add_argument("--wait", type=int, default=300, help="렌더링 후 추가 대기(ms) (기본: 300)")
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[오류] playwright 가 설치되어 있지 않습니다.  pip install -r requirements.txt")
        return 1

    sources = collect_sources(args.inputs, args.input_dir)
    if not sources:
        print("변환할 HTML이 없습니다.")
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)

    ok = failed = 0
    with sync_playwright() as playwright:
        try:
            browser = launch_browser(playwright)
        except RuntimeError as exc:
            print(f"[오류] {exc}")
            return 1
        try:
            for source, stem in sources:
                dst = args.output_dir / f"{stem}.pdf"
                label = source if isinstance(source, str) else source.name
                print(f"변환 중: {label}")
                try:
                    mode = convert(browser, source, dst, args)
                    print(f"  -> {dst} ({mode}, {dst.stat().st_size / 1024:.0f} KB)")
                    ok += 1
                except Exception as exc:
                    print(f"  [실패] {exc}")
                    failed += 1
        finally:
            browser.close()

    print(f"완료: 성공 {ok}, 실패 {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
