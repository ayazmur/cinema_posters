"""Формирование текстовой версии расписания для публикации в соцсетях."""

from __future__ import annotations

from typing import Dict, List

from .models import CinemaSettings, Movie, Project
from .poster import entry_price_text, entry_pushkin, entry_times, group_sessions


def schedule_text(settings: CinemaSettings, project: Project,
                  movies_by_id: Dict[str, Movie], with_emoji: bool = True) -> str:
    entries = group_sessions(project, movies_by_id)
    lines: List[str] = []

    title = settings.name
    if with_emoji:
        title = f"🎬 {title}"
    lines.append(title)
    lines.append(f"Расписание с {project.start.strftime('%d.%m')} по {project.end.strftime('%d.%m')}")
    if settings.slogan:
        lines.append(settings.slogan)
    lines.append("")

    if not entries:
        lines.append("Сеансы пока не добавлены.")

    for entry in entries:
        movie = entry.movie
        title_line = movie.title
        if movie.age:
            title_line += f" ({movie.age})"
        if movie.format:
            title_line += f" {movie.format}"
        lines.append(title_line)

        for session in entry.sessions:
            parts = [session.time]
            if session.hall:
                parts.append(session.hall)
            price = entry_price_text(entry)
            parts.append(price)
            if entry_pushkin(entry):
                parts.append("Пушкинская карта")
            lines.append("   " + " · ".join(parts))
        lines.append("")

    footer = " · ".join(p for p in (settings.footer, settings.phone, settings.site) if p)
    if footer:
        lines.append(footer)
    return "\n".join(lines).strip() + "\n"
