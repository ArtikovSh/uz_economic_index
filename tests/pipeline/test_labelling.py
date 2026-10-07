"""label_pending with several requests in flight, on a fake classifier (no network)."""
import threading
import time

import pandas as pd
import pytest

import llm_classifier as lc
from config import LLM_LABEL_VERSION
from store import PENDING_COLS

REAL_SLEEP = time.sleep


def pending(n):
    return pd.DataFrame([{
        "channel": "@a", "message_id": i, "date": f"2026-10-01 {i // 60:02d}:{i % 60:02d}:00",
        "views": 1, "forwards": 0, "raw_text": f"post {i}", "scraped_at": "2026-10-03 00:00:00",
        "is_economic": None, "primary_topic": None, "relevance": None, "sentiment": None,
        "is_ad": None, "is_digest": None, "is_foreign": None,
        "label_version": None, "label_model": None, "label_error": None,
    } for i in range(n)], columns=PENDING_COLS)


def label(text):
    return {"is_economic": 1, "primary_topic": "macro", "relevance": 1.0,
            "sentiment": 0.5 if text.endswith("7") else 0.0, "is_ad": 0, "is_digest": 0, "is_foreign": 0}


@pytest.fixture
def fake(monkeypatch):
    """A classifier that records calls and the most requests it saw at once."""
    seen = {"calls": [], "busy": 0, "peak": 0}
    lock = threading.Lock()
    behaviour = {}

    def classify(model, texts, channels=None, deadline=None, meta=None):
        with lock:
            seen["busy"] += 1
            seen["peak"] = max(seen["peak"], seen["busy"])
            seen["calls"].append((model, len(texts)))
        try:
            REAL_SLEEP(0.02)
            rule = behaviour.get("rule")
            if rule:
                rule(model, texts)
            return [label(t) for t in texts]
        finally:
            with lock:
                seen["busy"] -= 1

    monkeypatch.setattr(lc, "classify_batch", classify)
    monkeypatch.setattr(lc, "candidate_models", lambda sticky=None: ["m1", "m2"])
    monkeypatch.setattr(lc, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(lc, "OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(lc, "LLM_BATCH_SIZE", 5)
    monkeypatch.setattr(lc, "LLM_WORKERS", 4)
    monkeypatch.setattr(lc, "LLM_RPM", 0)
    monkeypatch.setattr(lc, "LLM_MAX_REQUESTS", 1000)
    monkeypatch.setattr(lc.time, "sleep", lambda s: None)        # no real pauses
    seen["behaviour"] = behaviour
    return seen


def test_all_posts_labelled_with_requests_in_parallel(fake):
    out, status = lc.label_pending(pending(100))
    assert status["new"] == 100 and status["error"] is None and not status["warnings"]
    assert (out["label_version"] == LLM_LABEL_VERSION).all() and (out["label_model"] == "m1").all()
    assert out.loc[7, "sentiment"] == 0.5 and out.loc[8, "sentiment"] == 0.0
    assert len(fake["calls"]) == 20 and fake["peak"] > 1


def test_request_cap_leaves_the_rest_for_next_run(fake, monkeypatch):
    monkeypatch.setattr(lc, "LLM_MAX_REQUESTS", 6)
    out, status = lc.label_pending(pending(100))
    assert status["new"] == 30 and len(fake["calls"]) == 6
    assert "request cap" in status["warnings"][0]
    labelled = out.index[out["label_version"] == LLM_LABEL_VERSION].tolist()
    assert labelled == list(range(30))                       # oldest first


def test_bad_output_is_split_and_a_lone_post_retried(fake):
    def rule(model, texts):
        if "post 3" in texts:                                 # one post the model always fails
            raise ValueError("ids do not match")
    fake["behaviour"]["rule"] = rule
    out, status = lc.label_pending(pending(10))
    assert status["new"] == 9
    assert out.loc[3, "label_error"] == "ids do not match"
    assert pd.isna(out.loc[3, "label_version"])
    out, status = lc.label_pending(out)                       # failed again in a second run
    assert out.loc[3, "label_model"] == "m1:unlabelled" and out.loc[3, "primary_topic"] == "non_economic"


def test_unavailable_model_switches_once_and_nothing_is_lost(fake):
    def rule(model, texts):
        if model == "m1":
            raise lc.ModelUnavailable("m1: not found")
    fake["behaviour"]["rule"] = rule
    out, status = lc.label_pending(pending(40))
    assert status["new"] == 40 and (out["label_model"] == "m2").all()
    assert [w for w in status["warnings"] if "switched" in w] == ["model switched m1 -> m2 (m1: not found)"]


def test_quota_stops_and_keeps_finished_batches(fake):
    calls = {"n": 0}
    lock = threading.Lock()

    def rule(model, texts):
        with lock:
            calls["n"] += 1
            n = calls["n"]
        if n > 6:
            raise lc.QuotaExhausted("m1: daily limit reached")
    fake["behaviour"]["rule"] = rule
    out, status = lc.label_pending(pending(100))
    assert status["quota"] is True and status["error"] is None
    assert status["new"] == (out["label_version"] == LLM_LABEL_VERSION).sum() >= 25


def test_saves_progress_while_labelling(fake):
    saves = []
    out, status = lc.label_pending(pending(100), save=lambda df: saves.append(
        int((df["label_version"] == LLM_LABEL_VERSION).sum())))
    assert saves and saves[-1] == 100 and len(saves) >= 3
