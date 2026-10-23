from PIL import Image
import os
from pathlib import Path

def compress_image(input_path, output_path, quality=60, max_width=1920):
    """
    이미지를 압축합니다.
    
    Args:
        input_path: 입력 이미지 경로
        output_path: 출력 이미지 경로
        quality: JPEG 품질 (1-100, 낮을수록 용량 작음)
        max_width: 최대 너비 (이보다 크면 리사이즈)
    """
    try:
        # 이미지 열기
        img = Image.open(input_path)
        
        # EXIF 회전 정보 처리
        try:
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img)
        except:
            pass
        
        # 원본 크기
        original_size = os.path.getsize(input_path)
        width, height = img.size
        
        # 너비가 max_width보다 크면 리사이즈
        if width > max_width:
            ratio = max_width / width
            new_width = max_width
            new_height = int(height * ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            print(f"  리사이즈: {width}x{height} → {new_width}x{new_height}")
        
        # RGB로 변환 (JPEG는 RGBA 지원 안함)
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 압축하여 저장
        img.save(output_path, 'JPEG', quality=quality, optimize=True)
        
        # 결과 출력
        compressed_size = os.path.getsize(output_path)
        reduction = (1 - compressed_size / original_size) * 100
        
        print(f"  원본: {original_size / 1024:.1f}KB → 압축: {compressed_size / 1024:.1f}KB")
        print(f"  압축률: {reduction:.1f}% 감소")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 오류: {e}")
        return False

def compress_images_in_folder(input_folder='input', output_folder='output', 
                               quality=60, max_width=1920):
    """
    폴더 내 모든 이미지를 압축합니다.
    
    Args:
        input_folder: 입력 폴더 경로
        output_folder: 출력 폴더 경로
        quality: JPEG 품질 (1-100)
        max_width: 최대 너비
    """
    # 출력 폴더 생성
    Path(output_folder).mkdir(exist_ok=True)
    
    # 지원하는 이미지 확장자
    supported_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff', '.tif'}
    
    # 입력 폴더의 모든 파일 처리
    input_path = Path(input_folder)
    
    if not input_path.exists():
        print(f"❌ '{input_folder}' 폴더가 존재하지 않습니다.")
        return
    
    image_files = [f for f in input_path.iterdir() 
                   if f.is_file() and f.suffix.lower() in supported_extensions]
    
    if not image_files:
        print(f"'{input_folder}' 폴더에 이미지 파일이 없습니다.")
        return
    
    print(f"\n{'='*60}")
    print(f"이미지 압축 시작 (품질: {quality}, 최대 너비: {max_width}px)")
    print(f"{'='*60}\n")
    
    success_count = 0
    total_original_size = 0
    total_compressed_size = 0
    
    for idx, image_file in enumerate(image_files, 1):
        print(f"[{idx}/{len(image_files)}] {image_file.name}")
        
        # 출력 파일명 (확장자를 .jpg로 변경)
        output_file = Path(output_folder) / f"{image_file.stem}.jpg"
        
        original_size = os.path.getsize(image_file)
        
        if compress_image(str(image_file), str(output_file), quality, max_width):
            success_count += 1
            compressed_size = os.path.getsize(output_file)
            total_original_size += original_size
            total_compressed_size += compressed_size
        
        print()
    
    # 전체 결과 출력
    print(f"{'='*60}")
    print(f"압축 완료: {success_count}/{len(image_files)}개 성공")
    
    if total_original_size > 0:
        total_reduction = (1 - total_compressed_size / total_original_size) * 100
        print(f"전체 원본: {total_original_size / 1024 / 1024:.2f}MB")
        print(f"전체 압축: {total_compressed_size / 1024 / 1024:.2f}MB")
        print(f"전체 압축률: {total_reduction:.1f}% 감소")
    
    print(f"{'='*60}\n")

if __name__ == '__main__':
    # 설정값 (필요에 따라 조정)
    QUALITY = 25        # 품질: 낮을수록 용량 작음 (권장: 50-70)
    MAX_WIDTH = 1920    # 최대 너비: 이보다 크면 리사이즈 (권장: 1920)
    
    compress_images_in_folder(
        input_folder='input',
        output_folder='output',
        quality=QUALITY,
        max_width=MAX_WIDTH
    )
