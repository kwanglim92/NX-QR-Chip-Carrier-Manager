"""ROI Calibrator 다이얼로그 — Frequency/Q 박스를 이미지 위에서 시각 편집 (F-14).

사용 흐름
--------
1. 사용자가 Manual 탭에서 ``Calibrate ROI…`` 클릭
2. 참조 이미지 로드 (기본값: DB 저장 ROI 또는 ``image_parser.ROI`` 코드 기본값)
3. 캔버스 박스 드래그/리사이즈 또는 우측 QSpinBox 편집 (양방향 동기화)
4. ``Test OCR`` 버튼으로 현재 좌표 정확도 즉시 확인
5. ``Save`` 시 ``ocr_settings.save_roi`` 로 DB 영속화, 다이얼로그 accept

DB 저장은 호출자가 ``result_roi()`` 를 통해 수행 (이 다이얼로그는 저장 로직을
포함하지 않아 단위 테스트 용이).
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.core.image_parser import ROI as DEFAULT_ROI
from src.ui.theme import ACCENT, FG, FG2, GREEN, ORANGE, RED
from src.ui.widgets.roi_canvas import RoiCanvas

ROI_NAMES = ("frequency", "q_factor")


class RoiCalibratorDialog(QDialog):
    """ROI 시각적 편집 다이얼로그.

    Parameters
    ----------
    initial_roi
        현재 활성 ROI dict. None이면 ``DEFAULT_ROI`` 사용.
    sample_image
        시작 시 자동으로 로드할 이미지 경로. None이면 빈 캔버스로 시작.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        initial_roi: dict[str, tuple[int, int, int, int]] | None = None,
        sample_image: str | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Calibrate OCR ROI")
        self.resize(960, 640)

        self._roi: dict[str, tuple[int, int, int, int]] = (
            dict(initial_roi) if initial_roi else dict(DEFAULT_ROI)
        )

        outer = QVBoxLayout(self)
        outer.setSpacing(8)

        # ── 상단 바: 이미지 로드 + 해상도 표시 ──
        top = QHBoxLayout()
        self._btn_load_img = QPushButton("Load reference image…")
        self._btn_load_img.clicked.connect(self._on_load_image)
        top.addWidget(self._btn_load_img)

        self._lbl_resolution = QLabel("No image loaded")
        self._lbl_resolution.setStyleSheet(f"color: {FG2}; font-size: 12px;")
        top.addWidget(self._lbl_resolution)
        top.addStretch()
        outer.addLayout(top)

        # ── 중앙: 캔버스 + 사이드바 ──
        center = QHBoxLayout()

        self._canvas = RoiCanvas()
        self._canvas.roi_changed.connect(self._on_canvas_roi_changed)
        center.addWidget(self._canvas, 1)

        sidebar = QVBoxLayout()
        sidebar.setSpacing(8)
        self._spinboxes: dict[str, dict[str, QSpinBox]] = {}
        for name in ROI_NAMES:
            sidebar.addWidget(self._build_roi_group(name))

        # Test OCR
        test_group = QGroupBox("Test OCR")
        test_layout = QVBoxLayout(test_group)
        self._btn_test = QPushButton("Run OCR on current ROI")
        self._btn_test.clicked.connect(self._on_test_ocr)
        test_layout.addWidget(self._btn_test)
        self._lbl_test_result = QLabel("—")
        self._lbl_test_result.setWordWrap(True)
        self._lbl_test_result.setStyleSheet(f"color: {FG}; font-size: 12px;")
        test_layout.addWidget(self._lbl_test_result)

        # Debug Info — 접이식 (Test OCR 실행 후 진단 정보 표시)
        self._btn_debug_toggle = QPushButton("▶  Debug Info")
        self._btn_debug_toggle.setCheckable(True)
        self._btn_debug_toggle.setStyleSheet(
            f"text-align: left; color: {FG2}; padding: 2px 4px; "
            f"border: none; font-size: 11px;"
        )
        self._btn_debug_toggle.toggled.connect(self._on_debug_toggle)
        test_layout.addWidget(self._btn_debug_toggle)

        self._lbl_debug_info = QLabel("Test OCR 을 실행하면 진단 정보가 표시됩니다.")
        self._lbl_debug_info.setWordWrap(True)
        self._lbl_debug_info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._lbl_debug_info.setStyleSheet(
            f"color: {FG2}; font-size: 11px; "
            f"font-family: 'Consolas', 'Courier New', monospace; "
            f"padding: 4px; background-color: rgba(255,255,255,0.04); "
            f"border-radius: 3px;"
        )
        self._lbl_debug_info.setVisible(False)
        test_layout.addWidget(self._lbl_debug_info)

        sidebar.addWidget(test_group)
        sidebar.addStretch()

        sidebar_wrapper = QWidget()
        sidebar_wrapper.setLayout(sidebar)
        sidebar_wrapper.setFixedWidth(260)
        center.addWidget(sidebar_wrapper)

        outer.addLayout(center, 1)

        # ── 하단: 버튼 박스 ──
        btns = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel | QDialogButtonBox.Reset
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.Reset).setText("Reset to Default")
        btns.button(QDialogButtonBox.Reset).clicked.connect(self._on_reset)
        btns.button(QDialogButtonBox.Save).setText("Save")
        outer.addWidget(btns)

        # 초기 상태 주입
        self._current_image_path: str | None = None
        self._apply_roi_to_ui(self._roi, sync_canvas=True)
        if sample_image:
            self._load_image(sample_image)

    # ─── 사이드바 빌드 ───

    def _build_roi_group(self, name: str) -> QGroupBox:
        grp = QGroupBox(name.replace("_", " ").title() + " ROI")
        form = QFormLayout(grp)

        boxes: dict[str, QSpinBox] = {}
        for key, max_val in (("x", 10000), ("y", 10000), ("w", 2000), ("h", 2000)):
            sp = QSpinBox()
            sp.setRange(0, max_val)
            sp.setSingleStep(1)
            sp.valueChanged.connect(lambda _v, n=name: self._on_spin_changed(n))
            boxes[key] = sp
            form.addRow(f"{key} (px):", sp)
        self._spinboxes[name] = boxes
        return grp

    # ─── 이미지 로드 ───

    def _on_load_image(self) -> None:
        start_dir = str(Path(self._current_image_path).parent) if self._current_image_path else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Load reference image", start_dir,
            "Images (*.png *.jpg *.jpeg *.bmp);;All files (*)",
        )
        if path:
            self._load_image(path)

    def _load_image(self, path: str) -> None:
        ok = self._canvas.load_image(path)
        if not ok:
            self._lbl_resolution.setText("Failed to load image")
            self._lbl_resolution.setStyleSheet(f"color: {RED}; font-size: 12px;")
            return
        w, h = self._canvas.image_size()
        self._lbl_resolution.setText(f"{w} × {h}  │  {Path(path).name}")
        self._lbl_resolution.setStyleSheet(f"color: {FG}; font-size: 12px;")
        self._current_image_path = path

        # 새 이미지에 기존 ROI 박스 다시 그리기
        self._canvas.set_rois(self._roi)

    # ─── 동기화 ───

    def _apply_roi_to_ui(
        self,
        roi: dict[str, tuple[int, int, int, int]],
        *,
        sync_canvas: bool,
    ) -> None:
        """dict → spinbox(+옵션 canvas). 시그널 블로킹으로 에코 방지."""
        for name, rect in roi.items():
            if name not in self._spinboxes:
                continue
            x, y, w, h = rect
            for key, value in zip(("x", "y", "w", "h"), (x, y, w, h)):
                sp = self._spinboxes[name][key]
                sp.blockSignals(True)
                sp.setValue(value)
                sp.blockSignals(False)
        if sync_canvas and self._canvas.image_size() != (0, 0):
            self._canvas.set_rois(roi)

    def _on_canvas_roi_changed(self, name: str, rect: tuple[int, int, int, int]) -> None:
        """Canvas 드래그 → spinbox 값 갱신."""
        self._roi[name] = rect
        if name not in self._spinboxes:
            return
        x, y, w, h = rect
        for key, value in zip(("x", "y", "w", "h"), (x, y, w, h)):
            sp = self._spinboxes[name][key]
            sp.blockSignals(True)
            sp.setValue(value)
            sp.blockSignals(False)

    def _on_spin_changed(self, name: str) -> None:
        """Spinbox 편집 → canvas 박스 갱신."""
        boxes = self._spinboxes[name]
        rect = (
            boxes["x"].value(),
            boxes["y"].value(),
            boxes["w"].value(),
            boxes["h"].value(),
        )
        self._roi[name] = rect
        self._canvas.update_roi(name, rect)

    # ─── 액션 ───

    def _on_reset(self) -> None:
        self._roi = dict(DEFAULT_ROI)
        self._apply_roi_to_ui(self._roi, sync_canvas=True)
        self._lbl_test_result.setText("Reset to image_parser defaults.")
        self._lbl_test_result.setStyleSheet(f"color: {FG2}; font-size: 12px;")

    def _on_debug_toggle(self, checked: bool) -> None:
        """접이식 Debug Info 영역 토글."""
        self._lbl_debug_info.setVisible(checked)
        self._btn_debug_toggle.setText("▼  Debug Info" if checked else "▶  Debug Info")

    def _on_test_ocr(self) -> None:
        if not self._current_image_path:
            self._lbl_test_result.setText("Load a reference image first.")
            self._lbl_test_result.setStyleSheet(f"color: {ORANGE}; font-size: 12px;")
            self._lbl_debug_info.setText("진단 정보 없음 — 참조 이미지를 먼저 로드하세요.")
            return

        # 현재 ROI 로 extract_measurements 호출 — debug=True 로 raw OCR 텍스트 동시 수집
        try:
            from src.core.image_parser import extract_measurements
            reading = extract_measurements(
                self._current_image_path, roi=self._roi, debug=True,
            )
        except Exception as e:  # pragma: no cover - 안전망
            self._lbl_test_result.setText(f"OCR error: {e}")
            self._lbl_test_result.setStyleSheet(f"color: {RED}; font-size: 12px;")
            self._lbl_debug_info.setText(f"예외: {e!r}")
            return

        freq = reading.frequency
        q = reading.q_factor
        if freq is None and q is None:
            self._lbl_test_result.setText(
                "Both ROIs failed to read. Check box positions or image resolution."
            )
            self._lbl_test_result.setStyleSheet(f"color: {RED}; font-size: 12px;")
        else:
            parts = []
            if freq is not None:
                parts.append(f"freq={freq}")
            else:
                parts.append("freq=✗")
            if q is not None:
                parts.append(f"q={q}")
            else:
                parts.append("q=✗")
            color = GREEN if (freq is not None and q is not None) else ORANGE
            self._lbl_test_result.setText("  |  ".join(parts))
            self._lbl_test_result.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold;")

        # Debug Info — 이미지 해상도 + ROI 좌표 + raw OCR 텍스트
        img_w, img_h = self._canvas.image_size()
        fx, fy, fw, fh = self._roi.get("frequency", (0, 0, 0, 0))
        qx, qy, qw, qh = self._roi.get("q_factor", (0, 0, 0, 0))
        debug_lines = [
            f"Image:    {img_w} × {img_h}",
            f"Freq ROI: ({fx}, {fy}, {fw}, {fh})",
            f"  raw → {reading.raw_frequency_text!r}",
            f"Q ROI:    ({qx}, {qy}, {qw}, {qh})",
            f"  raw → {reading.raw_q_text!r}",
        ]
        self._lbl_debug_info.setText("\n".join(debug_lines))

    # ─── 저장 전 유효성 검증 (Phase 7A-B3) ───

    MIN_ROI_DIM = 10  # ROI 박스 최소 너비/높이 (px)

    def _validate_before_save(self) -> list[str]:
        """ROI 유효성 에러 목록 반환. 빈 리스트면 통과.

        체크:
        - 참조 이미지가 로드되어 있어야 함 (해상도 저장 키 결정에 필수)
        - 각 ROI 가 이미지 범위를 벗어나지 않아야 함
        - 각 ROI 너비·높이가 ``MIN_ROI_DIM`` 이상이어야 함
        """
        errors: list[str] = []

        size = self._canvas.image_size()
        if size == (0, 0):
            errors.append("참조 이미지를 먼저 로드하세요. (해상도가 있어야 저장 가능)")
            return errors

        W, H = size
        for name, (x, y, w, h) in self._roi.items():
            label = name.replace("_", " ").title()
            if w < self.MIN_ROI_DIM or h < self.MIN_ROI_DIM:
                errors.append(
                    f"{label}: 크기가 너무 작습니다 ({w}×{h}, 최소 "
                    f"{self.MIN_ROI_DIM}×{self.MIN_ROI_DIM})"
                )
            if x < 0 or y < 0:
                errors.append(f"{label}: 좌표가 음수입니다 ({x}, {y})")
            if x + w > W or y + h > H:
                errors.append(
                    f"{label}: 이미지 범위({W}×{H})를 벗어납니다 — "
                    f"(x={x}, y={y}, w={w}, h={h})"
                )

        return errors

    def accept(self) -> None:
        """Save 버튼 클릭 시 유효성 검증 후 다이얼로그 닫기."""
        errors = self._validate_before_save()
        if errors:
            QMessageBox.warning(
                self,
                "유효하지 않은 ROI 설정",
                "다음 문제를 해결한 뒤 다시 저장하세요:\n\n• " + "\n• ".join(errors),
            )
            return  # 다이얼로그 유지
        super().accept()

    # ─── 결과 반환 ───

    def result_roi(self) -> dict[str, tuple[int, int, int, int]]:
        """다이얼로그가 ``Accepted`` 상태로 종료될 때 호출자가 사용."""
        return dict(self._roi)

    def result_resolution(self) -> tuple[int, int] | None:
        """현재 로드된 참조 이미지의 해상도. 이미지가 없으면 None.

        Phase 7A: 호출자는 이 해상도 키로 ``save_roi_for(conn, W, H, roi)`` 를 호출.
        """
        size = self._canvas.image_size()
        if size == (0, 0):
            return None
        return size
