"""Оформление интерфейса приложения (QSS)."""

from __future__ import annotations

ACCENT = "#e23d42"
ACCENT_DARK = "#c22f34"
BG = "#0f1526"
BG_ALT = "#151d33"
PANEL = "#1a2440"
PANEL_ALT = "#212d4d"
BORDER = "#2c3a5e"
TEXT = "#e8edf9"
TEXT_MUTED = "#8e9dc0"

STYLESHEET = f"""
* {{
    font-family: "Segoe UI", "DejaVu Sans", "Arial", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}

QMainWindow, QDialog {{
    background: {BG};
}}

QWidget#Root {{
    background: {BG};
}}

QToolBar {{
    background: {BG_ALT};
    border: none;
    padding: 6px 8px;
    spacing: 4px;
}}
QToolBar QToolButton {{
    background: transparent;
    color: {TEXT};
    padding: 6px 12px;
    border-radius: 7px;
    font-weight: 600;
}}
QToolBar QToolButton:hover {{
    background: {PANEL_ALT};
}}
QToolBar QToolButton:pressed {{
    background: {ACCENT_DARK};
}}
QToolBar::separator {{
    background: {BORDER};
    width: 1px;
    margin: 6px 6px;
}}

QStatusBar {{
    background: {BG_ALT};
    color: {TEXT_MUTED};
    border-top: 1px solid {BORDER};
}}

QSplitter::handle {{
    background: {BG};
    width: 6px;
    height: 6px;
}}
QSplitter::handle:hover {{
    background: {ACCENT};
}}

QGroupBox {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 12px;
    margin-top: 16px;
    padding: 14px 12px 12px 12px;
    font-weight: 700;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 2px 10px;
    color: {TEXT};
    background: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

QLabel {{
    background: transparent;
}}
QLabel#PanelTitle {{
    font-size: 15px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#Hint {{
    color: {TEXT_MUTED};
}}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit, QTimeEdit, QPlainTextEdit, QTextEdit {{
    background: {BG_ALT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 8px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QDateEdit:focus, QTimeEdit:focus {{
    border: 1px solid {ACCENT};
}}
QLineEdit:read-only {{
    color: {TEXT_MUTED};
}}
QComboBox::drop-down, QDateEdit::drop-down, QTimeEdit::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView, QDateEdit QAbstractItemView {{
    background: {PANEL};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
    outline: none;
}}

QPushButton {{
    background: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 600;
}}
QPushButton:hover {{
    background: {BORDER};
}}
QPushButton:pressed {{
    background: {ACCENT_DARK};
}}
QPushButton:disabled {{
    color: {TEXT_MUTED};
    background: {BG_ALT};
}}
QPushButton#Primary {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: white;
    padding: 10px 16px;
    font-size: 14px;
}}
QPushButton#Primary:hover {{
    background: {ACCENT_DARK};
}}
QPushButton#Ghost {{
    background: transparent;
    border: 1px dashed {BORDER};
    color: {TEXT_MUTED};
}}

QListWidget, QTableWidget, QTreeWidget {{
    background: {BG_ALT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    outline: none;
    gridline-color: {BORDER};
    alternate-background-color: {PANEL};
}}
QListWidget::item {{
    padding: 7px 8px;
    border-radius: 6px;
}}
QListWidget::item:selected, QTableWidget::item:selected {{
    background: {ACCENT};
    color: white;
}}
QListWidget::item:hover {{
    background: {PANEL_ALT};
}}
QHeaderView::section {{
    background: {PANEL_ALT};
    color: {TEXT_MUTED};
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    padding: 6px 8px;
    font-weight: 700;
}}
QTableWidget QLineEdit, QTableWidget QComboBox, QTableWidget QSpinBox {{
    border-radius: 5px;
    padding: 3px 5px;
}}

QCheckBox {{
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 17px;
    height: 17px;
    border-radius: 5px;
    border: 1px solid {BORDER};
    background: {BG_ALT};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 10px;
    background: {PANEL};
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_MUTED};
    padding: 8px 16px;
    margin-right: 4px;
    border-radius: 8px;
    font-weight: 600;
}}
QTabBar::tab:selected {{
    background: {PANEL_ALT};
    color: {TEXT};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {ACCENT};
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0; width: 0;
}}

QScrollArea {{
    border: none;
    background: transparent;
}}

QMenu {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px;
}}
QMenu::item {{
    padding: 7px 20px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: {ACCENT};
}}

QToolTip {{
    background: {PANEL_ALT};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px 8px;
    border-radius: 6px;
}}
"""
