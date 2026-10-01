"""Модели данных: фильмы, сеансы, настройки кинотеатра и недельный проект."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional


def new_id() -> str:
    return uuid.uuid4().hex[:10]


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "да", "yes", "on"}
    return bool(value)


# --------------------------------------------------------------------------- #
#  Фильм
# --------------------------------------------------------------------------- #
@dataclass
class Movie:
    id: str = field(default_factory=new_id)
    title: str = "Новый фильм"
    age: str = "6+"
    price: int = 200
    duration: int = 0
    pushkin: bool = False
    poster: str = ""
    format: str = ""  # 2D/3D/IMAX и т.п.

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Movie":
        return cls(
            id=str(data.get("id") or new_id()),
            title=str(data.get("title") or "Без названия"),
            age=str(data.get("age") or ""),
            price=_as_int(data.get("price"), 200),
            duration=_as_int(data.get("duration"), 0),
            pushkin=_as_bool(data.get("pushkin")),
            poster=str(data.get("poster") or ""),
            format=str(data.get("format") or ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "age": self.age,
            "price": self.price,
            "duration": self.duration,
            "pushkin": self.pushkin,
            "poster": self.poster,
            "format": self.format,
        }


# --------------------------------------------------------------------------- #
#  Сеанс
# --------------------------------------------------------------------------- #
@dataclass
class Session:
    movie_id: str = ""
    time: str = "12:00"
    hall: str = ""
    price: Optional[int] = None       # переопределение цены фильма
    pushkin: Optional[bool] = None    # переопределение флага ПК

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        price = data.get("price")
        pushkin = data.get("pushkin")
        return cls(
            movie_id=str(data.get("movie_id") or ""),
            time=str(data.get("time") or "12:00"),
            hall=str(data.get("hall") or ""),
            price=_as_int(price) if price not in (None, "") else None,
            pushkin=_as_bool(pushkin) if pushkin is not None else None,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "movie_id": self.movie_id,
            "time": self.time,
            "hall": self.hall,
            "price": self.price,
            "pushkin": self.pushkin,
        }

    def sort_key(self) -> int:
        try:
            h, m = self.time.replace(".", ":").split(":")[:2]
            return int(h) * 60 + int(m)
        except (ValueError, AttributeError):
            return 0


# --------------------------------------------------------------------------- #
#  Настройки кинотеатра
# --------------------------------------------------------------------------- #
@dataclass
class CinemaSettings:
    name: str = "КИНОТЕАТР «ЮБИЛЕЙНЫЙ»"
    slogan: str = "ЛУЧШИЕ НОВИНКИ КИНО"
    logo: str = ""
    primary: str = "#e23d42"
    secondary: str = "#1677ad"
    accent: str = "#f0a028"
    background: str = "#0a1533"
    surface: str = "#ffffff"
    text: str = "#ffffff"
    text_dark: str = "#101b3a"
    footer: str = "БИЛЕТЫ В КАССЕ И НА САЙТЕ"
    phone: str = ""
    site: str = ""
    halls: List[str] = field(default_factory=lambda: ["Зал 1", "Зал 2"])

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CinemaSettings":
        base = cls()
        if not isinstance(data, dict):
            return base
        halls = data.get("halls")
        return cls(
            name=str(data.get("name") or base.name),
            slogan=str(data.get("slogan") or base.slogan),
            logo=str(data.get("logo") or ""),
            primary=str(data.get("primary") or base.primary),
            secondary=str(data.get("secondary") or base.secondary),
            accent=str(data.get("accent") or base.accent),
            background=str(data.get("background") or base.background),
            surface=str(data.get("surface") or base.surface),
            text=str(data.get("text") or base.text),
            text_dark=str(data.get("text_dark") or base.text_dark),
            footer=str(data.get("footer") or base.footer),
            phone=str(data.get("phone") or ""),
            site=str(data.get("site") or ""),
            halls=[str(h) for h in halls] if isinstance(halls, list) and halls else base.halls,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "slogan": self.slogan,
            "logo": self.logo,
            "primary": self.primary,
            "secondary": self.secondary,
            "accent": self.accent,
            "background": self.background,
            "surface": self.surface,
            "text": self.text,
            "text_dark": self.text_dark,
            "footer": self.footer,
            "phone": self.phone,
            "site": self.site,
            "halls": list(self.halls),
        }


# --------------------------------------------------------------------------- #
#  Недельный проект
# --------------------------------------------------------------------------- #
@dataclass
class Project:
    name: str = "Новая афиша"
    start_date: str = field(default_factory=lambda: date.today().isoformat())
    end_date: str = field(default_factory=lambda: date.today().isoformat())
    theme: str = "classic"
    size: str = "1600x900"
    sessions: List[Session] = field(default_factory=list)
    id: str = field(default_factory=new_id)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Project":
        sessions = [Session.from_dict(s) for s in data.get("sessions", []) if isinstance(s, dict)]
        return cls(
            name=str(data.get("name") or "Новая афиша"),
            start_date=str(data.get("start_date") or date.today().isoformat()),
            end_date=str(data.get("end_date") or date.today().isoformat()),
            theme=str(data.get("theme") or "classic"),
            size=str(data.get("size") or "1600x900"),
            sessions=sessions,
            id=str(data.get("id") or new_id()),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "theme": self.theme,
            "size": self.size,
            "sessions": [s.to_dict() for s in self.sessions],
            "id": self.id,
        }

    # ----------------------------------------------------------------- helpers
    @property
    def start(self) -> date:
        return _parse_date(self.start_date)

    @property
    def end(self) -> date:
        return _parse_date(self.end_date)

    def date_range_text(self, fmt: str = "%d.%m") -> str:
        return f"{self.start.strftime(fmt)} — {self.end.strftime(fmt)}"

    def default_name(self) -> str:
        return f"{self.start.strftime('%d.%m')}-{self.end.strftime('%d.%m')}"


def _parse_date(value: str) -> date:
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y", "%d.%m"):
        try:
            parsed = datetime.strptime(value, fmt)
            if fmt == "%d.%m":
                parsed = parsed.replace(year=date.today().year)
            return parsed.date()
        except ValueError:
            continue
    return date.today()
