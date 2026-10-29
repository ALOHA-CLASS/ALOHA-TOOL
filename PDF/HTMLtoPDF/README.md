# HTML → PDF 변환 프로그램

HTML을 브라우저(Chromium)로 실제 렌더링한 뒤, 화면에 보이는 그대로 PDF로 저장합니다.
배경색/배경 이미지, 웹폰트, 화면(screen) 스타일을 유지합니다.

## 사전 준비

```powershell
pip install -r requirements.txt
```

- PC에 설치된 **Microsoft Edge 또는 Chrome**을 자동으로 사용합니다.
- 둘 다 없으면 `python -m playwright install chromium` 을 실행하세요.

## 사용 방법

1. `input` 폴더에 `.html` / `.htm` 파일을 넣습니다.
2. 실행합니다.

```powershell
python main.py
```

3. `output` 폴더에 같은 이름의 PDF가 생성됩니다.

### 옵션

```powershell
python main.py page.html                         # 특정 파일만
python main.py a.html b.html --output "C:\out"   # 여러 파일, 출력 폴더 지정
python main.py https://example.com               # URL도 변환 가능
python main.py --width 1440                      # 렌더링 화면 폭(px), 기본 1280
python main.py --mode paged --format A4 --margin 10   # A4로 페이지 분할
python main.py --print-css                       # 인쇄용(@media print) 스타일 사용
```

| 모드 | 설명 |
| --- | --- |
| `single` (기본) | 페이지 나눔 없이 화면 전체를 한 장의 긴 페이지로 저장 (보이는 그대로) |
| `paged` | A4 등 용지 크기로 분할. 너무 긴 페이지(약 200인치 초과)는 자동으로 전환 |
