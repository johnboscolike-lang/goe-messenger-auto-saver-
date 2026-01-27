# GOE Messenger Auto Saver - Icon 생성 가이드

이 문서는 Windows 실행 파일(.exe)용 아이콘을 생성하는 방법을 설명합니다.

---

## 1. 권장 아이콘 크기

Windows .ico 파일은 여러 크기의 이미지를 포함해야 합니다:

| 크기 | 용도 |
|------|------|
| 16x16 | 작은 아이콘 (파일 탐색기 목록 보기) |
| 32x32 | 표준 아이콘 (바탕화면, 탐색기) |
| 48x48 | 큰 아이콘 (탐색기 타일 보기) |
| 256x256 | 초고해상도 (Vista 이상, 큰 아이콘 보기) |

**권장**: 모든 크기를 포함하는 것이 좋습니다.

---

## 2. 아이콘 생성 방법

### 방법 1: Python Pillow 사용 (권장)

프로젝트 루트의 `create_icon.py` 스크립트를 사용하세요:

```bash
# Pillow 설치
pip install Pillow

# 아이콘 생성
python create_icon.py
```

이 스크립트는 기본 플레이스홀더 아이콘을 생성합니다.

### 방법 2: 온라인 변환기 사용

PNG 이미지가 있다면 다음 무료 온라인 도구를 사용할 수 있습니다:

1. **ICO Convert** - https://icoconvert.com/
   - PNG 업로드 후 여러 크기 선택 가능

2. **ConvertICO** - https://convertico.com/
   - 간단한 드래그 앤 드롭 인터페이스

3. **Favicon.io** - https://favicon.io/favicon-converter/
   - 고품질 변환 지원

### 방법 3: 그래픽 소프트웨어 사용

- **GIMP** (무료): 파일 > 내보내기 > .ico 형식 선택
- **Photoshop**: ICO 플러그인 필요 또는 온라인 변환
- **IcoFX** (무료 버전 있음): 전문 아이콘 편집기

---

## 3. 플레이스홀더 아이콘 생성

현재 아이콘이 없다면 다음 단계를 따르세요:

### 자동 생성 (권장)

```bash
cd /Users/joseong-eun/Documents/goe-messenger-auto-saver
python create_icon.py
```

### 수동 생성

1. 256x256 PNG 이미지를 준비합니다
2. 로고 또는 "GOE" 텍스트를 포함시킵니다
3. 위의 온라인 변환기를 사용하여 .ico로 변환합니다
4. `assets/icon.ico`로 저장합니다

---

## 4. PyInstaller에서 아이콘 사용

### spec 파일 설정

```python
# gmas.spec
exe = EXE(
    pyz,
    a.scripts,
    # ...
    icon='assets/icon.ico',  # 아이콘 경로
    # ...
)
```

### 명령줄 옵션

```bash
pyinstaller --onefile --windowed --icon=assets/icon.ico src/main.py
```

---

## 5. 아이콘 디자인 권장사항

### 디자인 가이드

- **간단하게**: 작은 크기에서도 식별 가능해야 합니다
- **고대비**: 배경과 구분되는 색상 사용
- **일관성**: Windows 아이콘 스타일 가이드 준수

### GOE 메신저 아이콘 컨셉

- 편지 봉투 + 경기도 로고 조합
- 파란색 계열 (경기교육 컬러)
- 깔끔한 플랫 디자인

---

## 6. 파일 위치

아이콘 파일은 다음 위치에 저장하세요:

```
goe-messenger-auto-saver/
└── assets/
    └── icon.ico    # <-- 여기에 저장
```

---

## 참고 자료

- [Microsoft Icon Guidelines](https://docs.microsoft.com/en-us/windows/win32/uxguide/vis-icons)
- [Pillow ICO Documentation](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#ico)
- [PyInstaller Icon Options](https://pyinstaller.org/en/stable/usage.html#options)

---

*최종 수정: 2025-01-27*
