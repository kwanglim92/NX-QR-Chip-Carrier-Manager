---
name: PyInstaller 빌드 파이프라인
description: PyInstaller + Inno Setup 기반 PySide6 앱 배포 파이프라인
version: 1.0
---

# SKILL 18 — PyInstaller 빌드 파이프라인

## 핵심 요소
- **빌드 모드**: `--onefile` (단일 .exe, Tool용) / `--onedir` (폴더, Launcher용)
- **필수 옵션**: `--windowed`, `--noconfirm`, `--add-data "src;dst"` (Windows `;` 구분자)
- **UTF-8 설정**: `PYTHONUTF8=1`, `chcp 65001` (한국어 Windows 필수)
- **sys.stderr Guard**: `--windowed` 모드에서 `sys.stderr = None` 방지 코드 필수
- **build.bat**: 표준 빌드 스크립트 템플릿 (onefile/onedir 버전)
- **build_all.bat**: 멀티 Tool 프로젝트용 통합 빌드 스크립트
- **Inno Setup**: 설치 프로그램 생성 (선택 사항)

## 프로젝트 구조
```
project/
├── main.py          ← 진입점
├── build.bat        ← 빌드 스크립트
├── installer/       ← Inno Setup (선택)
├── dist/            ← 빌드 출력 (gitignore)
└── build/           ← 임시 빌드 파일 (gitignore)
```

## 주의사항
- `dist/`, `build/` 디렉토리는 `.gitignore`에 추가
- `--workpath build --specpath build`로 빌드 산출물 분리
- PyInstaller는 C 컴파일러 불필요 (Nuitka와 다름)
- `sys.stderr` Guard는 모든 라이브러리 import 전에 배치

## 관련 파일
`build.bat`, `build_all.bat`
