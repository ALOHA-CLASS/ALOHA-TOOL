# AVIF 이미지 변환

`input` 폴더에 있는 모든 AVIF 이미지를 원하는 형식으로 변환하여 `output` 폴더에 저장합니다.

## 설치

```powershell
pip install -r requirements.txt
```

Pillow 11.1.0 이상과 AVIF 지원이 포함된 Pillow 빌드가 필요합니다.

## 사용법

1. AVIF 파일들을 `input` 폴더에 넣습니다. 다른 형식의 파일과 하위 폴더는 무시합니다.
2. 이 폴더에서 `python main.py`를 실행합니다.
3. 출력 파일명(확장자 제외, 예: `photo`)과 출력 확장자를 입력합니다. 확장자를 비워두면 `jpg`를 사용합니다.

파일이 한 개라면 `photo.jpg`, 여러 개라면 입력 파일명을 정렬한 순서대로 `photo_1.jpg`, `photo_2.jpg`처럼 저장합니다. 변환 결과에 원본과 출력 파일명의 대응 관계가 표시됩니다.

명령줄에서도 실행할 수 있습니다:

```powershell
python main.py photo
python main.py photo --to png
python main.py photo --to webp
```

지원 확장자는 `jpg`, `jpeg`, `png`, `gif`, `webp`, `bmp`, `tif`, `tiff`입니다. 대소문자와 앞의 점(`.png`)도 허용합니다. 같은 이름의 결과 파일이 이미 있으면 덮어쓰지 않고 해당 파일의 오류를 표시한 뒤 나머지 파일을 계속 변환합니다. 하나라도 실패하면 종료 코드는 1입니다.

애니메이션 AVIF는 첫 번째 프레임만 변환합니다. JPEG는 투명도를 지원하지 않으므로 투명한 부분은 흰색 배경으로 합성됩니다. GIF는 색상과 투명도 표현에 제한이 있습니다.
