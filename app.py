"""Киноафиша — генератор афиш для кинотеатра.

Точка входа приложения. Запуск: ``python app.py``.
"""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from cinema import __version__
from cinema.main_window import MainWindow
from cinema.ui_theme import STYLESHEET


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Киноафиша")
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
