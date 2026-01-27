# Windows 배포 가이드

## 📦 배포 방식 비교

| 방식 | 장점 | 단점 | 추천 |
|------|------|------|------|
| **PyInstaller** | 간단, 단일 exe | 용량 큼 (50-100MB) | ✅ 추천 |
| **Nuitka** | 빠름, 작은 용량 | 컴파일 오래 걸림 | 성능 중요시 |
| **MSIX** | Windows Store 배포 | 복잡한 설정 | 공식 배포시 |
| **Inno Setup** | 설치 마법사 | 추가 도구 필요 | 전문적 배포 |

---

## 🚀 방법 1: PyInstaller (추천)

### 1-1. 설치
```bash
pip install pyinstaller
```

### 1-2. 단일 exe 생성
```bash
# 기본 명령어
pyinstaller --onefile --windowed --name "GOE메신저도우미" src/gui_dashboard.py

# 아이콘 추가시
pyinstaller --onefile --windowed --icon=assets/icon.ico --name "GOE메신저도우미" src/gui_dashboard.py
```

### 1-3. 옵션 설명
```
--onefile     : 단일 exe 파일로 생성
--windowed    : 콘솔 창 숨김 (GUI 앱)
--icon        : 프로그램 아이콘
--name        : exe 파일명
--add-data    : 추가 파일 포함
```

### 1-4. spec 파일 사용 (고급)
```python
# goe_messenger.spec
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/gui_dashboard.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config.yaml', '.'),           # 설정 파일
        ('assets/*', 'assets'),         # 이미지/아이콘
        ('credentials.json', '.'),      # Google API (주의!)
    ],
    hiddenimports=[
        'tkinter',
        'google.oauth2.credentials',
        'googleapiclient.discovery',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GOE메신저도우미',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,              # UPX 압축 (용량 감소)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,         # 콘솔 숨김
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico'
)
```

```bash
# spec 파일로 빌드
pyinstaller goe_messenger.spec
```

### 1-5. 결과물
```
dist/
└── GOE메신저도우미.exe    # 이 파일만 배포!
```

---

## 🛠️ 방법 2: 설치 프로그램 만들기 (Inno Setup)

### 2-1. Inno Setup 다운로드
https://jrsoftware.org/isinfo.php

### 2-2. 스크립트 예시 (setup.iss)
```iss
[Setup]
AppName=GOE 메신저 도우미
AppVersion=1.0.0
DefaultDirName={autopf}\GOE메신저도우미
DefaultGroupName=GOE 메신저 도우미
OutputBaseFilename=GOE메신저도우미_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "dist\GOE메신저도우미.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "config.yaml"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\GOE 메신저 도우미"; Filename: "{app}\GOE메신저도우미.exe"
Name: "{commondesktop}\GOE 메신저 도우미"; Filename: "{app}\GOE메신저도우미.exe"

[Run]
Filename: "{app}\GOE메신저도우미.exe"; Description: "프로그램 실행"; Flags: postinstall nowait
```

---

## 📁 배포 폴더 구조

### 간단 배포 (zip)
```
GOE메신저도우미_v1.0/
├── GOE메신저도우미.exe     # 실행 파일
├── config.yaml            # 설정 파일 (사용자 수정)
├── README.txt             # 사용 설명서
└── 첨부파일/               # 저장 폴더 (빈 폴더)
```

### 설치 프로그램 배포
```
GOE메신저도우미_Setup.exe   # 더블클릭으로 설치
```

---

## ⚠️ 배포 시 주의사항

### 1. Google API 인증 처리
```python
# credentials.json은 배포하지 않음!
# 대신 사용자가 직접 생성하도록 안내

# 또는 OAuth 앱 등록 후 client_id만 포함
GOOGLE_CLIENT_ID = "your-client-id.apps.googleusercontent.com"
```

### 2. 설정 파일 경로
```python
import os
import sys

def get_config_path():
    """exe 실행 시와 개발 시 경로 분기"""
    if getattr(sys, 'frozen', False):
        # PyInstaller로 패키징된 경우
        base_path = os.path.dirname(sys.executable)
    else:
        # 개발 환경
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    return os.path.join(base_path, 'config.yaml')
```

### 3. 첫 실행 시 설정 마법사
```python
def first_run_setup():
    """첫 실행 시 설정 안내"""
    config_path = get_config_path()
    
    if not os.path.exists(config_path):
        # 기본 설정 파일 생성
        default_config = {
            'messenger_path': r'C:\Program Files (x86)\AtMessenger7',
            'save_path': os.path.expanduser('~/Documents/GOE메신저'),
            'google_calendar': {
                'enabled': False,
                'calendar_id': 'primary'
            }
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, allow_unicode=True)
        
        # 설정 안내 다이얼로그 표시
        show_setup_dialog()
```

### 4. 자동 업데이트 (선택)
```python
import requests

def check_update():
    """GitHub Release에서 최신 버전 확인"""
    try:
        response = requests.get(
            'https://api.github.com/repos/your/repo/releases/latest',
            timeout=5
        )
        latest = response.json()['tag_name']
        
        if latest > CURRENT_VERSION:
            return latest, latest['assets'][0]['browser_download_url']
    except:
        pass
    
    return None, None
```

---

## 🔧 빌드 자동화 스크립트

### build.bat (Windows)
```batch
@echo off
echo === GOE 메신저 도우미 빌드 ===

:: 가상환경 활성화
call venv\Scripts\activate

:: 의존성 설치
pip install -r requirements.txt
pip install pyinstaller

:: 기존 빌드 삭제
rmdir /s /q build dist

:: PyInstaller 빌드
pyinstaller --onefile --windowed --icon=assets/icon.ico --name "GOE메신저도우미" src/gui_dashboard.py

:: 설정 파일 복사
copy config.yaml dist\
copy README.md dist\

:: 완료
echo.
echo === 빌드 완료! ===
echo 결과물: dist\GOE메신저도우미.exe
pause
```

### build.py (Python)
```python
import subprocess
import shutil
import os

def build():
    # 정리
    for folder in ['build', 'dist']:
        if os.path.exists(folder):
            shutil.rmtree(folder)
    
    # PyInstaller 실행
    subprocess.run([
        'pyinstaller',
        '--onefile',
        '--windowed',
        '--icon=assets/icon.ico',
        '--name=GOE메신저도우미',
        'src/gui_dashboard.py'
    ])
    
    # 추가 파일 복사
    shutil.copy('config.yaml', 'dist/')
    shutil.copy('README.md', 'dist/')
    
    print("✅ 빌드 완료: dist/GOE메신저도우미.exe")

if __name__ == '__main__':
    build()
```

---

## 📋 배포 체크리스트

- [ ] 버전 번호 업데이트
- [ ] README 작성
- [ ] config.yaml 기본값 설정
- [ ] 테스트 PC에서 실행 확인
- [ ] Windows Defender 검사 통과 확인
- [ ] 설치/실행 권한 확인
- [ ] Google API 인증 흐름 테스트
- [ ] 압축 파일 또는 설치 프로그램 생성

---

## 🎯 추천 배포 순서

1. **개발 완료** → 기능 테스트
2. **PyInstaller 빌드** → `dist/GOE메신저도우미.exe`
3. **다른 PC에서 테스트** → 의존성 누락 확인
4. **zip 배포** (초기)
   ```
   GOE메신저도우미_v1.0.zip
   ├── GOE메신저도우미.exe
   ├── config.yaml
   └── README.txt
   ```
5. **Inno Setup** (정식 배포 시) → 설치 프로그램

---

## 💡 팁

### 용량 줄이기
```bash
# UPX 압축 사용
pip install pyinstaller[encryption]
pyinstaller --onefile --upx-dir=/path/to/upx ...
```

### 바이러스 오탐 방지
- 코드 서명 인증서 구매 (유료)
- 또는 VirusTotal에 제출하여 화이트리스트 등록

### 포터블 버전
- 설정을 exe와 같은 폴더에 저장
- 레지스트리 사용 안 함
- USB에서 바로 실행 가능
