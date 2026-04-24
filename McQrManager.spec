# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 빌드 사양 — MC QR Code Chip Carrier Manager.

빌드 명령:
    pyinstaller --noconfirm --clean McQrManager.spec

산출물:
    dist/McQrManager/         ← onedir 모드 (권장)
    dist/McQrManager/McQrManager.exe
    dist/McQrManager/third_party/tesseract/tesseract.exe  (포터블 동봉)

주의:
- ``third_party/tesseract/`` 전체가 ``datas`` 로 번들됨. 실제 파일이 준비되지
  않았으면 빌드는 성공하지만 런타임에서 OCR 실패 → 사용자가 수기 입력으로
  fallback. tesseract_setup.configure_tesseract() 의 ``getattr(sys, 'frozen', False)``
  분기가 올바른 경로를 찾아준다.
- UPX는 사용하지 않음 (Windows Defender 오탐 방지).
- onedir 모드: 시작 속도가 빠르고 Tesseract DLL 수십 개를 재배치하지 않음.
"""
from pathlib import Path

block_cipher = None

# 프로젝트 루트
ROOT = Path(SPECPATH) if "SPECPATH" in globals() else Path.cwd()

# 번들할 데이터 파일/디렉터리 (source, dest) 튜플
# - third_party/tesseract/*  → dist/McQrManager/third_party/tesseract/
#   tesseract_setup._project_root() 가 sys.executable.parent 를 루트로 잡으므로
#   번들 내부 구조와 개발 경로 구조가 동일하게 유지된다.
datas = [
    (str(ROOT / "third_party" / "tesseract"), "third_party/tesseract"),
]


# 숨은 임포트 (PyInstaller 자동 분석이 놓칠 수 있는 모듈)
hiddenimports = [
    "pytesseract",
    # PIL 관련 — Pillow 플러그인들이 동적 로드되기 때문에 한 번씩 언급
    "PIL._imaging",
    "PIL.Image",
    "PIL.ImageDraw",
    "PIL.ImageFont",
    # PySide6는 자체 hook 이 있어 별도 지정 불필요
]


# 번들에 포함되지 않을 모듈 (배포 용량 최소화)
# 주의: ``unittest`` 는 pyparsing(matplotlib 간접 의존성)이 참조하므로 제외 금지.
excludes = [
    "tkinter",
    "PyQt5",
    "PyQt6",
    "PySide2",
    "pytest",
    "pytest_qt",
    "IPython",
]


a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="McQrManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # UPX 압축 금지 — 오탐 방지
    console=False,           # GUI 앱 — 콘솔 창 숨김
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets" / "icons" / "icon_lotcard_ref.ico"),
    # ↑ image.png (1254×1254) → 멀티 해상도 ICO (16/32/48/64/128/256)
    contents_directory=".",  # PyInstaller 6.x: _internal/ 대신 루트에 배치
                              # — tesseract_setup._project_root() 가 sys.executable.parent 를
                              # 루트로 해석하므로 third_party/tesseract/ 가 같은 상대 경로에 있어야 함
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="McQrManager",
)
