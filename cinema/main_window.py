"""Главное окно приложения «Киноафиша»."""

from __future__ import annotations

import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore import QDate, QTime, Qt, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDateEdit, QFileDialog, QFormLayout,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QSizePolicy,
    QSpinBox, QSplitter, QStatusBar, QTimeEdit, QToolBar, QVBoxLayout, QWidget,
)

from . import paths, storage
from .models import CinemaSettings, Movie, Project, Session, new_id
from .poster import SIZE_LABELS, SIZES, THEMES, render_poster, theme_label
from .schedule_text import schedule_text
from .settings_dialog import SettingsDialog
from .widgets import MovieListWidget, PosterDropLabel, PreviewLabel, ScheduleTable

_TIME_RE = re.compile(r"^\s*(\d{1,2})\s*[:.\s]\s*(\d{1,2})?\s*$|^\s*(\d{1,2})\s*$")


def parse_time(text: str) -> Optional[QTime]:
    """Разбирает «9:00», «09.30», «9» и похожие записи в QTime."""
    match = _TIME_RE.match(text)
    if not match:
        return None
    if match.group(3) is not None:
        hours, minutes = int(match.group(3)), 0
    else:
        hours, minutes = int(match.group(1)), int(match.group(2) or 0)
    if 0 <= hours < 24 and 0 <= minutes < 60:
        return QTime(hours, minutes)
    return None


class MainWindow(QMainWindow):
    def __init__(self, settings: Optional[CinemaSettings] = None):
        super().__init__()
        paths.ensure_dirs()
        storage.maybe_migrate_legacy()

        self.settings = settings or storage.load_settings()
        self.movies: List[Movie] = storage.load_movies()
        self.project: Project = self._new_project()
        self.current_movie_id: Optional[str] = None
        self._updating_table = False
        self._dirty = False

        self._autosave = QTimer(self)
        self._autosave.setSingleShot(True)
        self._autosave.setInterval(900)
        self._autosave.timeout.connect(self._do_autosave)

        self.setWindowTitle(f"Киноафиша — {self.settings.name}")
        self.resize(1480, 900)
        self._build_ui()
        self._reload_movie_list()
        self._load_project_into_ui()
        self._reload_project_combo()

    # ------------------------------------------------------------------ проект
    def _new_project(self) -> Project:
        start = date.today()
        end = start + timedelta(days=6)
        project = Project(name="Новая афиша", start_date=start.isoformat(),
                          end_date=end.isoformat())
        project.name = project.default_name()
        return project

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 10, 10, 6)
        layout.setSpacing(8)

        self._build_toolbar()
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Готово")

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_center_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([330, 660, 460])
        layout.addWidget(splitter)

    def _build_toolbar(self) -> None:
        bar = QToolBar("Панель инструментов")
        bar.setMovable(False)
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(bar)

        def add(text: str, slot, shortcut: Optional[str] = None) -> QAction:
            action = QAction(text, self)
            action.triggered.connect(slot)
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))
            bar.addAction(action)
            return action

        add("Новая неделя", self.new_project, "Ctrl+N")
        add("Открыть", self.open_project, "Ctrl+O")
        add("Сохранить", self.save_project, "Ctrl+S")
        add("Сохранить как", self.save_project_as, "Ctrl+Shift+S")
        bar.addSeparator()
        add("Настройки кинотеатра", self.open_settings)
        bar.addSeparator()

        bar.addWidget(QLabel(" Проект: "))
        self.project_combo = QComboBox()
        self.project_combo.setMinimumWidth(200)
        self.project_combo.activated.connect(self._open_project_from_combo)
        bar.addWidget(self.project_combo)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bar.addWidget(spacer)
        add("Скопировать расписание", self.copy_schedule, "Ctrl+Shift+C")
        add("Предпросмотр", self.update_preview, "F5")

    # ------------------------------------------------------------- левая панель
    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        library = QGroupBox("Библиотека фильмов")
        lib_layout = QVBoxLayout(library)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск фильма…")
        self.search_edit.textChanged.connect(self._reload_movie_list)
        lib_layout.addWidget(self.search_edit)

        self.movie_list = MovieListWidget()
        self.movie_list.currentRowChanged.connect(self._select_movie_row)
        self.movie_list.posterDroppedOnRow.connect(self._poster_dropped_on_row)
        lib_layout.addWidget(self.movie_list, 1)

        lib_buttons = QHBoxLayout()
        add_movie = QPushButton("+ Фильм")
        dup = QPushButton("Дублировать")
        delete = QPushButton("Удалить")
        add_movie.clicked.connect(self.add_movie)
        dup.clicked.connect(self.duplicate_movie)
        delete.clicked.connect(self.delete_movie)
        lib_buttons.addWidget(add_movie)
        lib_buttons.addWidget(dup)
        lib_buttons.addWidget(delete)
        lib_layout.addLayout(lib_buttons)
        layout.addWidget(library, 3)

        editor = QGroupBox("Карточка фильма")
        ed = QVBoxLayout(editor)
        self.poster_label = PosterDropLabel()
        self.poster_label.posterDropped.connect(self._poster_dropped_here)
        self.poster_label.clicked.connect(self.choose_poster)
        ed.addWidget(self.poster_label)
        self.poster_info = QLabel("Постер не выбран")
        self.poster_info.setObjectName("Hint")
        self.poster_info.setWordWrap(True)
        ed.addWidget(self.poster_info)

        form = QFormLayout()
        self.title_edit = QLineEdit()
        self.age_edit = QLineEdit()
        self.age_edit.setPlaceholderText("6+")
        self.format_edit = QLineEdit()
        self.format_edit.setPlaceholderText("2D / 3D / IMAX")
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(0, 400)
        self.duration_spin.setSuffix(" мин")
        self.price_spin = QSpinBox()
        self.price_spin.setRange(0, 100000)
        self.price_spin.setSuffix(" ₽")
        self.pushkin_check = QCheckBox("Пушкинская карта")
        form.addRow("Название:", self.title_edit)
        form.addRow("Возраст:", self.age_edit)
        form.addRow("Формат:", self.format_edit)
        form.addRow("Длительность:", self.duration_spin)
        form.addRow("Цена:", self.price_spin)
        form.addRow(self.pushkin_check)
        ed.addLayout(form)

        ed_buttons = QGridLayout()
        ed_buttons.setHorizontalSpacing(6)
        ed_buttons.setVerticalSpacing(6)
        poster_btn = QPushButton("Выбрать файл…")
        paste_poster_btn = QPushButton("Из буфера")
        paste_poster_btn.setToolTip("Вставить изображение из буфера обмена")
        remove_poster_btn = QPushButton("Убрать постер")
        save_movie = QPushButton("Сохранить фильм")
        save_movie.setObjectName("Primary")
        poster_btn.clicked.connect(self.choose_poster)
        paste_poster_btn.clicked.connect(self.paste_poster)
        remove_poster_btn.clicked.connect(self.remove_poster)
        save_movie.clicked.connect(self.save_movie)
        ed_buttons.addWidget(poster_btn, 0, 0)
        ed_buttons.addWidget(paste_poster_btn, 0, 1)
        ed_buttons.addWidget(remove_poster_btn, 1, 0)
        ed_buttons.addWidget(save_movie, 1, 1)
        ed.addLayout(ed_buttons)
        layout.addWidget(editor, 4)
        return panel

    # ----------------------------------------------------------- центр
    def _build_center_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        info = QGroupBox("Неделя")
        info_layout = QHBoxLayout(info)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Название проекта")
        self.name_edit.editingFinished.connect(self._project_meta_changed)
        self.start_date = QDateEdit(QDate.currentDate())
        self.end_date = QDateEdit(QDate.currentDate().addDays(6))
        for widget in (self.start_date, self.end_date):
            widget.setCalendarPopup(True)
            widget.setDisplayFormat("dd.MM.yyyy")
            widget.dateChanged.connect(self._project_meta_changed)
        info_layout.addWidget(QLabel("Название:"))
        info_layout.addWidget(self.name_edit, 1)
        info_layout.addWidget(QLabel("С"))
        info_layout.addWidget(self.start_date)
        info_layout.addWidget(QLabel("ПО"))
        info_layout.addWidget(self.end_date)
        layout.addWidget(info)

        schedule = QGroupBox("Расписание сеансов")
        sched_layout = QVBoxLayout(schedule)

        quick = QHBoxLayout()
        self.quick_movie = QComboBox()
        self.quick_movie.setMinimumWidth(220)
        self.quick_times = QLineEdit()
        self.quick_times.setPlaceholderText("Время сеансов, например 10:00, 12:30, 15:00")
        self.quick_hall = QComboBox()
        self.quick_hall.setEditable(True)
        add_sessions = QPushButton("+ Добавить сеансы")
        add_sessions.clicked.connect(self.add_quick_sessions)
        quick.addWidget(self.quick_movie, 2)
        quick.addWidget(self.quick_times, 2)
        quick.addWidget(self.quick_hall, 1)
        quick.addWidget(add_sessions)
        sched_layout.addLayout(quick)

        self.table = ScheduleTable()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Время", "Фильм", "Зал", "Цена", "ПК"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.movieDropped.connect(self._movie_dropped_on_table)
        sched_layout.addWidget(self.table, 1)

        sched_buttons = QHBoxLayout()
        remove = QPushButton("Удалить сеанс")
        clear = QPushButton("Очистить")
        sort = QPushButton("Сортировать по времени")
        copy_btn = QPushButton("Скопировать расписание")
        copy_btn.setObjectName("Primary")
        remove.clicked.connect(self.remove_session)
        clear.clicked.connect(self.clear_schedule)
        sort.clicked.connect(self.sort_schedule)
        copy_btn.clicked.connect(self.copy_schedule)
        sched_buttons.addWidget(remove)
        sched_buttons.addWidget(clear)
        sched_buttons.addWidget(sort)
        sched_buttons.addStretch()
        sched_buttons.addWidget(copy_btn)
        sched_layout.addLayout(sched_buttons)
        layout.addWidget(schedule, 1)
        return panel

    # ----------------------------------------------------------- правая панель
    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        preview_group = QGroupBox("Афиша")
        preview_layout = QVBoxLayout(preview_group)

        options = QFormLayout()
        self.theme_combo = QComboBox()
        for key, (label, _) in THEMES.items():
            self.theme_combo.addItem(label, key)
        self.size_combo = QComboBox()
        for key, label in SIZE_LABELS.items():
            self.size_combo.addItem(label, key)
        self.theme_combo.currentIndexChanged.connect(self._appearance_changed)
        self.size_combo.currentIndexChanged.connect(self._appearance_changed)
        options.addRow("Стиль:", self.theme_combo)
        options.addRow("Формат:", self.size_combo)
        preview_layout.addLayout(options)

        self.preview = PreviewLabel()
        preview_layout.addWidget(self.preview, 1)

        buttons = QHBoxLayout()
        refresh = QPushButton("Обновить предпросмотр")
        refresh.clicked.connect(self.update_preview)
        export = QPushButton("Сохранить PNG")
        export.setObjectName("Primary")
        export.clicked.connect(self.export_png)
        copy_img = QPushButton("Копировать")
        copy_img.clicked.connect(self.copy_image)
        open_folder = QPushButton("Папка")
        open_folder.clicked.connect(self.open_output)
        buttons.addWidget(refresh)
        buttons.addWidget(export)
        buttons.addWidget(copy_img)
        buttons.addWidget(open_folder)
        preview_layout.addLayout(buttons)
        layout.addWidget(preview_group, 1)
        return panel

    # ============================================================ фильмы
    def _reload_movie_list(self, *_args) -> None:
        query = self.search_edit.text().strip().lower() if hasattr(self, "search_edit") else ""
        self.movie_list.blockSignals(True)
        self.movie_list.clear()
        selected_row = -1
        for movie in self.movies:
            if query and query not in movie.title.lower():
                continue
            item_text = movie.title
            if movie.age:
                item_text += f"  ({movie.age})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, movie.id)
            self.movie_list.addItem(item)
            if movie.id == self.current_movie_id:
                selected_row = self.movie_list.count() - 1
        self.movie_list.blockSignals(False)

        self._reload_movie_combos()
        if selected_row >= 0:
            self.movie_list.setCurrentRow(selected_row)
        elif self.movie_list.count():
            self.movie_list.setCurrentRow(0)
        else:
            self.current_movie_id = None
            self._clear_movie_form()

    def _reload_movie_combos(self) -> None:
        for combo in (self.quick_movie,):
            current = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            for movie in self.movies:
                combo.addItem(movie.title, movie.id)
            if current:
                index = combo.findData(current)
                if index >= 0:
                    combo.setCurrentIndex(index)
            combo.blockSignals(False)
        self._reload_hall_combo()

    def _reload_hall_combo(self) -> None:
        current = self.quick_hall.currentText()
        self.quick_hall.blockSignals(True)
        self.quick_hall.clear()
        self.quick_hall.addItems(self.settings.halls)
        if current:
            self.quick_hall.setCurrentText(current)
        self.quick_hall.blockSignals(False)

    def _movie_by_id(self, movie_id: Optional[str]) -> Optional[Movie]:
        for movie in self.movies:
            if movie.id == movie_id:
                return movie
        return None

    def _select_movie_row(self, row: int) -> None:
        if row < 0:
            return
        item = self.movie_list.item(row)
        if item is None:
            return
        self.current_movie_id = item.data(Qt.ItemDataRole.UserRole)
        movie = self._movie_by_id(self.current_movie_id)
        if movie:
            self._load_movie_form(movie)

    def _load_movie_form(self, movie: Movie) -> None:
        self.title_edit.setText(movie.title)
        self.age_edit.setText(movie.age)
        self.format_edit.setText(movie.format)
        self.duration_spin.setValue(movie.duration)
        self.price_spin.setValue(movie.price)
        self.pushkin_check.setChecked(movie.pushkin)
        poster_path = storage.resolve_poster(movie.poster)
        self.poster_label.set_image(poster_path)
        self.poster_info.setText(poster_path.name if poster_path else "Постер не выбран")

    def _clear_movie_form(self) -> None:
        self.title_edit.clear()
        self.age_edit.clear()
        self.format_edit.clear()
        self.duration_spin.setValue(0)
        self.price_spin.setValue(0)
        self.pushkin_check.setChecked(False)
        self.poster_label.set_image(None)
        self.poster_info.setText("Сначала выберите фильм")

    def _collect_movie_form(self, movie: Movie) -> None:
        movie.title = self.title_edit.text().strip() or "Без названия"
        movie.age = self.age_edit.text().strip()
        movie.format = self.format_edit.text().strip()
        movie.duration = self.duration_spin.value()
        movie.price = self.price_spin.value()
        movie.pushkin = self.pushkin_check.isChecked()

    def add_movie(self) -> None:
        movie = Movie(title="Новый фильм")
        self.movies.append(movie)
        self.current_movie_id = movie.id
        storage.save_movies(self.movies)
        self._reload_movie_list()
        self.statusBar().showMessage("Фильм добавлен", 2500)

    def duplicate_movie(self) -> None:
        movie = self._movie_by_id(self.current_movie_id)
        if not movie:
            return
        copy = Movie.from_dict(movie.to_dict())
        copy.id = new_id()
        copy.title = f"{movie.title} (копия)"
        self.movies.append(copy)
        self.current_movie_id = copy.id
        storage.save_movies(self.movies)
        self._reload_movie_list()

    def delete_movie(self) -> None:
        movie = self._movie_by_id(self.current_movie_id)
        if not movie:
            return
        answer = QMessageBox.question(self, "Удалить фильм",
                                      f"Удалить «{movie.title}» и его сеансы?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.movies = [m for m in self.movies if m.id != movie.id]
        self.project.sessions = [s for s in self.project.sessions if s.movie_id != movie.id]
        self.current_movie_id = None
        storage.save_movies(self.movies)
        self._reload_movie_list()
        self.refresh_table()
        self._mark_dirty()

    def save_movie(self) -> None:
        movie = self._movie_by_id(self.current_movie_id)
        if not movie:
            return
        self._collect_movie_form(movie)
        storage.save_movies(self.movies)
        self._reload_movie_list()
        self.refresh_table()
        self.statusBar().showMessage("Фильм сохранён", 2500)

    def choose_poster(self) -> None:
        movie = self._movie_by_id(self.current_movie_id)
        if not movie:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите постер", str(paths.POSTERS),
            "Изображения (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff)")
        if path:
            self._assign_poster(movie, Path(path))

    def paste_poster(self) -> None:
        movie = self._movie_by_id(self.current_movie_id)
        if not movie:
            QMessageBox.information(self, "Сначала выберите фильм",
                                    "Выберите фильм в библиотеке, затем вставьте постер.")
            return
        clipboard_image = QApplication.clipboard().image()
        if clipboard_image.isNull():
            QMessageBox.information(self, "В буфере нет изображения",
                                    "Скопируйте изображение, затем нажмите «Вставить».")
            return
        paths.OUTPUT.mkdir(parents=True, exist_ok=True)
        temporary = paths.OUTPUT / "_clipboard-poster.png"
        try:
            if not clipboard_image.save(str(temporary), "PNG"):
                raise OSError("Не удалось сохранить изображение из буфера.")
            self._assign_poster(movie, temporary)
        finally:
            temporary.unlink(missing_ok=True)

    def remove_poster(self) -> None:
        movie = self._movie_by_id(self.current_movie_id)
        if not movie:
            return
        movie.poster = ""
        storage.save_movies(self.movies)
        self.poster_label.set_image(None)
        self.poster_info.setText("Постер не выбран")
        self.statusBar().showMessage(f"Постер фильма «{movie.title}» удалён", 2500)

    def _assign_poster(self, movie: Movie, path: Path) -> None:
        try:
            from PIL import Image

            with Image.open(path) as image:
                image.verify()
            movie.poster = storage.import_poster(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить постер:\n{exc}")
            return
        storage.save_movies(self.movies)
        if movie.id == self.current_movie_id:
            poster_path = storage.resolve_poster(movie.poster)
            self.poster_label.set_image(poster_path)
            self.poster_info.setText(poster_path.name if poster_path else "Постер не выбран")
        self.statusBar().showMessage(f"Постер «{movie.title}» обновлён", 2500)

    def _poster_dropped_here(self, path: str) -> None:
        movie = self._movie_by_id(self.current_movie_id)
        if movie:
            self._assign_poster(movie, Path(path))

    def _poster_dropped_on_row(self, row: int, path: str) -> None:
        item = self.movie_list.item(row)
        if item is None:
            return
        movie = self._movie_by_id(item.data(Qt.ItemDataRole.UserRole))
        if movie:
            self._assign_poster(movie, Path(path))
            self.movie_list.setCurrentRow(row)

    # ============================================================ расписание
    def refresh_table(self) -> None:
        self._updating_table = True
        self.table.setRowCount(0)
        for session in self.project.sessions:
            self._append_session_row(session)
        self._updating_table = False

    def _append_session_row(self, session: Session) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        time_edit = QTimeEdit()
        time_edit.setDisplayFormat("HH:mm")
        parsed = QTime.fromString(session.time, "HH:mm")
        time_edit.setTime(parsed if parsed.isValid() else QTime(12, 0))
        time_edit.timeChanged.connect(self._on_table_changed)
        self.table.setCellWidget(row, 0, time_edit)

        movie = self._movie_by_id(session.movie_id)
        movie_combo = QComboBox()
        for candidate in self.movies:
            movie_combo.addItem(candidate.title, candidate.id)
        if movie:
            index = movie_combo.findData(movie.id)
            if index >= 0:
                movie_combo.setCurrentIndex(index)
        movie_combo.currentIndexChanged.connect(
            lambda _idx, w=movie_combo: self._on_session_movie_changed(w))
        self.table.setCellWidget(row, 1, movie_combo)

        hall_combo = QComboBox()
        hall_combo.setEditable(True)
        hall_combo.addItem("")
        hall_combo.addItems(self.settings.halls)
        hall_combo.setCurrentText(session.hall)
        hall_combo.currentTextChanged.connect(self._on_table_changed)
        self.table.setCellWidget(row, 2, hall_combo)

        price_spin = QSpinBox()
        price_spin.setRange(0, 100000)
        price_spin.setSuffix(" ₽")
        price_spin.setValue(session.price if session.price is not None
                            else (movie.price if movie else 0))
        price_spin.valueChanged.connect(self._on_table_changed)
        self.table.setCellWidget(row, 3, price_spin)

        pushkin = QCheckBox()
        pushkin.setChecked(session.pushkin if session.pushkin is not None
                           else (movie.pushkin if movie else False))
        pushkin.stateChanged.connect(self._on_table_changed)
        holder = QWidget()
        holder_layout = QHBoxLayout(holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        holder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        holder_layout.addWidget(pushkin)
        self.table.setCellWidget(row, 4, holder)

    def _on_session_movie_changed(self, combo: QComboBox) -> None:
        if self._updating_table:
            return
        row = self._row_of_widget(combo)
        if row < 0:
            return
        movie = self._movie_by_id(combo.currentData())
        if movie:
            price_spin = self.table.cellWidget(row, 3)
            if isinstance(price_spin, QSpinBox):
                price_spin.setValue(movie.price)
        self._on_table_changed()

    def _row_of_widget(self, widget: QWidget) -> int:
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                if self.table.cellWidget(row, col) is widget:
                    return row
            holder = self.table.cellWidget(row, 4)
            if holder and widget.parent() is holder:
                return row
        return -1

    def _on_table_changed(self, *_args) -> None:
        if self._updating_table:
            return
        sessions: List[Session] = []
        for row in range(self.table.rowCount()):
            time_widget = self.table.cellWidget(row, 0)
            movie_widget = self.table.cellWidget(row, 1)
            hall_widget = self.table.cellWidget(row, 2)
            price_widget = self.table.cellWidget(row, 3)
            holder = self.table.cellWidget(row, 4)
            pushkin_widget = holder.findChild(QCheckBox) if holder else None
            movie_id = movie_widget.currentData() if isinstance(movie_widget, QComboBox) else ""
            movie = self._movie_by_id(movie_id)
            price = price_widget.value() if isinstance(price_widget, QSpinBox) else 0
            checked = pushkin_widget.isChecked() if isinstance(pushkin_widget, QCheckBox) else False
            sessions.append(Session(
                movie_id=movie_id or "",
                time=time_widget.time().toString("HH:mm") if isinstance(time_widget, QTimeEdit) else "12:00",
                hall=hall_widget.currentText().strip() if isinstance(hall_widget, QComboBox) else "",
                price=None if (movie and price == movie.price) else price,
                pushkin=None if (movie and checked == movie.pushkin) else checked,
            ))
        self.project.sessions = sessions
        self._mark_dirty()

    def add_quick_sessions(self) -> None:
        movie_id = self.quick_movie.currentData()
        if not movie_id:
            QMessageBox.information(self, "Нет фильмов",
                                    "Сначала добавьте фильм в библиотеку.")
            return
        raw = self.quick_times.text().replace(";", ",").replace(" ", "")
        times = [t for t in raw.split(",") if t]
        if not times:
            times = ["12:00"]
        hall = self.quick_hall.currentText().strip()
        added = 0
        for value in times:
            parsed = parse_time(value)
            if parsed is None:
                continue
            self.project.sessions.append(Session(movie_id=movie_id,
                                                 time=parsed.toString("HH:mm"),
                                                 hall=hall))
            added += 1
        if not added:
            QMessageBox.warning(self, "Неверное время",
                                "Укажите время в формате ЧЧ:ММ, например 10:00, 12:30")
            return
        self.project.sessions.sort(key=Session.sort_key)
        self.quick_times.clear()
        self.refresh_table()
        self._mark_dirty()
        self.statusBar().showMessage(f"Добавлено сеансов: {added}", 2500)

    def remove_session(self) -> None:
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        current = self.table.currentRow()
        if not rows and current >= 0:
            rows = [current]
        if not rows:
            return
        for row in rows:
            self.table.removeRow(row)
        self._on_table_changed()

    def clear_schedule(self) -> None:
        if not self.project.sessions:
            return
        if QMessageBox.question(self, "Очистить", "Удалить все сеансы?") != QMessageBox.StandardButton.Yes:
            return
        self.project.sessions = []
        self.refresh_table()
        self._mark_dirty()

    def sort_schedule(self) -> None:
        self.project.sessions.sort(key=Session.sort_key)
        self.refresh_table()
        self._mark_dirty()

    def _movie_dropped_on_table(self, payload: str) -> None:
        try:
            movie_id, row_text = payload.split(":")
            row = int(row_text)
        except ValueError:
            return
        movie = self._movie_by_id(movie_id)
        if not movie:
            return
        session = Session(movie_id=movie.id, time="12:00")
        row = max(0, min(row, len(self.project.sessions)))
        self.project.sessions.insert(row, session)
        self.refresh_table()
        self._mark_dirty()

    # ============================================================ афиша
    def _current_theme(self) -> str:
        return self.theme_combo.currentData() or self.project.theme

    def _current_size(self) -> str:
        return self.size_combo.currentData() or self.project.size

    def _movies_by_id(self) -> Dict[str, Movie]:
        return {movie.id: movie for movie in self.movies}

    def update_preview(self) -> None:
        if not self.project.sessions:
            self.preview.clear_image()
            self.preview.setText("Добавьте сеансы,\nчтобы увидеть афишу")
            return
        try:
            image = render_poster(self.settings, self.project, self._movies_by_id(),
                                  self._current_theme(), self._current_size())
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Ошибка генерации", str(exc))
            return
        tmp = paths.OUTPUT / "_preview.png"
        paths.OUTPUT.mkdir(parents=True, exist_ok=True)
        image.save(tmp)
        self.preview.set_image(tmp)
        self.statusBar().showMessage("Предпросмотр обновлён", 2000)

    def export_png(self) -> Path:
        image = render_poster(self.settings, self.project, self._movies_by_id(),
                              self._current_theme(), self._current_size())
        paths.OUTPUT.mkdir(parents=True, exist_ok=True)
        base = storage.slugify(self.project.name) or "afisha"
        out = paths.OUTPUT / f"{base}_{self._current_theme()}_{self._current_size()}.png"
        image.save(out, quality=95)
        self.preview.set_image(out)
        self.statusBar().showMessage(f"Сохранено: {out.name}", 4000)
        QMessageBox.information(self, "Готово", f"Афиша сохранена:\n{out}")
        return out

    def copy_image(self) -> None:
        if not self.project.sessions:
            return
        image = render_poster(self.settings, self.project, self._movies_by_id(),
                              self._current_theme(), self._current_size())
        tmp = paths.OUTPUT / "_clipboard.png"
        paths.OUTPUT.mkdir(parents=True, exist_ok=True)
        image.save(tmp)
        QApplication.clipboard().setPixmap(QPixmap(str(tmp)))
        self.statusBar().showMessage("Изображение скопировано в буфер", 3000)

    def copy_schedule(self) -> None:
        if not self.project.sessions:
            QMessageBox.information(self, "Пусто", "В расписании нет сеансов.")
            return
        text = schedule_text(self.settings, self.project, self._movies_by_id())
        QApplication.clipboard().setText(text)
        self.statusBar().showMessage("Расписание скопировано в буфер обмена", 4000)

    def open_output(self) -> None:
        paths.OUTPUT.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(str(paths.OUTPUT))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                os.system(f'open "{paths.OUTPUT}"')
            else:
                os.system(f'xdg-open "{paths.OUTPUT}"')
        except OSError:
            pass

    def _appearance_changed(self) -> None:
        self.project.theme = self._current_theme()
        self.project.size = self._current_size()
        self._mark_dirty()
        if self.project.sessions:
            self.update_preview()

    # ============================================================ проекты
    def _read_project_meta(self) -> None:
        self.project.name = self.name_edit.text().strip() or self.project.default_name()
        self.project.start_date = self.start_date.date().toString("yyyy-MM-dd")
        self.project.end_date = self.end_date.date().toString("yyyy-MM-dd")

    def _project_meta_changed(self) -> None:
        self._read_project_meta()
        self._mark_dirty()

    def _load_project_into_ui(self) -> None:
        self.name_edit.blockSignals(True)
        self.name_edit.setText(self.project.name)
        self.name_edit.blockSignals(False)
        self.start_date.blockSignals(True)
        self.end_date.blockSignals(True)
        self.start_date.setDate(QDate.fromString(self.project.start_date, "yyyy-MM-dd"))
        self.end_date.setDate(QDate.fromString(self.project.end_date, "yyyy-MM-dd"))
        self.start_date.blockSignals(False)
        self.end_date.blockSignals(False)

        theme_index = self.theme_combo.findData(self.project.theme)
        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentIndex(theme_index if theme_index >= 0 else 0)
        self.theme_combo.blockSignals(False)
        size_index = self.size_combo.findData(self.project.size)
        self.size_combo.blockSignals(True)
        self.size_combo.setCurrentIndex(size_index if size_index >= 0 else 0)
        self.size_combo.blockSignals(False)

        self.refresh_table()
        self.preview.clear_image()
        if self.project.sessions:
            self.update_preview()

    def new_project(self) -> None:
        self._do_autosave()
        name, ok = QInputDialog.getText(self, "Новая неделя", "Название проекта:",
                                        text=self._new_project().default_name())
        if not ok:
            return
        self.project = self._new_project()
        if name.strip():
            self.project.name = name.strip()
        self._load_project_into_ui()
        storage.save_project(self.project)
        self._reload_project_combo()
        self.statusBar().showMessage("Создан новый проект", 2500)

    def open_project(self) -> None:
        start_dir = str(paths.PROJECTS)
        path, _ = QFileDialog.getOpenFileName(self, "Открыть проект", start_dir,
                                              "Проект (*.json)")
        if path:
            self._load_project_file(Path(path))

    def _open_project_from_combo(self) -> None:
        path = self.project_combo.currentData()
        if path:
            self._load_project_file(Path(path))

    def _load_project_file(self, path: Path) -> None:
        project = storage.load_project(path)
        if project is None:
            QMessageBox.warning(self, "Ошибка", "Не удалось прочитать проект.")
            return
        self._do_autosave()
        self.project = project
        self._load_project_into_ui()
        self.statusBar().showMessage(f"Открыт проект «{project.name}»", 3000)

    def _reload_project_combo(self) -> None:
        if not hasattr(self, "project_combo"):
            return
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        current_path = storage.project_path(self.project)
        for path in storage.list_projects():
            project = storage.load_project(path)
            label = project.name if project else path.stem
            self.project_combo.addItem(label, str(path))
            if path == current_path:
                self.project_combo.setCurrentIndex(self.project_combo.count() - 1)
        self.project_combo.blockSignals(False)

    def save_project(self) -> None:
        self._project_meta_changed()
        path = storage.save_project(self.project)
        self._reload_project_combo()
        self._dirty = False
        self.statusBar().showMessage(f"Проект сохранён: {path.name}", 3000)

    def save_project_as(self) -> None:
        name, ok = QInputDialog.getText(self, "Сохранить как", "Название проекта:",
                                        text=self.project.name)
        if not ok or not name.strip():
            return
        self.project.name = name.strip()
        self.name_edit.setText(self.project.name)
        self.save_project()

    def _mark_dirty(self) -> None:
        self._dirty = True
        if hasattr(self, "_autosave"):
            self._autosave.start()

    def _do_autosave(self) -> None:
        if not self._dirty:
            return
        self._read_project_meta()
        storage.save_project(self.project)
        storage.save_settings(self.settings)
        self._dirty = False
        self._reload_project_combo()

    # ============================================================ настройки
    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.settings = dialog.result_settings()
            storage.save_settings(self.settings)
            self._reload_hall_combo()
            self.refresh_table()
            self.setWindowTitle(f"Киноафиша — {self.settings.name}")
            if self.project.sessions:
                self.update_preview()
            self.statusBar().showMessage("Настройки сохранены", 3000)

    # ============================================================ прочее
    def closeEvent(self, event):  # noqa: N802
        self._do_autosave()
        super().closeEvent(event)
