# JFIF 이미지 변환

`input` 폴더의 JFIF 이미지를 원하는 형식으로 변환하여 `output` 폴더에 저장합니다. 확장자가 `.jfif`인 JPEG 이미지만 처리합니다.

## 설치

```powershell
pip install -r requirements.txt
```

## 사용법

1. JFIF 파일을 `input` 폴더에 넣습니다. 다른 파일과 하위 폴더는 무시합니다.
2. 이 폴더에서 `python main.py`를 실행합니다.
3. 출력 파일명(확장자 제외)과 출력 확장자를 입력합니다. 확장자를 비워두면 `jpg`를 사용합니다.

명령줄에서도 실행할 수 있습니다:

```powershell
python main.py photo
python main.py photo --to png
python main.py photo --to webp
```

지원 확장자는 `jpg`, `jpeg`, `png`, `gif`, `webp`, `bmp`, `tif`, `tiff`입니다. 대소문자와 앞의 점(`.png`)도 허용합니다.

파일이 한 개라면 `photo.jpg`, 여러 개라면 입력 파일명을 정렬한 순서대로 `photo_1.jpg`, `photo_2.jpg`처럼 저장합니다. 결과에는 원본과 출력 파일명의 대응 관계가 표시됩니다. 기존 파일은 덮어쓰지 않으며, 실패한 파일이 있어도 나머지 파일을 계속 변환합니다. 하나라도 실패하면 종료 코드는 1입니다.

EXIF 방향 정보는 이미지에 적용되며 출력은 RGB로 저장됩니다. GIF는 색상 표현에 제한이 있습니다.
