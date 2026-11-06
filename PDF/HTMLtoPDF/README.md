# HTML → PDF 변환 프로그램

HTML을 브라우저(Chromium)로 실제 렌더링한 뒤, 기본적으로 **A4 여러 페이지**로 나누어 PDF로 저장합니다.
배경색/배경 이미지, 웹폰트, 화면(screen) 스타일을 유지하며 첫 페이지만이 아닌 전체 페이지를 저장합니다.

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

3. 시작 시 상하좌우 여백(mm)을 입력합니다. Enter만 누르면 **10mm**를 적용합니다.
4. `output` 폴더에 같은 이름의 PDF가 생성됩니다.

`--margin 10`처럼 지정하면 입력 질문 없이 바로 변환합니다.
`single` 모드는 여백을 묻지 않습니다. 표준 입력을 읽을 수 없는 환경에서는 안내 후 10mm를 적용합니다.

### 옵션

```powershell
python main.py page.html                         # 특정 파일만
python main.py a.html b.html --output "C:\out"   # 여러 파일, 출력 폴더 지정
python main.py https://example.com               # URL도 변환 가능
python main.py --width 1440                      # 렌더링 화면 폭(px), 기본 1280
python main.py --margin 10                       # 여백 입력 없이 A4 변환, 여백 10mm
python main.py --mode single                     # 기존처럼 긴 페이지로 저장
python main.py --print-css                       # 인쇄용(@media print) 스타일 사용
```

### A4 인쇄용 HTML 변환

HTML에 A4 인쇄 스타일(`@page`, `@media print`)이 정의된 경우 아래처럼 변환합니다.
`--print-css`가 인쇄 스타일을 활성화하고, 페이지 분할 모드가 A4 용지에 맞춰 PDF를 생성합니다.

```powershell
python main.py --mode paged --format A4 --print-css
```

PDF 바깥 여백은 기본 **상하좌우 10mm**이며, HTML의 `@page` 여백보다 `--margin` 설정이 우선합니다.
`html`, `body`, `.page`의 바깥 여백과 패딩도 페이지 분할 모드에서 제거합니다.
여백을 변경하려면 `--margin 3` 등으로 지정하세요. 여백 없이 저장하려면 `--margin 0`을 사용합니다.

### 표 잘림 방지

페이지 분할 모드에서는 표의 최소 폭·고정 폭을 용지에 맞추고,
셀의 긴 글씨와 뱃지가 셀 안에서 줄바꿈되도록 보정합니다.
표를 감싼 스크롤 영역은 스크롤 없이 전체 내용을 출력하며,
표 전체가 아닌 행 단위로 페이지를 나누어 불필요한 빈 공간을 줄입니다.
한 행이 용지 한 장보다 크면 해당 행도 여러 페이지로 나뉠 수 있습니다.
배경색과 글꼴은 유지하고 원본 HTML 파일은 변경하지 않습니다.
`single` 모드는 기존 화면 레이아웃을 유지합니다.

| 모드 | 설명 |
| --- | --- |
| `paged` (기본) | A4 등 용지 크기로 전체 내용을 여러 페이지로 분할 |
| `single` | 화면 전체를 긴 페이지로 저장. HTML의 강제 페이지 나눔이 있으면 여러 페이지가 생성되며, 모두 저장. 너무 긴 페이지(약 200인치 초과)는 `paged`로 자동 전환 |

기존 기본값은 `single`이었지만, A4 문서를 빠짐없이 출력하도록 `paged`로 변경했습니다.
`--print-css`를 지정하지 않으면 기존처럼 화면 스타일을 사용합니다.
HTML에 `height:100vh; overflow:hidden` 등으로 내용 자체를 숨기는 스타일이 있다면,
해당 스타일은 HTML의 인쇄 CSS에서 해제해야 합니다.

## 회귀 테스트

브라우저로 실제 PDF를 생성하여 A4 크기, 자동/강제 페이지 나눔, 마지막 페이지 내용,
표의 마지막 열·뱃지 줄바꿈과 여백 설정까지 확인합니다.

```powershell
pip install -r requirements-test.txt
python -m unittest discover -s . -p "test_main.py" -v
```
