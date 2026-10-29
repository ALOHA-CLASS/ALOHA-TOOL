"""QR 코드 생성 프로그램 (단일 / 다중 생성, CLI + Tkinter GUI).

사용법:
    python main.py                                  # GUI 실행
    python main.py single "https://example.com"     # 단일 생성
    python main.py batch                            # input/format.json 으로 다중 생성
    python main.py batch input/sample.json          # 지정한 JSON 으로 다중 생성
"""
import argparse
import json
import os
import re
import sys

import qrcode
from PIL import Image, ImageColor
from qrcode.constants import (
    ERROR_CORRECT_H,
    ERROR_CORRECT_L,
    ERROR_CORRECT_M,
    ERROR_CORRECT_Q,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DEFAULT_JSON = os.path.join(INPUT_DIR, "format.json")

# 확장자 -> Pillow 저장 포맷
FORMATS = {
    "png": "PNG",
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "webp": "WEBP",
    "bmp": "BMP",
    "gif": "GIF",
    "tiff": "TIFF",
}
EXTENSIONS = ["png", "jpg", "webp", "bmp", "gif", "tiff"]

ERROR_LEVELS = {
    "L": ERROR_CORRECT_L,  # 약 7%
    "M": ERROR_CORRECT_M,  # 약 15%
    "Q": ERROR_CORRECT_Q,  # 약 25%
    "H": ERROR_CORRECT_H,  # 약 30%
}

DEFAULTS = {
    "size": 500,  # 최종 이미지 한 변의 픽셀 수
    "ext": "png",
    "border": 4,  # 여백(모듈 단위)
    "error_correction": "M",
    "fill_color": "black",
    "back_color": "white",
}

SAMPLE_JSON = {
    "defaults": {"size": 500, "ext": "png", "error_correction": "M"},
    "items": [
        {"name": "homepage", "data": "https://example.com"},
        {"name": "wifi", "data": "WIFI:T:WPA;S:MyWiFi;P:password1234;;", "size": 400},
        {
            "name": "contact",
            "data": "BEGIN:VCARD\nVERSION:3.0\nFN:홍길동\nTEL:010-1234-5678\nEND:VCARD",
            "ext": "jpg",
            "error_correction": "H",
        },
        {
            "name": "colored",
            "data": "Hello QR",
            "size": 800,
            "ext": "webp",
            "fill_color": "#1a73e8",
            "back_color": "#ffffff",
            "border": 2,
        },
    ],
}


def sanitize_name(name):
    name = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", str(name)).strip(" .")
    return name or "qr"


def normalize_options(opts):
    """옵션 dict 를 기본값과 병합하고 검증한다."""
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in opts.items() if v is not None and v != ""})

    try:
        merged["size"] = int(merged["size"])
        merged["border"] = int(merged["border"])
    except (TypeError, ValueError):
        raise ValueError("size / border 는 정수여야 합니다.")
    if not 21 <= merged["size"] <= 10000:
        raise ValueError("size 는 21 ~ 10000 픽셀 사이여야 합니다.")
    if not 0 <= merged["border"] <= 50:
        raise ValueError("border 는 0 ~ 50 사이여야 합니다.")

    merged["ext"] = str(merged["ext"]).lower().lstrip(".")
    if merged["ext"] not in FORMATS:
        raise ValueError(
            f"지원하지 않는 확장자: {merged['ext']} (지원: {', '.join(EXTENSIONS)})"
        )

    merged["error_correction"] = str(merged["error_correction"]).upper()
    if merged["error_correction"] not in ERROR_LEVELS:
        raise ValueError("error_correction 은 L, M, Q, H 중 하나여야 합니다.")

    for key in ("fill_color", "back_color"):
        try:
            ImageColor.getrgb(str(merged[key]))
        except ValueError:
            raise ValueError(f"{key} 값이 올바른 색상이 아닙니다: {merged[key]}")
    return merged


def make_qr_image(data, **opts):
    """QR 코드를 size x size 픽셀의 PIL 이미지로 만든다."""
    if data is None or str(data) == "":
        raise ValueError("data(QR에 넣을 내용)가 비어 있습니다.")
    o = normalize_options(opts)

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_LEVELS[o["error_correction"]],
        box_size=1,
        border=o["border"],
    )
    qr.add_data(str(data))
    qr.make(fit=True)

    total = qr.modules_count + o["border"] * 2
    size = o["size"]
    back = ImageColor.getrgb(str(o["back_color"]))
    fill = ImageColor.getrgb(str(o["fill_color"]))

    # 모듈이 흐려지지 않도록 정수 배율로 그린 뒤 배경 캔버스 중앙에 배치
    qr.box_size = max(1, size // total)
    img = qr.make_image(fill_color=fill, back_color=back).get_image().convert("RGB")
    if img.width > size:  # 지정 크기가 모듈 수보다 작은 경우
        return img.resize((size, size), Image.NEAREST)
    canvas = Image.new("RGB", (size, size), back)
    canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2))
    return canvas


def save_qr(data, name="qr", output_dir=OUTPUT_DIR, **opts):
    """QR 코드를 파일로 저장하고 경로를 반환한다."""
    o = normalize_options(opts)
    img = make_qr_image(data, **o)
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{sanitize_name(name)}.{o['ext']}")
    if o["ext"] == "gif":
        img = img.convert("P", palette=Image.ADAPTIVE)
    img.save(path, FORMATS[o["ext"]])
    return path


def load_items(json_path):
    """JSON 파일에서 (items, defaults) 를 읽는다."""
    with open(json_path, "r", encoding="utf-8-sig") as f:
        return parse_items(json.load(f))


def parse_items(obj):
    """형식: {"defaults": {...}, "items": [{...}]}  또는  [{...}, {...}]"""
    if isinstance(obj, list):
        defaults, items = {}, obj
    elif isinstance(obj, dict):
        defaults, items = obj.get("defaults", {}) or {}, obj.get("items")
    else:
        raise ValueError("JSON 최상위는 객체 또는 배열이어야 합니다.")
    if not isinstance(items, list) or not items:
        raise ValueError('"items" 배열이 비어 있거나 없습니다.')
    if not isinstance(defaults, dict):
        raise ValueError('"defaults" 는 객체여야 합니다.')
    return items, defaults


def generate_batch(items, defaults, output_dir=OUTPUT_DIR, log=print):
    """여러 QR 을 생성한다. (성공 개수, 실패 개수) 반환."""
    ok = fail = 0
    used = set()
    for idx, item in enumerate(items, 1):
        try:
            if not isinstance(item, dict):
                raise ValueError("항목은 객체여야 합니다.")
            opts = dict(defaults)
            opts.update(item)
            data = opts.pop("data", None)
            name = opts.pop("name", None) or f"qr_{idx:03d}"
            ext = str(opts.get("ext", DEFAULTS["ext"])).lower().lstrip(".")
            base, n = sanitize_name(name), 1
            unique = base
            while (unique.lower(), ext) in used:  # Windows 는 대소문자 구분 안 함
                n += 1
                unique = f"{base}_{n}"
            used.add((unique.lower(), ext))
            path = save_qr(data, unique, output_dir, **opts)
            log(f"[OK]   #{idx} {path}")
            ok += 1
        except Exception as e:  # 한 항목 실패가 전체를 막지 않도록
            log(f"[FAIL] #{idx} {e}")
            fail += 1
    return ok, fail


# ----------------------------- CLI -----------------------------

def build_parser():
    p = argparse.ArgumentParser(description="QR 코드 생성 프로그램")
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("single", help="단일 QR 코드 생성")
    s.add_argument("data", help="QR 코드에 넣을 내용")
    s.add_argument("--name", default="qr", help="저장할 파일명(확장자 제외)")
    s.add_argument("--size", type=int, default=DEFAULTS["size"], help="한 변의 픽셀 수")
    s.add_argument("--ext", default=DEFAULTS["ext"], choices=sorted(FORMATS), help="이미지 확장자")
    s.add_argument("--border", type=int, default=DEFAULTS["border"], help="여백(모듈 단위)")
    s.add_argument("--ec", default=DEFAULTS["error_correction"], choices=list(ERROR_LEVELS), help="오류 정정 수준")
    s.add_argument("--fill", default=DEFAULTS["fill_color"], help="QR 색상")
    s.add_argument("--back", default=DEFAULTS["back_color"], help="배경 색상")
    s.add_argument("--output", default=OUTPUT_DIR, help="저장 폴더")

    b = sub.add_parser("batch", help="JSON 파일로 다중 QR 코드 생성")
    b.add_argument("json", nargs="?", default=DEFAULT_JSON, help="JSON 파일 경로 (기본: input/format.json)")
    b.add_argument("--output", default=OUTPUT_DIR, help="저장 폴더")

    sub.add_parser("gui", help="GUI 실행 (기본값)")
    return p


def run_cli(args):
    if args.cmd == "single":
        path = save_qr(
            args.data, args.name, args.output,
            size=args.size, ext=args.ext, border=args.border,
            error_correction=args.ec, fill_color=args.fill, back_color=args.back,
        )
        print(f"저장 완료: {path}")
        return 0
    items, defaults = load_items(args.json)
    ok, fail = generate_batch(items, defaults, args.output)
    print(f"완료: 성공 {ok}, 실패 {fail}")
    return 1 if fail else 0


# ----------------------------- GUI -----------------------------

def run_gui():
    import tkinter as tk
    from tkinter import colorchooser, filedialog, messagebox, scrolledtext, ttk

    from PIL import ImageTk

    root = tk.Tk()
    root.title("QR 코드 생성기")
    root.geometry("760x640")

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=8, pady=8)
    single = ttk.Frame(nb, padding=10)
    multi = ttk.Frame(nb, padding=10)
    nb.add(single, text="단일 생성")
    nb.add(multi, text="다중 생성 (JSON)")

    # ---- 단일 생성 ----
    ttk.Label(single, text="내용 (URL / 텍스트)").grid(row=0, column=0, sticky="nw")
    txt = tk.Text(single, height=5, width=40)
    txt.grid(row=0, column=1, columnspan=3, sticky="we", pady=2)

    name_v = tk.StringVar(value="qr")
    size_v = tk.IntVar(value=DEFAULTS["size"])
    ext_v = tk.StringVar(value=DEFAULTS["ext"])
    border_v = tk.IntVar(value=DEFAULTS["border"])
    ec_v = tk.StringVar(value=DEFAULTS["error_correction"])
    fill_v = tk.StringVar(value=DEFAULTS["fill_color"])
    back_v = tk.StringVar(value=DEFAULTS["back_color"])
    out_v = tk.StringVar(value=OUTPUT_DIR)

    def row(r, label, widget):
        ttk.Label(single, text=label).grid(row=r, column=0, sticky="w", pady=2)
        widget.grid(row=r, column=1, sticky="w", pady=2)

    row(1, "파일명", ttk.Entry(single, textvariable=name_v, width=24))
    row(2, "크기 (px)", ttk.Spinbox(single, from_=21, to=10000, increment=50, textvariable=size_v, width=10))
    row(3, "이미지 확장자", ttk.Combobox(single, textvariable=ext_v, values=EXTENSIONS, state="readonly", width=10))
    row(4, "여백 (모듈)", ttk.Spinbox(single, from_=0, to=50, textvariable=border_v, width=10))
    row(5, "오류 정정", ttk.Combobox(single, textvariable=ec_v, values=list(ERROR_LEVELS), state="readonly", width=10))

    def pick_color(var):
        c = colorchooser.askcolor(color=var.get())[1]
        if c:
            var.set(c)

    for r, label, var in ((6, "QR 색상", fill_v), (7, "배경 색상", back_v)):
        f = ttk.Frame(single)
        ttk.Entry(f, textvariable=var, width=12).pack(side="left")
        ttk.Button(f, text="선택", command=lambda v=var: pick_color(v)).pack(side="left", padx=4)
        row(r, label, f)

    def pick_dir(var):
        d = filedialog.askdirectory(initialdir=var.get())
        if d:
            var.set(d)

    f = ttk.Frame(single)
    ttk.Entry(f, textvariable=out_v, width=32).pack(side="left")
    ttk.Button(f, text="폴더", command=lambda: pick_dir(out_v)).pack(side="left", padx=4)
    row(8, "저장 폴더", f)

    preview = ttk.Label(single, relief="sunken", anchor="center")
    preview.grid(row=1, column=2, rowspan=8, columnspan=2, padx=12, sticky="n")
    preview.photo = None

    def collect():
        return dict(
            size=size_v.get(), ext=ext_v.get(), border=border_v.get(),
            error_correction=ec_v.get(), fill_color=fill_v.get(), back_color=back_v.get(),
        )

    def do_preview():
        try:
            img = make_qr_image(txt.get("1.0", "end").strip("\n"), **collect())
            img.thumbnail((260, 260), Image.NEAREST)
            preview.photo = ImageTk.PhotoImage(img)
            preview.configure(image=preview.photo)
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def do_save():
        try:
            path = save_qr(txt.get("1.0", "end").strip("\n"), name_v.get(), out_v.get(), **collect())
            messagebox.showinfo("완료", f"저장되었습니다.\n{path}")
        except Exception as e:
            messagebox.showerror("오류", str(e))

    bf = ttk.Frame(single)
    bf.grid(row=9, column=0, columnspan=4, pady=12)
    ttk.Button(bf, text="미리보기", command=do_preview).pack(side="left", padx=6)
    ttk.Button(bf, text="저장", command=do_save).pack(side="left", padx=6)

    # ---- 다중 생성 ----
    top = ttk.Frame(multi)
    top.pack(fill="x")
    editor = scrolledtext.ScrolledText(multi, height=18, font=("Consolas", 10))
    log_box = scrolledtext.ScrolledText(multi, height=8, state="disabled")
    multi_out = tk.StringVar(value=OUTPUT_DIR)

    def load_file():
        p = filedialog.askopenfilename(initialdir=INPUT_DIR, filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if p:
            with open(p, "r", encoding="utf-8-sig") as fh:
                editor.delete("1.0", "end")
                editor.insert("1.0", fh.read())

    def insert_sample():
        editor.delete("1.0", "end")
        editor.insert("1.0", json.dumps(SAMPLE_JSON, ensure_ascii=False, indent=2))

    def log(msg):
        log_box.configure(state="normal")
        log_box.insert("end", msg + "\n")
        log_box.see("end")
        log_box.configure(state="disabled")
        root.update_idletasks()

    def do_batch():
        try:
            items, defaults = parse_items(json.loads(editor.get("1.0", "end")))
        except Exception as e:
            messagebox.showerror("JSON 오류", str(e))
            return
        log_box.configure(state="normal")
        log_box.delete("1.0", "end")
        log_box.configure(state="disabled")
        ok, fail = generate_batch(items, defaults, multi_out.get(), log)
        log(f"완료: 성공 {ok}, 실패 {fail}")

    ttk.Button(top, text="JSON 불러오기", command=load_file).pack(side="left")
    ttk.Button(top, text="샘플 넣기", command=insert_sample).pack(side="left", padx=4)
    ttk.Label(top, text="  저장 폴더").pack(side="left")
    ttk.Entry(top, textvariable=multi_out, width=36).pack(side="left", padx=4)
    ttk.Button(top, text="폴더", command=lambda: pick_dir(multi_out)).pack(side="left")
    ttk.Button(top, text="일괄 생성", command=do_batch).pack(side="right")
    editor.pack(fill="both", expand=True, pady=6)
    log_box.pack(fill="x")

    if os.path.isfile(DEFAULT_JSON) and os.path.getsize(DEFAULT_JSON) > 0:
        try:
            with open(DEFAULT_JSON, "r", encoding="utf-8-sig") as fh:
                editor.insert("1.0", fh.read())
        except OSError:
            insert_sample()
    else:
        insert_sample()

    root.mainloop()


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.cmd in (None, "gui"):
        run_gui()
        return 0
    try:
        return run_cli(args)
    except Exception as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
