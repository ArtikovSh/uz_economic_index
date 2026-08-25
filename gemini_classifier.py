"""
Gemini-based message classifier with caching and a rule-based fallback.

- Only NEW (channel, message_id) pairs are sent to Gemini; results are cached in
  data/llm_labels.csv, so re-runs over the growing master cost nothing for posts
  already labelled.
- Messages are sent in batches with a forced JSON schema (structured output).
- Any batch that errors (no key, network, quota, bad JSON) transparently falls
  back to the rule-based classifier for that batch, so the pipeline never breaks.
  Only genuine Gemini labels are persisted, so failed posts are retried next run.
"""
import json
import time
import numpy as np
import pandas as pd
import requests

from config import (GEMINI_API_KEY, GEMINI_MODEL, LLM_BATCH_SIZE, LLM_MAX_CHARS,
                    LLM_LABELS_CSV, LLM_LABEL_VERSION, ECON_MIN_HITS)
from prompts import SYSTEM_PROMPT, RESPONSE_SCHEMA, build_user_prompt, CATEGORIES

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
LABEL_COLS = ["is_economic", "primary_topic", "relevance", "sentiment",
              "is_ad", "is_digest", "is_foreign"]


# --------------------------------------------------------------- API call ------
def _call_gemini(texts):
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": build_user_prompt(texts)}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
        },
    }
    url = API_URL.format(model=GEMINI_MODEL)
    last = None
    for attempt in range(4):
        r = requests.post(url, params={"key": GEMINI_API_KEY}, json=payload, timeout=120)
        if r.status_code == 200:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            arr = json.loads(text)
            if len(arr) != len(texts):
                raise ValueError(f"expected {len(texts)} labels, got {len(arr)}")
            return arr
        last = f"{r.status_code}: {r.text[:180]}"
        if r.status_code in (429, 500, 503):
            time.sleep(2 * (attempt + 1))
            continue
        break
    raise RuntimeError(f"Gemini call failed ({last})")


def _to_label(d):
    topic = d.get("topic", "non_economic")
    if topic not in CATEGORIES:
        topic = "non_economic"
    econ = bool(d.get("economic")) and topic != "non_economic"
    return {
        "is_economic": int(econ),
        "primary_topic": topic if econ else "non_economic",
        "relevance": max(0.0, min(1.0, float(d.get("relevance", 0.0)))) if econ else 0.0,
        "sentiment": max(-1.0, min(1.0, float(d.get("sentiment", 0.0)))),
        "is_ad": int(bool(d.get("is_ad"))),
        "is_digest": int(bool(d.get("is_digest"))),
        "is_foreign": int(bool(d.get("is_foreign"))),
    }


# ------------------------------------------------------- rule-based fallback ---
def _rule_labels(texts):
    from categorizer import classify
    from sentiment import aspect_sentiment
    out = []
    for t in texts:
        c = classify(t)
        s, _ = aspect_sentiment(t)
        econ = c["econ_hits"] >= ECON_MIN_HITS
        out.append({
            "is_economic": int(econ),
            "primary_topic": c["primary_topic"],
            "relevance": float(1 - np.exp(-c["econ_hits"] / 2.0)) if econ else 0.0,
            "sentiment": s,
            "is_ad": c["is_ad"], "is_digest": c["is_digest"], "is_foreign": c["is_foreign"],
        })
    return out


# ------------------------------------------------------------------ cache ------
def _load_cache():
    import os
    if not os.path.exists(LLM_LABELS_CSV):
        return {}
    df = pd.read_csv(LLM_LABELS_CSV)
    if "label_version" in df.columns:
        df = df[df["label_version"].astype(str) == LLM_LABEL_VERSION]
    out = {}
    for _, r in df.iterrows():
        out[str(r["key"])] = {c: r[c] for c in LABEL_COLS if c in df.columns}
    return out


def _append_cache(rows):
    import os
    if not rows:
        return
    new = pd.DataFrame(rows)
    if os.path.exists(LLM_LABELS_CSV):
        old = pd.read_csv(LLM_LABELS_CSV)
        combined = pd.concat([old, new], ignore_index=True)
    else:
        combined = new
    combined = combined.drop_duplicates(subset=["key"], keep="last")
    combined.to_csv(LLM_LABELS_CSV, index=False, encoding="utf-8")


# --------------------------------------------------------------- public --------
def label_messages(df: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame aligned to df.index with LABEL_COLS (Gemini + cache)."""
    key = (df["channel"].astype(str) + "|" + df["message_id"].astype(str)).tolist()
    cache = _load_cache()
    result = dict(cache)

    todo = [(i, k) for i, k in zip(df.index, key) if k not in cache]
    if todo:
        print(f"  Gemini: classifying {len(todo)} new posts "
              f"({len(cache)} cached) with {GEMINI_MODEL}")
        idxs = [i for i, _ in todo]
        keys = [k for _, k in todo]
        texts = (df.loc[idxs, "raw_text"].fillna("").astype(str)
                 .str.slice(0, LLM_MAX_CHARS).tolist())
        to_persist = []
        for start in range(0, len(texts), LLM_BATCH_SIZE):
            bt, bk = texts[start:start + LLM_BATCH_SIZE], keys[start:start + LLM_BATCH_SIZE]
            try:
                labels = [_to_label(d) for d in _call_gemini(bt)]
                src = "gemini"
            except Exception as e:
                print(f"    batch {start // LLM_BATCH_SIZE}: {e} -> rule fallback")
                labels = _rule_labels(bt)
                src = "rules"
            for k, lab in zip(bk, labels):
                result[k] = lab
                if src == "gemini":
                    to_persist.append({"key": k, "label_version": LLM_LABEL_VERSION, **lab})
            print(f"    {min(start + LLM_BATCH_SIZE, len(texts))}/{len(texts)} ({src})")
        _append_cache(to_persist)

    return pd.DataFrame([result[k] for k in key], index=df.index)[LABEL_COLS]
