---
name: PyInstaller Build Pipeline
description: Standard PyInstaller + Inno Setup build pipeline for PySide6 desktop applications. Provides consistent build.bat and installer templates.
version: 1.0
project_origin: Park Analyzer
related_skills: [01-pyside6-dark-theme]
---

# SKILL 18 — PyInstaller Build Pipeline

## Overview

Standardized build pipeline for PySide6 desktop applications. Produces standalone `.exe` via PyInstaller and optional installer via Inno Setup.

**When to use:** When packaging a PySide6 desktop application for distribution.

## Prerequisites

| Tool | Install |
|------|---------|
| Python 3.11+ | Required |
| PyInstaller | `pip install pyinstaller` |
| Inno Setup 6 | [Download](https://jrsoftware.org/isdl.php) — only for installer |

> Note: C compiler (MinGW/MSVC) is **not** required — PyInstaller bundles the Python interpreter, it does not compile to native code.

## Build Modes

PyInstaller supports two packaging modes:

| Mode | Flag | Output | Use Case |
|------|------|--------|----------|
| **onefile** | `--onefile` | 단일 `.exe` | Tool 모듈 (작은 단위 프로그램) |
| **onedir** | `--onedir` | 폴더 (`.exe` + `_internal/`) | 런처 (modules/ 폴더 포함 필요) |

## Standard Project Build Structure

```
project/
├── main.py                 ← Entry point
├── build.bat               ← Build script
├── installer/              ← Only if installer needed
│   └── setup.iss
├── dist/                   ← Build output (gitignored)
│   └── MyApp.exe           # onefile mode
├── build/                  ← PyInstaller work files (gitignored)
├── core/                   ← Business logic
├── ui/                     ← PySide6 GUI
└── config/                 ← Settings files
```

## build.bat Template (onefile — Tool용)

```batch
@echo off
chcp 65001 >nul 2>&1
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo Building with PyInstaller (onefile)...

python -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "MyToolName" ^
    --distpath dist ^
    --workpath build ^
    --specpath build ^
    --add-data "config;config" ^
    --hidden-import=core ^
    --hidden-import=ui ^
    main.py

if %ERRORLEVEL% neq 0 ( echo BUILD FAILED & pause & exit /b 1 )
echo Build SUCCESS!
pause
```

## build.bat Template (onedir — Launcher용)

```batch
@echo off
chcp 65001 >nul 2>&1
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo Building with PyInstaller (onedir)...

python -m PyInstaller ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --name "ParkAnalyzer" ^
    --distpath dist ^
    --workpath build ^
    --specpath build ^
    --add-data "config;config" ^
    --hidden-import=core ^
    --hidden-import=ui ^
    main.py

if %ERRORLEVEL% neq 0 ( echo BUILD FAILED & pause & exit /b 1 )

REM Copy modules/ to dist
xcopy /E /I /Y /Q "modules" "dist\ParkAnalyzer\modules" >nul
echo Build SUCCESS!
pause
```

## Key PyInstaller Options

| Option | Purpose |
|--------|---------|
| `--onefile` | Single .exe output (for tools) |
| `--onedir` | Folder output with .exe + dependencies (for launcher) |
| `--windowed` | No console window for GUI apps |
| `--noconfirm` | Overwrite previous build without asking |
| `--name "Name"` | Output executable name |
| `--distpath dist` | Output directory for built files |
| `--workpath build` | Temp build directory |
| `--specpath build` | .spec file location |
| `--add-data "src;dst"` | Bundle data directories (Windows uses `;` separator) |
| `--hidden-import=pkg` | Include packages not auto-detected |

## sys.stderr Guard (Important)

PyInstaller `--windowed` mode sets `sys.stderr = None`. Libraries like `loguru` that write to stderr will crash with `AttributeError: 'NoneType'` unless guarded:

```python
import sys
import os

# PyInstaller --windowed sets sys.stderr to None
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
```

Place this **before** any library import that uses stderr (e.g., `loguru`, `logging`).

## Build Commands

```
build.bat              Build .exe
build.bat inno         Create Inno Setup installer
build.bat sign         Sign .exe with code certificate
```

## Master Build (build_all.bat)

For multi-tool projects like Park Analyzer, `build_all.bat` orchestrates:

1. Build each Tool (PyInstaller `--onefile`)
2. Copy built .exe to `modules/`
3. Build launcher (PyInstaller `--onedir`)
4. Code signing

## Notes

- Always add `dist/` and `build/` to `.gitignore`
- Set `PYTHONUTF8=1` to avoid mbcs codec errors on Korean Windows
- Use `--workpath build --specpath build` to keep build artifacts separate from source
- Each tool project only needs `build.bat` (no installer)
- Only the launcher project needs `installer/setup.iss`
- PyInstaller does not require a C compiler (unlike Nuitka)
