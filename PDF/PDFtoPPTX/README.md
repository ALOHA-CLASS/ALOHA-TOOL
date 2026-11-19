# PDF → PPTX 변환 프로그램

PDF를 PowerPoint(`.pptx`)로 변환합니다. PDF의 모든 페이지를 슬라이드 한 장씩 이미지로 배치해 원본의 모양을 유지하고, PDF에 지정된 외부 웹 링크와 페이지 이동 링크를 클릭 가능한 영역으로 복원합니다.

## 사전 준비

```powershell
pip install -r requirements.txt
```

## 사용 방법

`input` 폴더에 PDF 파일을 넣고 실행하면 폴더 안의 모든 PDF를 변환합니다.

```powershell
python main.py
```

특정 파일, 입력/출력 폴더 또는 렌더링 해상도를 지정할 수도 있습니다.

```powershell
python main.py "input\보고서.pdf"
python main.py --input "C:\문서\PDF" --output "C:\문서\PPTX" --dpi 240
python main.py "C:\문서\보고서.pdf" --output "C:\문서\PPTX" --dpi 300
```

기본 해상도는 180 DPI이며, `--dpi`는 1~1200 사이로 지정할 수 있습니다. 출력 파일은 PDF와 같은 이름의 `.pptx`로 생성됩니다.

## 변환 방식 및 링크

- PDF의 각 페이지를 빠짐없이 개별 슬라이드로 변환합니다.
- 페이지를 이미지로 넣으므로 원본의 글꼴과 배치를 유지하지만, 슬라이드에서 텍스트나 개별 요소를 직접 편집할 수는 없습니다.
- PDF의 웹 URL 링크와 문서 내 페이지 이동 링크를 클릭 가능한 영역으로 복원합니다.
- 그 외 링크 종류(예: 다른 파일을 여는 링크)는 지원하지 않으며 변환 결과에 안내 메시지를 표시합니다.
- PDF에 링크 주석으로 저장되지 않은 시각적 링크는 자동으로 복원할 수 없습니다.
