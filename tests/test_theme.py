from PySide6.QtGui import QPalette

from src.ui import theme


def test_normalize_mode_defaults_to_dark():
    assert theme.normalize_mode(None) == "dark"
    assert theme.normalize_mode("dark") == "dark"
    assert theme.normalize_mode("LIGHT") == "light"
    assert theme.normalize_mode("unexpected") == "dark"


def test_dark_palette_core_values_unchanged():
    assert theme.MOCHA["BG"] == "#1e1e2e"
    assert theme.MOCHA["FG"] == "#cdd6f4"
    assert theme.MOCHA["ACCENT"] == "#89b4fa"


def test_light_and_dark_palettes_are_symmetric():
    assert set(theme.MOCHA) == set(theme.LATTE)


def test_build_palette_uses_theme_colors():
    pal = theme.build_palette(theme.LATTE)
    assert pal.color(QPalette.ColorRole.Window).name() == "#ffffff"
    assert pal.color(QPalette.ColorRole.WindowText).name() == "#000000"
    assert pal.color(QPalette.ColorRole.Link).name() == "#1677c5"
