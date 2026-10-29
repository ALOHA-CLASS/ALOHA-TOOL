# QR 코드 생성 프로그램

단일 / 다중(JSON) QR 코드 생성. Tkinter GUI 와 CLI 를 모두 지원합니다.

## 설치

```powershell
pip install -r requirements.txt
```

## 사용법

### GUI (기본)

```powershell
python main.py
```

- **단일 생성** 탭: 내용, 파일명, 크기(px), 확장자, 여백, 오류 정정, 색상, 저장 폴더 설정 + 미리보기
- **다중 생성** 탭: JSON 을 불러오거나 직접 편집 후 `일괄 생성`

### CLI

```powershell
python main.py single "https://example.com" --name site --size 600 --ext jpg
python main.py batch                       # input/format.json 사용
python main.py batch input/sample.json     # 지정한 JSON 사용
```

결과는 기본적으로 `output/` 폴더에 저장됩니다. (`--output` 으로 변경)

## 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `size` | 이미지 한 변의 픽셀 수 (21~10000) | 500 |
| `ext` | 확장자: png, jpg, jpeg, webp, bmp, gif, tiff | png |
| `border` | 여백 (모듈 단위, 0~50) | 4 |
| `error_correction` | 오류 정정 L / M / Q / H | M |
| `fill_color` | QR 색상 (이름 또는 `#RRGGBB`) | black |
| `back_color` | 배경 색상 | white |

## JSON 형식 (`input/format.json`, `input/sample.json`)

```json
{
  "defaults": { "size": 500, "ext": "png" },
  "items": [
    { "name": "homepage", "data": "https://example.com" },
    { "name": "colored", "data": "Hello", "size": 800, "ext": "webp", "fill_color": "#1a73e8" }
  ]
}
```

- `data` 필수, `name` 생략 시 `qr_001` 형태로 자동 지정
- `defaults` 는 모든 항목의 공통값이며 항목에 적은 값이 우선
- `[ {...}, {...} ]` 처럼 배열만 써도 됨
- 같은 이름이 중복되면 `_2`, `_3` 이 붙음
