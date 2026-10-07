"""history.py with a fake Telegram and a fake labeller (no network, no files)."""
from datetime import date, timedelta

import pandas as pd

import history
from config import LLM_LABEL_VERSION
from store import INDEX_COLS, LEDGER_COLS, PENDING_COLS, RAW_COLS, typed


def labeller(skip=0):
    def label(pending, save=None, sticky=None):
        pending = pending.copy()
        for c in ("primary_topic", "topics", "headline"):
            pending[c] = pending[c].astype(object)
        todo = [i for i in pending.index if str(pending.at[i, "label_version"]) != LLM_LABEL_VERSION]
        for i in todo[skip:]:
            for c, v in {"is_economic": 1, "primary_topic": "trade", "topics": "trade", "headline": "H",
                         "relevance": 1.0, "sentiment": 0.5, "is_ad": 0, "is_digest": 0, "is_foreign": 0,
                         "label_version": LLM_LABEL_VERSION, "label_model": "gpt-6-luna"}.items():
                pending.at[i, c] = v
        return pending, {"error": None, "warnings": [], "new": len(todo[skip:]), "todo": len(todo), "quota": False}
    return label


def setup(monkeypatch, store, skip=0, quiet=()):
    """quiet: (channel, day) pairs without posts."""
    calls = []

    async def scraper(channels, start, end):
        calls.append((channels[0], start, end))
        rows, day = [], (start + timedelta(hours=5)).date()
        while history.utc(day) < end:
            if (channels[0], day) not in quiet:
                at = (history.utc(day) + timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")
                rows.append({"channel": channels[0], "message_id": int(day.strftime("%m%d")), "date": at,
                             "views": 5, "forwards": 0, "raw_text": "Eksport oshdi", "scraped_at": at})
            day += timedelta(days=1)
        return pd.DataFrame(rows, columns=RAW_COLS), {}

    monkeypatch.setattr(history, "active_channels", lambda: ["@a", "@b"])
    monkeypatch.setattr(history, "target_day_range", lambda: (None, None, date(2026, 2, 10)))
    monkeypatch.setattr(history, "run_scraper", scraper)
    monkeypatch.setattr(history, "label_pending", labeller(skip))
    monkeypatch.setattr(history, "load_ledger", lambda: store["ledger"])
    monkeypatch.setattr(history, "load_pending", lambda: store["pending"])
    monkeypatch.setattr(history, "load_indices", lambda: store["indices"])
    monkeypatch.setattr(history, "write_ledger", lambda df: store.__setitem__("ledger", typed(df.copy())))
    monkeypatch.setattr(history, "save_pending", lambda df: store.__setitem__("pending", typed(df.copy())))
    monkeypatch.setattr(history, "write_csv", lambda df, path: store.__setitem__("indices", df.copy()))
    monkeypatch.setattr(history, "export_results", lambda *a, **k: None)
    monkeypatch.setattr(history, "REPORT", str(store["dir"] / "report.txt"))
    return calls


def empty_store(tmp_path):
    return {"ledger": typed(pd.DataFrame(columns=LEDGER_COLS)), "pending": typed(pd.DataFrame(columns=PENDING_COLS)),
            "indices": typed(pd.DataFrame(columns=INDEX_COLS)), "dir": tmp_path}


def test_months_and_days():
    assert history.months_in("2025-11..2026-02") == [(2025, 11), (2025, 12), (2026, 1), (2026, 2)]
    assert len(history.month_days(2026, 2, date(2026, 12, 1))) == 28
    assert history.month_days(2026, 3, date(2026, 2, 10)) == []


def test_two_months_then_the_rest_of_the_current_month(tmp_path, monkeypatch):
    store = empty_store(tmp_path)
    calls = setup(monkeypatch, store, quiet={("@b", date(2026, 1, 7))})
    assert history.main("2026-01..2026-03", fresh=True) == 0
    ledger, idx = store["ledger"], store["indices"]
    assert len(ledger) == 2 * (31 + 10) - 1 and set(ledger["label_version"]) == {LLM_LABEL_VERSION}
    assert ledger["date"].is_monotonic_increasing
    kun = idx[idx["period_type"] == "kun"].set_index("period")
    assert len(kun) == 41 and kun.loc["2026-01-07", "note"] == "yig'ilmagan kanal: @b"
    assert "2026-01" in set(idx.loc[idx["period_type"] == "oy", "period"])
    report = (tmp_path / "report.txt").read_text(encoding="utf-8")
    assert "2026-01: 61 post" in report and "2026-03: hali boshlanmagan" in report

    calls.clear()                                       # later: the current month's remaining days
    monkeypatch.setattr(history, "target_day_range", lambda: (None, None, date(2026, 2, 15)))
    history.main("2026-01..2026-02")
    starts = sorted((ch, (s + timedelta(hours=5)).date()) for ch, s, _ in calls)
    assert starts == [("@a", date(2026, 2, 11)), ("@b", date(2026, 1, 7)), ("@b", date(2026, 2, 11))]   # only missing days
    assert len(store["ledger"]) == 2 * (31 + 15) - 1


def test_unfinished_labelling_waits_and_is_reported(tmp_path, monkeypatch):
    store = empty_store(tmp_path)
    setup(monkeypatch, store, skip=3)
    history.main("2026-02", fresh=True)
    assert len(store["pending"]) == 3 and len(store["ledger"]) == 17
    assert "3 post hali belgilanmadi" in (tmp_path / "report.txt").read_text(encoding="utf-8")
