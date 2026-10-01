"""Пользовательские виджеты: предпросмотр, Drag&Drop постеров и фильмов."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QMimeData, QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QDrag, QPixmap
from PyQt6.QtWidgets import QAbstractItemView, QLabel, QListWidget, QTableWidget

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
MOVIE_MIME = "application/x-cinema-movie"


def _image_paths(mime: QMimeData) -> list[str]:
    if not mime.hasUrls():
        return []
    paths = []
    for url in mime.urls():
        local = url.toLocalFile()
        if local and Path(local).suffix.lower() in IMAGE_SUFFIXES:
            paths.append(local)
    return paths


class PosterDropLabel(QLabel):
    """Область предпросмотра постера, принимающая файлы перетаскиванием."""

    posterDropped = pyqtSignal(str)
    clicked = pyqtSignal()

    def __init__(self, text: str = "Выберите файл или перетащите постер сюда", parent=None):
        super().__init__(text, parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMinimumHeight(190)
        self._pixmap: Optional[QPixmap] = None
        self.setObjectName("PosterDrop")
        self.setToolTip("Нажмите, чтобы выбрать файл, или перетащите изображение сюда")
        self._apply_style()

    def _apply_style(self, dropping: bool = False) -> None:
        if dropping:
            border, background, color = "2px dashed #e23d42", "#1a2440", "#e8edf9"
        elif self._pixmap:
            border, background, color = "1px solid #2c3a5e", "#0b1120", "#8e9dc0"
        else:
            border, background, color = "2px dashed #2c3a5e", "#151d33", "#8e9dc0"
        self.setStyleSheet(
            f"border: {border}; border-radius: 10px; background: {background}; color: {color};"
        )

    def set_image(self, path: Optional[Path]) -> None:
        if path and Path(path).exists():
            pix = QPixmap(str(path))
            if not pix.isNull():
                self._pixmap = pix
                self.setText("")
                self._apply_style()
                self._rescale()
                return
        self._pixmap = None
        self.setPixmap(QPixmap())
        self.setText("Выберите файл или перетащите постер сюда")
        self._apply_style()

    def _rescale(self) -> None:
        if self._pixmap is None:
            return
        self.setPixmap(self._pixmap.scaled(
            max(120, self.width() - 16), max(120, self.height() - 16),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._rescale()

    def dragEnterEvent(self, event):  # noqa: N802
        if _image_paths(event.mimeData()):
            event.acceptProposedAction()
            self._apply_style(dropping=True)

    def dragLeaveEvent(self, event):  # noqa: N802
        self._apply_style()

    def dropEvent(self, event):  # noqa: N802
        paths = _image_paths(event.mimeData())
        if paths:
            self.posterDropped.emit(paths[0])
            event.acceptProposedAction()
        self.dragLeaveEvent(event)


class PreviewLabel(QLabel):
    """Масштабируемый предпросмотр готовой афиши."""

    def __init__(self, parent=None):
        super().__init__("Нажмите «Обновить предпросмотр»", parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumWidth(360)
        self.setStyleSheet("background: #0b1120; border-radius: 12px; color: #8e9dc0;")
        self._pixmap: Optional[QPixmap] = None

    def set_image(self, path_or_pixmap) -> None:
        self._pixmap = (path_or_pixmap if isinstance(path_or_pixmap, QPixmap)
                        else QPixmap(str(path_or_pixmap)))
        if self._pixmap.isNull():
            self._pixmap = None
            return
        self._rescale()

    def clear_image(self) -> None:
        self._pixmap = None
        self.setPixmap(QPixmap())
        self.setText("Нажмите «Обновить предпросмотр»")

    def _rescale(self) -> None:
        if self._pixmap is None:
            return
        self.setPixmap(self._pixmap.scaled(
            max(100, self.width() - 12), max(100, self.height() - 12),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._rescale()


class MovieListWidget(QListWidget):
    """Список фильмов: перетаскивание постера на строку и фильма в расписание."""

    posterDroppedOnRow = pyqtSignal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

    def dragEnterEvent(self, event):  # noqa: N802
        if _image_paths(event.mimeData()):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):  # noqa: N802
        if _image_paths(event.mimeData()):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):  # noqa: N802
        paths = _image_paths(event.mimeData())
        if paths:
            row = self.row(self.itemAt(event.position().toPoint()))
            if row >= 0:
                self.posterDroppedOnRow.emit(row, paths[0])
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def startDrag(self, supported_actions):  # noqa: N802
        item = self.currentItem()
        if item is None:
            return
        mime = QMimeData()
        mime.setData(MOVIE_MIME, str(item.data(Qt.ItemDataRole.UserRole)).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)


class ScheduleTable(QTableWidget):
    """Таблица сеансов, принимающая фильм перетаскиванием из библиотеки."""

    movieDropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasFormat(MOVIE_MIME):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):  # noqa: N802
        if event.mimeData().hasFormat(MOVIE_MIME):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):  # noqa: N802
        if event.mimeData().hasFormat(MOVIE_MIME):
            movie_id = bytes(event.mimeData().data(MOVIE_MIME)).decode("utf-8")
            row = self.rowAt(int(event.position().y()))
            if row < 0:
                row = self.rowCount()
            self.movieDropped.emit(f"{movie_id}:{row}")
            event.acceptProposedAction()
            return
        super().dropEvent(event)
