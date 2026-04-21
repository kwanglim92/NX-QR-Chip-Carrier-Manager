"""전체 UI 레이아웃 빌더 (SKILL 12 패턴)."""
from __future__ import annotations

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QPushButton, QLineEdit, QDoubleSpinBox, QDateEdit,
    QGroupBox, QFormLayout, QTextEdit, QProgressBar,
    QStackedWidget, QToolBar, QStatusBar, QTabWidget,
    QComboBox, QSpinBox, QToolButton, QMenu,
)

from src.ui.theme import ACCENT, FG, FG2, BG, BG2, BG3, GREEN, PURPLE
from src.ui.widgets.slot_grid_widget import SlotGridWidget
from src.ui.widgets.image_viewer import ImageViewer
from src.ui.widgets.qr_input_widget import QRInputWidget
from src.ui.widgets.system_logger import SystemLogger
from src.ui.widgets.manual_grid_widget import ManualGridWidget
from src.ui.widgets.history_table import HistoryTable
from src.ui.widgets.slot_detail_table import SlotDetailTable
from src.ui.widgets.stats_dashboard import StatsDashboard


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
        self._build_history_page()

        # 하단: QR 입력 + 진행 상태
        self._build_bottom_bar(main_layout)

        # 상태 바
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("Select a folder to start")

    def _build_toolbar(self, parent_layout):
        toolbar_layout = QHBoxLayout()

        self.btn_atx_mode = QPushButton("ATX Mode")
        self.btn_atx_mode.setProperty("accent", "true")
        self.btn_atx_mode.clicked.connect(lambda: self._switch_mode("atx"))
        toolbar_layout.addWidget(self.btn_atx_mode)

        self.btn_manual_mode = QPushButton("Manual Mode")
        self.btn_manual_mode.clicked.connect(lambda: self._switch_mode("manual"))
        toolbar_layout.addWidget(self.btn_manual_mode)

        self.btn_export_mode = QPushButton("CSV Export")
        self.btn_export_mode.clicked.connect(lambda: self._switch_mode("export"))
        toolbar_layout.addWidget(self.btn_export_mode)

        self.btn_history_mode = QPushButton("History")
        self.btn_history_mode.clicked.connect(lambda: self._switch_mode("history"))
        toolbar_layout.addWidget(self.btn_history_mode)

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
        folder_group = QGroupBox("ATX Result Folder")
        fg_layout = QVBoxLayout(folder_group)

        folder_row = QHBoxLayout()
        self.atx_folder_input = QLineEdit()
        self.atx_folder_input.setReadOnly(True)
        self.atx_folder_input.setPlaceholderText("Select a folder...")
        folder_row.addWidget(self.atx_folder_input)

        self.btn_browse_atx = QPushButton("Browse")
        self.btn_browse_atx.clicked.connect(self._browse_atx_folder)
        folder_row.addWidget(self.btn_browse_atx)
        fg_layout.addLayout(folder_row)

        # 폴더 정보
        info_form = QFormLayout()
        self.lbl_po = QLabel("-")
        self.lbl_probe_type = QLabel("-")
        self.lbl_quantity = QLabel("-")
        info_form.addRow("PO Number:", self.lbl_po)
        info_form.addRow("Probe Type:", self.lbl_probe_type)
        info_form.addRow("Quantity:", self.lbl_quantity)
        fg_layout.addLayout(info_form)

        left_layout.addWidget(folder_group)

        # 이미지 뷰어
        self.atx_img_group = QGroupBox("FreqSweep Image")
        img_group = self.atx_img_group
        img_layout = QVBoxLayout(img_group)
        self.atx_image_viewer = ImageViewer()
        img_layout.addWidget(self.atx_image_viewer)

        left_layout.addWidget(img_group, 1)

        # 로그
        log_group = QGroupBox("Log")
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
        self.slot_grid.slot_reset_qr.connect(self._on_slot_reset_qr)
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
        img_group = QGroupBox("Sweep Image")
        img_layout = QVBoxLayout(img_group)
        self.manual_image_viewer = ImageViewer()
        img_layout.addWidget(self.manual_image_viewer)
        left_layout.addWidget(img_group, 1)

        # 측정값 입력 폼
        data_group = QGroupBox("Measurement Input")
        data_form = QFormLayout(data_group)

        self.manual_freq_input = QDoubleSpinBox()
        self.manual_freq_input.setRange(0, 9999)
        self.manual_freq_input.setDecimals(2)
        self.manual_freq_input.setSpecialValueText(" ")
        data_form.addRow("Frequency (KHz):", self.manual_freq_input)

        self.manual_q_input = QDoubleSpinBox()
        self.manual_q_input.setRange(0, 9999)
        self.manual_q_input.setDecimals(2)
        self.manual_q_input.setSpecialValueText(" ")
        data_form.addRow("Q:", self.manual_q_input)

        left_layout.addWidget(data_group)

        # 적용 버튼
        self.btn_apply_manual = QPushButton("Apply")
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

        ctrl_row.addWidget(QLabel("Columns:"))
        self.manual_col_spin = QSpinBox()
        self.manual_col_spin.setRange(1, 8)
        self.manual_col_spin.setValue(4)
        self.manual_col_spin.setFixedWidth(60)
        self.manual_col_spin.valueChanged.connect(self._on_manual_columns_changed)
        ctrl_row.addWidget(self.manual_col_spin)

        ctrl_row.addStretch()

        btn_load_images = QPushButton("Load")
        btn_load_images.clicked.connect(self._browse_manual_images)
        ctrl_row.addWidget(btn_load_images)

        btn_add_tab = QPushButton("+ Add Tab")
        btn_add_tab.clicked.connect(self._add_probe_tab)
        ctrl_row.addWidget(btn_add_tab)

        btn_del_tab = QPushButton("Delete Tab")
        btn_del_tab.clicked.connect(self._remove_current_probe_tab)
        ctrl_row.addWidget(btn_del_tab)

        btn_reset = QPushButton("Reset")
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

        overview_header = QLabel("Overview")
        overview_header.setProperty("header", "true")
        self._overview_layout.addWidget(overview_header)
        self._overview_layout.addStretch()
        self.manual_tabs.addTab(overview_page, "Overview")

        splitter.addWidget(right)
        splitter.setSizes([400, 600])

        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(splitter)

        self.stack.addWidget(page)  # index 1

    # ─── CSV 내보내기 페이지 ───
    def _build_export_page(self):
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(4, 4, 4, 4)
        page_layout.setSpacing(4)

        # ── Action Bar (상단) ──
        action_bar = QHBoxLayout()
        action_bar.setSpacing(8)

        self.lbl_export_status = QLabel("No data")
        self.lbl_export_status.setStyleSheet(f"color: {FG2}; font-size: 13px;")
        action_bar.addWidget(self.lbl_export_status)

        self.export_progress_bar = QProgressBar()
        self.export_progress_bar.setRange(0, 100)
        self.export_progress_bar.setValue(0)
        self.export_progress_bar.setFixedHeight(16)
        self.export_progress_bar.setFixedWidth(200)
        action_bar.addWidget(self.export_progress_bar)

        action_bar.addStretch()

        # Save CSV 드롭다운
        self.btn_save_csv = QToolButton()
        self.btn_save_csv.setText(" Save CSV ")
        self.btn_save_csv.setProperty("accent", "true")
        self.btn_save_csv.setPopupMode(QToolButton.InstantPopup)
        save_menu = QMenu(self.btn_save_csv)
        save_menu.addAction("CSV Only", self._export_csv)
        save_menu.addAction("CSV + Images", self._export_csv_with_images)
        self.btn_save_csv.setMenu(save_menu)
        action_bar.addWidget(self.btn_save_csv)

        # Upload 드롭다운
        self.btn_upload = QToolButton()
        self.btn_upload.setText(" Upload ")
        self.btn_upload.setPopupMode(QToolButton.InstantPopup)
        upload_menu = QMenu(self.btn_upload)
        upload_menu.addAction("Upload CSV", self._upload_csv_only)
        upload_menu.addAction("Upload CSV + Images", self._upload_csv_with_images)
        self.btn_upload.setMenu(upload_menu)
        action_bar.addWidget(self.btn_upload)

        self.upload_progress = QProgressBar()
        self.upload_progress.setFixedWidth(120)
        self.upload_progress.setFixedHeight(16)
        self.upload_progress.setVisible(False)
        action_bar.addWidget(self.upload_progress)

        page_layout.addLayout(action_bar)

        # ── 좌우 분할 ──
        splitter = QSplitter(Qt.Horizontal)

        # 좌측: 이미지 + 서버 상태
        left = QWidget()
        left.setMinimumWidth(280)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        img_group = QGroupBox("Sweep Image")
        img_layout = QVBoxLayout(img_group)
        self.export_image_viewer = ImageViewer()
        img_layout.addWidget(self.export_image_viewer)
        left_layout.addWidget(img_group, 1)

        # 서버 상태 행
        server_row = QHBoxLayout()
        self.lbl_server_status = QLabel("○ Disconnected")
        self.lbl_server_status.setStyleSheet(f"color: {FG2};")
        server_row.addWidget(self.lbl_server_status)
        server_row.addStretch()

        self.btn_server_toggle = QPushButton("Login")
        self.btn_server_toggle.setFixedWidth(80)
        self.btn_server_toggle.clicked.connect(self._do_login)
        server_row.addWidget(self.btn_server_toggle)

        left_layout.addLayout(server_row)

        splitter.addWidget(left)

        # 우측: 통합 슬롯 테이블
        right = QWidget()
        right.setMinimumWidth(400)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.slot_detail_table = SlotDetailTable()
        self.slot_detail_table.slot_selected.connect(self._on_slot_detail_selected)
        right_layout.addWidget(self.slot_detail_table, 1)

        splitter.addWidget(right)
        splitter.setSizes([350, 650])

        page_layout.addWidget(splitter, 1)

        self.stack.addWidget(page)  # index 2

    # ─── 이력 페이지 ───
    def _build_history_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)

        header = QLabel("History")
        header.setProperty("header", "true")
        layout.addWidget(header)

        # 탭: Records / Statistics
        self.history_tabs = QTabWidget()

        # ── Records 탭 ──
        records_tab = QWidget()
        records_layout = QVBoxLayout(records_tab)
        records_layout.setContentsMargins(4, 8, 4, 4)

        # 필터 행
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Week:"))
        self.history_week_combo = QComboBox()
        self.history_week_combo.setFixedWidth(120)
        self.history_week_combo.currentTextChanged.connect(
            lambda: self._refresh_history()
        )
        filter_row.addWidget(self.history_week_combo)

        filter_row.addSpacing(10)
        filter_row.addWidget(QLabel("Search:"))
        self.history_search_input = QLineEdit()
        self.history_search_input.setPlaceholderText("PO / Probe Type...")
        self.history_search_input.setFixedWidth(200)
        self.history_search_input.returnPressed.connect(self._on_history_search)
        filter_row.addWidget(self.history_search_input)

        btn_search = QPushButton("Search")
        btn_search.clicked.connect(self._on_history_search)
        filter_row.addWidget(btn_search)

        btn_refresh_history = QPushButton("Refresh")
        btn_refresh_history.clicked.connect(self._refresh_history)
        filter_row.addWidget(btn_refresh_history)

        filter_row.addStretch()
        records_layout.addLayout(filter_row)

        # ── 상하 분할: 상단 PO 목록 / 하단 슬롯 상세 ──
        history_splitter = QSplitter(Qt.Vertical)

        # ── 상단: PO 목록 테이블 + 버튼 ──
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(4)

        self.history_table = HistoryTable()
        self.history_table.selection_changed.connect(self._on_history_selection_changed)
        self.history_table.row_selected.connect(self._on_history_row_selected)
        top_layout.addWidget(self.history_table, 1)

        # 버튼 행
        history_btn_row = QHBoxLayout()

        btn_load_record = QPushButton("Load Record")
        btn_load_record.setProperty("accent", "true")
        btn_load_record.clicked.connect(self._on_history_load)
        history_btn_row.addWidget(btn_load_record)

        btn_check_all = QPushButton("Check All")
        btn_check_all.clicked.connect(lambda: self.history_table.check_all())
        history_btn_row.addWidget(btn_check_all)

        btn_uncheck = QPushButton("Uncheck All")
        btn_uncheck.clicked.connect(lambda: self.history_table.uncheck_all())
        history_btn_row.addWidget(btn_uncheck)

        btn_delete_record = QPushButton("Delete")
        btn_delete_record.clicked.connect(self._on_history_delete)
        history_btn_row.addWidget(btn_delete_record)

        self.lbl_selection_count = QLabel("")
        history_btn_row.addWidget(self.lbl_selection_count)

        history_btn_row.addStretch()

        btn_backup = QPushButton("Backup DB")
        btn_backup.clicked.connect(self._on_backup_db)
        history_btn_row.addWidget(btn_backup)

        btn_restore = QPushButton("Restore DB")
        btn_restore.clicked.connect(self._on_restore_db)
        history_btn_row.addWidget(btn_restore)

        top_layout.addLayout(history_btn_row)
        history_splitter.addWidget(top_widget)

        # ── 하단: 슬롯 상세 패널 ──
        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(0, 4, 0, 0)
        detail_layout.setSpacing(4)

        # 상세 헤더: PO 정보 + 폴더 열기 버튼
        detail_header = QHBoxLayout()
        self.lbl_detail_info = QLabel("Select a record to view details")
        self.lbl_detail_info.setStyleSheet(
            f"color: {ACCENT}; font-weight: bold; font-size: 14px;"
        )
        detail_header.addWidget(self.lbl_detail_info)
        detail_header.addStretch()

        self.btn_open_folder = QPushButton("Open Folder")
        self.btn_open_folder.setFixedWidth(110)
        self.btn_open_folder.clicked.connect(self._on_open_source_folder)
        self.btn_open_folder.setEnabled(False)
        detail_header.addWidget(self.btn_open_folder)

        detail_layout.addLayout(detail_header)

        # 좌우 분할: 이미지 뷰어 | 슬롯 테이블
        detail_splitter = QSplitter(Qt.Horizontal)

        self.history_image_viewer = ImageViewer()
        detail_splitter.addWidget(self.history_image_viewer)

        self.history_slot_table = SlotDetailTable()
        self.history_slot_table.slot_selected.connect(self._on_history_slot_selected)
        detail_splitter.addWidget(self.history_slot_table)

        detail_splitter.setSizes([300, 500])
        detail_layout.addWidget(detail_splitter, 1)

        history_splitter.addWidget(detail_widget)
        history_splitter.setSizes([300, 250])

        records_layout.addWidget(history_splitter, 1)

        self.history_tabs.addTab(records_tab, "Records")

        # ── Statistics 탭 ──
        self.stats_dashboard = StatsDashboard()
        self.history_tabs.addTab(self.stats_dashboard, "Statistics")

        layout.addWidget(self.history_tabs, 1)

        self.stack.addWidget(page)  # index 3

    # ─── 하단 바: QR 입력 + 진행률 ───
    def _build_bottom_bar(self, parent_layout):
        self._bottom_bar = QWidget()
        bottom_layout = QHBoxLayout(self._bottom_bar)
        bottom_layout.setContentsMargins(4, 4, 4, 4)

        self.qr_input = QRInputWidget()
        self.qr_input.qr_scanned.connect(self._on_qr_scanned)
        bottom_layout.addWidget(self.qr_input, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(200)
        self.progress_bar.setFormat("%v / %m matched")
        bottom_layout.addWidget(self.progress_bar)

        parent_layout.addWidget(self._bottom_bar)

    # ─── 모드 전환 ───
    def _switch_mode(self, mode: str):
        modes = {"atx": 0, "manual": 1, "export": 2, "history": 3}
        idx = modes.get(mode, 0)
        self.stack.setCurrentIndex(idx)

        for btn, m in [(self.btn_atx_mode, "atx"), (self.btn_manual_mode, "manual"),
                       (self.btn_export_mode, "export"), (self.btn_history_mode, "history")]:
            btn.setProperty("accent", "true" if m == mode else "false")
            btn.style().polish(btn)

        self.current_mode = mode

        # QR 바는 ATX/Manual 모드에서만 표시
        self._bottom_bar.setVisible(mode in ("atx", "manual"))

        if mode == "export":
            self._refresh_export_view()
        elif mode == "history":
            if hasattr(self, '_db_conn'):
                self._refresh_history()
