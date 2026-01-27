# -*- mode: python ; coding: utf-8 -*-
"""
GOE 메신저 도우미 PyInstaller Spec File

빌드 명령어:
    pyinstaller goe_messenger.spec

출력:
    dist/GOE메신저도우미.exe (Windows)
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# 프로젝트 루트 경로
PROJECT_ROOT = os.path.abspath(os.path.dirname(SPECPATH))

# 아이콘 파일 경로 (있으면 사용)
ICON_PATH = os.path.join(PROJECT_ROOT, 'assets', 'icon.ico')
if not os.path.exists(ICON_PATH):
    ICON_PATH = None

# ============================================================
# Analysis 설정
# ============================================================

# Hidden imports: 런타임에 동적으로 임포트되는 모듈들
hidden_imports = [
    # GUI 관련
    'tkinter',
    'tkinter.ttk',
    'tkinter.messagebox',
    'tkinter.filedialog',
    'tkinter.scrolledtext',
    'ttkbootstrap',
    'ttkbootstrap.constants',
    'ttkbootstrap.style',
    'ttkbootstrap.widgets',
    'ttkbootstrap.tooltip',
    'ttkbootstrap.scrolled',
    'ttkbootstrap.tableview',

    # Google API 관련
    'google.oauth2.credentials',
    'google.oauth2.service_account',
    'google.auth.transport.requests',
    'googleapiclient.discovery',
    'googleapiclient.errors',
    'googleapiclient.http',

    # Windows 자동화 관련 (pywinauto)
    'pywinauto',
    'pywinauto.application',
    'pywinauto.findwindows',
    'pywinauto.controls',
    'pywinauto.controls.uiawrapper',
    'pywinauto.controls.win32_controls',
    'pywinauto.keyboard',
    'pywinauto.mouse',
    'pywinauto.timings',
    'pywinauto.backend',
    'pywinauto.win32_hooks',
    'comtypes',
    'comtypes.client',

    # 스크린샷/이미지 관련
    'pyautogui',
    'pyscreeze',
    'PIL',
    'PIL.Image',
    'PIL.ImageGrab',
    'PIL.ImageTk',

    # 데이터 처리
    'yaml',
    'json',
    'sqlite3',

    # 문자열 유사도 (선택적)
    'rapidfuzz',
    'rapidfuzz.fuzz',
    'rapidfuzz.process',

    # 기타 표준 라이브러리
    'datetime',
    'logging',
    'argparse',
    'subprocess',
    're',
    'pathlib',
    'dataclasses',
    'typing',
    'uuid',
    'hashlib',

    # 프로젝트 내부 모듈
    'src',
    'src.main',
    'src.config',
    'src.database',
    'src.models',
    'src.messenger',
    'src.extractor',
    'src.saver',
    'src.importance',
    'src.grouping',
    'src.calendar_sync',
    'src.ai_chat',
    'src.utils',
    'src.gui_dashboard',
    'src.settings_dialog',
    'mcp',
    'mcp.server',
    'mcp.tools',
]

# 데이터 파일 수집
datas = [
    # data 폴더의 설정/데이터 파일들
    (os.path.join(PROJECT_ROOT, 'data', 'keywords.yaml'), 'data'),
    (os.path.join(PROJECT_ROOT, 'data', 'messages.json'), 'data'),
    (os.path.join(PROJECT_ROOT, 'data', 'status.json'), 'data'),

    # assets 폴더 전체
    (os.path.join(PROJECT_ROOT, 'assets'), 'assets'),

    # 설정 파일 (있는 경우)
    # (os.path.join(PROJECT_ROOT, 'config.yaml'), '.'),
]

# 존재하는 파일만 포함
datas = [(src, dst) for src, dst in datas if os.path.exists(src)]

# ttkbootstrap 테마 데이터 수집
try:
    datas += collect_data_files('ttkbootstrap')
except Exception:
    pass

# ============================================================
# Analysis 객체 생성
# ============================================================

a = Analysis(
    # 엔트리포인트
    [os.path.join(PROJECT_ROOT, 'src', 'main.py')],

    # 추가 경로
    pathex=[
        PROJECT_ROOT,
        os.path.join(PROJECT_ROOT, 'src'),
        os.path.join(PROJECT_ROOT, 'mcp'),
    ],

    # 바이너리 파일 (dll 등)
    binaries=[],

    # 데이터 파일
    datas=datas,

    # Hidden imports
    hiddenimports=hidden_imports,

    # 훅 경로
    hookspath=[],

    # 훅 설정 파일
    hooksconfig={},

    # 런타임 훅
    runtime_hooks=[],

    # 제외할 모듈
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'notebook',
        'jupyter',
        'IPython',
        'pytest',
        'sphinx',
    ],

    # Windows 특정 설정
    win_no_prefer_redirects=False,
    win_private_assemblies=False,

    # 암호화 키 (None = 암호화 안함)
    cipher=None,

    # 시스템 경로 사용 안함
    noarchive=False,
)

# ============================================================
# PYZ 아카이브 (Python 모듈 압축)
# ============================================================

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=None,
)

# ============================================================
# EXE 설정
# ============================================================

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],

    # 실행 파일 이름
    name='GOE메신저도우미',

    # 디버그 모드
    debug=False,

    # 부트로더 무시 신호
    bootloader_ignore_signals=False,

    # 심볼 제거 (배포용)
    strip=False,

    # UPX 압축 사용
    upx=True,

    # UPX 제외 대상 (일부 DLL은 압축하면 문제 발생)
    upx_exclude=[
        'vcruntime140.dll',
        'python3.dll',
        'api-ms-win*.dll',
    ],

    # 런타임 임시 폴더 사용
    runtime_tmpdir=None,

    # 콘솔 창 표시 여부 (False = GUI 모드, 콘솔 없음)
    console=False,

    # 관리자 권한 요청 안함
    disable_windowed_traceback=False,

    # 아이콘
    icon=ICON_PATH,

    # 대상 아키텍처 (None = 자동)
    target_arch=None,

    # codesign 정보 (None = 서명 안함)
    codesign_identity=None,
    entitlements_file=None,

    # 버전 정보 (Windows)
    version=None,  # version_info.txt 파일 경로를 지정할 수 있음
)

# ============================================================
# 빌드 후 작업 안내
# ============================================================
"""
빌드 완료 후:

1. 테스트:
   dist/GOE메신저도우미.exe 실행하여 정상 동작 확인

2. 배포 전 확인사항:
   - Windows Defender 등 백신 프로그램에서 오진 여부 확인
   - 다른 PC에서 실행 테스트 (Visual C++ Runtime 필요할 수 있음)

3. 데이터 폴더:
   - 첫 실행 시 %APPDATA%/GOE메신저도우미 폴더가 생성됩니다
   - 사용자 설정 및 데이터베이스가 해당 폴더에 저장됩니다

4. 문제 해결:
   - 실행 안 될 경우: --console 옵션으로 빌드하여 오류 메시지 확인
   - DLL 오류: Visual C++ Redistributable 설치 필요

5. 용량 줄이기:
   - UPX 압축이 적용되어 있음
   - 추가 용량 감소 필요시 excludes 목록에 불필요한 모듈 추가
"""
