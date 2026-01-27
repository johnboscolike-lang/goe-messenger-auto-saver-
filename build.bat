@echo off
setlocal enabledelayedexpansion
chcp 65001 > nul

:: ============================================================
:: GOE 메신저 도우미 - 빌드 스크립트
:: ============================================================
:: 사용법:
::   build.bat          - 일반 빌드 (spec 파일 사용)
::   build.bat debug    - 디버그 빌드 (콘솔 포함)
::   build.bat clean    - 빌드 폴더 정리
::   build.bat package  - 빌드 후 배포용 zip 생성
:: ============================================================

:: 버전 정보 (src/__init__.py 에서 가져옴)
set VERSION=1.0.0
set APP_NAME=GOE메신저도우미
set SPEC_FILE=goe_messenger.spec

:: 빌드 모드 확인
set BUILD_MODE=%1
if "%BUILD_MODE%"=="" set BUILD_MODE=normal

echo.
echo ========================================
echo  %APP_NAME% v%VERSION% - 빌드 스크립트
echo ========================================
echo  빌드 모드: %BUILD_MODE%
echo ========================================
echo.

:: ============================================================
:: clean 모드 처리
:: ============================================================
if "%BUILD_MODE%"=="clean" (
    echo [정리] 빌드 폴더 삭제 중...
    if exist "build" (
        rmdir /s /q build
        echo   - build 폴더 삭제됨
    )
    if exist "dist" (
        rmdir /s /q dist
        echo   - dist 폴더 삭제됨
    )
    if exist "__pycache__" (
        rmdir /s /q __pycache__
        echo   - __pycache__ 폴더 삭제됨
    )
    for /d /r %%d in (__pycache__) do (
        if exist "%%d" (
            rmdir /s /q "%%d"
        )
    )
    echo.
    echo [완료] 정리가 완료되었습니다.
    echo.
    goto :end
)

:: ============================================================
:: Python 환경 확인
:: ============================================================
echo [1/6] Python 환경 확인 중...

python --version > nul 2>&1
if errorlevel 1 (
    echo.
    echo [오류] Python이 설치되지 않았습니다.
    echo        https://www.python.org 에서 Python을 설치해주세요.
    echo.
    goto :error
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VER=%%i
echo   - Python %PYTHON_VER% 발견

:: ============================================================
:: 가상환경 확인/생성 및 활성화
:: ============================================================
echo [2/6] 가상환경 설정 중...

if not exist "venv" (
    echo   - 가상환경 생성 중...
    python -m venv venv
    if errorlevel 1 (
        echo [오류] 가상환경 생성에 실패했습니다.
        goto :error
    )
    echo   - 가상환경 생성 완료
) else (
    echo   - 기존 가상환경 사용
)

call venv\Scripts\activate
if errorlevel 1 (
    echo [오류] 가상환경 활성화에 실패했습니다.
    goto :error
)
echo   - 가상환경 활성화됨

:: ============================================================
:: 의존성 설치
:: ============================================================
echo [3/6] 의존성 설치 중...

pip install -r requirements.txt -q
if errorlevel 1 (
    echo [오류] 의존성 설치에 실패했습니다.
    goto :error
)
echo   - requirements.txt 설치 완료

pip install pyinstaller -q
if errorlevel 1 (
    echo [오류] PyInstaller 설치에 실패했습니다.
    goto :error
)
echo   - PyInstaller 설치 완료

:: ============================================================
:: 기존 빌드 정리
:: ============================================================
echo [4/6] 기존 빌드 정리 중...

if exist "build" (
    rmdir /s /q build
    echo   - build 폴더 삭제됨
)
if exist "dist" (
    rmdir /s /q dist
    echo   - dist 폴더 삭제됨
)
echo   - 정리 완료

:: ============================================================
:: PyInstaller 빌드
:: ============================================================
echo [5/6] exe 파일 생성 중...

:: 빌드 모드에 따른 옵션 설정
set WINDOWED_OPT=--windowed
set BUILD_NAME=%APP_NAME%

if "%BUILD_MODE%"=="debug" (
    set WINDOWED_OPT=--console
    set BUILD_NAME=%APP_NAME%_Debug
    echo   - 디버그 모드: 콘솔 창 포함
)

:: spec 파일이 있으면 사용, 없으면 직접 빌드
if exist "%SPEC_FILE%" if not "%BUILD_MODE%"=="debug" (
    echo   - spec 파일 사용: %SPEC_FILE%
    pyinstaller %SPEC_FILE% --noconfirm
) else (
    echo   - 직접 빌드 모드
    pyinstaller ^
        --onefile ^
        %WINDOWED_OPT% ^
        --name "%BUILD_NAME%" ^
        --add-data "src;src" ^
        --add-data "data;data" ^
        --add-data "assets;assets" ^
        --hidden-import "tkinter" ^
        --hidden-import "tkinter.ttk" ^
        --hidden-import "tkinter.messagebox" ^
        --hidden-import "tkinter.filedialog" ^
        --hidden-import "tkcalendar" ^
        --hidden-import "PIL" ^
        --hidden-import "PIL.Image" ^
        --hidden-import "PIL.ImageTk" ^
        --noconfirm ^
        src/main.py
)

if errorlevel 1 (
    echo.
    echo [오류] PyInstaller 빌드에 실패했습니다.
    goto :error
)

:: ============================================================
:: 빌드 결과 확인 및 데이터 파일 복사
:: ============================================================
echo [6/6] 빌드 결과 확인 및 데이터 파일 복사 중...

:: exe 파일 확인
if not exist "dist\%BUILD_NAME%.exe" (
    echo [오류] exe 파일이 생성되지 않았습니다.
    goto :error
)
echo   - %BUILD_NAME%.exe 생성 완료

:: 데이터 폴더 복사
if exist "data" (
    if not exist "dist\data" mkdir "dist\data"
    xcopy /s /e /y /q "data\*" "dist\data\" > nul 2>&1
    echo   - data 폴더 복사 완료
)

:: assets 폴더 복사
if exist "assets" (
    if not exist "dist\assets" mkdir "dist\assets"
    xcopy /s /e /y /q "assets\*" "dist\assets\" > nul 2>&1
    echo   - assets 폴더 복사 완료
)

:: config.yaml 복사 (있는 경우)
if exist "config.yaml" (
    copy /y "config.yaml" "dist\config.yaml" > nul 2>&1
    echo   - config.yaml 복사 완료
)

:: README 복사
if exist "README.md" (
    copy /y "README.md" "dist\README.md" > nul 2>&1
    echo   - README.md 복사 완료
)

:: ============================================================
:: package 모드: ZIP 패키지 생성
:: ============================================================
if "%BUILD_MODE%"=="package" (
    echo.
    echo [추가] 배포용 ZIP 패키지 생성 중...

    set ZIP_NAME=%APP_NAME%_v%VERSION%.zip

    :: PowerShell을 사용하여 ZIP 생성
    powershell -Command "Compress-Archive -Path 'dist\*' -DestinationPath 'dist\!ZIP_NAME!' -Force"

    if errorlevel 1 (
        echo [경고] ZIP 생성에 실패했습니다. 수동으로 압축해주세요.
    ) else (
        echo   - !ZIP_NAME! 생성 완료
    )
)

:: ============================================================
:: 빌드 완료
:: ============================================================
echo.
echo ========================================
echo  빌드 완료!
echo ========================================
echo.
echo  버전: v%VERSION%
echo  결과물 위치: dist\%BUILD_NAME%.exe
echo.
if "%BUILD_MODE%"=="package" (
    echo  배포 패키지: dist\%APP_NAME%_v%VERSION%.zip
    echo.
)
echo  dist 폴더 내용:
dir /b dist
echo.
echo ========================================

:: 파일 크기 표시
for %%F in ("dist\%BUILD_NAME%.exe") do (
    set SIZE=%%~zF
    set /a SIZE_MB=!SIZE!/1048576
    echo  exe 크기: !SIZE_MB! MB
)
echo ========================================
echo.
goto :end

:: ============================================================
:: 오류 처리
:: ============================================================
:error
echo.
echo ========================================
echo  [빌드 실패]
echo ========================================
echo.
echo  오류가 발생했습니다.
echo  위의 오류 메시지를 확인해주세요.
echo.
pause
exit /b 1

:: ============================================================
:: 종료
:: ============================================================
:end
pause
endlocal
exit /b 0
