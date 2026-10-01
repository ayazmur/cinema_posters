"""Генерация афиш: несколько дизайнов и форматов.

Публичная точка входа — :func:`render_poster`. Тема выбирается ключом из
:data:`THEMES`, формат — ключом из :data:`SIZES`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from .models import CinemaSettings, Movie, Project, Session
from .storage import resolve_poster

Color = Tuple[int, int, int]

# --------------------------------------------------------------------------- #
#  Форматы
# --------------------------------------------------------------------------- #
SIZES: Dict[str, Tuple[int, int]] = {
    "1600x900": (1600, 900),      # соцсеть / сайт, 16:9
    "1080x1350": (1080, 1350),    # пост 4:5
    "1080x1080": (1080, 1080),    # квадрат
    "1080x1920": (1080, 1920),    # stories 9:16
    "2480x3508": (2480, 3508),    # A4 для печати
}

SIZE_LABELS: Dict[str, str] = {
    "1600x900": "Соцсеть 16:9 (1600×900)",
    "1080x1350": "Пост 4:5 (1080×1350)",
    "1080x1080": "Квадрат 1:1 (1080×1080)",
    "1080x1920": "Stories 9:16 (1080×1920)",
    "2480x3508": "Печать A4 (2480×3508)",
}


# --------------------------------------------------------------------------- #
#  Работа с цветом
# --------------------------------------------------------------------------- #
def parse_color(value: str, default: Color = (255, 255, 255)) -> Color:
    value = (value or "").strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        return default
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return default


def mix(a: Color, b: Color, t: float) -> Color:
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore[return-value]


def lighten(color: Color, t: float) -> Color:
    return mix(color, (255, 255, 255), t)


def darken(color: Color, t: float) -> Color:
    return mix(color, (0, 0, 0), t)


def luminance(color: Color) -> float:
    r, g, b = color
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def readable(color: Color) -> Color:
    return (17, 23, 43) if luminance(color) > 0.6 else (255, 255, 255)


# --------------------------------------------------------------------------- #
#  Шрифты
# --------------------------------------------------------------------------- #
_FONT_CACHE: Dict[Tuple[int, bool], ImageFont.FreeTypeFont] = {}
_FONT_DIRS = [
    Path("C:/Windows/Fonts"),
    Path("/usr/share/fonts"),
    Path("/Library/Fonts"),
    Path("/System/Library/Fonts"),
]
_BOLD_NAMES = ["seguisb.ttf", "segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf",
               "DejaVuSansCondensed-Bold.ttf", "LiberationSans-Bold.ttf"]
_REG_NAMES = ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf",
              "DejaVuSansCondensed.ttf", "LiberationSans-Regular.ttf"]


def _find_font_file(bold: bool) -> Optional[Path]:
    from .paths import RESOURCES

    bundled = RESOURCES / "assets" / "fonts"
    names = _BOLD_NAMES if bold else _REG_NAMES
    for name in names:
        candidate = bundled / name
        if candidate.exists():
            return candidate
    for directory in _FONT_DIRS:
        if not directory.exists():
            continue
        for name in names:
            candidate = directory / name
            if candidate.exists():
                return candidate
    return None


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    size = max(8, int(size))
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    path = _find_font_file(bold)
    try:
        fnt = ImageFont.truetype(str(path), size) if path else ImageFont.load_default(size)
    except (OSError, TypeError):
        try:
            fnt = ImageFont.load_default(size)
        except TypeError:
            fnt = ImageFont.load_default()
    _FONT_CACHE[key] = fnt  # type: ignore[assignment]
    return fnt  # type: ignore[return-value]


# --------------------------------------------------------------------------- #
#  Вспомогательные примитивы
# --------------------------------------------------------------------------- #
def vertical_gradient(size: Tuple[int, int], top: Color, bottom: Color) -> Image.Image:
    w, h = size
    column = Image.new("RGB", (1, h))
    for y in range(h):
        column.putpixel((0, y), mix(top, bottom, y / max(1, h - 1)))
    return column.resize((w, h), Image.Resampling.BILINEAR)


def diagonal_gradient(size: Tuple[int, int], c1: Color, c2: Color) -> Image.Image:
    w, h = size
    small = Image.new("RGB", (64, 64))
    for y in range(64):
        for x in range(64):
            small.putpixel((x, y), mix(c1, c2, (x + y) / 126))
    return small.resize((w, h), Image.Resampling.BILINEAR)


def add_glow(img: Image.Image, center: Tuple[int, int], radius: int,
             color: Color, alpha: int = 130) -> Image.Image:
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    x, y = center
    od.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color + (alpha,))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius / 2))
    return Image.alpha_composite(img, overlay)


def rounded_image(path: Path, size: Tuple[int, int], radius: int) -> Image.Image:
    """Помещает постер целиком в рамку, не отрезая края.

    Свободное пространство заполняется затемнённой размытой копией постера,
    чтобы портретные изображения хорошо смотрелись и в широких макетах.
    """
    source = ImageOps.exif_transpose(Image.open(path)).convert("RGBA")
    cover = ImageOps.fit(source.convert("RGB"), size, Image.Resampling.LANCZOS)
    blur_radius = max(5, int(min(size) * 0.025))
    cover = cover.filter(ImageFilter.GaussianBlur(blur_radius))
    cover = ImageEnhance.Brightness(cover).enhance(0.48).convert("RGBA")

    foreground = ImageOps.contain(source, size, Image.Resampling.LANCZOS)
    x = (size[0] - foreground.width) // 2
    y = (size[1] - foreground.height) // 2
    cover.alpha_composite(foreground, (x, y))

    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size[0] - 1, size[1] - 1),
        radius=min(radius, size[0] // 2, size[1] // 2),
        fill=255,
    )
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    out.paste(cover, (0, 0), mask)
    return out


def placeholder_poster(size: Tuple[int, int], movie: Movie, c1: Color, c2: Color) -> Image.Image:
    w, h = size
    base = vertical_gradient((w, h), c1, c2).convert("RGBA")
    d = ImageDraw.Draw(base)
    initial = (movie.title.strip()[:1] or "?").upper()
    fnt = font(int(h * 0.34), True)
    d.text((w / 2, h / 2 - h * 0.05), initial, font=fnt,
           fill=(255, 255, 255, 90), anchor="mm")
    d.rectangle((0, h - 6, w, h), fill=(255, 255, 255, 60))
    return base


def wrap_text(d: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont,
              max_width: int) -> List[str]:
    words = text.split()
    if not words:
        return [""]
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        try:
            width = d.textlength(candidate, font=fnt)
        except AttributeError:
            width = d.textbbox((0, 0), candidate, font=fnt)[2]
        if width <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_center(d: ImageDraw.ImageDraw, box: Sequence[int], text: str,
                fnt: ImageFont.FreeTypeFont, fill, spacing: int = 6) -> None:
    x1, y1, x2, y2 = box
    d.multiline_text(((x1 + x2) / 2, (y1 + y2) / 2), text, font=fnt, fill=fill,
                     anchor="mm", align="center", spacing=spacing)


def draw_left(d: ImageDraw.ImageDraw, x: float, y: float, text: str,
              fnt: ImageFont.FreeTypeFont, fill) -> None:
    d.text((x, y), text, font=fnt, fill=fill, anchor="lm")


def draw_text_fit(d: ImageDraw.ImageDraw, text: str, box: Sequence[int],
                  max_size: int, fill, d_bold: bool = True,
                  min_size: int = 12) -> int:
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    size = max_size
    while size > min_size:
        fnt = font(size, d_bold)
        lines = wrap_text(d, text, fnt, bw)
        joined = "\n".join(lines)
        bbox = d.multiline_textbbox((0, 0), joined, font=fnt, spacing=4, align="center")
        if (bbox[2] - bbox[0]) <= bw and (bbox[3] - bbox[1]) <= bh:
            draw_center(d, box, joined, fnt, fill)
            return size
        size -= 2
    fnt = font(min_size, d_bold)
    draw_center(d, box, "\n".join(wrap_text(d, text, fnt, bw)), fnt, fill)
    return min_size


def paste_logo(img: Image.Image, settings: CinemaSettings, box: Sequence[int],
               logo_h: int) -> bool:
    path = resolve_poster(settings.logo)
    if not path:
        return False
    try:
        logo = ImageOps.exif_transpose(Image.open(path)).convert("RGBA")
    except OSError:
        return False
    ratio = logo.width / logo.height
    logo = logo.resize((int(logo_h * ratio), logo_h), Image.Resampling.LANCZOS)
    x1, y1, x2, y2 = box
    x = int((x1 + x2) / 2 - logo.width / 2)
    y = int((y1 + y2) / 2 - logo.height / 2)
    img.alpha_composite(logo, (max(0, x), max(0, y)))
    return True


# --------------------------------------------------------------------------- #
#  Группировка сеансов
# --------------------------------------------------------------------------- #
@dataclass
class Entry:
    movie: Movie
    sessions: List[Session]


def group_sessions(project: Project, movies_by_id: Dict[str, Movie]) -> List[Entry]:
    order: List[str] = []
    buckets: Dict[str, List[Session]] = {}
    seen_movies: Dict[str, Movie] = {}
    for session in project.sessions:
        movie = movies_by_id.get(session.movie_id)
        if movie is None:
            continue
        if session.movie_id not in buckets:
            buckets[session.movie_id] = []
            order.append(session.movie_id)
        buckets[session.movie_id].append(session)
        seen_movies[session.movie_id] = movie
    entries: List[Entry] = []
    for movie_id in order:
        sessions = sorted(buckets[movie_id], key=Session.sort_key)
        entries.append(Entry(movie=seen_movies[movie_id], sessions=sessions))
    return entries


def session_price(session: Session, movie: Movie) -> int:
    return session.price if session.price is not None else movie.price


def session_pushkin(session: Session, movie: Movie) -> bool:
    return session.pushkin if session.pushkin is not None else movie.pushkin


def entry_price_text(entry: Entry) -> str:
    prices = sorted({session_price(s, entry.movie) for s in entry.sessions})
    if not prices:
        return f"{entry.movie.price} ₽"
    if len(prices) == 1:
        return f"{prices[0]} ₽"
    return f"{prices[0]}–{prices[-1]} ₽"


def entry_times(entry: Entry) -> List[str]:
    return [s.time for s in entry.sessions]


def entry_pushkin(entry: Entry) -> bool:
    return any(session_pushkin(s, entry.movie) for s in entry.sessions)


def hall_names(project: Project, movies_by_id: Dict[str, Movie]) -> List[str]:
    halls: List[str] = []
    for session in project.sessions:
        if session.hall and session.hall not in halls:
            halls.append(session.hall)
    return halls


# --------------------------------------------------------------------------- #
#  Контекст рисования
# --------------------------------------------------------------------------- #
@dataclass
class Palette:
    bg: Color
    primary: Color
    secondary: Color
    accent: Color
    surface: Color
    text: Color
    text_dark: Color


@dataclass
class Ctx:
    img: Image.Image
    d: ImageDraw.ImageDraw
    w: int
    h: int
    s: CinemaSettings
    p: Project
    entries: List[Entry]
    c: Palette

    @property
    def vertical(self) -> bool:
        return self.h > self.w * 1.15

    @property
    def scale(self) -> float:
        return min(self.w, self.h) / 1000


def _palette(settings: CinemaSettings) -> Palette:
    return Palette(
        bg=parse_color(settings.background, (10, 21, 51)),
        primary=parse_color(settings.primary, (226, 61, 66)),
        secondary=parse_color(settings.secondary, (22, 119, 173)),
        accent=parse_color(settings.accent, (240, 160, 40)),
        surface=parse_color(settings.surface, (255, 255, 255)),
        text=parse_color(settings.text, (255, 255, 255)),
        text_dark=parse_color(settings.text_dark, (16, 27, 58)),
    )


# --------------------------------------------------------------------------- #
#  Общие блоки
# --------------------------------------------------------------------------- #
def _date_line(ctx: Ctx) -> str:
    return f"С {ctx.p.start.strftime('%d.%m')} ПО {ctx.p.end.strftime('%d.%m')}"


def _draw_brand(ctx: Ctx, dark: bool = True) -> None:
    c, d, w = ctx.c, ctx.d, ctx.w
    text_color = c.text if dark else c.text_dark
    y = int(ctx.h * 0.055)
    logo_h = int(ctx.h * 0.075)
    if paste_logo(ctx.img, ctx.s, (0, 0, w, y + logo_h), logo_h):
        d = ImageDraw.Draw(ctx.img)
        ctx.d = d
        d.text((w / 2, y + logo_h + int(ctx.h * 0.03)), _date_line(ctx),
               font=font(int(20 * ctx.scale), True),
               fill=c.primary if not dark else c.accent, anchor="mm")
        return
    draw_text_fit(d, ctx.s.name, (int(w * 0.08), int(ctx.h * 0.025), int(w * 0.92), int(ctx.h * 0.11)),
                  int(56 * ctx.scale), text_color, True)
    d.text((w / 2, int(ctx.h * 0.125)), _date_line(ctx),
           font=font(int(22 * ctx.scale), True), fill=c.accent if dark else c.primary, anchor="mm")


def _draw_footer(ctx: Ctx, fill: Color, text_color: Color) -> None:
    c, d, w, h = ctx.c, ctx.d, ctx.w, ctx.h
    d.rectangle((0, int(h * 0.945), w, h), fill=fill)
    parts = [ctx.s.footer]
    contact = " · ".join(p for p in (ctx.s.phone, ctx.s.site) if p)
    if contact:
        parts.append(contact)
    parts.append(ctx.s.slogan)
    d.text((w / 2, int(h * 0.973)), "   ·   ".join(p for p in parts if p),
           font=font(int(18 * ctx.scale), True), fill=text_color, anchor="mm")


def _poster_image(ctx: Ctx, movie: Movie, size: Tuple[int, int],
                  radius: int, c1: Color, c2: Color) -> Image.Image:
    path = resolve_poster(movie.poster)
    if path:
        try:
            return rounded_image(path, size, radius)
        except OSError:
            pass
    return placeholder_poster(size, movie, c1, c2)


def _time_pills(d: ImageDraw.ImageDraw, times: Sequence[str], box: Sequence[int],
                fnt: ImageFont.FreeTypeFont, bg: Color, fg: Color,
                gap: int, spacing: int = 10) -> int:
    x1, y1, x2, y2 = box
    x, y, row_h = x1, y1, y2 - y1
    for t in times:
        tw = int(d.textlength(t, font=fnt)) + int(fnt.size * 1.1)
        if x + tw > x2 and x > x1:
            x = x1
            y += row_h + spacing
        d.rounded_rectangle((x, y, x + tw, y + row_h), radius=row_h // 2, fill=bg)
        d.text((x + tw / 2, y + row_h / 2), t, font=fnt, fill=fg, anchor="mm")
        x += tw + gap
    return y + row_h


# --------------------------------------------------------------------------- #
#  Тема: Classic — карточки постеров и строка расписания
# --------------------------------------------------------------------------- #
def theme_classic(ctx: Ctx) -> None:
    c, d, w, h = ctx.c, ctx.d, ctx.w, ctx.h
    ctx.img.paste(vertical_gradient((w, h), lighten(c.bg, 0.08), darken(c.bg, 0.25)), (0, 0))
    ctx.d = d = ImageDraw.Draw(ctx.img)
    _draw_brand(ctx, dark=True)

    entries = ctx.entries
    if not entries:
        return

    # Строка расписания (текстом)
    panel_top = int(h * 0.16)
    panel_h = min(int(h * 0.30), int(len(entries) * h * 0.052) + int(h * 0.04))
    x1, x2 = int(w * 0.06), int(w * 0.94)
    d.rounded_rectangle((x1, panel_top, x2, panel_top + panel_h), radius=int(24 * ctx.scale),
                        fill=lighten(c.bg, 0.14))
    row_h = (panel_h - int(24 * ctx.scale)) / max(1, min(len(entries), 6))
    fs = font(int(min(row_h * 0.42, 24 * ctx.scale)), True)
    fs_time = font(int(min(row_h * 0.42, 24 * ctx.scale)), True)
    for i, entry in enumerate(entries[:6]):
        y = panel_top + int(12 * ctx.scale) + i * row_h
        cy = y + row_h / 2
        d.text((x1 + int(24 * ctx.scale), cy), " · ".join(entry_times(entry)),
               font=fs_time, fill=c.accent, anchor="lm")
        d.text((x1 + int(w * 0.22), cy),
               f"{entry.movie.title} ({entry.movie.age})" if entry.movie.age else entry.movie.title,
               font=fs, fill=c.text, anchor="lm")
        if entry_pushkin(entry):
            d.text((x2 - int(w * 0.24), cy), "Пушкинская карта",
                   font=font(int(16 * ctx.scale), True), fill=c.primary, anchor="lm")
        d.text((x2 - int(24 * ctx.scale), cy), entry_price_text(entry),
               font=fs_time, fill=c.text, anchor="rm")

    # Карточки с постерами
    cards = entries[:5]
    count = max(1, len(cards))
    left = int(w * 0.045)
    gap = int(w * 0.018)
    card_w = (w - 2 * left - (count - 1) * gap) // count
    card_top = panel_top + panel_h + int(h * 0.03)
    card_bottom = int(h * 0.93)
    card_h = card_bottom - card_top
    poster_h = int(card_h * 0.62)
    for i, entry in enumerate(cards):
        cx = left + i * (card_w + gap)
        d.rounded_rectangle((cx, card_top, cx + card_w, card_bottom),
                            radius=int(16 * ctx.scale), fill=c.surface)
        poster = _poster_image(ctx, entry.movie, (card_w - int(10 * ctx.scale), poster_h),
                               int(12 * ctx.scale), c.secondary, darken(c.secondary, 0.4))
        ctx.img.alpha_composite(poster, (cx + int(5 * ctx.scale), card_top + int(5 * ctx.scale)))
        pill_fg = c.accent if i == 0 else c.secondary
        pill_h = int(h * 0.045)
        times = entry_times(entry)
        label = times[0] + (f" +{len(times) - 1}" if len(times) > 1 else "")
        fnt = font(int(h * 0.028), True)
        tw = int(d.textlength(label, font=fnt)) + int(20 * ctx.scale)
        px = cx + (card_w - tw) // 2
        py = card_top + poster_h - pill_h // 2
        d.rounded_rectangle((px, py, px + tw, py + pill_h), radius=pill_h // 2, fill=pill_fg)
        d.text((px + tw / 2, py + pill_h / 2), label, font=fnt, fill=readable(pill_fg), anchor="mm")
        title_box = (cx + int(8 * ctx.scale), card_top + poster_h + int(10 * ctx.scale),
                     cx + card_w - int(8 * ctx.scale), card_top + poster_h + int(card_h * 0.28))
        draw_text_fit(d, entry.movie.title, title_box, int(22 * ctx.scale), c.text_dark, True,
                      int(12 * ctx.scale))
        d.text(((cx + cx + card_w) / 2, card_bottom - int(16 * ctx.scale)), entry_price_text(entry),
               font=font(int(20 * ctx.scale), True), fill=c.secondary, anchor="mm")
    _draw_footer(ctx, darken(c.bg, 0.35), c.text)


# --------------------------------------------------------------------------- #
#  Тема: Grid — сетка постеров
# --------------------------------------------------------------------------- #
def theme_grid(ctx: Ctx) -> None:
    c, d, w, h = ctx.c, ctx.d, ctx.w, ctx.h
    ctx.img.paste(diagonal_gradient((w, h), darken(c.bg, 0.1), lighten(c.secondary, -0.1)), (0, 0))
    ctx.d = d = ImageDraw.Draw(ctx.img)
    d.rectangle((0, 0, w, int(h * 0.035)), fill=c.primary)
    _draw_brand(ctx, dark=True)

    entries = ctx.entries
    if not entries:
        return
    top = int(h * 0.16)
    bottom = int(h * 0.93)
    cols = 1 if ctx.vertical else min(3, len(entries))
    cols = 2 if ctx.vertical and len(entries) > 1 else cols
    rows = (len(entries) + cols - 1) // cols
    margin = int(w * 0.05)
    gap = int(w * 0.03)
    cell_w = (w - 2 * margin - (cols - 1) * gap) // cols
    cell_h = (bottom - top - (rows - 1) * gap) // max(1, rows)
    poster_h = int(cell_h * 0.72)
    for i, entry in enumerate(entries):
        r, col = divmod(i, cols)
        cx = margin + col * (cell_w + gap)
        cy = top + r * (cell_h + gap)
        poster = _poster_image(ctx, entry.movie, (cell_w, poster_h), int(16 * ctx.scale),
                               c.secondary, c.primary)
        ctx.img.alpha_composite(poster, (cx, cy))
        y = cy + poster_h + int(cell_h * 0.04)
        d.text((cx, y), entry.movie.title[:28], font=font(int(22 * ctx.scale), True),
               fill=c.text, anchor="la")
        times = " · ".join(entry_times(entry))
        d.text((cx, y + int(cell_h * 0.13)), times, font=font(int(19 * ctx.scale), True),
               fill=c.accent, anchor="la")
        d.text((cx + cell_w, y), entry_price_text(entry), font=font(int(20 * ctx.scale), True),
               fill=c.text, anchor="ra")
    _draw_footer(ctx, darken(c.bg, 0.4), c.text)


# --------------------------------------------------------------------------- #
#  Тема: Magazine — крупный герой + список
# --------------------------------------------------------------------------- #
def theme_magazine(ctx: Ctx) -> None:
    c, d, w, h = ctx.c, ctx.d, ctx.w, ctx.h
    ctx.img.paste(vertical_gradient((w, h), darken(c.bg, 0.15), c.bg), (0, 0))
    ctx.d = d = ImageDraw.Draw(ctx.img)
    entries = ctx.entries
    if not entries:
        _draw_brand(ctx, True)
        return
    if ctx.vertical:
        hero_h = int(h * 0.46)
        poster_w = w
    else:
        hero_h = h
        poster_w = int(w * 0.42)
    hero = entries[0]
    poster = _poster_image(ctx, hero.movie, (poster_w, hero_h), 0, c.secondary, c.primary)
    ctx.img.alpha_composite(poster, (0, 0))
    # затемнение поверх
    shade = Image.new("RGBA", (poster_w, hero_h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    if ctx.vertical:
        for yy in range(hero_h):
            sd.line((0, yy, poster_w, yy), fill=(0, 0, 0, int(200 * max(0, (yy - hero_h * 0.45) / (hero_h * 0.55)))))
    else:
        for xx in range(poster_w):
            sd.line((xx, 0, xx, hero_h), fill=(0, 0, 0, int(210 * max(0, (xx - poster_w * 0.25) / (poster_w * 0.75)))))
    ctx.img.alpha_composite(shade, (0, 0))
    ctx.d = d = ImageDraw.Draw(ctx.img)

    if ctx.vertical:
        title_box = (int(w * 0.06), int(h * 0.30), int(w * 0.94), int(h * 0.42))
        draw_text_fit(d, hero.movie.title, title_box, int(70 * ctx.scale), c.text, True)
        d.text((w / 2, int(h * 0.43)), " · ".join(entry_times(hero)), font=font(int(30 * ctx.scale), True),
               fill=c.accent, anchor="mm")
        list_top = int(h * 0.50)
        row_h = int((h * 0.42) / max(1, len(entries) - 1)) if len(entries) > 1 else 0
        for i, entry in enumerate(entries[1:8]):
            y = list_top + i * row_h
            cy = y + row_h / 2
            d.text((int(w * 0.07), cy), " · ".join(entry_times(entry)), font=font(int(26 * ctx.scale), True),
                   fill=c.accent, anchor="lm")
            d.text((int(w * 0.30), cy), entry.movie.title, font=font(int(26 * ctx.scale), True),
                   fill=c.text, anchor="lm")
            d.text((int(w * 0.93), cy), entry_price_text(entry), font=font(int(24 * ctx.scale), True),
                   fill=c.text, anchor="rm")
    else:
        tx = int(w * 0.47)
        _draw_brand(ctx, True)
        title_box = (tx, int(h * 0.18), int(w * 0.95), int(h * 0.30))
        draw_text_fit(d, hero.movie.title, title_box, int(64 * ctx.scale), c.text, True)
        d.text((tx, int(h * 0.31)), " · ".join(entry_times(hero)), font=font(int(28 * ctx.scale), True),
               fill=c.accent, anchor="la")
        d.text((tx, int(h * 0.35)), entry_price_text(hero), font=font(int(26 * ctx.scale), True),
               fill=c.text, anchor="la")
        rows = entries[1:9]
        top = int(h * 0.42)
        row_h = int(h * 0.50 / max(1, len(rows))) if rows else 0
        for i, entry in enumerate(rows):
            y = top + i * row_h
            cy = y + row_h / 2
            d.line((tx, y, int(w * 0.95), y), fill=lighten(c.bg, 0.25), width=1)
            d.text((tx, cy), " · ".join(entry_times(entry)), font=font(int(24 * ctx.scale), True),
                   fill=c.accent, anchor="lm")
            d.text((tx + int(w * 0.16), cy), entry.movie.title[:36], font=font(int(24 * ctx.scale), True),
                   fill=c.text, anchor="lm")
            d.text((int(w * 0.95), cy), entry_price_text(entry), font=font(int(22 * ctx.scale), True),
                   fill=c.text, anchor="rm")
    _draw_footer(ctx, darken(c.bg, 0.4), c.text)


# --------------------------------------------------------------------------- #
#  Тема: Neon — неоновая
# --------------------------------------------------------------------------- #
def theme_neon(ctx: Ctx) -> None:
    c, d, w, h = ctx.c, ctx.d, ctx.w, ctx.h
    ctx.img.paste(vertical_gradient((w, h), (5, 4, 20), (16, 6, 40)), (0, 0))
    ctx.img = add_glow(ctx.img, (int(w * 0.8), int(h * 0.2)), int(w * 0.35), c.primary, 90)
    ctx.img = add_glow(ctx.img, (int(w * 0.15), int(h * 0.85)), int(w * 0.35), c.secondary, 90)
    ctx.d = d = ImageDraw.Draw(ctx.img)
    neon = c.primary
    accent = c.secondary
    # заголовок
    draw_text_fit(d, ctx.s.name, (int(w * 0.06), int(h * 0.03), int(w * 0.94), int(h * 0.11)),
                  int(54 * ctx.scale), neon, True)
    d.text((w / 2, int(h * 0.125)), _date_line(ctx), font=font(int(22 * ctx.scale), True),
           fill=accent, anchor="mm")

    entries = ctx.entries[:5]
    if not entries:
        _draw_footer(ctx, (5, 4, 20), neon)
        return
    count = len(entries)
    if ctx.vertical:
        cols = 1 if count == 1 else 2
    else:
        cols = count
    rows = (count + cols - 1) // cols
    top = int(h * 0.17)
    bottom = int(h * 0.93)
    margin = int(w * 0.05)
    gap = int(w * 0.025)
    cell_w = (w - 2 * margin - (cols - 1) * gap) // cols
    cell_h = (bottom - top - (rows - 1) * gap) // max(1, rows)
    for i, entry in enumerate(entries):
        r, col = divmod(i, cols)
        cx = margin + col * (cell_w + gap)
        cy = top + r * (cell_h + gap)
        poster = _poster_image(ctx, entry.movie, (cell_w - 4, cell_h - 4), int(14 * ctx.scale),
                               darken(c.primary, 0.3), darken(c.secondary, 0.3))
        border = Image.new("RGBA", (cell_w, cell_h), (0, 0, 0, 0))
        ImageDraw.Draw(border).rounded_rectangle((1, 1, cell_w - 2, cell_h - 2),
                                                 radius=int(16 * ctx.scale), outline=neon + (255,), width=3)
        ctx.img.alpha_composite(poster, (cx + 2, cy + 2))
        ctx.img.alpha_composite(border, (cx, cy))
        d.text((cx + int(cell_w * 0.5), cy + cell_h - int(14 * ctx.scale)),
               entry_price_text(entry), font=font(int(20 * ctx.scale), True), fill=(255, 255, 255),
               anchor="mm")
    # строка расписания
    _draw_footer(ctx, (5, 4, 20), neon)


# --------------------------------------------------------------------------- #
#  Тема: Minimal — светлая минималистичная
# --------------------------------------------------------------------------- #
def theme_minimal(ctx: Ctx) -> None:
    c, d, w, h = ctx.c, ctx.d, ctx.w, ctx.h
    bg = (247, 246, 243)
    ink = (24, 24, 27)
    ctx.img.paste(bg, (0, 0))
    ctx.d = d = ImageDraw.Draw(ctx.img)
    d.rectangle((int(w * 0.06), int(h * 0.045), int(w * 0.06) + int(w * 0.012), int(h * 0.115)),
                fill=c.primary)
    d.text((int(w * 0.09), int(h * 0.055)), ctx.s.name, font=font(int(38 * ctx.scale), True),
           fill=ink, anchor="la")
    d.text((int(w * 0.09), int(h * 0.105)), ctx.s.slogan.upper(),
           font=font(int(18 * ctx.scale)), fill=(120, 120, 128), anchor="la")
    d.text((int(w * 0.94), int(h * 0.075)), _date_line(ctx), font=font(int(24 * ctx.scale), True),
           fill=ink, anchor="ra")
    d.line((int(w * 0.06), int(h * 0.15), int(w * 0.94), int(h * 0.15)), fill=(220, 220, 220), width=2)

    entries = ctx.entries
    if not entries:
        return
    top = int(h * 0.19)
    bottom = int(h * 0.93)
    row_h = (bottom - top) / max(1, len(entries[:8]))
    for i, entry in enumerate(entries[:8]):
        y = top + i * row_h
        cy = y + row_h / 2
        if i % 2 == 0:
            d.rectangle((int(w * 0.045), y, int(w * 0.955), y + row_h), fill=(241, 240, 236))
        d.text((int(w * 0.07), cy), " · ".join(entry_times(entry)), font=font(int(26 * ctx.scale), True),
               fill=c.primary, anchor="lm")
        title = entry.movie.title
        if entry.movie.age:
            title += f"  ({entry.movie.age})"
        d.text((int(w * 0.34), cy), title[:44], font=font(int(26 * ctx.scale), True), fill=ink, anchor="lm")
        if entry_pushkin(entry):
            d.text((int(w * 0.78), cy), "ПК", font=font(int(20 * ctx.scale), True), fill=c.secondary, anchor="lm")
        d.text((int(w * 0.93), cy), entry_price_text(entry), font=font(int(24 * ctx.scale), True),
               fill=ink, anchor="rm")
    d.rectangle((0, int(h * 0.945), w, h), fill=ink)
    d.text((w / 2, int(h * 0.972)), f"{ctx.s.footer}  ·  {ctx.s.slogan}", font=font(int(18 * ctx.scale), True),
           fill=(247, 246, 243), anchor="mm")


# --------------------------------------------------------------------------- #
#  Тема: Retro — винтажная
# --------------------------------------------------------------------------- #
def theme_retro(ctx: Ctx) -> None:
    c, d, w, h = ctx.c, ctx.d, ctx.w, ctx.h
    cream = (243, 231, 205)
    ink = (54, 40, 28)
    ctx.img.paste(cream, (0, 0))
    ctx.d = d = ImageDraw.Draw(ctx.img)
    for i in range(0, w, 28):
        d.line((i, 0, i, h), fill=(236, 222, 193), width=1)
    d.rectangle((int(w * 0.03), int(h * 0.03), int(w * 0.97), int(h * 0.97)),
                outline=ink, width=int(6 * ctx.scale))
    d.rectangle((int(w * 0.045), int(h * 0.045), int(w * 0.955), int(h * 0.955)),
                outline=c.primary, width=int(3 * ctx.scale))
    draw_text_fit(d, ctx.s.name, (int(w * 0.08), int(h * 0.07), int(w * 0.92), int(h * 0.16)),
                  int(52 * ctx.scale), ink, True)
    d.rectangle((int(w * 0.28), int(h * 0.17), int(w * 0.72), int(h * 0.205)), fill=c.primary)
    d.text((w / 2, int(h * 0.187)), _date_line(ctx), font=font(int(22 * ctx.scale), True),
           fill=cream, anchor="mm")

    entries = ctx.entries
    if not entries:
        return
    left = int(w * 0.08)
    right = int(w * 0.92)
    top = int(h * 0.24)
    bottom = int(h * 0.92)
    row_h = (bottom - top) / max(1, len(entries[:8]))
    for i, entry in enumerate(entries[:8]):
        y = top + i * row_h
        cy = y + row_h / 2
        if i:
            d.line((left, y, right, y), fill=(120, 100, 70), width=1)
        d.text((left, cy), " · ".join(entry_times(entry)), font=font(int(28 * ctx.scale), True),
               fill=c.secondary, anchor="lm")
        d.text((left + int(w * 0.26), cy), entry.movie.title[:40], font=font(int(28 * ctx.scale), True),
               fill=ink, anchor="lm")
        d.text((right, cy), entry_price_text(entry), font=font(int(24 * ctx.scale), True),
               fill=ink, anchor="rm")
    d.text((w / 2, int(h * 0.955)), f"{ctx.s.footer}  ·  {ctx.s.slogan}", font=font(int(17 * ctx.scale), True),
           fill=ink, anchor="mm")


# --------------------------------------------------------------------------- #
#  Тема: List — типографский список с миниатюрами
# --------------------------------------------------------------------------- #
def theme_list(ctx: Ctx) -> None:
    c, d, w, h = ctx.c, ctx.d, ctx.w, ctx.h
    ctx.img.paste(vertical_gradient((w, h), c.bg, darken(c.secondary, 0.55)), (0, 0))
    ctx.d = d = ImageDraw.Draw(ctx.img)
    d.rectangle((0, 0, int(w * 0.012), h), fill=c.primary)
    _draw_brand(ctx, True)

    entries = ctx.entries
    if not entries:
        return
    top = int(h * 0.18)
    bottom = int(h * 0.93)
    row_h = (bottom - top) / max(1, len(entries[:8]))
    thumb_h = int(row_h * 0.72)
    thumb_w = int(thumb_h * 0.68)
    for i, entry in enumerate(entries[:8]):
        y = top + i * row_h
        cy = y + row_h / 2
        if i % 2 == 0:
            d.rounded_rectangle((int(w * 0.04), y + 4, int(w * 0.96), y + row_h - 4),
                                radius=int(12 * ctx.scale), fill=lighten(c.bg, 0.10))
        poster = _poster_image(ctx, entry.movie, (thumb_w, thumb_h), int(8 * ctx.scale),
                               c.secondary, c.primary)
        ctx.img.alpha_composite(poster, (int(w * 0.06), int(cy - thumb_h / 2)))
        tx = int(w * 0.06) + thumb_w + int(w * 0.02)
        d.text((tx, cy - thumb_h * 0.18), entry.movie.title[:40], font=font(int(24 * ctx.scale), True),
               fill=c.text, anchor="lm")
        d.text((tx, cy + thumb_h * 0.22), " · ".join(entry_times(entry)),
               font=font(int(20 * ctx.scale), True), fill=c.accent, anchor="lm")
        d.text((int(w * 0.95), cy), entry_price_text(entry), font=font(int(24 * ctx.scale), True),
               fill=c.text, anchor="rm")
    _draw_footer(ctx, darken(c.bg, 0.4), c.text)


# --------------------------------------------------------------------------- #
#  Тема: Bright — яркие цветные блоки
# --------------------------------------------------------------------------- #
def theme_bright(ctx: Ctx) -> None:
    c, d, w, h = ctx.c, ctx.d, ctx.w, ctx.h
    ctx.img.paste(c.surface, (0, 0))
    ctx.d = d = ImageDraw.Draw(ctx.img)
    d.rectangle((0, 0, w, int(h * 0.14)), fill=c.primary)
    d.rectangle((0, int(h * 0.14), w, int(h * 0.155)), fill=c.accent)
    d.text((int(w * 0.05), int(h * 0.07)), ctx.s.name, font=font(int(36 * ctx.scale), True),
           fill=readable(c.primary), anchor="lm")
    d.text((int(w * 0.95), int(h * 0.055)), _date_line(ctx), font=font(int(22 * ctx.scale), True),
           fill=readable(c.primary), anchor="rm")

    entries = ctx.entries
    if not entries:
        return
    top = int(h * 0.17)
    bottom = int(h * 0.93)
    row_h = (bottom - top) / max(1, len(entries[:8]))
    accent_colors = [c.primary, c.secondary, c.accent]
    for i, entry in enumerate(entries[:8]):
        y = top + i * row_h
        cy = y + row_h / 2
        bar = accent_colors[i % len(accent_colors)]
        d.rounded_rectangle((int(w * 0.05), y + 5, int(w * 0.95), y + row_h - 5),
                            radius=int(14 * ctx.scale), fill=(245, 246, 250))
        d.rounded_rectangle((int(w * 0.05), y + 5, int(w * 0.075), y + row_h - 5),
                            radius=int(14 * ctx.scale), fill=bar)
        d.text((int(w * 0.10), cy), " · ".join(entry_times(entry)), font=font(int(26 * ctx.scale), True),
               fill=c.text_dark, anchor="lm")
        d.text((int(w * 0.32), cy), entry.movie.title[:42], font=font(int(26 * ctx.scale), True),
               fill=c.text_dark, anchor="lm")
        if entry_pushkin(entry):
            d.text((int(w * 0.80), cy), "Пушкинская карта", font=font(int(18 * ctx.scale), True),
                   fill=c.primary, anchor="lm")
        d.text((int(w * 0.94), cy), entry_price_text(entry), font=font(int(24 * ctx.scale), True),
               fill=bar, anchor="rm")
    d.rectangle((0, int(h * 0.945), w, h), fill=c.text_dark)
    d.text((w / 2, int(h * 0.972)), f"{ctx.s.footer}  ·  {ctx.s.slogan}", font=font(int(18 * ctx.scale), True),
           fill=c.surface, anchor="mm")


# --------------------------------------------------------------------------- #
#  Реестр тем
# --------------------------------------------------------------------------- #
THEMES: Dict[str, Tuple[str, object]] = {
    "classic": ("Классика", theme_classic),
    "grid": ("Сетка постеров", theme_grid),
    "magazine": ("Журнальный", theme_magazine),
    "neon": ("Неон", theme_neon),
    "minimal": ("Минимализм", theme_minimal),
    "retro": ("Ретро", theme_retro),
    "list": ("Список", theme_list),
    "bright": ("Яркие блоки", theme_bright),
}


def theme_label(key: str) -> str:
    return THEMES.get(key, (key, None))[0]


def render_poster(settings: CinemaSettings, project: Project,
                  movies_by_id: Dict[str, Movie], theme: Optional[str] = None,
                  size: Optional[str] = None) -> Image.Image:
    theme = theme or project.theme
    size_key = size or project.size
    w, h = SIZES.get(size_key, SIZES["1600x900"])
    entries = group_sessions(project, movies_by_id)

    img = Image.new("RGBA", (w, h), parse_color(settings.background) + (255,))
    d = ImageDraw.Draw(img)
    ctx = Ctx(img=img, d=d, w=w, h=h, s=settings, p=project,
              entries=entries, c=_palette(settings))
    func = THEMES.get(theme, THEMES["classic"])[1]
    try:
        func(ctx)  # type: ignore[operator]
    except Exception:  # noqa: BLE001 — афиша важнее падения из-за темы
        ctx.img = Image.new("RGBA", (w, h), parse_color(settings.background) + (255,))
        ctx.d = ImageDraw.Draw(ctx.img)
        _draw_brand(ctx, True)
        _draw_footer(ctx, darken(ctx.c.bg, 0.4), ctx.c.text)
    return ctx.img.convert("RGB")
