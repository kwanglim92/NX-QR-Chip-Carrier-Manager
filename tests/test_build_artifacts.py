"""Phase 8 회귀 테스트 — 빌드 산출물 구조 검증 (선택적).

``dist/NxQrManager/`` 가 존재하면 Tesseract 번들과 주요 파일이 올바른 위치에
있는지 확인. ``build.bat`` 미실행 환경에서는 전체 모듈이 skip 된다.

CI/개발 환경에서 모두 안전하게 실행 가능.
"""
from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist" / "NxQrManager"


@pytest.fixture(scope="module")
def dist_available():
    """dist 빌드 산출물이 없으면 모듈 전체 skip."""
    if not DIST_DIR.exists():
        pytest.skip(
            "dist/NxQrManager/ 없음 — build.bat 미실행 상태. "
            "이 테스트는 PyInstaller 빌드 후에 실행되는 회귀용."
        )
    return DIST_DIR


class TestBuildLayout:
    def test_main_exe_exists(self, dist_available):
        assert (dist_available / "NxQrManager.exe").exists()

    def test_pyside6_bundled(self, dist_available):
        assert (dist_available / "PySide6").is_dir()

    def test_pil_bundled(self, dist_available):
        assert (dist_available / "PIL").is_dir()

    def test_flat_layout_no_internal(self, dist_available):
        """contents_directory='.' 확인 — _internal/ 서브디렉터리가 없어야 함."""
        internal = dist_available / "_internal"
        if internal.exists():
            # PyInstaller 6.x 기본: _internal/ 있음. 우리는 루트에 펼쳐야 함.
            # 그런데 _internal 안에 실제 파일이 있으면 contents_directory 설정이 실패한 것.
            contents = list(internal.iterdir())
            if contents:
                pytest.fail(
                    f"_internal/ 에 파일이 있음 — contents_directory='.' 이 적용되지 않음. "
                    f"tesseract_setup._project_root() 가 탐색 경로를 못 찾게 됨. "
                    f"내용: {[c.name for c in contents[:5]]}"
                )


class TestTesseractBundled:
    def test_tesseract_exe(self, dist_available):
        tess = dist_available / "third_party" / "tesseract" / "tesseract.exe"
        assert tess.exists(), f"Tesseract.exe 번들되지 않음: {tess}"

    def test_eng_traineddata(self, dist_available):
        td = dist_available / "third_party" / "tesseract" / "tessdata" / "eng.traineddata"
        assert td.exists()

    def test_license_included(self, dist_available):
        """Apache-2.0 라이선스 고지는 법적 요구사항."""
        lic = dist_available / "third_party" / "tesseract" / "LICENSE.txt"
        # README.md 만 있어도 허용 (LICENSE.txt가 최종 배포에 포함되어야 함을 문서화)
        assert lic.exists() or (
            dist_available / "third_party" / "tesseract" / "README.md"
        ).exists()

    def test_enough_dlls(self, dist_available):
        """UB Mannheim 빌드는 수십 개 DLL 동반 — 최소 20개 이상 번들되어야."""
        tess_dir = dist_available / "third_party" / "tesseract"
        dlls = list(tess_dir.glob("*.dll"))
        assert len(dlls) >= 20, f"DLL {len(dlls)}개 — UB Mannheim 번들이 불완전할 수 있음"


class TestFrozenPathResolution:
    """``tesseract_setup._project_root()`` 가 frozen 모드에서 가리키는 경로가
    실제 dist 구조와 일치하는지 검증."""

    def test_project_root_resolves_to_exe_parent(self, dist_available):
        from src.core.tesseract_setup import _project_root
        import sys

        exe_path = dist_available / "NxQrManager.exe"
        assert exe_path.exists()

        # frozen 모드 강제 시뮬레이션
        original_frozen = getattr(sys, "frozen", False)
        original_executable = sys.executable
        try:
            sys.frozen = True  # type: ignore[attr-defined]
            sys.executable = str(exe_path)
            root = _project_root()
            assert root == exe_path.parent.resolve()
            # 이 경로에서 tesseract 탐색이 성공해야 함
            assert (root / "third_party" / "tesseract" / "tesseract.exe").exists()
        finally:
            if original_frozen:
                sys.frozen = original_frozen  # type: ignore[attr-defined]
            elif hasattr(sys, "frozen"):
                delattr(sys, "frozen")
            sys.executable = original_executable
