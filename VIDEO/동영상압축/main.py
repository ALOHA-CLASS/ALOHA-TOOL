import os
import subprocess
from pathlib import Path

def compress_video(input_path, output_path):
    """
    동영상을 최대한 압축하여 저장합니다.
    H.265 (HEVC) 코덱과 낮은 CRF 값을 사용하여 고압축률을 달성합니다.
    """
    # CRF 값: 낮을수록 품질이 좋지만, 높을수록 압축률이 높음 (28-35 권장)
    # preset: slower/veryslow일수록 압축률이 높음
    
    ffmpeg_command = [
        'ffmpeg',
        '-i', str(input_path),
        '-c:v', 'libx265',           # H.265/HEVC 코덱 (H.264보다 약 50% 더 압축)
        '-crf', '32',                 # 높은 압축률 (28-35 범위, 32는 고압축)
        '-preset', 'veryslow',        # 최대 압축률을 위한 느린 인코딩
        '-c:a', 'aac',                # 오디오 코덱
        '-b:a', '64k',                # 오디오 비트레이트 낮춤
        '-ac', '1',                   # 모노 오디오 (스테레오보다 용량 절약)
        '-movflags', '+faststart',    # 스트리밍 최적화
        '-tag:v', 'hvc1',             # 호환성을 위한 태그
        '-y',                         # 덮어쓰기
        str(output_path)
    ]
    
    try:
        print(f"압축 중: {input_path.name}")
        result = subprocess.run(
            ffmpeg_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )
        
        if result.returncode == 0:
            # 파일 크기 비교
            original_size = input_path.stat().st_size
            compressed_size = output_path.stat().st_size
            ratio = (1 - compressed_size / original_size) * 100
            
            print(f"✓ 완료: {input_path.name}")
            print(f"  원본: {original_size / (1024*1024):.2f} MB")
            print(f"  압축: {compressed_size / (1024*1024):.2f} MB")
            print(f"  압축률: {ratio:.1f}%\n")
            return True
        else:
            print(f"✗ 실패: {input_path.name}")
            print(f"  오류: {result.stderr}\n")
            return False
            
    except Exception as e:
        print(f"✗ 예외 발생: {input_path.name}")
        print(f"  {str(e)}\n")
        return False

def main():
    # 경로 설정
    input_dir = Path('input')
    output_dir = Path('output')
    
    # output 디렉토리 생성
    output_dir.mkdir(exist_ok=True)
    
    # 지원하는 동영상 확장자
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.mpeg', '.mpg'}
    
    # input 디렉토리의 동영상 파일 찾기
    video_files = [
        f for f in input_dir.iterdir() 
        if f.is_file() and f.suffix.lower() in video_extensions
    ]
    
    if not video_files:
        print("input 폴더에 동영상 파일이 없습니다.")
        print(f"지원 형식: {', '.join(video_extensions)}")
        return
    
    print(f"총 {len(video_files)}개의 동영상 파일을 발견했습니다.\n")
    print("=" * 60)
    
    # 각 동영상 압축
    success_count = 0
    for video_file in video_files:
        # 출력 파일명 (확장자는 .mp4로 통일)
        output_file = output_dir / f"{video_file.stem}_compressed.mp4"
        
        if compress_video(video_file, output_file):
            success_count += 1
    
    print("=" * 60)
    print(f"\n완료: {success_count}/{len(video_files)}개 파일 압축 성공")

if __name__ == "__main__":
    # ffmpeg 설치 확인
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("오류: ffmpeg가 설치되어 있지 않습니다.")
        print("\n설치 방법:")
        print("1. https://ffmpeg.org/download.html 에서 다운로드")
        print("2. 또는 Chocolatey 사용: choco install ffmpeg")
        print("3. 또는 Scoop 사용: scoop install ffmpeg")
        exit(1)
    
    main()
