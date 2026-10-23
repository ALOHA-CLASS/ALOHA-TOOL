# 동영상 압축 프로그램

input 폴더의 동영상 파일들을 최대한 압축하여 output 폴더에 저장하는 프로그램입니다.

## 주요 특징

- **H.265 (HEVC) 코덱**: H.264보다 약 50% 더 높은 압축률
- **CRF 32**: 높은 압축률 설정 (28-35 범위)
- **veryslow preset**: 최대 압축률을 위한 느린 인코딩
- **모노 오디오**: 64kbps로 오디오 용량 최소화
- **다양한 포맷 지원**: mp4, avi, mov, mkv, wmv, flv, webm 등

## 사전 준비

### ffmpeg 설치

Windows에서 ffmpeg 설치:

```powershell
# Chocolatey 사용
choco install ffmpeg

# 또는 Scoop 사용
scoop install ffmpeg

# 또는 수동 설치
# https://ffmpeg.org/download.html 에서 다운로드
```

## 사용 방법

1. `input` 폴더에 압축할 동영상 파일을 넣습니다
2. 프로그램을 실행합니다:

```powershell
python main.py
```

3. 압축된 동영상이 `output` 폴더에 생성됩니다

## 압축 설정 조정

`main.py`의 다음 값들을 조정하여 압축률과 품질의 균형을 맞출 수 있습니다:

- **CRF 값** (현재: 32)
  - 낮을수록 품질 좋음, 파일 크기 큼 (18-24: 고품질)
  - 높을수록 압축률 높음, 품질 낮음 (28-35: 고압축)
  
- **Preset** (현재: veryslow)
  - ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow
  - 느릴수록 압축률 높음 (시간은 더 걸림)

- **오디오 비트레이트** (현재: 64k)
  - 64k: 최소 품질 (모노)
  - 128k: 일반 품질 (스테레오)
  - 192k: 좋은 품질 (스테레오)

## 출력 예시

```
총 2개의 동영상 파일을 발견했습니다.

============================================================
압축 중: sample_video.mp4
✓ 완료: sample_video.mp4
  원본: 150.00 MB
  압축: 45.00 MB
  압축률: 70.0%

압축 중: another_video.mov
✓ 완료: another_video.mov
  원본: 200.00 MB
  압축: 55.00 MB
  압축률: 72.5%

============================================================

완료: 2/2개 파일 압축 성공
```
