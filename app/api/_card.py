"""Render the bot's daily and weekly summary cards without external I/O."""
from datetime import date
from functools import lru_cache
from io import BytesIO
from math import ceil, floor
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

__all__ = ["render"]

_SCALE = 2
_FONT_DIR = Path(__file__).resolve().parent / "_fonts"
_BACKGROUND = "#0F1B2D"
_PANEL = "#142338"
_WHITE = "#FFFFFF"
_MUTED = "#9FB0C6"
_AXIS = "#8EA0B8"
_BLUE = "#7AA2FF"
_POSITIVE = "#45C7D3"
_NEGATIVE = "#FF9A62"
_MONTHS = {
    "uz": "yanvar fevral mart aprel may iyun iyul avgust sentabr oktabr noyabr dekabr".split(),
    "ru": "января февраля марта апреля мая июня июля августа сентября октября ноября декабря".split(),
    "en": "January February March April May June July August September October November December".split(),
}
_SHORT_MONTHS = {
    "uz": "yan fev mar apr may iyn iyl avg sen okt noy dek".split(),
    "ru": "янв фев мар апр мая июн июл авг сен окт ноя дек".split(),
    "en": "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(),
}
_TEXT = {
    "uz": {
        "tagline": "iqtisodiy yangiliklar indeksi",
        "kun": "Kunlik xulosa", "hafta": "Haftalik xulosa",
        "eai": "E’TIBOR · EAI", "esi": "KAYFIYAT · ESI", "unit": "f.b.",
        "days": "So‘nggi {n} kun", "weeks": "So‘nggi {n} hafta", "gap": "ma’lumot yo‘q",
    },
    "ru": {
        "tagline": "индекс экономических новостей",
        "kun": "Итоги дня", "hafta": "Итоги недели",
        "eai": "ВНИМАНИЕ · EAI", "esi": "НАСТРОЕНИЕ · ESI", "unit": "п.п.",
        "days": "Последние {n} дн.", "weeks": "Последние {n} нед.", "gap": "нет данных",
    },
    "en": {
        "tagline": "economic news index",
        "kun": "Daily summary", "hafta": "Weekly summary",
        "eai": "ATTENTION · EAI", "esi": "SENTIMENT · ESI", "unit": "pp",
        "days": "Last {n} days", "weeks": "Last {n} weeks", "gap": "no data",
    },
}


def _number(value, lang, signed=False):
    if value is None:
        return "—"
    sign = "−" if value < 0 else "+" if signed and value > 0 else ""
    digits = f"{abs(value):.1f}"
    return sign + (digits if lang == "en" else digits.replace(".", ","))


def _day_month(value, lang, short=False):
    day = date.fromisoformat(value)
    month = (_SHORT_MONTHS if short else _MONTHS)[lang][day.month - 1]
    return f"{day.day}{'-' if lang == 'uz' else ' '}{month}"


def _period_date(start, end, lang):
    if start == end:
        return f"{_day_month(start, lang)} {start[:4]}"
    if start[:7] == end[:7]:
        return f"{date.fromisoformat(start).day}–{_day_month(end, lang)} {end[:4]}"
    first = _day_month(start, lang)
    if start[:4] != end[:4]:
        first += f" {start[:4]}"
    return f"{first} – {_day_month(end, lang)} {end[:4]}"


@lru_cache(maxsize=128)
def _font(size, weight="Regular"):
    return ImageFont.truetype(str(_FONT_DIR / f"IBMPlexSans-{weight}.ttf"), round(size * _SCALE))


@lru_cache(maxsize=2048)
def _width(text, size, weight="Regular", spacing=0):
    return _font(size, weight).getlength(text) / _SCALE + max(0, len(text) - 1) * spacing


def _baseline(y, size, weight, line_height=None):
    ascent, descent = _font(size, weight).getmetrics()
    return y + ((line_height or size * 1.3) - (ascent + descent) / _SCALE) / 2 + ascent / _SCALE


def _fit(text, size, width, weight="Regular", spacing=0):
    while size > 10 and _width(text, size, weight, spacing) > width:
        size -= 1
    return size


class _Canvas:
    def __init__(self):
        self.image = Image.new("RGB", (1200 * _SCALE, 675 * _SCALE), _BACKGROUND)
        self.draw = ImageDraw.Draw(self.image, "RGBA")

    def rect(self, box, color, radius=0, outline=None, width=1):
        self.draw.rounded_rectangle(tuple(v * _SCALE for v in box), radius=radius * _SCALE,
                                    fill=color, outline=outline, width=round(width * _SCALE))

    def circle(self, x, y, radius, color):
        self.draw.ellipse(tuple(v * _SCALE for v in (x - radius, y - radius, x + radius, y + radius)), fill=color)

    def line(self, points, color, width=1, rounded=False):
        self.draw.line([(x * _SCALE, y * _SCALE) for x, y in points], fill=color,
                       width=round(width * _SCALE), joint="curve")
        if rounded:
            for x, y in points:
                self.circle(x, y, width / 2, color)

    def text(self, x, y, text, size, color=_WHITE, weight="Regular", spacing=0,
             align="left", line_height=None, baseline=False):
        width = _width(text, size, weight, spacing)
        x -= width / 2 if align == "center" else width if align == "right" else 0
        y = y if baseline else _baseline(y, size, weight, line_height)
        font = _font(size, weight)
        if spacing:
            for i, char in enumerate(text):
                offset = _width(text[:i], size, weight) + i * spacing
                self.draw.text(((x + offset) * _SCALE, y * _SCALE), char, font=font, fill=color, anchor="ls")
        else:
            self.draw.text((x * _SCALE, y * _SCALE), text, font=font, fill=color, anchor="ls")
        return width


def _logo(canvas):
    x, y, scale = 56, 52, 46 / 36
    canvas.rect((x, y, x + 46, y + 46), "#1D2E4A", radius=10 * scale)
    canvas.line([(x + a * scale, y + b * scale) for a, b in [(8, 23), (14, 17), (19, 21), (28, 11)]],
                _WHITE, 2.6 * scale, rounded=True)
    canvas.circle(x + 28 * scale, y + 11 * scale, 2.6 * scale, _BLUE)


def _chip(canvas, x, y, value, lang, metric):
    if value is None:
        return
    background, color = (255, 255, 255, 26), _WHITE
    if metric == "esi" and value:
        background = (60, 196, 209, 41) if value > 0 else (255, 138, 76, 41)
        color = _POSITIVE if value > 0 else _NEGATIVE
    label = _number(abs(value), lang) + (f" {_TEXT[lang]['unit']}" if metric == "eai" else "")
    width = 24 + 16 + 6 + _width(label, 17, "SemiBold")
    canvas.rect((x, y, x + width, y + 32), background, radius=16)
    # These vertices are PATHS.up, PATHS.down and PATHS.minus on the 24px grid.
    paths = [[(7, 17), (17, 7)], [(9, 7), (17, 7), (17, 15)]] if value > 0 else (
        [[(7, 7), (17, 17)], [(17, 9), (17, 17), (9, 17)]] if value < 0 else [[(5, 12), (19, 12)]])
    for points in paths:
        canvas.line([(x + 12 + a * 16 / 24, y + 8 + b * 16 / 24) for a, b in points],
                    color, 2.4 * 16 / 24, rounded=True)
    canvas.text(x + 34, y + 5, label, 17, color, "SemiBold", line_height=22)


def _metric(canvas, x, metric, value, delta, lang):
    canvas.text(x, 261, _TEXT[lang][metric], 14, _MUTED, "SemiBold", spacing=1.2)
    label = _number(value, lang, signed=metric == "esi")
    color = _WHITE
    if metric == "esi" and value is not None:
        color = _POSITIVE if value > 0 else _NEGATIVE if value < 0 else _WHITE
    size = 66
    suffix = metric == "eai" and value is not None
    while size > 10 and (_width(label, size, "SemiBold", -1.5)
                         + (_width("%", round(size * 34 / 66), "SemiBold") if suffix else 0)) > 178:
        size -= 1
    baseline = _baseline(285, size, "SemiBold", 69.3)
    width = canvas.text(x, baseline, label, size, color, "SemiBold", spacing=-1.5, baseline=True)
    if suffix:
        canvas.text(x + width, baseline, "%", round(size * 34 / 66), _MUTED, "SemiBold", baseline=True)
    _chip(canvas, x, 365, delta, lang, metric)


def _gaps(canvas, values, x, y, height, lang, label=False):
    step = 560 / len(values)
    start = None
    for i, value in enumerate([*values, 0]):
        if value is None and start is None:
            start = i
        elif value is not None and start is not None:
            left, width = x + step * start, step * (i - start)
            canvas.rect((left, y, left + width, y + height), (255, 255, 255, 13), radius=8)
            if label and width >= 90:
                canvas.text(left + width / 2, y + 120, _TEXT[lang]["gap"], 13, _AXIS,
                            align="center", baseline=True)
            start = None


def _grid(canvas, x, y, solid=False, alpha=26):
    color = (255, 255, 255, alpha)
    if solid:
        canvas.line([(x, y), (x + 560, y)], color)
    else:
        for offset in range(0, 560, 9):
            canvas.line([(x + offset, y), (x + min(offset + 3, 560), y)], color)


def _eai_chart(canvas, values, lang):
    x, y = 517, 121
    present = [value for value in values if value is not None]
    lo = floor((min(present) - 2) / 5) * 5 if present else 0
    hi = max(lo + 10, ceil((max(present) + 2) / 5) * 5) if present else 10
    step = 560 / len(values)
    _gaps(canvas, values, x, y, 236, lang, label=True)
    for offset, value in [(14, hi), (114, (hi + lo) / 2), (214, lo)]:
        _grid(canvas, x, y + offset, solid=offset == 214, alpha=41 if offset == 214 else 26)
        label = str(int(value)) if value == int(value) else _number(value, lang)
        canvas.text(x + 620, y + offset + 5, label.replace("-", "−") + "%", 14, _AXIS,
                    align="right", baseline=True)
    segment, last = [], None
    for i, value in enumerate([*values, None]):
        if value is None:
            if len(segment) == 1:
                canvas.circle(*segment[0], 5, _BLUE)
            elif segment:
                canvas.line(segment, _BLUE, 3.5, rounded=True)
            segment = []
        else:
            last = (x + step * (i + 0.5), y + 14 + (hi - value) / (hi - lo) * 200)
            segment.append(last)
    if last is not None:
        # SVG strokes are centered on the marker's radius.
        canvas.circle(*last, 8.5, _PANEL)
        canvas.circle(*last, 5.5, _BLUE)


def _esi_chart(canvas, series, lang):
    x, y = 517, 367
    values = [row["esi"] for row in series]
    largest = max((abs(value) for value in values if value is not None), default=0)
    limit = next((value for value in [10, 20, 30, 50, 75, 100] if value >= largest), 100)
    step = 560 / len(values)
    _gaps(canvas, values, x, y, 150, lang)
    for offset, label in [(23, f"+{limit}"), (75, "0"), (127, f"−{limit}")]:
        _grid(canvas, x, y + offset, solid=offset == 75, alpha=71 if offset == 75 else 26)
        canvas.text(x + 620, y + offset + 5, label, 14, _AXIS, align="right", baseline=True)
    width = min(10, step * 0.55)
    for i, value in enumerate(values):
        if value is None or value == 0:
            continue
        height = max(2, abs(value) * 52 / limit)
        left = x + step * (i + 0.5) - width / 2
        top = y + 75 - height if value > 0 else y + 75
        canvas.rect((left, top, left + width, top + height), "#3CC4D1" if value > 0 else "#FF8A4C")
    indices = sorted({floor(k * (len(series) - 1) / 4 + 0.5) for k in range(5)})
    for i in indices:
        label = _day_month(series[i]["start"], lang, short=True)
        width = _width(label, 14)
        left = x if i == 0 else x + step * (i + 0.5) - width / 2
        left = max(x, min(left, x + 620 - width))
        canvas.text(left, y + 176, label, 14, _AXIS, baseline=True)


def render(card: dict) -> bytes:
    """Return a 1200x675 RGB PNG; card and its series are never modified."""
    lang, kind, series = card["lang"], card["kind"], card["series"]
    text = _TEXT[lang]
    canvas = _Canvas()
    canvas.rect((488, 52, 1144, 623), _PANEL, radius=24, outline=(255, 255, 255, 20))
    _logo(canvas)
    canvas.text(116, 54, "UZ Economic Index", 19, weight="SemiBold", spacing=0.2)
    canvas.text(116, 79, text["tagline"], 14, _MUTED)
    title_size = _fit(text[kind], 40, 380, "SemiBold", -0.6)
    canvas.text(56, 142, text[kind], title_size, weight="SemiBold", spacing=-0.6, line_height=44)
    period = _period_date(card["start"], card["end"], lang)
    canvas.text(56, 192, period, _fit(period, 22, 380), _MUTED)
    _metric(canvas, 56, "eai", card["eai"], card["d_eai"], lang)
    _metric(canvas, 258, "esi", card["esi"], card["d_esi"], lang)
    heading = text["days" if kind == "kun" else "weeks"].format(n=len(series))
    canvas.text(517, 79, heading, 20, weight="SemiBold")
    legend_esi = 1115 - _width("ESI", 14)
    legend_eai = legend_esi - 18 - 20 - _width("EAI, %", 14)
    canvas.rect((legend_eai - 26, 91, legend_eai - 8, 94), _BLUE, radius=1.5)
    canvas.text(legend_eai, 83, "EAI, %", 14, _MUTED)
    canvas.rect((legend_esi - 18, 87.5, legend_esi - 8, 97.5), "#3CC4D1", radius=3)
    canvas.text(legend_esi, 83, "ESI", 14, _MUTED)
    _eai_chart(canvas, [row["eai"] for row in series], lang)
    _esi_chart(canvas, series, lang)
    output = BytesIO()
    canvas.image.resize((1200, 675), Image.Resampling.LANCZOS).save(output, format="PNG")
    return output.getvalue()
