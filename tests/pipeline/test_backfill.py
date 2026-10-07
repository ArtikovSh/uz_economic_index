"""backfill.py on in-memory tables and a fake Telegram (no network)."""
from datetime import date

import pandas as pd

import backfill
from store import LEDGER_COLS, PENDING_COLS, RAW_COLS


def raw(channel, mid, utc):
    return {"channel": channel, "message_id": mid, "date": utc, "views": 1, "forwards": 0,
            "raw_text": "news", "scraped_at": "2026-10-07 00:00:00"}


def test_days_in_range_and_single_day():
    assert backfill.days_in("2026-09-29..2026-10-01") == [date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 1)]
    assert backfill.days_in("2026-10-02") == [date(2026, 10, 2)]


def test_window_is_the_tashkent_day_in_utc():
    start, end = backfill.window(date(2026, 9, 28))
    assert (start.isoformat(), end.isoformat()) == ("2026-09-27T19:00:00+00:00", "2026-09-28T19:00:00+00:00")


def test_collects_only_missing_days_and_channels(monkeypatch):
    ledger = pd.DataFrame([{**raw("@a", 1, "2026-09-26 10:00:00"), "date_local": "2026-09-26 15:00"}],
                          columns=LEDGER_COLS)
    pending = pd.DataFrame([raw("@a", 2, "2026-09-28 05:00:00")], columns=PENDING_COLS)   # @a has 28 Sep
    calls, saved = [], []

    async def scraper(channels, start, end):
        calls.append((end.date().isoformat(), tuple(channels)))         # end = next Tashkent midnight
        rows = [raw(ch, 100 + len(calls) * 10 + i, end.strftime("%Y-%m-%d 08:00:00")) for i, ch in enumerate(channels)]
        return pd.DataFrame(rows, columns=RAW_COLS), ({"@b": "ValueError: no such channel"} if len(calls) == 2 else {})

    monkeypatch.setattr(backfill, "active_channels", lambda: ["@a", "@b"])
    monkeypatch.setattr(backfill, "load_ledger", lambda: ledger)
    monkeypatch.setattr(backfill, "load_pending", lambda: pending)
    monkeypatch.setattr(backfill, "save_pending", lambda df: saved.append(len(df)))
    monkeypatch.setattr(backfill, "run_scraper", scraper)

    code = backfill.main("2026-09-25..2026-09-29")       # 25, 26: final; 28: only @b missing
    assert calls == [("2026-09-27", ("@a", "@b")), ("2026-09-28", ("@b",)), ("2026-09-29", ("@a", "@b"))]
    assert saved == [3, 4, 6]
    assert code == 1                                       # a channel failed on 28 Sep -> alert
