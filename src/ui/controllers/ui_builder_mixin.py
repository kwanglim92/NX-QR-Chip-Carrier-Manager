"""전체 UI 레이아웃 빌더 (SKILL 12 패턴)."""
from __future__ import annotations

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QPushButton, QLineEdit, QDoubleSpinBox, QDateEdit,
    QGroupBox, QFormLayout, QTextEdit, QProgressBar,
    QStackedWidget, QToolBar, QStatusBar, QTabWidget,
    QComboBox, QSpinBox,
)

from src.ui.theme import ACCENT, FG, FG2, BG, BG2, BG3, GREEN, PURPLE
from src.ui.widgets.slot_grid_widget import SlotGridWidget
from src.ui.widgets.image_viewer import ImageViewer
from src.ui.widgets.qr_input_widget import QRInputWidget
from src.ui.widgets.csv_preview_table import CSVPreviewTable
from src.ui.widgets.system_logger import SystemLogger
from src.ui.widgets.manual_grid_widget import ManualGridWidget


class UIBuilderMixin:
    def _build_ui(self):
        self.setWindowTitle("NX QR Chip Carrier Manager")
        self.resize(1280, 800)

        # 중앙 위젯
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 4, 8, 4)
        main_layout.setSpacing(4)

        # 상단 모드 전환 바
        self._build_toolbar(main_layout)

        # 메인 콘텐츠: QStackedWidget (ATX / Manual / Export)
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack, 1)

        self._build_atx_page()
        self._build_manual_page()
        self._build_export_page()

        # 하단: QR 입력 + 진행 상태
        self._build_bottom_bar(main_layout)

        # 상태 바
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("폴더를 선택하여 시작하세요")

    def _build_toolbar(self, parent_layout):
        toolbar_layout = QHBoxLayout()

        self.btn_atx_mode = QPushButton("ATX 모드")
        self.btn_atx_mode.setProperty("accent", "true")
        self.btn_atx_mode.clicked.connect(lambda: self._switch_mode("atx"))
        toolbar_layout.addWidget(self.btn_atx_mode)

        self.btn_manual_mode = QPushButton("수동 모드")
        self.btn_manual_mode.clicked.connect(lambda: self._switch_mode("manual"))
        toolbar_layout.addWidget(self.btn_manual_mode)

        self.btn_export_mode = QPushButton("CSV 내보내기")
        self.btn_export_mode.clicked.connect(lambda: self._switch_mode("export"))
        toolbar_layout.addWidget(self.btn_export_mode)

        # 생산일자 — 모드 버튼 바로 우측
        toolbar_layout.addSpacing(20)
        toolbar_layout.addWidget(QLabel("생산일자:"))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("yyyyMMdd")
        self.date_edit.setFixedWidth(130)
        self.date_edit.dateChanged.connect(self._on_date_changed)
        toolbar_layout.addWidget(self.date_edit)

        toolbar_layout.addStretch()

        parent_layout.addLayout(toolbar_layout)

    # ─── ATX 모드 페이지 ───
    def _build_atx_page(self):
        page = QWidget()
        splitter = QSplitter(Qt.Horizontal)

        # 좌측 패널
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(4, 4, 4, 4)

        # 폴더 선택
        folder_group = QGroupBox("ATX 결과 폴더")
        fg_layout = QVBoxLayout(folder_group)

        folder_row = QHBoxLayout()
        self.atx_folder_input = QLineEdit()
        self.atx_folder_input.setReadOnly(True)
        self.atx_folder_input.setPlaceholderText("폴더를 선택하세요...")
        folder_row.addWidget(self.atx_folder_input)

        self.btn_browse_atx = QPushButton("찾아보기")
        self.btn_browse_atx.clicked.connect(self._browse_atx_folder)
        folder_row.addWidget(self.btn_browse_atx)
        fg_layout.addLayout(folder_row)

        # 폴더 정보
        info_form = QFormLayout()
        self.lbl_po = QLabel("-")
        self.lbl_probe_type = QLabel("-")
        self.lbl_quantity = QLabel("-")
        info_form.addRow("PO 번호:", self.lbl_po)
        info_form.addRow("Probe Type:", self.lbl_probe_type)
        info_form.addRow("수량:", self.lbl_quantity)
        fg_layout.addLayout(info_form)

        left_layout.addWidget(folder_group)

        # 이미지 뷰어
        self.atx_img_group = QGroupBox("FreqSweep 이미지")
        img_group = self.atx_img_group
        img_layout = QVBoxLayout(img_group)
        self.atx_image_viewer = ImageViewer()
        img_layout.addWidget(self.atx_image_viewer)

        # Drive 입력
        drive_row = QHBoxLayout()
        drive_row.addWidget(QLabel("Drive (%):"))
        self.atx_drive_input = QDoubleSpinBox()
        self.atx_drive_input.setRange(0, 100)
        self.atx_drive_input.setDecimals(2)
        self.atx_drive_input.setSingleStep(0.01)
        self.atx_drive_input.setSpecialValueText("-")
        drive_row.addWidget(self.atx_drive_input)

        self.btn_apply_drive = QPushButton("적용")
        self.btn_apply_drive.clicked.connect(self._apply_drive)
        drive_row.addWidget(self.btn_apply_drive)
        img_layout.addLayout(drive_row)

        left_layout.addWidget(img_group, 1)

        # 로그
        log_group = QGroupBox("로그")
        log_layout = QVBoxLayout(log_group)
        self._log_te = QTextEdit()
        self._log_te.setMaximumHeight(150)
        log_layout.addWidget(self._log_te)
        left_layout.addWidget(log_group)

        self.logger = SystemLogger(self._log_te)

        splitter.addWidget(left)

        # 우측 패널: 슬롯 그리드
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 4, 4, 4)

        self.slot_grid = SlotGridWidget()
        self.slot_grid.slot_clicked.connect(self._on_slot_selected)
        right_layout.addWidget(self.slot_grid, 1)

        splitter.addWidget(right)
        splitter.setSizes([400, 600])

        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(splitter)

        self.stack.addWidget(page)  # index 0

    # ─── 수동 모드 페이지 ───
    def _build_manual_page(self):
        page = QWidget()
        splitter = QSplitter(Qt.Horizontal)

        # ── 좌측 패널: 이미지 뷰어 + 입력 폼 ──
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(4, 4, 4, 4)

        # 이미지 뷰어
        img_group = QGroupBox("Sweep 이미지")
        img_layout = QVBoxLayout(img_group)
        self.manual_image_viewer = ImageViewer()
        img_layout.addWidget(self.manual_image_viewer)
        left_layout.addWidget(img_group, 1)

        # 측정값 입력 폼
        data_group = QGroupBox("측정값 입력")
        data_form = QFormLayout(data_group)

        self.manual_freq_input = QDoubleSpinBox()
        self.manual_freq_input.setRange(0, 9999)
        self.manual_freq_input.setDecimals(2)
        self.manual_freq_input.setSuffix(" KHz")
        data_form.addRow("Frequency:", self.manual_freq_input)

        self.manual_drive_input = QDoubleSpinBox()
        self.manual_drive_input.setRange(0, 100)
        self.manual_drive_input.setDecimals(2)
        self.manual_drive_input.setSuffix(" %")
        data_form.addRow("Drive:", self.manual_drive_input)

        self.manual_q_input = QDoubleSpinBox()
        self.manual_q_input.setRange(0, 9999)
        self.manual_q_input.setDecimals(2)
        data_form.addRow("Q:", self.manual_q_input)

        left_layout.addWidget(data_group)

        # 적용 버튼
        self.btn_apply_manual = QPushButton("적용")
        self.btn_apply_manual.setProperty("accent", "true")
        self.btn_apply_manual.clicked.connect(self._apply_manual_entry)
        left_layout.addWidget(self.btn_apply_manual)

        splitter.addWidget(left)

        # ── 우측 패널: Probe Type 탭 + 카드 그리드 ──
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 4, 4, 4)

        # 상단 컨트롤: 열 수 + 탭 추가/삭제
        ctrl_row = QHBoxLayout()

        ctrl_row.addWidget(QLabel("열 수:"))
        self.manual_col_spin = QSpinBox()
        self.manual_col_spin.setRange(1, 8)
        self.manual_col_spin.setValue(4)
        self.manual_col_spin.setFixedWidth(60)
        self.manual_col_spin.valueChanged.connect(self._on_manual_columns_changed)
        ctrl_row.addWidget(self.manual_col_spin)

        ctrl_row.addStretch()

        btn_load_images = QPushButton("불러오기")
        btn_load_images.clicked.connect(self._browse_manual_images)
        ctrl_row.addWidget(btn_load_images)

        btn_add_tab = QPushButton("+ 탭 추가")
        btn_add_tab.clicked.connect(self._add_probe_tab)
        ctrl_row.addWidget(btn_add_tab)

        btn_del_tab = QPushButton("탭 삭제")
        btn_del_tab.clicked.connect(self._remove_current_probe_tab)
        ctrl_row.addWidget(btn_del_tab)

        btn_reset = QPushButton("초기화")
        btn_reset.clicked.connect(self._reset_manual_all)
        ctrl_row.addWidget(btn_reset)

        right_layout.addLayout(ctrl_row)

        # QTabWidget: Probe Type 탭들 + 전체 현황 탭
        self.manual_tabs = QTabWidget()
        right_layout.addWidget(self.manual_tabs, 1)

        # 전체 현황 탭 (고정, 마지막)
        overview_page = QWidget()
        self._overview_layout = QVBoxLayout(overview_page)
        self._overview_layout.setContentsMargins(12, 12, 12, 12)

        overview_header = QLabel("전체 현황")
        overview_header.setProperty("header", "true")
        self._overview_layout.addWidget(overview_header)
        self._overview_layout.addStretch()
        self.manual_tabs.addTab(overview_page, "전체 현황")

        splitter.addWidget(right)
        splitter.setSizes([400, 600])

        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(splitter)

        self.stack.addWidget(page)  # index 1

    # ─── CSV 내보내기 페이지 ───
    def _build_export_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)

        header = QLabel("CSV 미리보기 & 내보내기")
        header.setProperty("header", "true")
        layout.addWidget(header)

        self.csv_preview = CSVPreviewTable()
        layout.addWidget(self.csv_preview, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_refresh_preview = QPushButton("미리보기 새로고침")
        self.btn_refresh_preview.clicked.connect(self._refresh_csv_preview)
        btn_row.addWidget(self.btn_refresh_preview)

        self.btn_export_csv = QPushButton("CSV 저장")
        self.btn_export_csv.setProperty("accent", "true")
        self.btn_export_csv.clicked.connect(self._export_csv)
        btn_row.addWidget(self.btn_export_csv)

        self.btn_export_with_images = QPushButton("CSV + 이미지 저장")
        self.btn_export_with_images.setProperty("accent", "true")
        self.btn_export_with_images.clicked.connect(self._export_csv_with_images)
        btn_row.addWidget(self.btn_export_with_images)

        layout.addLayout(btn_row)

        self.stack.addWidget(page)  # index 2

    # ─── 하단 바: QR 입력 + 진행률 ───
    def _build_bottom_bar(self, parent_layout):
        bottom = QWidget()
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(4, 4, 4, 4)

        self.qr_input = QRInputWidget()
        self.qr_input.qr_scanned.connect(self._on_qr_scanned)
        bottom_layout.addWidget(self.qr_input, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(200)
        self.progress_bar.setFormat("%v / %m 매칭")
        bottom_layout.addWidget(self.progress_bar)

        parent_layout.addWidget(bottom)

    # ─── 모드 전환 ───
    def _switch_mode(self, mode: str):
        modes = {"atx": 0, "manual": 1, "export": 2}
        idx = modes.get(mode, 0)
        self.stack.setCurrentIndex(idx)

        for btn, m in [(self.btn_atx_mode, "atx"), (self.btn_manual_mode, "manual"),
                       (self.btn_export_mode, "export")]:
            btn.setProperty("accent", "true" if m == mode else "false")
            btn.style().polish(btn)

        self.current_mode = mode
        if mode == "export":
            self._refresh_csv_preview()
