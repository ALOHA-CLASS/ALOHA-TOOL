# PDF → 이미지 변환 프로그램

input 폴더의 PDF 파일을 페이지별 이미지로 변환하여 output 폴더에 저장하는 프로그램입니다.

## 주요 특징

- **원하는 확장자로 변환**: jpg, png, webp, gif, bmp, tiff 중 선택 가능
- **페이지별 번호 매김**: `{PDF 파일명}-001.jpg`, `{PDF 파일명}-002.jpg` ... 형식으로 저장
- **해상도(DPI) 조절 가능**: 선명도와 용량을 원하는 대로 조정
- **여러 PDF 일괄 변환**: input 폴더에 PDF를 여러 개 넣으면 한 번에 모두 변환

## 사전 준비

### 라이브러리 설치

```powershell
pip install -r requirements.txt
```

## 사용 방법

### 1) 대화형 실행

1. `input` 폴더에 변환할 PDF 파일을 넣습니다
2. 프로그램을 실행합니다:

```powershell
python main.py
```

3. 변환할 확장자를 입력하면 (예: `jpg`) input 폴더의 모든 PDF가 변환됩니다
4. 변환된 이미지가 `output` 폴더에 `제목-001.jpg` 형식으로 생성됩니다

### 2) 커맨드라인 인자로 실행

```powershell
python main.py --to jpg
python main.py --to png --dpi 300
python main.py --input "C:\path\to\folder" --output "C:\path\to\out" --to jpg
python main.py report.pdf --to png        # 단일 파일만 변환
```

## 옵션

| 옵션 | 설명 | 기본값 |
| --- | --- | --- |
| `--to` | 변환할 확장자 (jpg, jpeg, png, webp, gif, bmp, tiff) | 미지정 시 대화형으로 질문 |
| `--dpi` | 렌더링 해상도. 높을수록 선명하지만 용량이 커짐 | 200 |
| `--quality` | JPEG/WEBP 저장 품질 (1-100) | 95 |
| `--input` | 입력 폴더 경로 | `input` |
| `--output` | 출력 폴더 경로 | `output` |

## 출력 예시

`보고서.pdf` (3페이지)를 jpg로 변환하면 `output` 폴더에 다음과 같이 저장됩니다:

```
output/
  보고서-001.jpg
  보고서-002.jpg
  보고서-003.jpg
```
