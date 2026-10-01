"""Диалог настроек кинотеатра: название, логотип, цвета, контакты."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QColorDialog, QDialog, QFileDialog, QFormLayout, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from .models import CinemaSettings
from .storage import import_poster

COLOR_FIELDS = [
    ("primary", "Основной цвет"),
    ("secondary", "Дополнительный"),
    ("accent", "Акцент"),
    ("background", "Фон"),
    ("surface", "Карточки"),
    ("text", "Текст на фоне"),
    ("text_dark", "Тёмный текст"),
]


class _ColorButton(QPushButton):
    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._color = color or "#ffffff"
        self.setFixedSize(46, 28)
        self.clicked.connect(self._pick)
        self._apply()

    def _apply(self) -> None:
        self.setStyleSheet(
            f"background:{self._color}; border:1px solid #2c3a5e; border-radius:6px;"
        )
        self.setToolTip(self._color)

    def _pick(self) -> None:
        color = QColorDialog.getColor(QColor(self._color), self, "Выберите цвет")
        if color.isValid():
            self._color = color.name()
            self._apply()

    def color(self) -> str:
        return self._color


class SettingsDialog(QDialog):
    def __init__(self, settings: CinemaSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки кинотеатра")
        self.setMinimumWidth(520)
        self.settings = settings

        root = QVBoxLayout(self)

        info = QFormLayout()
        self.name_edit = QLineEdit(settings.name)
        self.slogan_edit = QLineEdit(settings.slogan)
        self.footer_edit = QLineEdit(settings.footer)
        self.phone_edit = QLineEdit(settings.phone)
        self.phone_edit.setPlaceholderText("+7 ...")
        self.site_edit = QLineEdit(settings.site)
        self.site_edit.setPlaceholderText("example.ru")
        self.halls_edit = QLineEdit(", ".join(settings.halls))
        self.halls_edit.setPlaceholderText("Зал 1, Зал 2, VIP")

        info.addRow("Название:", self.name_edit)
        info.addRow("Слоган:", self.slogan_edit)
        info.addRow("Подвал афиши:", self.footer_edit)
        info.addRow("Телефон:", self.phone_edit)
        info.addRow("Сайт:", self.site_edit)
        info.addRow("Залы:", self.halls_edit)
        root.addLayout(info)

        logo_row = QHBoxLayout()
        self.logo_edit = QLineEdit(settings.logo)
        self.logo_edit.setReadOnly(True)
        browse = QPushButton("Логотип…")
        clear = QPushButton("Убрать")
        browse.clicked.connect(self._pick_logo)
        clear.clicked.connect(lambda: self.logo_edit.setText(""))
        logo_row.addWidget(QLabel("Логотип:"))
        logo_row.addWidget(self.logo_edit, 1)
        logo_row.addWidget(browse)
        logo_row.addWidget(clear)
        root.addLayout(logo_row)

        colors = QGridLayout()
        self.color_buttons: dict[str, _ColorButton] = {}
        for i, (key, label) in enumerate(COLOR_FIELDS):
            button = _ColorButton(getattr(settings, key))
            self.color_buttons[key] = button
            row, col = divmod(i, 2)
            colors.addWidget(QLabel(label + ":"), row, col * 2)
            colors.addWidget(button, row, col * 2 + 1)
        root.addLayout(colors)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Отмена")
        save = QPushButton("Сохранить")
        save.setObjectName("Primary")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

    def _pick_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите логотип", "", "Images (*.png *.jpg *.jpeg *.webp *.svg)"
        )
        if path:
            try:
                self.logo_edit.setText(import_poster(Path(path)))
            except OSError:
                self.logo_edit.setText(path)

    def result_settings(self) -> CinemaSettings:
        halls = [h.strip() for h in self.halls_edit.text().split(",") if h.strip()]
        data = self.settings.to_dict()
        data.update({
            "name": self.name_edit.text().strip() or self.settings.name,
            "slogan": self.slogan_edit.text().strip(),
            "footer": self.footer_edit.text().strip(),
            "phone": self.phone_edit.text().strip(),
            "site": self.site_edit.text().strip(),
            "logo": self.logo_edit.text().strip(),
            "halls": halls or self.settings.halls,
        })
        for key, button in self.color_buttons.items():
            data[key] = button.color()
        return CinemaSettings.from_dict(data)
