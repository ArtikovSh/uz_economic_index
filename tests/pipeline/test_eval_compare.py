"""The check of new rules on a stored month (evaluate.py, EVAL_MONTH): sample and comparison."""
import pandas as pd

import evaluate as ev


def ledger():
    rows = []
    for i in range(40):
        kind = i % 4
        rows.append({"date_local": f"2026-01-{1 + i % 28:02d} 10:{i:02d}", "channel": "@a", "message_id": i,
                     "raw_text": f"post {i}", "is_ad": int(kind == 0), "econ": int(kind >= 2),
                     "tone": {2: 1, 3: -1}.get(kind), "primary_topic": "trade" if kind >= 2 else "non_economic",
                     "headline": "#Тезкор" if i == 5 else f"h{i}"})
    rows.append({**rows[0], "date_local": "2026-02-01 09:00", "message_id": 99})       # another month
    rows.append({**rows[1], "date_local": "2026-01-18 17:53", "channel": "@oper_uz", "message_id": 77})
    return pd.DataFrame(rows)


def test_month_sample_takes_the_reviewed_posts_and_each_stored_outcome(monkeypatch):
    monkeypatch.setattr(ev, "STRATA", {"reklama": 3, "boshqa": 3, "iqt+": 3, "iqt0": 3, "iqt-": 3})
    df = ev.month_sample(ledger(), "2026-01")
    assert 99 not in set(df["message_id"])                                   # only the month asked for
    assert df[df["set"] == "reviewed"]["message_id"].tolist() == [77]         # ("@oper_uz", "2026-01-18 17:53")
    assert df["set"].value_counts().to_dict() == {"reklama": 3, "boshqa": 3, "iqt+": 3, "iqt-": 3,
                                                  "hashtag": 1, "reviewed": 1}
    assert df["message_id"].is_unique
    assert set(df["old"]) == {"reklama", "boshqa", "iqt+", "iqt-"}
    assert ev.month_sample(ledger(), "2026-01").equals(df)                    # the same posts every run


def test_compare_writes_old_and_new_side_by_side(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "OUT", str(tmp_path))
    monkeypatch.setattr(ev, "MONTH", "2026-01")
    monkeypatch.setattr(ev, "STRATA", {"reklama": 2, "boshqa": 2, "iqt+": 2, "iqt0": 0, "iqt-": 2})
    monkeypatch.setattr(ev, "load_ledger", ledger)

    def fake_label(df, model):                    # the new rules call every post economic and positive
        out = df.copy()
        out["primary_topic"], out["headline"], out["outcome"] = "business", "Yangi sarlavha", "iqt+"
        return out, [{"posts": len(df), "seconds": 1.0, "tokens": (100, 10, 0), "error": None}]
    monkeypatch.setattr(ev, "label", fake_label)
    assert ev.compare("gpt-6-luna") == 0
    out = pd.read_csv(tmp_path / "compare_2026-01.csv")
    assert set(out.columns) >= {"old", "new", "old_topic", "primary_topic", "old_headline", "headline", "changed"}
    assert out.loc[out["old"] == "iqt+", "changed"].all()                    # same outcome, other topic
    report = (tmp_path / "COMPARE_2026-01.md").read_text(encoding="utf-8")
    assert "- reklama -> iqt+: 2" in report and "eski 1, yangi 0" in report
