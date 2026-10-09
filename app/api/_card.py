"""Render the bot's daily and weekly summary cards without external I/O, laid out like the
double-chart page of the Central Bank's publication guide: a section heading, a 3 pt rule, two
figures side by side (EAI line | ESI bars) with their own titles, the latest values in bold, a
0.5 pt rule and the source. Arimo (Arial's metrics), 8 pt inside the charts, 12 pt titles;
1600 px stand for 17 cm, two 8.3 cm figures and the gap between them."""
from datetime import date
from functools import lru_cache
from io import BytesIO
from math import ceil, floor, log10
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

__all__ = ["render"]

_WIDTH = 1600
_PT = _WIDTH / 482                   # pixels per typographic point at 17 cm
_SCALE = 2                           # drawn twice as large, then reduced: smooth edges
_MARGIN, _GAP = 34, 60
_FONT_DIR = Path(__file__).resolve().parent / "_fonts"
_BLUE = (47, 73, 111)                # the guide's base colour 1
_GREY, _BLACK, _WHITE = (191, 191, 191), (0, 0, 0), (255, 255, 255)
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
_GROUP_MONTHS = {                    # under the days of a month on the axis
    "uz": _MONTHS["uz"],
    "ru": "январь февраль март апрель май июнь июль август сентябрь октябрь ноябрь декабрь".split(),
    "en": _MONTHS["en"],
}
_TEXT = {
    "uz": {"kun": "Kunlik xulosa", "hafta": "Haftalik xulosa",
           "eai": ("E’tibor indeksi (EAI)", "foizda"), "esi": ("Kayfiyat indeksi (ESI)", "balans"),
           "source": "Manba: Telegram kanallaridagi xabarlar asosida hisob-kitoblar."},
    "ru": {"kun": "Итоги дня", "hafta": "Итоги недели",
           "eai": ("Индекс внимания (EAI)", "в процентах"), "esi": ("Индекс настроения (ESI)", "баланс"),
           "source": "Источник: расчёты на основе сообщений Telegram-каналов."},
    "en": {"kun": "Daily summary", "hafta": "Weekly summary",
           "eai": ("Attention index (EAI)", "per cent"), "esi": ("Sentiment index (ESI)", "balance"),
           "source": "Source: calculations based on posts in Telegram channels."},
}


def _number(value, lang, signed=False):
    if value is None:
        return "—"
    sign = "−" if value < 0 else "+" if signed and value > 0 else ""
    digits = f"{abs(value):.1f}"
    return sign + (digits if lang == "en" else digits.replace(".", ","))


def _tick(value, lang, decimals):
    digits = f"{abs(value):.{decimals}f}"
    return ("−" if value < 0 else "") + (digits if lang == "en" else digits.replace(".", ","))


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


@lru_cache(maxsize=64)
def _font(points, bold=False, italic=False):
    style = {(0, 0): "Regular", (1, 0): "Bold", (0, 1): "Italic", (1, 1): "BoldItalic"}[(bold, italic)]
    return ImageFont.truetype(str(_FONT_DIR / f"Arimo-{style}.ttf"), round(points * _PT * _SCALE))


def _scale(lo, hi, steps=4):
    """Round axis limits and the values between them (at most one decimal)."""
    if hi - lo < 1e-9:
        hi = lo + 1
    raw = (hi - lo) / steps
    magnitude = 10 ** floor(log10(raw))
    step = max(0.1, next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw - 1e-9))
    first, last = floor(lo / step + 1e-9) * step, ceil(hi / step - 1e-9) * step
    ticks = [round(first + i * step, 1) for i in range(round((last - first) / step) + 1)]
    return ticks, (0 if all(t == int(t) for t in ticks) else 1)


def _smooth(points, steps=12):
    """Catmull-Rom curve through the points: a smoothed line, as the guide asks."""
    if len(points) < 3:
        return points
    p = [points[0], *points, points[-1]]
    out = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for k in range(steps):
            t = k / steps
            out.append(tuple(0.5 * (2 * p1[j] + (p2[j] - p0[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t * t
                                    + (3 * p1[j] - p0[j] - 3 * p2[j] + p3[j]) * t ** 3) for j in (0, 1)))
    return out + [points[-1]]


class _Canvas:
    def __init__(self, height):
        self.image = Image.new("RGB", (_WIDTH * _SCALE, height * _SCALE), _WHITE)
        self.draw = ImageDraw.Draw(self.image)

    def line(self, points, color, points_wide):
        self.draw.line([(x * _SCALE, y * _SCALE) for x, y in points], fill=color,
                       width=max(1, round(points_wide * _PT * _SCALE)), joint="curve")

    def rect(self, box, color):
        x0, y0, x1, y1 = box
        self.draw.rectangle((x0 * _SCALE, min(y0, y1) * _SCALE, x1 * _SCALE, max(y0, y1) * _SCALE), fill=color)

    def text(self, x, y, text, points, bold=False, italic=False, anchor="la"):
        self.draw.text((x * _SCALE, y * _SCALE), text, font=_font(points, bold, italic), fill=_BLACK, anchor=anchor)

    def width(self, text, points, bold=False, italic=False):
        return _font(points, bold, italic).getlength(text) / _SCALE

    def label(self, text, x, y, anchor, frame):
        """A bold 8 pt data label, moved if needed to stay inside the plot frame."""
        x0, y0, x1, y1 = (v / _SCALE for v in self.draw.textbbox((x * _SCALE, y * _SCALE), text,
                                                                     font=_font(8, True), anchor=anchor))
        left, top, right, bottom = frame
        dx = (left + 4 - x0) if x0 < left + 4 else (right - 4 - x1) if x1 > right - 4 else 0
        dy = (top + 4 - y0) if y0 < top + 4 else (bottom - 4 - y1) if y1 > bottom - 4 else 0
        self.text(x + dx, y + dy, text, 8, bold=True, anchor=anchor)

    def wrapped(self, x0, x1, y, words, points, step):
        """Words given as (word, bold, italic), wrapped between x0 and x1; returns the last line's y."""
        x = x0
        for word, bold, italic in words:
            width = self.width(word, points, bold, italic)
            if x > x0 and x + width > x1:
                x, y = x0, y + step
            self.text(x, y, word, points, bold, italic)
            x += width + self.width(" ", points)
        return y

    def png(self, height):
        output = BytesIO()
        self.image.crop((0, 0, _WIDTH * _SCALE, height * _SCALE)).resize(
            (_WIDTH, height), Image.Resampling.LANCZOS).save(output, format="PNG")
        return output.getvalue()


def _figure(canvas, x0, x1, top, title, values, days, kind, lang, bars):
    """One figure: its title, the framed plot, the axes and the latest values; returns its bottom."""
    name, unit = title
    words = [(w, True, False) for w in (name + ",").split()] + [(w, False, True) for w in unit.split()]
    top = canvas.wrapped(x0, x1, top, words, 12, 46) + 64
    have = [v for v in values if v is not None]
    if bars:
        ticks, decimals = _scale(min([0, *have]), max([0, *have]) * 1.1 if have else 50)
    else:
        ticks, decimals = _scale(0, max(have) * 1.12 if have else 40)
    left = x0 + max(canvas.width(_tick(v, lang, decimals), 8) for v in ticks) + 10
    right, bottom = x1, top + 400
    y = lambda v: bottom - (v - ticks[0]) / (ticks[-1] - ticks[0]) * (bottom - top)
    frame = (left, top, right, bottom)

    # the plot-area frame and the zero line: grey, 0.75 pt; no gridlines, no tick marks
    canvas.line([(left, top), (right, top), (right, bottom), (left, bottom), (left, top)], _GREY, 0.75)
    canvas.line([(left, y(0)), (right, y(0))], _GREY, 0.75)
    for v in ticks:
        canvas.text(left - 10, y(v), _tick(v, lang, decimals), 8, anchor="rm")

    n = max(1, len(values))
    slot = (right - left) / n
    centre = lambda i: left + slot * (i + 0.5)
    shown = 1 if kind == "kun" else 3                     # 30 days leave room for one label, 12 weeks for three
    latest = [i for i in range(len(values) - 1, -1, -1) if values[i] is not None][:shown]
    if bars:
        width = slot / 2.5                                # gap width 150%
        for i, v in enumerate(values):
            if v:
                canvas.rect((centre(i) - width / 2, y(v), centre(i) + width / 2, y(0)), _BLUE)
        for i in latest:
            v = values[i]
            # above the taller of the bar and its two neighbours: a label pushed in from the frame
            # edge must not sit on the next bar
            near = [values[j] for j in range(max(0, i - 2), min(len(values), i + 3)) if values[j] is not None]
            if v >= 0:
                canvas.label(_number(v, lang), centre(i), y(max(near)) - 8, "mb", frame)
            else:
                canvas.label(_number(v, lang), centre(i), y(min(near)) + 8, "mt", frame)
    else:
        segment = []
        for i, v in enumerate([*values, None]):
            if v is None:
                if len(segment) > 1:
                    canvas.line(_smooth(segment), _BLUE, 1.75)
                elif segment:
                    canvas.line([(segment[0][0] - 6, segment[0][1]), (segment[0][0] + 6, segment[0][1])], _BLUE, 1.75)
                segment = []
            else:
                segment.append((centre(i), y(v)))
        for i in latest:
            canvas.label(_number(values[i], lang), centre(i), y(values[i]) - 14, "mb", frame)

    # category axis: day numbers (or week starts) below the frame, each month named once
    for i, day in enumerate(days):
        if len(days) == 1 or (kind == "kun" and (day.day == 1 or day.day % 5 == 0)) or \
                (kind != "kun" and (len(days) - 1 - i) % 2 == 0):
            canvas.text(centre(i), bottom + 10, str(day.day), 8, anchor="mt")
    groups = []
    for i, day in enumerate(days):
        if not groups or groups[-1][0] != (day.year, day.month):
            groups.append([(day.year, day.month), i, i])
        groups[-1][2] = i
    for (_, month), first, last in groups:
        if last - first >= 2 or len(groups) == 1:
            canvas.text(left + slot * (first + last + 1) / 2, bottom + 46, _GROUP_MONTHS[lang][month - 1], 8, anchor="mt")
    for _, first, _ in groups[1:]:
        canvas.line([(left + slot * first, bottom), (left + slot * first, bottom + 76)], _GREY, 0.75)
    return bottom + 80


def render(card: dict) -> bytes:
    """Return an RGB PNG 1600 px wide (about 760 px tall); card and its series are never modified."""
    lang, kind, series = card["lang"], card["kind"], card["series"]
    text = _TEXT[lang]
    canvas = _Canvas(1100)
    heading = f"{text[kind]}, {_period_date(card['start'], card['end'], lang)}"
    canvas.text(_MARGIN, 22, heading, 14, bold=True, italic=True)
    canvas.line([(_MARGIN, 88), (_WIDTH - _MARGIN, 88)], _BLUE, 3)
    half = (_WIDTH - 2 * _MARGIN - _GAP) / 2
    days = [date.fromisoformat(row["start"]) for row in series]
    left = _figure(canvas, _MARGIN, _MARGIN + half, 112, text["eai"], [row["eai"] for row in series],
                   days, kind, lang, bars=False)
    right = _figure(canvas, _MARGIN + half + _GAP, _WIDTH - _MARGIN, 112, text["esi"], [row["esi"] for row in series],
                    days, kind, lang, bars=True)
    y = max(left, right) + 14
    canvas.line([(_MARGIN, y), (_WIDTH - _MARGIN, y)], _BLUE, 0.5)
    y = canvas.wrapped(_MARGIN, _WIDTH - _MARGIN, y + 12, [(w, False, True) for w in text["source"].split()], 8, 32)
    return canvas.png(round(y + 30 + 24))
