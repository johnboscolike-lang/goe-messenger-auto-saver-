#!/usr/bin/env python3
"""
GOE Messenger Auto Saver - Icon Generator

이 스크립트는 Pillow를 사용하여 기본 플레이스홀더 아이콘을 생성합니다.
생성된 아이콘은 assets/icon.ico에 저장됩니다.

사용법:
    python create_icon.py

요구사항:
    pip install Pillow
"""

import os
import sys
from pathlib import Path


def check_pillow():
    """Pillow 설치 여부를 확인합니다."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        return True
    except ImportError:
        return False


def create_icon():
    """플레이스홀더 아이콘을 생성합니다."""
    from PIL import Image, ImageDraw, ImageFont

    # 아이콘 크기 목록 (Windows 표준)
    sizes = [16, 32, 48, 256]

    # 색상 정의
    bg_color = (41, 98, 255)       # 파란색 배경 (경기교육 컬러)
    text_color = (255, 255, 255)   # 흰색 텍스트
    accent_color = (255, 193, 7)   # 노란색 악센트

    images = []

    for size in sizes:
        # 새 이미지 생성 (RGBA for transparency support)
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 둥근 사각형 배경
        padding = max(1, size // 16)
        draw.rounded_rectangle(
            [padding, padding, size - padding - 1, size - padding - 1],
            radius=max(2, size // 8),
            fill=bg_color
        )

        # 편지 봉투 아이콘 그리기
        envelope_margin = size // 4
        envelope_top = size // 3
        envelope_bottom = size - envelope_margin

        # 봉투 본체
        draw.rectangle(
            [envelope_margin, envelope_top, size - envelope_margin, envelope_bottom],
            fill=text_color
        )

        # 봉투 삼각형 (뚜껑)
        center_x = size // 2
        triangle_top = envelope_top - (size // 10)
        draw.polygon(
            [
                (envelope_margin, envelope_top),
                (center_x, triangle_top),
                (size - envelope_margin, envelope_top)
            ],
            fill=text_color
        )

        # 봉투 V 라인 (내부)
        v_top = envelope_top + (size // 16)
        v_bottom = (envelope_top + envelope_bottom) // 2
        line_width = max(1, size // 16)
        draw.line(
            [(envelope_margin + line_width, v_top), (center_x, v_bottom)],
            fill=bg_color,
            width=line_width
        )
        draw.line(
            [(size - envelope_margin - line_width, v_top), (center_x, v_bottom)],
            fill=bg_color,
            width=line_width
        )

        # 작은 알림 점 (새 메시지 표시)
        if size >= 32:
            dot_radius = max(2, size // 10)
            dot_x = size - envelope_margin
            dot_y = envelope_top
            draw.ellipse(
                [dot_x - dot_radius, dot_y - dot_radius,
                 dot_x + dot_radius, dot_y + dot_radius],
                fill=accent_color
            )

        images.append(img)

    return images


def save_icon(images, output_path):
    """이미지들을 ICO 파일로 저장합니다."""
    from PIL import Image

    # 가장 큰 이미지를 기본으로 사용
    main_image = images[-1]  # 256x256

    # ICO 파일로 저장 (모든 크기 포함)
    main_image.save(
        output_path,
        format='ICO',
        sizes=[(img.width, img.height) for img in images]
    )


def create_simple_icon_without_pillow(output_path):
    """
    Pillow 없이 간단한 ICO 파일 구조를 생성합니다.
    이 방법은 기본적인 단색 아이콘만 생성합니다.
    """
    # ICO 파일 헤더
    # 참고: https://en.wikipedia.org/wiki/ICO_(file_format)

    # 16x16 파란색 단색 아이콘을 위한 최소 ICO 파일
    # 이것은 매우 기본적인 플레이스홀더입니다

    print("경고: Pillow 없이는 기본적인 플레이스홀더만 생성됩니다.")
    print("더 나은 아이콘을 위해 'pip install Pillow'를 실행하세요.")

    # 기본 16x16 ICO 바이너리 데이터 (파란색 사각형)
    ico_data = bytes([
        # ICONDIR header
        0x00, 0x00,  # Reserved
        0x01, 0x00,  # Type (1 = ICO)
        0x01, 0x00,  # Number of images

        # ICONDIRENTRY
        0x10,        # Width (16)
        0x10,        # Height (16)
        0x00,        # Color count (0 = 256+)
        0x00,        # Reserved
        0x01, 0x00,  # Color planes
        0x20, 0x00,  # Bits per pixel (32)
        0x68, 0x04, 0x00, 0x00,  # Size of image data
        0x16, 0x00, 0x00, 0x00,  # Offset of image data
    ])

    # BMP header for 16x16 32-bit image
    bmp_header = bytes([
        0x28, 0x00, 0x00, 0x00,  # Header size (40)
        0x10, 0x00, 0x00, 0x00,  # Width (16)
        0x20, 0x00, 0x00, 0x00,  # Height (32, doubled for AND mask)
        0x01, 0x00,              # Color planes (1)
        0x20, 0x00,              # Bits per pixel (32)
        0x00, 0x00, 0x00, 0x00,  # Compression (none)
        0x00, 0x04, 0x00, 0x00,  # Image size
        0x00, 0x00, 0x00, 0x00,  # X pixels per meter
        0x00, 0x00, 0x00, 0x00,  # Y pixels per meter
        0x00, 0x00, 0x00, 0x00,  # Colors used
        0x00, 0x00, 0x00, 0x00,  # Important colors
    ])

    # 16x16 pixel data (BGRA format, bottom-up)
    # 파란색 (경기교육 컬러: RGB 41, 98, 255)
    blue_pixel = bytes([0xFF, 0x62, 0x29, 0xFF])  # BGRA
    pixels = blue_pixel * 16 * 16

    # AND mask (16x16, 1 bit per pixel, all transparent)
    and_mask = bytes([0x00] * 16 * 4)  # 16 rows, 4 bytes per row (32-bit aligned)

    with open(output_path, 'wb') as f:
        f.write(ico_data)
        f.write(bmp_header)
        f.write(pixels)
        f.write(and_mask)

    return True


def main():
    """메인 함수"""
    # 프로젝트 루트 경로
    script_dir = Path(__file__).parent
    assets_dir = script_dir / 'assets'
    output_path = assets_dir / 'icon.ico'

    # assets 디렉토리 확인
    if not assets_dir.exists():
        assets_dir.mkdir(parents=True)
        print(f"디렉토리 생성: {assets_dir}")

    print("=" * 50)
    print("GOE Messenger Auto Saver - Icon Generator")
    print("=" * 50)

    if check_pillow():
        print("\n[OK] Pillow가 설치되어 있습니다.")
        print("아이콘을 생성합니다...\n")

        try:
            images = create_icon()
            save_icon(images, output_path)
            print(f"[SUCCESS] 아이콘 생성 완료!")
            print(f"저장 위치: {output_path}")
            print(f"\n포함된 크기:")
            for img in images:
                print(f"  - {img.width}x{img.height}")
        except Exception as e:
            print(f"[ERROR] 아이콘 생성 실패: {e}")
            sys.exit(1)
    else:
        print("\n[WARNING] Pillow가 설치되어 있지 않습니다.")
        print("기본 플레이스홀더 아이콘을 생성합니다...\n")
        print("더 나은 아이콘을 위해 다음 명령을 실행하세요:")
        print("  pip install Pillow\n")

        try:
            create_simple_icon_without_pillow(output_path)
            print(f"[SUCCESS] 기본 아이콘 생성 완료!")
            print(f"저장 위치: {output_path}")
            print("\n참고: 이것은 매우 기본적인 플레이스홀더입니다.")
            print("Pillow를 설치하면 더 좋은 아이콘을 생성할 수 있습니다.")
        except Exception as e:
            print(f"[ERROR] 아이콘 생성 실패: {e}")
            sys.exit(1)

    print("\n" + "=" * 50)
    print("PyInstaller에서 사용하려면:")
    print(f"  pyinstaller --icon={output_path} your_script.py")
    print("=" * 50)


if __name__ == '__main__':
    main()
