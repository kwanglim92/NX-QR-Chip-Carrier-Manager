# Phase 7 — 설치형 배포 빌드 가능성 분석

> **Status**: 분석 단계. 실제 구현은 별도 작업(Phase 7)으로 분리.
> **기준일**: 2026-04-22 (Phase 6 종료 시점)
> **대상**: NX QR Chip Carrier Manager (PySide6 데스크톱 앱) — 현재는 **MC QR Code Chip Carrier Manager** 로 리브랜드됨 (Phase 9). 아래 "NxQrManager.spec", "dist/NxQrManager/", "%LOCALAPPDATA%/NXQRChipCarrierManager/" 등은 분석 당시의 명칭으로, 현재 이름은 각각 "McQrManager.spec", "dist/McQrManager/", "%LOCALAPPDATA%/MCQRCodeChipCarrier/" 입니다. 이 문서는 **이력 보존용**으로 원문 유지됩니다.
> **최신 기준**: 현재 제품 요구사항, 최신 기능, 테스트 현황은 [`docs/PRD.md`](./PRD.md) 를 기준으로 확인합니다.

---

## 1. 현재 상태 요약

### 1.1 코드 측면에서 **이미 배포 대비가 된 부분**

| 항목 | 위치 | 대비 상태 |
|------|------|-----------|
| PyInstaller 경로 분기 | `src/core/tesseract_setup.py:_project_root()` | ✅ `getattr(sys, "frozen", False)` 체크로 `sys.executable` 기반 루트 산출 |
| 한글/공백 경로 대응 | `src/core/tesseract_setup.py:_to_short_path()` | ✅ Windows `GetShortPathNameW`로 8.3 변환, `--tessdata-dir` 로 전달 |
| 테마 리소스 | `src/ui/theme.py` | ✅ QSS는 Python 상수로 하드코딩 — 외부 `.qss` 파일 없음 |
| 데이터 디렉터리 분리 | `src/core/database.py:get_db_dir()` | ✅ `%LOCALAPPDATA%/NXQRChipCarrierManager/` — 설치 경로와 분리 |
| 이미지 저장 분리 | `src/core/database.py` Import/Export 경로 | ✅ DB에는 파일 경로만. 이미지는 파일 시스템 참조 |
| Tesseract 포터블 | `third_party/tesseract/` | ✅ tesseract.exe + 60+ DLL + tessdata/eng.traineddata + LICENSE.txt (~73MB) |
| ROI 사용자 커스터마이징 | `src/core/ocr_settings.py` + DB `app_settings.ocr_roi` | ✅ Phase 6B에서 추가. 재설치해도 데이터 디렉터리의 DB 보존 시 유지 |

### 1.2 **빠진 산출물**

| 항목 | 필요성 |
|------|--------|
| PyInstaller `.spec` | 🔴 필수 |
| `build.bat` / `build.py` 래퍼 | 🔴 필수 |
| Inno Setup `.iss` 스크립트 | 🟡 권장 (MSI/EXE 인스톨러용) |
| VC++ Runtime 의존성 선언 | 🟡 권장 |
| GitHub Actions 릴리즈 워크플로우 | 🟢 선택 |
| 코드 서명 인증서 | 🟢 선택 (SmartScreen 우회) |

### 1.3 즉석 평가

현재 상태에서 "PyInstaller 로 한 번 빌드하면 바로 실행 가능한가?" → **약 80% 가능**.
- 앱 자체는 기동 가능 (`sys.frozen` 분기 완성, 리소스 하드코딩)
- 관문: `third_party/tesseract/` 번들링 + `pytesseract` hidden import 명시 필요
- 위험: Pillow의 `_imaging` 이 PyInstaller hidden import 자동 탐지되지만 버전에 따라 누락 가능

---

## 2. Phase 7 실행 단계 (구현 시 참고)

### Step 1 — PyInstaller `.spec` 작성

**파일**: `NxQrManager.spec` (프로젝트 루트)

핵심 엔트리:

```python
# NxQrManager.spec
# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Tesseract 포터블 번들 전체를 onedir 내부의 third_party/tesseract/로 복사
        ('third_party/tesseract', 'third_party/tesseract'),
    ],
    hiddenimports=[
        'pytesseract',
        'PIL._tkinter_finder',
        # PySide6는 hook이 포함되어 있어 명시 불필요
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # 쓰지 않는 거대 패키지 제외 (배포 크기 최적화)
        'tkinter',
        'PyQt5', 'PyQt6',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='NxQrManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # UPX는 AV 오탐 원인 — 비활성
    console=False,       # GUI 앱 — 콘솔 창 숨김
    icon=None,           # 추후 .ico 추가 시 지정
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='NxQrManager',
)
```

**주의점**:
- `console=False` — GUI 앱에서 콘솔 창이 뜨지 않도록
- `datas=[('third_party/tesseract', 'third_party/tesseract')]` — 소스는 상대 경로,
  대상은 번들 내 동일 경로. `src/core/tesseract_setup.py:_project_root()` 가 `sys.executable.parent`를
  루트로 잡으므로 이 구조가 그대로 동작.
- `upx=False` — UPX 압축은 Windows Defender 오탐률이 매우 높아 사용하지 않음.

### Step 2 — `build.bat` 작성

**파일**: `build.bat` (프로젝트 루트)

```bat
@echo off
setlocal
pushd %~dp0

REM 정리
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM 가상환경 활성화 (옵션)
REM call .venv\Scripts\activate.bat

REM 빌드
pyinstaller --noconfirm --clean NxQrManager.spec > build.log 2>&1
if errorlevel 1 (
    echo Build failed. See build.log
    popd
    exit /b 1
)

echo Build OK. Output: dist\NxQrManager\
popd
```

### Step 3 — 스모크 검증 (빌드 직후)

1. `dist\NxQrManager\NxQrManager.exe` 더블클릭 → 메인 윈도우 기동 확인
2. Manual 모드 진입 → 샘플 이미지 `P2602074_..(01.09)/1.jpg` 드롭
3. 로그창에 `OCR 자동 추출: 1/1 전부 성공` 표시 확인
4. 카드에 `Freq=396.04, Q=710.682` pre-fill 확인

**실패 시 대응**:
| 증상 | 원인 후보 | 조치 |
|------|-----------|------|
| `ModuleNotFoundError: pytesseract` | hidden imports 누락 | `.spec`의 `hiddenimports`에 추가 |
| `TesseractNotFoundError` | 바이너리 번들링 실패 | `.spec`의 `datas` 경로 확인, `dist/NxQrManager/third_party/tesseract/tesseract.exe` 존재 여부 |
| `Failed loading language 'eng'` | tessdata 경로 문제 | Phase 5에서 검증된 short path + `--tessdata-dir` 로직이 frozen 환경에서 작동하는지 디버그 로그 확인 |
| 앱이 기동하지 않음 (EXE 창만 깜빡) | `console=False`로 에러 숨김 | 임시로 `console=True` 빌드 후 터미널 에러 확인 |

### Step 4 — Inno Setup 인스톨러 작성 (권장)

**파일**: `installer.iss` (프로젝트 루트)

```iss
[Setup]
AppId={{9E4C8C12-XXXX-XXXX-XXXX-XXXXXXXXXXXX}
AppName=NX QR Chip Carrier Manager
AppVersion=1.0.0
AppPublisher=<company>
DefaultDirName={autopf}\NxQrManager
DefaultGroupName=NX QR Chip Carrier Manager
OutputBaseFilename=NxQrManager-Setup-1.0.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\NxQrManager.exe
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline dialog

[Files]
Source: "dist\NxQrManager\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\NX QR Chip Carrier Manager"; Filename: "{app}\NxQrManager.exe"
Name: "{group}\Uninstall"; Filename: "{uninstallexe}"
Name: "{commondesktop}\NX QR Chip Carrier Manager"; Filename: "{app}\NxQrManager.exe"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\NxQrManager.exe"; Description: "Launch app"; Flags: postinstall nowait
```

**특기사항**:
- `PrivilegesRequired=lowest` — 관리자 권한 없이 사용자 폴더(`%LOCALAPPDATA%`)에 설치 가능
- `{autopf}` — 32/64비트 구분해 적절한 Program Files 사용
- VC++ Redistributable 번들 여부: `third_party/tesseract/` 가 이미 필요한 DLL을 포함하므로
  추가 번들 불필요로 판단. 실측 VM 테스트 후 필요 시 `[Run]` 섹션에 `vc_redist.x64.exe /quiet` 추가.

### Step 5 — 깨끗한 Windows VM 테스트 (필수)

- Python 미설치 상태의 Windows 10/11 VM
- 한글 사용자 이름 경로에서도 재현 (현재 개발 경로 `새 폴더` 와 유사)
- 설치 → 기동 → OCR 경로 → DB 생성 경로 확인

### Step 6 — GitHub Actions (선택)

**파일**: `.github/workflows/release.yml`

태그 푸시 시 자동 빌드 & 아티팩트 업로드 — 구현 시 `windows-latest` 러너 사용.

---

## 3. 알려진 위험 요소

| 리스크 | 가능성 | 영향 | 대응 |
|--------|:------:|:----:|------|
| Windows Defender SmartScreen 경고 | 높음 | 중 | 코드 서명 인증서 구매 또는 EV 인증서 (장기) |
| Pillow hidden import 누락 | 중 | 중 | `_imaging`, `_tkinter_finder`, `ImageQt` hook 추가 |
| `%LOCALAPPDATA%` 한글 경로 이슈 | 낮 | 낮 | Phase 5의 short path 로직으로 이미 대응됨 |
| Tesseract 바이너리가 git LFS 필요 | 중 | 낮 | 현재 `.gitignore`로 제외됨. 배포 빌드 전 별도 저장소/LFS/artifact에서 pull 필요 |
| PyInstaller `--onefile` 시작 지연 | 낮 | 낮 | `--onedir` (권장) 로 회피 |

---

## 4. 결론

현재 코드는 **배포 빌드를 바로 수행할 수 있는 상태**이며, 필요한 추가 작업은 다음과 같이 추정됩니다:

| 작업 | 예상 소요 |
|------|-----------|
| `.spec` + `build.bat` 작성 및 첫 빌드 | 1~2시간 |
| 첫 빌드의 hidden import 디버깅 | 30분~2시간 (Pillow/PySide6 hook 상태에 따라) |
| Inno Setup `.iss` 작성 및 설치 테스트 | 1~2시간 |
| 깨끗한 VM 스모크 테스트 | 1시간 |
| **합계** | **반일~1일** |

이 작업을 별도 Phase 7로 분리하는 이유:
- Phase 6의 유지보수성 개선(로그 UI + ROI Calibrator) 과 독립적
- 빌드 산출물은 CI/릴리즈 파이프라인 기반 작업이라 개별 검증이 필요
- VM 필수 검증 단계가 있어 수동 반복 작업을 수반

Phase 7 진입 시 이 문서를 체크리스트로 활용하시면 됩니다.
