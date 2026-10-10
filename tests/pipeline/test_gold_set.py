"""The control set of check.py: well-formed entries, labelled in the pipeline's batch size."""
import config
import gold_set
from gold_set import GOLD

OUTCOMES = {"reklama", "boshqa", "iqt+", "iqt0", "iqt-"}


def test_entries_are_complete_and_distinct():
    for ch, want, why, text in GOLD:
        assert ch.startswith("@") and want in OUTCOMES and why.strip()
        assert text.strip() and "\r" not in text
        assert len(text) <= config.LLM_MAX_CHARS            # the pipeline cuts longer posts
    assert len({g[3] for g in GOLD}) == len(GOLD)


def test_outcome_classes():
    base = {"is_ad": False, "is_economic": True, "is_digest": False, "is_foreign": False, "sentiment": 0.5}
    assert gold_set.outcome(base) == "iqt+"
    assert gold_set.outcome({**base, "sentiment": 0.1}) == "iqt0"
    assert gold_set.outcome({**base, "sentiment": -0.5}) == "iqt-"
    assert gold_set.outcome({**base, "is_foreign": True}) == "boshqa"
    assert gold_set.outcome({**base, "is_economic": False}) == "boshqa"
    assert gold_set.outcome({**base, "is_ad": True}) == "reklama"


def test_check_labels_in_the_pipeline_batch_size(monkeypatch):
    import check
    import llm_classifier as lc
    sizes = []

    def fake(model, texts, channels, deadline=None, meta=None):
        sizes.append(len(texts))
        return [{"text": t, "channel": c} for t, c in zip(texts, channels)]
    monkeypatch.setattr(lc, "classify_batch", fake)
    monkeypatch.setattr(check, "LLM_BATCH_SIZE", 25)
    labels = check.label_gold("model", GOLD, None)
    assert [(x["channel"], x["text"]) for x in labels] == [(g[0], g[3]) for g in GOLD]   # in order
    assert sizes == [25] * (len(GOLD) // 25) + ([len(GOLD) % 25] if len(GOLD) % 25 else [])
