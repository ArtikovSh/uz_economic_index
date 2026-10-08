from datetime import date

import pandas as pd
import pytest

from config import LLM_LABEL_VERSION
from indicator import (
    finalize_days,
    has_ad_marker,
    index_row,
    ledger_rows,
    local_day,
    new_index_rows,
    period_of,
)
from store import INDEX_COLS, LEDGER_COLS, PENDING_COLS


def pending_rows(*overrides):
    base = {
        "channel": "@a", "date": "2026-10-01 08:00:00", "views": 10,
        "forwards": 1, "raw_text": "Economic news", "scraped_at": "2026-10-02 08:00:00",
        "is_economic": 1, "primary_topic": "macro", "relevance": 0.8,
        "sentiment": 0.0, "is_ad": 0, "is_digest": 0, "is_foreign": 0,
        "label_version": LLM_LABEL_VERSION, "label_model": "test", "label_error": None,
    }
    return pd.DataFrame(
        [{**base, "message_id": n, **values} for n, values in enumerate(overrides, 1)],
        columns=PENDING_COLS,
    )


def empty_pending():
    return pd.DataFrame(columns=PENDING_COLS)


def empty_ledger():
    return pd.DataFrame(columns=LEDGER_COLS)


def empty_indices():
    return pd.DataFrame(columns=INDEX_COLS)


@pytest.mark.parametrize("text", [
    "(реклама)", "( Reklama )", "#реклама", "# reklama",
    "на правах рекламы", "reklama huquqida",
    "Yangilik. Реклама", "Yangilik. **Reklama**", "Yangilik. Reklama.",
    "#партнерский материал", "#hamkorlik", "Reklama huquqi asosida", "Текст\nerid: 2VtzqwXYZ",
    "Текст\nРеклама. ООО «Ромашка», ИНН 123",
])
def test_has_ad_marker_detects_sponsorship(text):
    assert has_ad_marker(text) is True


@pytest.mark.parametrize("text", ["рынок рекламы вырос на 5%", "Реклама на билбордах подорожала.",
                                  "Hamkorlik kengayadi", "", None])
def test_has_ad_marker_ignores_other_text(text):
    assert has_ad_marker(text) is False


@pytest.mark.parametrize("utc, expected", [
    ("2026-09-30 19:30:00", date(2026, 10, 1)),
    ("2026-09-30 18:59:00", date(2026, 9, 30)),
])
def test_local_day_crosses_tashkent_midnight(utc, expected):
    assert local_day(pd.Series([utc])).iloc[0] == expected


@pytest.mark.parametrize("day, ptype, label, start, end", [
    (date(2026, 10, 1), "kun", "2026-10-01", date(2026, 10, 1), date(2026, 10, 1)),
    (date(2026, 12, 31), "hafta", None, date(2026, 12, 28), date(2027, 1, 3)),
    (date(2027, 1, 1), "hafta", None, date(2026, 12, 28), date(2027, 1, 3)),
    (date(2028, 2, 10), "oy", "2028-02", date(2028, 2, 1), date(2028, 2, 29)),
    (date(2026, 10, 1), "oy", "2026-10", date(2026, 10, 1), date(2026, 10, 31)),
    (date(2028, 2, 10), "chorak", "2028-Q1", date(2028, 1, 1), date(2028, 3, 31)),
    (date(2026, 11, 20), "chorak", "2026-Q4", date(2026, 10, 1), date(2026, 12, 31)),
    (date(2028, 2, 10), "yil", "2028", date(2028, 1, 1), date(2028, 12, 31)),
])
def test_period_of_boundaries(day, ptype, label, start, end):
    if ptype == "hafta":
        iso = day.isocalendar()
        label = f"{iso.year}-W{iso.week:02d}"
    assert period_of(day, ptype) == (label, start, end)


def test_ledger_rows_ad_and_economic_flags():
    rows = ledger_rows(pending_rows(
        {},
        {"is_ad": 1},
        {"raw_text": "(реклама)"},
        {"is_digest": 1},
        {"is_foreign": 1},
    )).set_index("message_id")
    assert rows["is_ad"].tolist() == [0, 1, 1, 0, 0]
    assert rows["ad_marker"].tolist() == [0, 0, 1, 0, 0]
    assert rows["nonad"].tolist() == [1, 0, 0, 1, 1]
    assert rows["econ"].tolist() == [1, 0, 0, 0, 0]


def test_ledger_rows_tone_boundaries_and_non_economic_nan():
    rows = ledger_rows(pending_rows(
        {"sentiment": 0.15},
        {"sentiment": 0.16},
        {"sentiment": -0.15},
        {"sentiment": -0.16},
        {"sentiment": 0.9, "is_economic": 0},
        {"sentiment": -0.9, "is_foreign": 1},
    )).set_index("message_id")
    assert rows.loc[[1, 2, 3, 4], "tone"].tolist() == [0, 1, 0, -1]
    assert pd.isna(rows.loc[5, "tone"])
    assert pd.isna(rows.loc[6, "tone"])


def test_ledger_rows_local_timestamp_columns_and_sort_order():
    rows = ledger_rows(pending_rows(
        {"date": "2026-09-30 19:30:00", "channel": "@b", "message_id": 2},
        {"date": "2026-09-30 19:30:00", "channel": "@a", "message_id": 3},
        {"date": "2026-09-30 19:30:00", "channel": "@a", "message_id": 1},
    ))
    assert list(rows.columns) == LEDGER_COLS
    assert rows["date_local"].tolist() == ["2026-10-01 00:30"] * 3
    assert list(zip(rows["channel"], rows["message_id"])) == [
        ("@a", 1), ("@a", 3), ("@b", 2),
    ]


def test_index_row_counts_and_rounding():
    posts = pd.DataFrame([
        {"day": date(2026, 10, 1), "channel": "@a", "nonad": 1, "econ": 1, "tone": 1},
        {"day": date(2026, 10, 1), "channel": "@b", "nonad": 1, "econ": 1, "tone": 0},
        {"day": date(2026, 10, 1), "channel": "@b", "nonad": 1, "econ": 0, "tone": pd.NA},
    ])
    row = index_row("kun", "2026-10-01", date(2026, 10, 1), date(2026, 10, 1), posts, ["@a", "@b"])
    assert (row["posts"], row["days"], row["days_expected"]) == (3, 1, 1)
    assert (row["nonad"], row["econ"], row["pos"], row["neu"], row["neg"]) == (3, 2, 1, 1, 0)
    assert (row["EAI"], row["ESI"], row["note"]) == (66.7, 50.0, "")


def test_index_row_negative_balance():
    posts = pd.DataFrame({
        "day": [date(2026, 10, 1)] * 3, "channel": ["@a"] * 3,
        "nonad": [1, 1, 1], "econ": [1, 1, 1], "tone": [1, -1, -1],
    })
    row = index_row("kun", "2026-10-01", date(2026, 10, 1), date(2026, 10, 1), posts, ["@a"])
    assert (row["pos"], row["neu"], row["neg"], row["ESI"]) == (1, 0, 2, -33.3)


def test_index_row_zero_denominators_are_nan():
    posts = pd.DataFrame({
        "day": [date(2026, 10, 1)], "channel": ["@a"],
        "nonad": [0], "econ": [0], "tone": [pd.NA],
    })
    row = index_row("kun", "2026-10-01", date(2026, 10, 1), date(2026, 10, 1), posts, ["@a"])
    assert pd.isna(row["EAI"])
    assert pd.isna(row["ESI"])
    posts["nonad"] = 1
    row = index_row("kun", "2026-10-01", date(2026, 10, 1), date(2026, 10, 1), posts, ["@a"])
    assert row["EAI"] == 0.0
    assert pd.isna(row["ESI"])


def test_index_row_daily_missing_channel_note():
    posts = pd.DataFrame({
        "day": [date(2026, 10, 1)], "channel": ["@a"],
        "nonad": [1], "econ": [1], "tone": [0],
    })
    row = index_row("kun", "2026-10-01", date(2026, 10, 1), date(2026, 10, 1), posts, ["@c", "@a", "@b"])
    assert row["note"] == "yig'ilmagan kanal: @b, @c"


def test_index_row_period_gap_note_and_expected_days():
    posts = pd.DataFrame({
        "day": [date(2026, 10, 1), date(2026, 10, 3)], "channel": ["@a", "@a"],
        "nonad": [1, 1], "econ": [1, 1], "tone": [0, 0],
    })
    row = index_row("hafta", "2026-W40", date(2026, 9, 28), date(2026, 10, 4), posts, ["@a"])
    assert (row["days"], row["days_expected"], row["note"]) == (2, 7, "5 kun ma'lumotsiz")


def test_finalize_days_waits_for_oldest_unlabelled_post():
    pending = pending_rows(
        {"date": "2026-10-01 08:00:00", "label_version": "v3"},
        {"date": "2026-10-02 08:00:00"},
    )
    rows, remaining, days = finalize_days(pending, empty_ledger(), date(2026, 10, 2), ["@a"])
    assert rows.empty
    assert remaining["message_id"].tolist() == [1, 2]
    assert days == []


@pytest.mark.parametrize("post_day", ["2026-10-02 08:00:00", "2026-10-03 08:00:00"])
def test_finalize_days_waits_for_missing_channel_on_or_after_target(post_day):
    pending = pending_rows({"date": post_day, "channel": "@a"})
    rows, remaining, days = finalize_days(pending, empty_ledger(), date(2026, 10, 2), ["@a", "@b"])
    assert rows.empty
    assert remaining["message_id"].tolist() == [1]
    assert days == []


def test_finalize_days_allows_older_day_with_missing_channel():
    pending = pending_rows(
        {"date": "2026-10-01 08:00:00", "channel": "@a"},
        {"date": "2026-10-02 08:00:00", "channel": "@a"},
        {"date": "2026-10-02 09:00:00", "channel": "@b"},
    )
    rows, remaining, days = finalize_days(pending, empty_ledger(), date(2026, 10, 2), ["@a", "@b"])
    assert rows["message_id"].tolist() == [1, 2, 3]
    assert remaining.empty
    assert days == [date(2026, 10, 1), date(2026, 10, 2)]


def test_finalize_days_does_not_repeat_ledger_post():
    ledger = ledger_rows(pending_rows({"channel": "@a", "message_id": 1}))
    pending = pending_rows(
        {"channel": "@a", "message_id": 1},
        {"channel": "@b", "message_id": 2},
    )
    rows, remaining, days = finalize_days(pending, ledger, date(2026, 10, 1), ["@a", "@b"])
    assert rows["message_id"].tolist() == [2]
    assert remaining.empty
    assert days == [date(2026, 10, 1)]


def test_finalize_days_empty_pending_returns_empty_triple():
    rows, remaining, days = finalize_days(empty_pending(), empty_ledger(), date(2026, 10, 1), ["@a"])
    assert rows.empty and remaining.empty and days == []


def test_new_index_rows_only_emits_closed_days():
    ledger = ledger_rows(pending_rows({"date": "2026-10-01 08:00:00"}))
    rows = new_index_rows(ledger, empty_indices(), empty_pending(), date(2026, 10, 1), ["@a"])
    assert list(zip(rows["period_type"], rows["period"])) == [("kun", "2026-10-01")]
    assert list(rows.columns) == INDEX_COLS


def test_new_index_rows_emits_closed_periods_in_end_and_type_order():
    ledger = ledger_rows(pending_rows({"date": "2026-12-31 08:00:00"}))
    rows = new_index_rows(ledger, empty_indices(), empty_pending(), date(2026, 12, 31), ["@a"])
    assert list(zip(rows["period_type"], rows["period"])) == [
        ("kun", "2026-12-31"), ("oy", "2026-12"),
        ("chorak", "2026-Q4"), ("yil", "2026"),
    ]
    assert rows["end"].tolist() == ["2026-12-31"] * 4


def test_new_index_rows_skips_existing_period_type_and_label():
    ledger = ledger_rows(pending_rows({"date": "2026-12-31 08:00:00"}))
    indices = pd.DataFrame([{"period_type": "oy", "period": "2026-12"}])
    rows = new_index_rows(ledger, indices, empty_pending(), date(2026, 12, 31), ["@a"])
    assert list(rows["period_type"]) == ["kun", "chorak", "yil"]


def test_new_index_rows_closes_old_period_without_pending():
    ledger = ledger_rows(pending_rows({"date": "2026-10-01 08:00:00"}))
    rows = new_index_rows(ledger, empty_indices(), empty_pending(), date(2026, 10, 6), ["@a"])
    week = rows.loc[rows["period_type"] == "hafta"].iloc[0]
    iso = date(2026, 10, 1).isocalendar()
    assert week["period"] == f"{iso.year}-W{iso.week:02d}"
    assert (week["days"], week["days_expected"], week["note"]) == (1, 7, "6 kun ma'lumotsiz")
    assert rows["period_type"].tolist() == ["kun", "hafta"]


def test_new_index_rows_keeps_period_open_when_pending_remains():
    ledger = ledger_rows(pending_rows({"date": "2026-10-01 08:00:00"}))
    pending = pending_rows({"date": "2026-10-03 08:00:00"})
    rows = new_index_rows(ledger, empty_indices(), pending, date(2026, 10, 6), ["@a"])
    assert rows["period_type"].tolist() == ["kun"]


def test_new_index_rows_empty_ledger_has_index_columns():
    rows = new_index_rows(empty_ledger(), empty_indices(), empty_pending(), date(2026, 10, 1), ["@a"])
    assert rows.empty
    assert list(rows.columns) == INDEX_COLS
