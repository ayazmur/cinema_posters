"""Сохранение и загрузка данных: фильмы, настройки, недельные проекты."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import paths
from .models import CinemaSettings, Movie, Project, new_id


# --------------------------------------------------------------------------- #
#  Утилиты JSON
# --------------------------------------------------------------------------- #
def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


# --------------------------------------------------------------------------- #
#  Настройки
# --------------------------------------------------------------------------- #
def load_settings() -> CinemaSettings:
    return CinemaSettings.from_dict(_load_json(paths.SETTINGS_FILE, {}))


def save_settings(settings: CinemaSettings) -> None:
    _save_json(paths.SETTINGS_FILE, settings.to_dict())


# --------------------------------------------------------------------------- #
#  Библиотека фильмов
# --------------------------------------------------------------------------- #
def load_movies() -> List[Movie]:
    raw = _load_json(paths.MOVIES_FILE, [])
    movies: List[Movie] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                movies.append(Movie.from_dict(_normalize_legacy(item)))
    return movies


def save_movies(movies: List[Movie]) -> None:
    _save_json(paths.MOVIES_FILE, [m.to_dict() for m in movies])


def _normalize_legacy(item: Dict[str, Any]) -> Dict[str, Any]:
    """Поддержка старого формата, где поля фильма и сеанса были в одной записи."""
    if "id" in item and "price" in item:
        return item
    value = dict(item)
    value.setdefault("id", new_id())
    return value


# --------------------------------------------------------------------------- #
#  Проекты (недельные афиши)
# --------------------------------------------------------------------------- #
_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def slugify(text: str) -> str:
    text = _INVALID.sub("", text).strip().strip(".")
    text = re.sub(r"\s+", " ", text)
    return text or "proekt"


def project_path(project: Project) -> Path:
    return paths.PROJECTS / f"{slugify(project.name)}.json"


def save_project(project: Project) -> Path:
    path = project_path(project)
    _save_json(path, project.to_dict())
    return path


def delete_project_file(project: Project) -> None:
    try:
        project_path(project).unlink()
    except OSError:
        pass


def list_projects() -> List[Path]:
    if not paths.PROJECTS.exists():
        return []
    return sorted(paths.PROJECTS.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def load_project(path: Path) -> Optional[Project]:
    data = _load_json(path, None)
    if not isinstance(data, dict):
        return None
    return Project.from_dict(data)


# --------------------------------------------------------------------------- #
#  Постеры
# --------------------------------------------------------------------------- #
def import_poster(source: Path) -> str:
    """Копирует постер в папку posters/ и возвращает относительный путь."""
    paths.POSTERS.mkdir(parents=True, exist_ok=True)
    source = Path(source)
    target = paths.POSTERS / source.name
    counter = 1
    while target.exists() and target.resolve() != source.resolve():
        target = paths.POSTERS / f"{source.stem}_{counter}{source.suffix}"
        counter += 1
    if source.resolve() != target.resolve():
        shutil.copy2(source, target)
    try:
        return str(target.relative_to(paths.BASE)).replace("\\", "/")
    except ValueError:
        return str(target)


def resolve_poster(rel: str) -> Optional[Path]:
    """Возвращает существующий абсолютный путь к постеру или None."""
    if not rel:
        return None
    path = Path(rel)
    if not path.is_absolute():
        path = paths.BASE / rel
    return path if path.exists() else None


# --------------------------------------------------------------------------- #
#  Миграция старого формата
# --------------------------------------------------------------------------- #
def maybe_migrate_legacy() -> None:
    """Переносит data/schedule.json в projects/ и создаёт настройки по умолчанию."""
    legacy = paths.DATA / "schedule.json"
    if not paths.MOVIES_FILE.exists() and legacy.exists():
        data = _load_json(legacy, [])
        if isinstance(data, list):
            movies = [Movie.from_dict(_normalize_legacy(d)) for d in data if isinstance(d, dict)]
            save_movies(movies)
