# 이미지 배경 투명화

로고, 아이콘, 상품 이미지의 **단색 배경**을 제거하고 투명 PNG 또는 WebP로 저장하는
Python 3.10+ 콘솔 프로그램입니다. 이미지가 외부 서버로 전송되지 않습니다.
복잡한 사진의 인물/사물을 자동 분리하는 AI 누끼 도구는 아닙니다.

## 설치 및 실행

PowerShell에서:

```powershell
Set-Location 'C:\ALOHA\GITHUB\ALOHA-TOOL\IMG\배경투명'
python -m pip install -r requirements.txt
python main.py
```

`input` 폴더에 이미지를 넣고 실행하면 확장자와 옵션을 선택한 후,
각 이미지의 출력 파일명을 입력합니다. Enter로 기본값을 선택할 수 있습니다.
결과는 `output` 폴더에 저장되며 기본 파일명은
`원본이름_transparent.png` 또는 `.webp`입니다.
파일명에 폴더 경로나 Windows에서 사용할 수 없는 문자는 입력할 수 없습니다.
확장자를 생략하거나 `.png`/`.webp`를 붙여도 선택한 출력 형식의 확장자가 적용됩니다.
같은 이름이 있으면 `_1`, `_2`를 붙이며 원본과 기존 결과를 덮어쓰지 않습니다.
기본 입출력 폴더는 실행 위치가 아니라 이 프로그램이 있는 폴더 기준입니다.

## 옵션

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--to` | 대화형 선택 | `png` 또는 `webp`. 지정하면 추가 질문 없이 실행 |
| `--background` | `auto` | 테두리에서 가장 흔한 불투명/반투명 색 자동 선택. `white`, `black`, `"#RRGGBB"`로 직접 지정 가능 |
| `--tolerance` | `30` | 0~255. 배경색과 RGB 각 채널 차이의 최댓값이 이 값 이하면 제거. 높일수록 더 넓은 색상 범위 제거 |
| `--softness` | `20` | 0~255. 허용 오차 바깥의 추가 색상 범위에서 제거량을 점진적으로 줄임. 0은 경계가 뚜렷한 제거 |
| `--strength` | `100` | 0~100%. 100은 배경 완전 제거, 50은 배경 알파를 약 절반으로, 0은 원래 투명도 유지 |
| `--scope` | `all` | `all`: 내부의 같은 색도 제거. `edges`: 이미지 테두리에서 상하좌우로 연결된 배경만 제거 |
| `--feather` | `0` | 0~20px. 제거 마스크에 가우시안 흐림 적용. 높이면 경계가 부드러워지지만 전경도 일부 투명해질 수 있음 |
| `--lossy` | 사용 안 함 | WebP 손실 압축 사용. 기본 WebP는 무손실이며, PNG에는 사용 불가 |
| `--quality` | `95` | 1~100. 손실 WebP의 화질. 무손실 WebP에서는 압축 노력 수준이며 화질 손실 없음. PNG에는 영향 없음 |
| `--input` | `input` | 일괄 처리할 입력 폴더 (하위 폴더 제외) |
| `--output` | `output` | 출력 폴더. 원본이 있는 입력 폴더와 달라야 함 |
| `--name` | 원본이름_transparent | 출력 파일명. 대화형에서는 생략 시 이미지마다 입력. 일괄 처리에 지정하면 같은 이름에 중복 번호를 붙여 저장 |

### 실행 예

```powershell
# 첨부한 MicroPython 같은 흰 배경 로고: 내부의 흰 부분도 제거
python main.py --to png --background white

# 배경색 자동 감지, WebP 무손실 저장
python main.py --to webp

# 출력 파일명 지정: output\내로고.webp
python main.py --to webp --name '내로고'

# 전경 내부의 흰색은 보존하고 테두리 배경만 제거
python main.py --to png --background white --scope edges

# 더 넓은 배경색 범위, 부드러운 경계
python main.py --to png --tolerance 50 --softness 30 --feather 1

# 배경을 반투명하게 유지
python main.py --to png --background white --strength 50

# 특정 색상 제거 + 손실 WebP 저장
python main.py --to webp --background "#00FF00" --lossy --quality 90

# 단일 파일 / 입출력 폴더 지정
python main.py '.\input\MicroPython.png' --to png --background white
python main.py --to png --input 'C:\사진\원본' --output 'C:\사진\결과'
```

## 조절 요령과 주의 사항

- 흰색 배경 로고는 `white`, 검은색 배경은 `black`을 권장합니다.
  자동 감지는 테두리의 전경색을 배경으로 오인할 수 있습니다.
- 흰 테두리가 남으면 `tolerance`를 조금 높이세요. 전경까지 지워지면 낮추거나
  `edges`로 바꾸세요. `all`은 흰 배경 속 로고 내부의 흰 구멍까지 지웁니다.
- 전경이 테두리 배경과 같은 색으로 이어져 있으면 `edges`에서도 지워질 수 있습니다.
- 이미 투명한 픽셀과 반투명 픽셀의 기존 알파는 보존하거나 낮추기만 합니다.
  테두리 전체가 투명하면 자동 감지할 수 없으므로 배경색을 직접 지정하세요.
- 색상 기반 제거이므로 그라데이션/복잡한 배경이나 배경색이 섞인 가장자리의
  완벽한 복원은 보장하지 않습니다. 제거 후 RGB 색상을 재구성하지 않습니다.
- 입력: PNG, WebP, JPEG, BMP, TIFF, GIF. 애니메이션/다중 페이지는 손실 방지를 위해
  오류로 처리합니다. EXIF 회전 방향을 적용하며 원본 해상도는 유지합니다.
- 손상된 파일은 이름과 오류를 표시하고 다음 파일을 계속 처리합니다.
  하나라도 실패하면 종료 코드 1, 잘못된 CLI 옵션은 2, 전체 성공은 0입니다.
- 투명 이미지가 뷰어에서 흰색/검은색으로 보일 수 있습니다. 바둑판 배경을 지원하는
  편집기에서 실제 투명도를 확인하세요.

## 테스트

```powershell
python -m unittest -v
```
