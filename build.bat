@echo off
REM NX QR Chip Carrier Manager — PyInstaller 빌드 래퍼 (Phase 8)
REM
REM 사용법:
REM   1) 가상환경 활성화 (선택): call .venv\Scripts\activate.bat
REM   2) 의존성 설치: pip install -r requirements.txt -r requirements-dev.txt
REM   3) 이 스크립트 실행: build.bat
REM
REM 산출물:
REM   dist\NxQrManager\NxQrManager.exe
REM   dist\NxQrManager\third_party\tesseract\tesseract.exe
REM   (Inno Setup 인스톨러는 별도: iscc installer.iss)

setlocal EnableDelayedExpansion

REM 스크립트 위치로 이동 (프로젝트 루트)
pushd "%~dp0"

echo.
echo ========================================
echo   NX QR Chip Carrier Manager — Build
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

REM 3) PyInstaller 호출
echo [2/4] Running PyInstaller ^(onedir mode^) ...
python -m PyInstaller --noconfirm --clean NxQrManager.spec
if errorlevel 1 (
    echo.
    echo   [ERROR] PyInstaller build failed. See build log above.
    popd
    exit /b 1
)

REM 4) 산출물 검증
echo.
echo [3/4] Verifying artifacts ...
if not exist "dist\NxQrManager\NxQrManager.exe" (
    echo   [ERROR] dist\NxQrManager\NxQrManager.exe not produced.
    popd
    exit /b 1
)

if exist "dist\NxQrManager\third_party\tesseract\tesseract.exe" (
    echo   [OK] Tesseract bundled.
) else (
    echo   [WARN] Tesseract NOT in bundle ^(OCR will silently fall back^).
)

echo.
echo [4/4] Build artifacts:
dir /b "dist\NxQrManager" 2>nul | findstr /v /c:".pyc"

echo.
echo ========================================
echo   Build SUCCESS
echo   Run: dist\NxQrManager\NxQrManager.exe
echo   Installer next: iscc installer.iss
echo ========================================
echo.

popd
endlocal
