"""Application theme tokens and QSS.

Theme selection is read at import time from
``QSettings("ParkSystems", "McQrManager")`` key ``app/theme``. Most widgets import
color values directly from this module, so theme changes are applied after an app
restart rather than live-swapped.
"""
from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QPalette

THEME_ORG = "ParkSystems"
THEME_APP = "McQrManager"
THEME_KEY = "app/theme"


MOCHA = {
    "BG": "#1e1e2e",
    "BG2": "#282840",
    "BG3": "#313244",
    "BG4": "#45475a",
    "FG": "#cdd6f4",
    "FG2": "#a6adc8",
    "FG3": "#9399b2",
    "ACCENT": "#89b4fa",
    "GREEN": "#a6e3a1",
    "RED": "#f38ba8",
    "ORANGE": "#fab387",
    "YELLOW": "#f9e2af",
    "PURPLE": "#cba6f7",
    "TEAL": "#94e2d5",
    "EMPHASIS": "#89b4fa",
    "HEADER_BG": "#282840",
    "HEADER_FG": "#a6adc8",
    "VHEADER_BG": "#282840",
    "VHEADER_FG": "#a6adc8",
    "ACCENT_HOVER": "#a0c4ff",
    "CARD_SELECTED_BG": "#2a2a50",
    "SELECT_BG": "#282840",
    "SELECT_FG": "#89b4fa",
    "BADGE_FG": "#1e1e2e",
}

LATTE = {
    "BG": "#ffffff",
    "BG2": "#f2f2f2",
    "BG3": "#e3e8ef",
    "BG4": "#a6a6a6",
    "FG": "#000000",
    "FG2": "#595959",
    "FG3": "#7f7f7f",
    "ACCENT": "#1677c5",
    "GREEN": "#2e8b4f",
    "RED": "#c62b3d",
    "ORANGE": "#e07b1e",
    "YELLOW": "#c9961c",
    "PURPLE": "#124ca2",
    "TEAL": "#3dbdff",
    "EMPHASIS": "#002060",
    "HEADER_BG": "#002060",
    "HEADER_FG": "#ffffff",
    "VHEADER_BG": "#ffffff",
    "VHEADER_FG": "#595959",
    "ACCENT_HOVER": "#1263a8",
    "CARD_SELECTED_BG": "#eaf3fb",
    "SELECT_BG": "#d7e9f8",
    "SELECT_FG": "#000000",
    "BADGE_FG": "#ffffff",
}

_CHART_CYCLE_DARK = [
    "#89b4fa", "#a6e3a1", "#fab387", "#cba6f7", "#f38ba8",
    "#f5c2e7", "#94e2d5", "#f9e2af",
]
_CHART_CYCLE_LIGHT = [
    "#002060", "#124ca2", "#1677c5", "#3dbdff", "#44e6e7",
    "#73fcd4", "#c62b3d", "#595959",
]


def normalize_mode(value: object) -> str:
    """Return ``light`` only for an explicit light value, otherwise ``dark``."""
    return "light" if str(value).lower() == "light" else "dark"


def read_theme_mode() -> str:
    """Read the persisted theme mode, defaulting to dark."""
    try:
        value = QSettings(THEME_ORG, THEME_APP).value(THEME_KEY, "dark")
    except Exception:
        value = "dark"
    return normalize_mode(value)


def palette_tokens(mode: str) -> dict[str, str]:
    return LATTE if normalize_mode(mode) == "light" else MOCHA


MODE = read_theme_mode()
_P = palette_tokens(MODE)

BG = _P["BG"]
BG2 = _P["BG2"]
BG3 = _P["BG3"]
BG4 = _P["BG4"]
FG = _P["FG"]
FG2 = _P["FG2"]
FG3 = _P["FG3"]
ACCENT = _P["ACCENT"]
GREEN = _P["GREEN"]
RED = _P["RED"]
ORANGE = _P["ORANGE"]
YELLOW = _P["YELLOW"]
PURPLE = _P["PURPLE"]
TEAL = _P["TEAL"]
EMPHASIS = _P["EMPHASIS"]
HEADER_BG = _P["HEADER_BG"]
HEADER_FG = _P["HEADER_FG"]
VHEADER_BG = _P["VHEADER_BG"]
VHEADER_FG = _P["VHEADER_FG"]
ACCENT_HOVER = _P["ACCENT_HOVER"]
CARD_SELECTED_BG = _P["CARD_SELECTED_BG"]
SELECT_BG = _P["SELECT_BG"]
SELECT_FG = _P["SELECT_FG"]
BADGE_FG = _P["BADGE_FG"]
CHART_CYCLE = _CHART_CYCLE_LIGHT if MODE == "light" else _CHART_CYCLE_DARK


def _build_style(p: dict[str, str]) -> str:
    """Build a QSS stylesheet from a palette token mapping."""
    bg = p["BG"]
    bg2 = p["BG2"]
    bg3 = p["BG3"]
    bg4 = p["BG4"]
    fg = p["FG"]
    fg2 = p["FG2"]
    accent = p["ACCENT"]
    green = p["GREEN"]
    red = p["RED"]
    purple = p["PURPLE"]
    teal = p["TEAL"]
    header_bg = p["HEADER_BG"]
    header_fg = p["HEADER_FG"]
    vheader_bg = p["VHEADER_BG"]
    vheader_fg = p["VHEADER_FG"]
    accent_hover = p["ACCENT_HOVER"]
    card_selected_bg = p["CARD_SELECTED_BG"]
    select_bg = p["SELECT_BG"]
    select_fg = p["SELECT_FG"]

    return f"""
QMainWindow, QWidget {{
    background: {bg};
    color: {fg};
    font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
    font-size: 14px;
}}
QTabWidget::pane {{ border: 1px solid {bg3}; background: {bg}; }}
QTabBar::tab {{
    background: {bg2}; color: {fg2}; padding: 6px 16px;
    border-top-left-radius: 4px; border-top-right-radius: 4px;
}}
QTabBar::tab:selected {{
    background: {bg}; color: {accent}; border-bottom: 2px solid {accent};
}}
QTabBar::tab:hover {{ background: {bg3}; color: {fg}; }}
QPushButton, QToolButton {{
    background: {bg2}; color: {fg}; border: 1px solid {bg3};
    border-radius: 4px; padding: 6px 14px; font-size: 14px;
}}
QPushButton:hover, QToolButton:hover {{ background: {bg3}; border-color: {accent}; }}
QPushButton:pressed, QToolButton:pressed {{ background: {accent}; color: {bg}; }}
QPushButton[accent="true"] {{
    background: {accent}; color: {bg}; font-weight: bold;
}}
QPushButton[accent="true"]:hover {{ background: {accent_hover}; }}
QPushButton[accent="true"]:disabled {{ background: {bg3}; color: {fg2}; font-weight: normal; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit {{
    background: {bg2}; color: {fg}; border: 1px solid {bg3};
    border-radius: 4px; padding: 5px 8px; font-size: 14px;
    selection-background-color: {accent}; selection-color: {bg};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus, QDateEdit:focus {{
    border: 1px solid {accent};
}}
QComboBox QAbstractItemView {{
    background: {bg2}; color: {fg};
    selection-background-color: {select_bg}; selection-color: {select_fg};
    border: 1px solid {bg3};
}}
QLabel {{ color: {fg}; }}
QLabel[header="true"] {{ color: {purple}; font-weight: bold; font-size: 15px; }}
QCheckBox {{ color: {fg}; spacing: 6px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border: 1px solid {bg4}; border-radius: 3px; background: {bg2};
}}
QCheckBox::indicator:hover {{ border-color: {accent}; }}
QCheckBox::indicator:checked {{ background: {accent}; border-color: {accent}; }}
QGroupBox {{
    color: {accent}; border: 1px solid {bg3}; border-radius: 6px;
    margin-top: 8px; padding-top: 14px; font-weight: bold;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}
QSplitter::handle {{ background: {bg3}; }}
QScrollArea {{ border: none; background: {bg}; }}
QTableWidget, QTableView {{
    background: {bg}; alternate-background-color: {bg2}; color: {fg};
    gridline-color: {bg3}; selection-background-color: {select_bg};
    selection-color: {select_fg}; border: 1px solid {bg3};
}}
QTableWidget::item:selected, QTableView::item:selected {{
    background: {select_bg}; color: {select_fg};
}}
QHeaderView::section {{
    padding: 4px 8px; border: none;
    border-right: 1px solid {bg3}; border-bottom: 1px solid {bg3};
}}
QHeaderView::section:horizontal {{ background: {header_bg}; color: {header_fg}; }}
QHeaderView::section:vertical {{ background: {vheader_bg}; color: {vheader_fg}; }}
QStatusBar {{ background: {bg2}; color: {fg2}; }}
QToolBar {{ background: {bg2}; border-bottom: 1px solid {bg3}; spacing: 4px; }}
QTextEdit {{
    background: {bg2}; color: {fg}; border: 1px solid {bg3};
    border-radius: 4px;
}}
QProgressBar {{
    background: {bg2}; border: 1px solid {bg3}; border-radius: 4px;
    text-align: center; color: {fg};
}}
QProgressBar::chunk {{ background: {accent}; border-radius: 3px; }}
QFrame[card="true"] {{
    background: {bg2}; border: 1px solid {bg3}; border-radius: 6px;
}}
QFrame[card="true"][state="matched"] {{ border: 2px solid {green}; }}
QFrame[card="true"][state="selected"] {{
    border: 2px solid {accent};
    border-left: 4px solid {accent};
    background: {card_selected_bg};
}}
QFrame[card="true"][state="loaded"] {{ border: 1px solid {accent}; }}
QFrame[card="true"][state="empty"] {{ border: 1px solid {bg3}; }}
QMenu {{
    background: {bg2}; color: {fg}; border: 1px solid {bg3};
}}
QMenu::item:selected {{ background: {select_bg}; color: {select_fg}; }}
QToolTip {{
    background: {bg2}; color: {fg}; border: 1px solid {bg3};
    padding: 4px 8px; border-radius: 4px;
}}
QScrollBar:vertical {{ background: {bg}; width: 10px; }}
QScrollBar::handle:vertical {{
    background: {bg3}; min-height: 28px; border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{ background: {bg4}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QDialog {{ background: {bg}; color: {fg}; }}
QMessageBox QLabel {{ color: {fg}; }}
QPushButton[danger="true"] {{ background: {red}; color: {bg}; font-weight: bold; }}
QPushButton[success="true"] {{ background: {green}; color: {bg}; font-weight: bold; }}
QLabel[status_ok="true"] {{ color: {green}; font-weight: bold; }}
QLabel[status_error="true"] {{ color: {red}; font-weight: bold; }}
QLabel[status_info="true"] {{ color: {teal}; font-weight: bold; }}
"""


def build_palette(p: dict[str, str]) -> QPalette:
    """Build an application QPalette matching the active stylesheet."""
    pal = QPalette()
    bg = QColor(p["BG"])
    bg2 = QColor(p["BG2"])
    bg3 = QColor(p["BG3"])
    fg = QColor(p["FG"])
    fg2 = QColor(p["FG2"])
    accent = QColor(p["ACCENT"])
    select_fg = QColor(p["SELECT_FG"])
    role = QPalette.ColorRole
    group = QPalette.ColorGroup

    pal.setColor(role.Window, bg)
    pal.setColor(role.WindowText, fg)
    pal.setColor(role.Base, bg)
    pal.setColor(role.AlternateBase, bg2)
    pal.setColor(role.Text, fg)
    pal.setColor(role.ToolTipBase, bg2)
    pal.setColor(role.ToolTipText, fg)
    pal.setColor(role.Button, bg2)
    pal.setColor(role.ButtonText, fg)
    pal.setColor(role.BrightText, QColor("#ffffff"))
    pal.setColor(role.Highlight, bg3)
    pal.setColor(role.HighlightedText, select_fg)
    pal.setColor(role.PlaceholderText, fg2)
    pal.setColor(role.Link, accent)
    for disabled_role in (role.Text, role.WindowText, role.ButtonText):
        pal.setColor(group.Disabled, disabled_role, fg2)
    return pal


DARK_STYLE = _build_style(MOCHA)
LIGHT_STYLE = _build_style(LATTE)
ACTIVE_STYLE = LIGHT_STYLE if MODE == "light" else DARK_STYLE
ACTIVE_PALETTE = build_palette(_P)
