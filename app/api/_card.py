"""Render the bot's daily and weekly summary cards without external I/O, in the Central Bank's
publication style: white background, the base colours, Arimo (Arial's metrics) 12 for the title and
8 inside the chart, no gridlines, a grey frame and zero line, the legend and the source below.
1000 px stand for 8.3 cm (a "double" chart), so the type reads on a phone as it does on paper."""
from datetime import date
from functools import lru_cache
from io import BytesIO
from math import ceil, floor, log10
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

__all__ = ["render"]

_SIZE = 1000
_PT = _SIZE / 235.3                  # pixels per typographic point at 8.3 cm
_SCALE = 2                           # drawn twice as large, then reduced: smooth edges
_MARGIN = 26
_FONT_DIR = Path(__file__).resolve().parent / "_fonts"
_BLUE, _RED = (47, 73, 111), (190, 52, 85)          # the guide's base colours 1 and 2
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
    "uz": {
        "kun": "Kunlik xulosa: kayfiyat va e’tibor indekslari",
        "hafta": "Haftalik xulosa: kayfiyat va e’tibor indekslari",
        "esi": "kayfiyat (ESI)", "eai": "e’tibor (EAI), foizda (o‘ng shkala)",
        "source": "Manba: Telegram kanallaridagi xabarlar asosida hisob-kitoblar.",
    },
    "ru": {
        "kun": "Итоги дня: индексы настроения и внимания",
        "hafta": "Итоги недели: индексы настроения и внимания",
        "esi": "настроение (ESI)", "eai": "внимание (EAI), в процентах (правая шкала)",
        "source": "Источник: расчёты на основе сообщений Telegram-каналов.",
    },
    "en": {
        "kun": "Daily summary: sentiment and attention indices",
        "hafta": "Weekly summary: sentiment and attention indices",
        "esi": "sentiment (ESI)", "eai": "attention (EAI), per cent (right scale)",
        "source": "Source: calculations based on posts in Telegram channels.",
    },
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
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw - 1e-9)
    step = max(step, 0.1)
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
        self.height = height
        self.image = Image.new("RGB", (_SIZE * _SCALE, height * _SCALE), _WHITE)
        self.draw = ImageDraw.Draw(self.image)

    def line(self, points, color, points_wide):
        self.draw.line([(x * _SCALE, y * _SCALE) for x, y in points], fill=color,
                       width=max(1, round(points_wide * _PT * _SCALE)), joint="curve")

    def rect(self, box, color):
        x0, y0, x1, y1 = box
        self.draw.rectangle((x0 * _SCALE, min(y0, y1) * _SCALE, x1 * _SCALE, max(y0, y1) * _SCALE), fill=color)

    def text(self, x, y, text, points, bold=False, italic=False, color=_BLACK, anchor="la"):
        self.draw.text((x * _SCALE, y * _SCALE), text, font=_font(points, bold, italic), fill=color, anchor=anchor)

    def width(self, text, points, bold=False, italic=False):
        return _font(points, bold, italic).getlength(text) / _SCALE

    def place(self, text, x, y, anchor, box):
        """A bold 8 pt data label moved, if needed, to stay inside the plot frame."""
        x0, y0, x1, y1 = (v / _SCALE for v in self.draw.textbbox((x * _SCALE, y * _SCALE), text,
                                                                     font=_font(8, True), anchor=anchor))
        left, top, right, bottom = box
        dx = (left + 4 - x0) if x0 < left + 4 else (right - 4 - x1) if x1 > right - 4 else 0
        dy = (top + 4 - y0) if y0 < top + 4 else (bottom - 4 - y1) if y1 > bottom - 4 else 0
        self.text(x + dx, y + dy, text, 8, bold=True, anchor=anchor)

    def png(self, height):
        output = BytesIO()
        self.image.crop((0, 0, _SIZE * _SCALE, height * _SCALE)).resize(
            (_SIZE, height), Image.Resampling.LANCZOS).save(output, format="PNG")
        return output.getvalue()


def _title(canvas, y, bold, italic):
    """3 pt rule above; 'Bold title, italic part' in 12 pt, wrapped at the margins."""
    canvas.line([(_MARGIN, y), (_SIZE - _MARGIN, y)], _BLUE, 3)
    y += 26
    x = _MARGIN
    words = [(w, True) for w in (bold + ",").split()] + [(w, False) for w in italic.split()]
    for word, is_bold in words:
        width = canvas.width(word, 12, bold=is_bold, italic=not is_bold)
        if x > _MARGIN and x + width > _SIZE - _MARGIN:
            x, y = _MARGIN, y + 60
        canvas.text(x, y, word, 12, bold=is_bold, italic=not is_bold)
        x += width + canvas.width(" ", 12)
    return y + 76


def _legend(canvas, y, items):
    """Bottom legend, centred; a second row when one is too wide."""
    rows, row = [], []
    for item in items:
        trial = row + [item]
        if row and sum(36 + 10 + canvas.width(i[0], 8) for i in trial) + 40 * (len(trial) - 1) > _SIZE - 2 * _MARGIN:
            rows.append(row)
            row = [item]
        else:
            row = trial
    rows.append(row)
    for row in rows:
        total = sum(36 + 10 + canvas.width(i[0], 8) for i in row) + 40 * (len(row) - 1)
        x = (_SIZE - total) / 2
        for label, color, kind in row:
            middle = y + 17
            if kind == "bar":
                canvas.rect((x + 10, middle - 9, x + 28, middle + 9), color)
            else:
                canvas.line([(x, middle), (x + 36, middle)], color, 1.75)
            canvas.text(x + 46, middle, label, 8, anchor="lm")
            x += 36 + 10 + canvas.width(label, 8) + 40
        y += 44
    return y


def render(card: dict) -> bytes:
    """Return an RGB PNG 1000 px wide (about as tall; a long title adds a line); card and its
    series are never modified."""
    lang, kind, series = card["lang"], card["kind"], card["series"]
    text = _TEXT[lang]
    canvas = _Canvas(1400)
    y = _title(canvas, 18, text[kind], _period_date(card["start"], card["end"], lang))
    left, right, top, bottom = _MARGIN + 66, _SIZE - _MARGIN - 66, y + 10, y + 570

    esi = [row["esi"] for row in series]
    eai = [row["eai"] for row in series]
    have_esi = [v for v in esi if v is not None]
    have_eai = [v for v in eai if v is not None]
    left_ticks, left_dec = _scale(min([0, *have_esi]), max([0, *have_esi]) if have_esi else 50)
    right_ticks, right_dec = _scale(0, max(have_eai) * 1.05 if have_eai else 40)
    ly = lambda v: bottom - (v - left_ticks[0]) / (left_ticks[-1] - left_ticks[0]) * (bottom - top)
    ry = lambda v: bottom - (v - right_ticks[0]) / (right_ticks[-1] - right_ticks[0]) * (bottom - top)

    # plot-area frame and the zero line: grey, 0.75 pt; no gridlines, no tick marks
    canvas.line([(left, top), (right, top), (right, bottom), (left, bottom), (left, top)], _GREY, 0.75)
    canvas.line([(left, ly(0)), (right, ly(0))], _GREY, 0.75)
    for v in left_ticks:
        canvas.text(left - 12, ly(v), _tick(v, lang, left_dec), 8, anchor="rm")
    for v in right_ticks:
        canvas.text(right + 12, ry(v), _tick(v, lang, right_dec), 8, anchor="lm")

    slot = (right - left) / max(1, len(series))
    bar = slot / 2.5                                       # gap width 150%
    centre = lambda i: left + slot * (i + 0.5)
    for i, v in enumerate(esi):
        if v:
            canvas.rect((centre(i) - bar / 2, ly(v), centre(i) + bar / 2, ly(0)), _BLUE)
    segment = []
    for i, v in enumerate([*eai, None]):
        if v is None:
            if len(segment) > 1:
                canvas.line(_smooth(segment), _RED, 1.75)
            elif segment:
                x0, y0 = segment[0]
                canvas.line([(x0 - 6, y0), (x0 + 6, y0)], _RED, 1.75)
            segment = []
        else:
            segment.append((centre(i), ry(v)))

    # data labels: the latest values, bold, clear of each other
    last_eai = next((i for i in range(len(eai) - 1, -1, -1) if eai[i] is not None), None)
    last_esi = next((i for i in range(len(esi) - 1, -1, -1) if esi[i] is not None), None)
    frame = (left, top, right, bottom)
    point = (centre(last_eai), ry(eai[last_eai])) if last_eai is not None else None
    above = True
    if point:
        bar_top = ly(max(esi[last_eai] or 0, 0))
        above = point[1] < bar_top
        canvas.place(_number(eai[last_eai], lang), point[0] - 16, point[1] + (-14 if above else 14),
                     "rb" if above else "rt", frame)
    if last_esi is not None:
        v = esi[last_esi]
        if v >= 0:
            x, y, anchor = centre(last_esi), ly(v) - 8, "mb"
            if point and not above and abs(y - point[1]) < 44:
                y = point[1] - 22
        elif ly(v) + 46 < bottom:
            x, y, anchor = centre(last_esi), ly(v) + 8, "mt"
        else:                                              # a deep bar: the label goes beside its end
            x, y, anchor = centre(last_esi) - bar / 2 - 8, ly(v) - 4, "rm"
        canvas.place(_number(v, lang), x, y, anchor, frame)

    # category axis: day numbers (or week starts) below the frame, each month named once
    days = [date.fromisoformat(row["start"]) for row in series]
    for i, day in enumerate(days):
        shown = (day.day == 1 or day.day % 5 == 0) if kind == "kun" else (len(days) - 1 - i) % 2 == 0
        if shown or len(days) == 1:
            canvas.text(centre(i), bottom + 12, str(day.day), 8, anchor="mt")
    groups = []
    for i, day in enumerate(days):
        if not groups or groups[-1][0] != (day.year, day.month):
            groups.append([(day.year, day.month), i, i])
        groups[-1][2] = i
    for (_, month), first, last in groups:
        if last - first >= 2 or len(groups) == 1:
            canvas.text(left + slot * (first + last + 1) / 2, bottom + 58, _GROUP_MONTHS[lang][month - 1], 8, anchor="mt")
    for _, first, _ in groups[1:]:
        canvas.line([(left + slot * first, bottom), (left + slot * first, bottom + 96)], _GREY, 0.75)

    y = _legend(canvas, bottom + 112, [(text["esi"], _BLUE, "bar"), (text["eai"], _RED, "line")])
    canvas.line([(_MARGIN, y + 20), (_SIZE - _MARGIN, y + 20)], _BLUE, 0.5)
    x, y = _MARGIN, y + 34                                 # the source, 8 pt italic, wrapped
    for word in text["source"].split():
        width = canvas.width(word, 8, italic=True)
        if x > _MARGIN and x + width > _SIZE - _MARGIN:
            x, y = _MARGIN, y + 42
        canvas.text(x, y, word, 8, italic=True)
        x += width + canvas.width(" ", 8, italic=True)
    return canvas.png(round(y + 40 + 26))
