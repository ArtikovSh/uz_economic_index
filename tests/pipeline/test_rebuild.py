"""rebuild.py on in-memory tables with a fake labeller (no network, no files)."""
from datetime import date

import pandas as pd

import rebuild
from config import LLM_LABEL_VERSION
from indicator import ledger_rows
from store import PENDING_COLS, typed


def post(channel, mid, utc, text, version="v5", sentiment=0.0):
    return {"channel": channel, "message_id": mid, "date": utc, "views": 10, "forwards": 0,
            "raw_text": text, "scraped_at": "2026-10-01 00:00:00", "is_economic": True,
            "primary_topic": "business", "relevance": 1.0, "sentiment": sentiment, "is_ad": False,
            "is_digest": False, "is_foreign": False, "label_version": version, "label_model": "gpt-6-luna"}


def tables():
    old = typed(pd.DataFrame([
        post("@a", 1, "2026-09-28 05:00:00", "kelishuv imzolandi yaxshi"),
        post("@a", 2, "2026-09-28 06:00:00", "tarif oshadi yomon", sentiment=-0.5),
        post("@b", 3, "2026-09-29 05:00:00", "tayinlov"),
        post("@b", 4, "2026-09-30 05:00:00", "yangi zavod yaxshi"),
        post("@c", 5, "2026-09-30 06:00:00", "yangi kanal"),          # @c is collected from 30 Sep only
    ], columns=PENDING_COLS))
    ledger = ledger_rows(old).reset_index(drop=True)
    pending = typed(pd.DataFrame([post("@a", 6, "2026-10-01 05:00:00", "yaxshi", version="v5")],
                                 columns=PENDING_COLS))
    return ledger, pending


def fake_labeller(missing=0):
    def label(work, save=None, sticky=None):
        work = work.copy()
        for n, i in enumerate(work.index):
            if n < missing:
                continue
            text = str(work.at[i, "raw_text"])
            work.loc[i, ["is_economic", "primary_topic", "relevance", "is_ad", "is_digest", "is_foreign"]] = \
                [True, "business", 1.0, False, False, False]
            work.at[i, "sentiment"] = 0.5 if "yaxshi" in text else -0.5 if "yomon" in text else 0.0
            work.at[i, "label_version"] = LLM_LABEL_VERSION
            work.at[i, "label_model"] = "gpt-6-luna"
        return work, {"error": None, "warnings": [], "new": len(work) - missing, "todo": len(work), "quota": False}
    return label


def run(monkeypatch, labeller):
    ledger, pending = tables()
    written, saved = {}, []
    monkeypatch.setattr(rebuild, "load_ledger", lambda: ledger)
    monkeypatch.setattr(rebuild, "load_pending", lambda: pending)
    monkeypatch.setattr(rebuild, "load_indices", lambda: typed(pd.DataFrame(columns=rebuild.INDEX_COLS)))
    monkeypatch.setattr(rebuild, "label_pending", labeller)
    monkeypatch.setattr(rebuild, "target_day", lambda: date(2026, 10, 3))
    monkeypatch.setattr(rebuild, "write_csv", lambda df, path: written.__setitem__(path, df.copy()))
    monkeypatch.setattr(rebuild, "save_pending", lambda df: saved.append(df.copy()))
    monkeypatch.setattr(rebuild, "export_results", lambda *a, **k: None)
    return rebuild.main(), written, saved


def test_rebuild_relabels_everything_and_recomputes(monkeypatch):
    code, written, saved = run(monkeypatch, fake_labeller())
    assert code == 0
    ledger = written[rebuild.MASTER_CSV]
    assert len(ledger) == 5 and set(ledger["label_version"]) == {LLM_LABEL_VERSION}
    assert ledger.set_index("message_id")["tone"].to_dict() == {1: 1, 2: -1, 3: 0, 4: 1, 5: 0}
    assert len(saved[0]) == 1 and saved[0]["label_version"].iloc[0] == LLM_LABEL_VERSION   # still waiting
    idx = written[rebuild.INDICES_CSV].set_index(["period_type", "period"])
    assert idx.loc[("kun", "2026-09-28"), "ESI"] == 0.0 and idx.loc[("kun", "2026-09-30"), "ESI"] == 50.0
    # a channel is expected from its first collected day on (@b from 29 Sep, @c from 30 Sep)
    assert idx.loc[("kun", "2026-09-28"), "note"] == ""
    assert idx.loc[("kun", "2026-09-29"), "note"] == "yig'ilmagan kanal: @a"
    assert idx.loc[("kun", "2026-09-30"), "note"] == "yig'ilmagan kanal: @a"
    assert ("oy", "2026-09") in idx.index and ("hafta", "2026-W40") not in idx.index   # week still open


def test_rebuild_writes_nothing_when_a_post_is_left(monkeypatch):
    code, written, saved = run(monkeypatch, fake_labeller(missing=1))
    assert code == 1 and written == {} and saved == []
