# 이미지 → PDF 병합 프로그램

input 폴더의 이미지 파일들을 파일명 순서대로 한 장씩 PDF 페이지로 만들어
하나의 PDF 파일로 병합하는 프로그램입니다.

## 주요 특징

- **여러 이미지를 한 PDF로 병합**: jpg, png, webp, bmp, tiff, gif 지원
- **순서 보장**: 파일명 오름차순(또는 직접 지정한 순서)으로 페이지 구성
- **투명 배경 처리**: PNG 등 투명 채널이 있는 이미지는 흰색 배경으로 합성
- **EXIF 회전 반영**: 스마트폰 사진의 회전 정보를 올바르게 반영
- **파일명 지정 가능**: 원하는 PDF 파일명으로 저장

## 사전 준비

### 라이브러리 설치

```powershell
pip install -r requirements.txt
```

## 사용 방법

### 1) 대화형 실행

1. `input` 폴더에 병합할 이미지 파일들을 넣습니다 (파일명 순서대로 페이지가 구성됩니다)
2. 프로그램을 실행합니다:

```powershell
python main.py
```

3. 저장할 PDF 파일명을 입력하면 `output` 폴더에 병합된 PDF가 생성됩니다

### 2) 커맨드라인 인자로 실행

```powershell
python main.py --name 제목
python main.py --input "C:\path\to\folder" --output "C:\path\to\out" --name 제목
python main.py img1.jpg img2.png img3.jpg --name 제목   # 지정한 파일만, 입력한 순서대로 병합
```

## 옵션

| 옵션 | 설명 | 기본값 |
| --- | --- | --- |
| `--name` | 저장할 PDF 파일명 (확장자 제외) | 미지정 시 대화형으로 질문 (기본값: `병합`) |
| `--dpi` | PDF 페이지 해상도 DPI | 200 |
| `--input` | 입력 폴더 경로 | `input` |
| `--output` | 출력 폴더 경로 | `output` |

## 출력 예시

`input` 폴더에 `01.jpg`, `02.jpg`, `03.jpg`를 넣고 파일명을 `제목`으로 입력하면:

```
output/
  제목.pdf   (01.jpg -> 1페이지, 02.jpg -> 2페이지, 03.jpg -> 3페이지)
```
