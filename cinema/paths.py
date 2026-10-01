"""Определение путей для запуска из исходников и из собранного .exe.

* :func:`app_dir` — папка, рядом с которой хранятся пользовательские данные
  (data/, projects/, posters/, output/). При запуске из .exe это папка с
  исполняемым файлом, чтобы данные не терялись между запусками.
* :func:`bundle_dir` — папка с ресурсами, встроенными в сборку (assets/).
"""

from __future__ import annotations

import sys
from pathlib import Path


def _frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """Каталог для записи пользовательских данных."""
    if _frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def bundle_dir() -> Path:
    """Каталог со встроенными ресурсами (только чтение)."""
    if _frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


BASE = app_dir()
RESOURCES = bundle_dir()

DATA = BASE / "data"
PROJECTS = BASE / "projects"
POSTERS = BASE / "posters"
OUTPUT = BASE / "output"
ASSETS = RESOURCES / "assets"

SETTINGS_FILE = DATA / "settings.json"
MOVIES_FILE = DATA / "movies.json"


def ensure_dirs() -> None:
    for path in (DATA, PROJECTS, POSTERS, OUTPUT):
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
