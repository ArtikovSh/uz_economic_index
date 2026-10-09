"""Database-free checks for the bot cards and committed PNG assets."""
import copy
from datetime import date, timedelta
import importlib.util
from io import BytesIO
from pathlib import Path
import sys

from PIL import Image
import pytest


REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "app" / "api"))
import _card  # noqa: E402


TILES = (
    "logo", "eai", "esi", "news", "topics", "up", "down", "week",
    "user", "bell", "lock", "globe", "check",
)
GLYPHS = (
    "dashboard", "topics", "news", "week", "eai", "esi", "user",
    "globe", "bell", "login", "back", "up", "down",
)


def card_data(kind="kun", lang="uz"):
    start = date(2026, 10, 5) if kind == "kun" else date(2026, 9, 28)
    count, step = (30, 1) if kind == "kun" else (12, 7)
    eai = [42.3, 47.2, 51.4, 45.1, 40.1]
    esi = [25.9, 14.7, 10.6, 0.0, -1.6]
    series = [
        {
            "start": (start - timedelta(days=step * (count - i - 1))).isoformat(),
            "eai": eai[i % len(eai)],
            "esi": esi[i % len(esi)],
        }
        for i in range(count)
    ]
    return {
        "kind": kind, "lang": lang,
        "start": start.isoformat(),
        "end": (start + timedelta(days=step - 1)).isoformat(),
        "eai": series[-1]["eai"], "esi": series[-1]["esi"],
        "d_eai": 8.3, "d_esi": -1.6,
        "nonad": 1234, "econ": 567, "channels": 5,
        "series": series,
    }


def assert_card_png(payload):
    assert isinstance(payload, bytes)
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    with Image.open(BytesIO(payload)) as image:
        image.load()
        assert image.format == "PNG"
        assert image.size == (1200, 675)
        assert image.mode == "RGB"


@pytest.mark.parametrize("lang", ["uz", "ru", "en"])
@pytest.mark.parametrize("kind", ["kun", "hafta"])
def test_render_languages_and_periods(lang, kind):
    card = card_data(kind, lang)
    original = copy.deepcopy(card)
    assert_card_png(_card.render(card))
    assert card == original


@pytest.mark.parametrize("case", [
    "gaps", "only_last_point", "one_point", "esi_none", "deltas_none",
    "negative_esi", "zero_deltas", "all_missing", "independent_gaps", "extremes",
])
def test_render_edge_cases(case):
    card = card_data()
    series = card["series"]
    if case == "gaps":
        for point in series[3:6] + series[20:27]:
            point.update(eai=None, esi=None)
    elif case == "only_last_point":
        card.update(lang="ru", d_eai=None, d_esi=None)
        for point in series[:-1]:
            point.update(eai=None, esi=None)
    elif case == "one_point":
        card["series"] = series[-1:]
    elif case == "esi_none":
        card.update(esi=None, d_esi=None)
        for point in series:
            point["esi"] = None
    elif case == "deltas_none":
        card.update(d_eai=None, d_esi=None)
    elif case == "negative_esi":
        card.update(esi=-3.2, d_esi=-8.0)
        series[-1]["esi"] = -3.2
    elif case == "zero_deltas":
        card.update(esi=0.0, d_eai=0.0, d_esi=0.0)
        series[-1]["esi"] = 0.0
    elif case == "all_missing":
        card.update(eai=None, esi=None, d_eai=None, d_esi=None, nonad=0, econ=0)
        for point in series:
            point.update(eai=None, esi=None)
    elif case == "independent_gaps":
        for point in series[2:8]:
            point["eai"] = None
        for point in series[9:16]:
            point["esi"] = None
    elif case == "extremes":
        series[0].update(eai=0.0, esi=-100.0)
        series[-1].update(eai=100.0, esi=100.0)
        card.update(eai=100.0, esi=100.0, d_eai=100.0, d_esi=200.0)
    original = copy.deepcopy(card)
    assert_card_png(_card.render(card))
    assert card == original


@pytest.mark.parametrize("lang, decimal, negative, positive, zero", [
    ("uz", "44,6", "−1,6", "+17,3", "0,0"),
    ("ru", "44,6", "−1,6", "+17,3", "0,0"),
    ("en", "44.6", "−1.6", "+17.3", "0.0"),
])
def test_number_formats(lang, decimal, negative, positive, zero):
    assert _card._number(44.6, lang) == decimal
    assert _card._number(-1.6, lang) == negative
    assert _card._number(17.3, lang, signed=True) == positive
    assert _card._number(0, lang, signed=True) == zero
    assert _card._number(-0.0, lang, signed=True) == zero
    assert _card._number(None, lang) == "—"
    assert _card._number(None, lang, signed=True) == "—"


@pytest.mark.parametrize("lang, day, same_month, week, new_year, tick", [
    ("uz", "4-oktabr 2026", "21–27-sentabr 2026", "29-sentabr – 5-oktabr 2026",
     "28-dekabr 2026 – 3-yanvar 2027", "5-sen"),
    ("ru", "4 октября 2026", "21–27 сентября 2026", "29 сентября – 5 октября 2026",
     "28 декабря 2026 – 3 января 2027", "5 сен"),
    ("en", "4 October 2026", "21–27 September 2026", "29 September – 5 October 2026",
     "28 December 2026 – 3 January 2027", "5 Sep"),
])
def test_date_formats(lang, day, same_month, week, new_year, tick):
    assert _card._period_date("2026-10-04", "2026-10-04", lang) == day
    assert _card._period_date("2026-09-21", "2026-09-27", lang) == same_month
    assert _card._period_date("2026-09-29", "2026-10-05", lang) == week
    assert _card._period_date("2026-12-28", "2027-01-03", lang) == new_year
    assert _card._day_month("2026-09-05", lang, short=True) == tick


def test_render_from_another_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    # A fresh module cannot reuse fonts cached while the working directory was the repo.
    spec = importlib.util.spec_from_file_location("_card_other_cwd", REPO / "app" / "api" / "_card.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    assert_card_png(module.render(card_data(lang="ru")))
    assert list(tmp_path.iterdir()) == []


def test_avatar_dimensions():
    with Image.open(REPO / "app" / "public" / "bot" / "avatar.png") as image:
        image.load()
        assert image.format == "PNG"
        assert image.size == (640, 640)


@pytest.mark.parametrize("name", TILES)
def test_tile_assets(name):
    with Image.open(REPO / "app" / "public" / "bot" / "emoji" / f"t-{name}.png") as image:
        image.load()
        assert image.format == "PNG"
        assert image.size == (100, 100)
        assert image.mode == "RGBA"
        assert image.getchannel("A").getextrema() == (0, 255)


@pytest.mark.parametrize("name", GLYPHS)
def test_glyph_assets(name):
    with Image.open(REPO / "app" / "public" / "bot" / "emoji" / f"g-{name}.png") as image:
        image.load()
        assert image.format == "PNG"
        assert image.size == (100, 100)
        assert image.mode == "RGBA"
        assert image.getchannel("A").getextrema() == (0, 255)
        for corner in ((0, 0), (99, 0), (0, 99), (99, 99)):
            assert image.getpixel(corner)[3] == 0
