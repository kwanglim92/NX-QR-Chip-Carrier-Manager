@echo off
chcp 65001 >nul
REM MC QR Code Chip Carrier Manager — PyInstaller 빌드 래퍼
REM
REM 사용법:
REM   1) 가상환경 활성화 (선택): call .venv\Scripts\activate.bat
REM   2) 의존성 설치: pip install -r requirements.txt -r requirements-dev.txt
REM   3) 이 스크립트 실행: build.bat
REM
REM 산출물:
REM   dist\McQrManager\McQrManager.exe
REM   dist\McQrManager\third_party\tesseract\tesseract.exe
REM   (Inno Setup 인스톨러는 별도: iscc installer.iss)
REM
REM 실행 주의:
REM   OK:       dist\McQrManager\McQrManager.exe
REM   DO NOT:   build\McQrManager\McQrManager.exe
REM             build\ 는 PyInstaller 중간 작업 폴더라 python311.dll 등
REM             런타임 DLL 이 없어 직접 실행하면 LoadLibrary 오류가 납니다.

setlocal EnableDelayedExpansion

REM 스크립트 위치로 이동 (프로젝트 루트)
pushd "%~dp0"

echo.
echo ========================================
echo   MC QR Code Chip Carrier Manager — Build
echo ========================================
echo.

REM 1) 이전 산출물 정리
if exist build (
    echo [1/4] Cleaning build/ ...
    rmdir /s /q build
)
if exist dist (
    echo [1/4] Cleaning dist/ ...
    rmdir /s /q dist
)

REM 2) Tesseract 번들 존재 확인
if not exist "third_party\tesseract\tesseract.exe" (
    echo.
    echo   [WARNING] third_party\tesseract\tesseract.exe 가 없습니다.
    echo             배포판에서 OCR 기능이 동작하지 않습니다.
    echo             Tesseract 바이너리를 third_party\tesseract\ 에 배치한 뒤 재빌드하세요.
    echo.
)

REM 2.5) 환경 정보 덤프 (진단용)
echo ----------------------------------------
echo  Environment
echo ----------------------------------------
echo  CWD: %CD%
where python
python --version
python -m PyInstaller --version
echo ----------------------------------------
echo.

REM 3) PyInstaller 호출 (콘솔 + build_log.txt 동시 저장)
echo [2/4] Running PyInstaller ^(onedir mode^) ... ^(log: build_log.txt^)
python -m PyInstaller --noconfirm --clean --log-level=INFO McQrManager.spec > build_log.txt 2>&1
set "PI_RC=!errorlevel!"
type build_log.txt
if not "!PI_RC!"=="0" (
    echo.
    echo   [ERROR] PyInstaller build failed ^(exit code !PI_RC!^).
    echo           Full log saved to: %CD%\build_log.txt
    echo.
    if not defined NO_PAUSE pause
    popd
    exit /b 1
)

REM 4) 산출물 검증
echo.
echo [3/4] Verifying artifacts ...
if not exist "dist\McQrManager\McQrManager.exe" (
    echo   [ERROR] dist\McQrManager\McQrManager.exe not produced.
    echo           Check build_log.txt for details.
    echo.
    if not defined NO_PAUSE pause
    popd
    exit /b 1
)

if exist "dist\McQrManager\python311.dll" (
    echo   [OK] Python runtime bundled.
) else (
    echo   [ERROR] dist\McQrManager\python311.dll not found.
    echo           Do not run build\McQrManager\McQrManager.exe.
    echo           Check build_log.txt and PyInstaller collection output.
    echo.
    if not defined NO_PAUSE pause
    popd
    exit /b 1
)

if exist "dist\McQrManager\third_party\tesseract\tesseract.exe" (
    echo   [OK] Tesseract bundled.
) else (
    echo   [WARN] Tesseract NOT in bundle ^(OCR will silently fall back^).
)

if exist "dist\McQrManager\docs\user-guide.html" (
    echo   [OK] User guide bundled.
) else (
    echo   [ERROR] dist\McQrManager\docs\user-guide.html not found.
    echo           Check McQrManager.spec datas for docs\user-guide.html.
    echo.
    if not defined NO_PAUSE pause
    popd
    exit /b 1
)

if exist "build\McQrManager\McQrManager.exe" (
    > "build\McQrManager\DO_NOT_RUN.txt" echo This is a PyInstaller intermediate build folder.
    >> "build\McQrManager\DO_NOT_RUN.txt" echo Do NOT run build\McQrManager\McQrManager.exe.
    >> "build\McQrManager\DO_NOT_RUN.txt" echo Run dist\McQrManager\McQrManager.exe instead.
)

echo.
echo [4/4] Build artifacts:
dir /b "dist\McQrManager" 2>nul | findstr /v /c:".pyc"

echo.
echo ========================================
echo   Build SUCCESS
echo   RUN ONLY:      dist\McQrManager\McQrManager.exe
echo   DO NOT RUN:    build\McQrManager\McQrManager.exe
echo                  ^(intermediate folder; missing runtime DLLs^)
echo   Installer next: iscc installer.iss
echo ========================================
echo.

if not defined NO_PAUSE pause
popd
endlocal
