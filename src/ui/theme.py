# Catppuccin Mocha 다크 테마
BG = '#1e1e2e'
BG2 = '#282840'
BG3 = '#313244'
FG = '#cdd6f4'
FG2 = '#a6adc8'
ACCENT = '#89b4fa'
GREEN = '#a6e3a1'
RED = '#f38ba8'
ORANGE = '#fab387'
PURPLE = '#cba6f7'

DARK_STYLE = f"""
QMainWindow, QWidget {{ background: {BG}; color: {FG}; font-family: 'Malgun Gothic'; font-size: 14px; }}
QTabWidget::pane {{ border: 1px solid {BG3}; background: {BG}; }}
QTabBar::tab {{
    background: {BG2}; color: {FG2}; padding: 6px 16px;
    border-top-left-radius: 4px; border-top-right-radius: 4px;
}}
QTabBar::tab:selected {{ background: {BG}; color: {ACCENT}; border-bottom: 2px solid {ACCENT}; }}
QPushButton {{
    background: {BG2}; color: {FG}; border: 1px solid {BG3};
    border-radius: 4px; padding: 6px 14px; font-size: 14px;
}}
QPushButton:hover {{ background: {BG3}; }}
QPushButton:pressed {{ background: {ACCENT}; color: {BG}; }}
QPushButton[accent="true"] {{ background: {ACCENT}; color: {BG}; font-weight: bold; }}
QPushButton[accent="true"]:hover {{ background: #a0c4ff; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit {{
    background: {BG2}; color: {FG}; border: 1px solid {BG3};
    border-radius: 4px; padding: 5px 8px; font-size: 14px;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {ACCENT};
}}
QLabel {{ color: {FG}; }}
QLabel[header="true"] {{ color: {PURPLE}; font-weight: bold; font-size: 15px; }}
QGroupBox {{
    color: {ACCENT}; border: 1px solid {BG3}; border-radius: 6px;
    margin-top: 8px; padding-top: 14px; font-weight: bold;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}
QSplitter::handle {{ background: {BG3}; }}
QScrollArea {{ border: none; background: {BG}; }}
QTableWidget {{
    background: {BG}; color: {FG}; gridline-color: {BG3};
    selection-background-color: {BG2}; border: 1px solid {BG3};
}}
QTableWidget::item:selected {{ background: {BG2}; color: {ACCENT}; }}
QHeaderView::section {{
    background: {BG2}; color: {FG2}; padding: 4px 8px;
    border: none; border-right: 1px solid {BG3}; border-bottom: 1px solid {BG3};
}}
QStatusBar {{ background: {BG2}; color: {FG2}; }}
QToolBar {{ background: {BG2}; border-bottom: 1px solid {BG3}; spacing: 4px; }}
QTextEdit {{ background: {BG2}; color: {FG}; border: 1px solid {BG3}; border-radius: 4px; }}
QProgressBar {{
    background: {BG2}; border: 1px solid {BG3}; border-radius: 4px;
    text-align: center; color: {FG};
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}
QFrame[card="true"] {{
    background: {BG2}; border: 1px solid {BG3}; border-radius: 6px;
}}
QFrame[card="true"][state="matched"] {{ border: 2px solid {GREEN}; }}
QFrame[card="true"][state="selected"] {{
    border: 2px solid {ACCENT};
    border-left: 4px solid {ACCENT};
    background: #2a2a50;
}}
QFrame[card="true"][state="loaded"] {{ border: 1px solid {ACCENT}; }}
QFrame[card="true"][state="empty"] {{ border: 1px solid {BG3}; }}
"""
