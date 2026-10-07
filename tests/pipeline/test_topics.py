"""Several topics per post (labels v6): parsing, storage and the topic table of the reports."""
import pandas as pd

import store
from llm_classifier import _to_label
from report_tables import build_tables


def test_label_keeps_the_topic_first_and_at_most_two_more():
    lab = _to_label({"economic": True, "topic": "prices_inflation",
                     "other_topics": ["energy_utility", "prices_inflation", "bogus", "non_economic", "fiscal", "trade"]})
    assert lab["primary_topic"] == "prices_inflation"
    assert lab["topics"] == "prices_inflation,energy_utility,fiscal"
    assert _to_label({"economic": False, "topic": "trade", "other_topics": ["business"]})["topics"] == "non_economic"
    assert _to_label({"economic": True, "topic": "trade"})["topics"] == "trade"        # field missing


def test_a_new_column_is_added_to_an_existing_table(tmp_path):
    path = str(tmp_path / "t.csv")
    pd.DataFrame([{"a": 1, "c": "x"}]).to_csv(path, index=False)
    out = store.append_rows(path, pd.DataFrame([{"a": 1, "c": "x"}]),
                            pd.DataFrame([{"a": 2, "b": "new", "c": "y"}]), ["a", "b", "c"])
    assert len(out) == 2
    back = pd.read_csv(path, dtype=str, keep_default_na=False)
    assert list(back.columns) == ["a", "b", "c"] and back.to_dict("records") == [
        {"a": "1", "b": "", "c": "x"}, {"a": "2", "b": "new", "c": "y"}]


def test_topic_table_counts_every_topic_and_splits_the_esi_share():
    rows = [("2026-10-05 09:00", "trade,business", 1), ("2026-10-05 10:00", "trade", -1),
            ("2026-10-05 11:00", "fiscal", 0)]
    ledger = pd.DataFrame([{
        "date_local": at, "channel": "@a", "message_id": i, "date": at, "views": 1, "forwards": 0,
        "scraped_at": at, "primary_topic": t.split(",")[0], "topics": t, "is_economic": 1, "relevance": 1.0,
        "sentiment": 0.5 * tone, "is_ad": 0, "ad_marker": 0, "is_digest": 0, "is_foreign": 0, "nonad": 1,
        "econ": 1, "tone": tone, "label_version": "v6", "label_model": "m", "raw_text": "Sarlavha"}
        for i, (at, t, tone) in enumerate(rows)])
    indices = pd.DataFrame([{"period_type": "kun", "period": "2026-10-05", "start": "2026-10-05",
                             "end": "2026-10-05", "days": 1, "days_expected": 1, "posts": 3, "nonad": 3,
                             "econ": 3, "pos": 1, "neu": 1, "neg": 1, "EAI": 100.0, "ESI": 0.0, "note": ""}])
    tables = build_tables(indices, ledger)
    topics = tables["Mavzular"].set_index("Mavzu")
    assert topics.loc["Tashqi savdo", "Xabarlar"] == 2 and topics.loc["Biznes", "Xabarlar"] == 1
    # the trade+business post gives each half of its share: trade 100*(0.5-1)/3, business 100*0.5/3
    assert round(topics.loc["Tashqi savdo", "ESI'ga hissa"], 3) == round(100 * -0.5 / 3, 3)
    assert round(topics["ESI'ga hissa"].sum(), 6) == 0.0
    assert tables["Xabarlar"]["Mavzu"].iloc[0] == "Tashqi savdo, Biznes"
