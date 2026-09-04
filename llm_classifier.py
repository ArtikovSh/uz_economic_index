"""
Provider-agnostic LLM message classifier with caching and rule-based fallback.

Providers (config.LLM_PROVIDER):
  * github — GitHub Models (OpenAI-compatible, free via GITHUB_TOKEN; GPT models)
  * gemini — Google Gemini API

Design:
  * only NEW (channel, message_id) pairs are classified; results cached in
    data/llm_labels.csv, so re-runs over the growing master are nearly free;
  * at most LLM_MAX_PER_RUN new posts are sent to the LLM per run (rate limits) —
    the rest use the rule-based classifier this run and are picked up next run,
    so a big backfill spreads across runs and never blows the quota;
  * messages go in batches; any batch error (quota, network, bad JSON, no creds)
    falls back to the rule-based classifier for that batch, and only genuine LLM
    labels are persisted (failed ones retry next run).
"""
import json
import time
import numpy as np
import pandas as pd
import requests

from config import (LLM_PROVIDER, OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL,
                    GITHUB_TOKEN, GITHUB_MODEL, GEMINI_API_KEY, GEMINI_MODEL,
                    LLM_BATCH_SIZE, LLM_MAX_CHARS, LLM_MAX_PER_RUN, LLM_SLEEP,
                    LLM_LABELS_CSV, LLM_LABEL_VERSION, ECON_MIN_HITS)
from prompts import SYSTEM_PROMPT, RESPONSE_SCHEMA, build_user_prompt, CATEGORIES

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
GITHUB_BASE = "https://models.github.ai/inference"
LABEL_COLS = ["is_economic", "primary_topic", "relevance", "sentiment",
              "is_ad", "is_digest", "is_foreign"]
_resolved = {"gemini_model": None, "openai_model": None}
_BAD_MODEL = ("whisper", "embedding", "tts", "guard", "moderation", "stt", "vision-only")


def list_openai_models(base_url, api_key):
    r = requests.get(f"{base_url}/models",
                     headers={"Authorization": f"Bearer {api_key}"}, timeout=60)
    r.raise_for_status()
    return [m["id"] for m in r.json().get("data", [])]


def resolve_openai_model(base_url, api_key, preferred):
    """Return a valid chat model id; auto-pick if the configured one 404s."""
    try:
        avail = list_openai_models(base_url, api_key)
    except Exception as e:
        print(f"  (could not list models: {e}); trying '{preferred}' as-is")
        return preferred
    if preferred in avail:
        return preferred
    chat = [m for m in avail if not any(b in m.lower() for b in _BAD_MODEL)]

    def pick(sub):
        return next((m for m in chat if sub in m.lower()), None)
    choice = (pick("gpt-oss-120b") or pick("gpt-oss") or pick("llama-3.3-70b")
              or pick("llama-3.1-8b") or pick("llama-3.3") or pick("llama")
              or (chat[0] if chat else (avail[0] if avail else preferred)))
    print(f"  model '{preferred}' unavailable -> using '{choice}'. "
          f"Available chat models: {chat[:12]}")
    return choice


def _retry_wait(resp, attempt):
    ra = resp.headers.get("Retry-After")
    if ra and ra.isdigit():
        return min(int(ra), 30)
    return 2 * (attempt + 1)


def _parse_results(obj, n):
    arr = obj["results"] if isinstance(obj, dict) and "results" in obj else obj
    if not isinstance(arr, list) or len(arr) != n:
        raise ValueError(f"expected {n} results, got {len(arr) if hasattr(arr,'__len__') else '?'}")
    return arr


# ----------------------------------------- OpenAI-compatible (Groq/OpenAI/...) -
def _call_openai(texts, base_url, api_key, model, label):
    body = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": build_user_prompt(texts)}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = f"{base_url}/chat/completions"
    last = None
    for attempt in range(5):
        r = requests.post(url, headers=headers, json=body, timeout=120)
        if r.status_code == 200:
            content = r.json()["choices"][0]["message"]["content"]
            return _parse_results(json.loads(content), len(texts))
        last = f"HTTP {r.status_code}: {r.text[:220]}"
        if r.status_code in (429, 500, 503):
            time.sleep(_retry_wait(r, attempt))
            continue
        break
    raise RuntimeError(f"{label} failed ({last})")


# ------------------------------------------------------------------ Gemini -----
def _gemini_models():
    r = requests.get(f"{GEMINI_BASE}/models", params={"key": GEMINI_API_KEY}, timeout=60)
    r.raise_for_status()
    return [m["name"].replace("models/", "") for m in r.json().get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])]


def resolve_gemini_model(preferred=None):
    preferred = (preferred or GEMINI_MODEL).replace("models/", "")
    try:
        avail = _gemini_models()
    except Exception as e:
        print(f"  (could not list Gemini models: {e}); trying '{preferred}'")
        return preferred
    if preferred in avail:
        return preferred

    def pick(pred):
        return next((m for m in avail if pred(m)), None)
    choice = (pick(lambda m: "flash" in m and "2.5" in m) or pick(lambda m: "flash" in m)
              or pick(lambda m: "pro" in m and "2.5" in m)
              or pick(lambda m: m.startswith("gemini") and "embedding" not in m)
              or (avail[0] if avail else preferred))
    print(f"  Gemini model '{preferred}' unavailable -> '{choice}'. Available: {avail[:10]}")
    return choice


def _call_gemini(texts):
    if _resolved["gemini_model"] is None:
        _resolved["gemini_model"] = resolve_gemini_model()
    model = _resolved["gemini_model"]
    url = f"{GEMINI_BASE}/models/{model}:generateContent"
    use_schema = True
    last = None
    for attempt in range(5):
        gen = {"temperature": 0, "responseMimeType": "application/json"}
        if use_schema:
            gen["responseSchema"] = RESPONSE_SCHEMA
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": build_user_prompt(texts)}]}],
            "generationConfig": gen,
        }
        r = requests.post(url, params={"key": GEMINI_API_KEY}, json=payload, timeout=120)
        if r.status_code == 200:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return _parse_results(json.loads(text), len(texts))
        last = f"HTTP {r.status_code}: {r.text[:220]}"
        if r.status_code == 400 and use_schema:
            use_schema = False
            continue
        if r.status_code in (429, 500, 503):
            time.sleep(_retry_wait(r, attempt))
            continue
        break
    raise RuntimeError(f"Gemini failed ({last})")


def _classify_batch(texts):
    if LLM_PROVIDER == "openai":
        if _resolved["openai_model"] is None:
            _resolved["openai_model"] = resolve_openai_model(
                OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL)
        raw = _call_openai(texts, OPENAI_BASE_URL, OPENAI_API_KEY,
                           _resolved["openai_model"], "OpenAI-compatible")
    elif LLM_PROVIDER == "github":
        raw = _call_openai(texts, GITHUB_BASE, GITHUB_TOKEN, GITHUB_MODEL, "GitHub Models")
    else:
        raw = _call_gemini(texts)
    return [_to_label(d) for d in raw]


def _active_model():
    if LLM_PROVIDER == "openai":
        return _resolved["openai_model"] or OPENAI_MODEL
    return {"github": GITHUB_MODEL, "gemini": GEMINI_MODEL}.get(LLM_PROVIDER, "")


# ------------------------------------------------------------------ mapping ----
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
    return {str(r["key"]): {c: r[c] for c in LABEL_COLS if c in df.columns}
            for _, r in df.iterrows()}


def _append_cache(rows):
    import os
    if not rows:
        return
    new = pd.DataFrame(rows)
    if os.path.exists(LLM_LABELS_CSV):
        new = pd.concat([pd.read_csv(LLM_LABELS_CSV), new], ignore_index=True)
    new.drop_duplicates(subset=["key"], keep="last").to_csv(LLM_LABELS_CSV, index=False, encoding="utf-8")


# --------------------------------------------------------------- public --------
def label_messages(df: pd.DataFrame) -> pd.DataFrame:
    key = (df["channel"].astype(str) + "|" + df["message_id"].astype(str)).tolist()
    cache = _load_cache()
    result = dict(cache)

    todo = [(i, k) for i, k in zip(df.index, key) if k not in cache]
    if todo:
        cap = LLM_MAX_PER_RUN if LLM_MAX_PER_RUN > 0 else len(todo)   # 0 = no cap
        capped = todo[:cap]
        deferred = todo[cap:]
        print(f"  LLM ({LLM_PROVIDER}/{_active_model()}): {len(capped)} new posts this "
              f"run ({len(cache)} cached, {len(deferred)} deferred)")
        idxs = [i for i, _ in capped]
        keys = [k for _, k in capped]
        texts = (df.loc[idxs, "raw_text"].fillna("").astype(str)
                 .str.slice(0, LLM_MAX_CHARS).tolist())
        to_persist = []
        llm_dead = False   # once the provider hard-fails, stop hammering it this run
        for start in range(0, len(texts), LLM_BATCH_SIZE):
            bt, bk = texts[start:start + LLM_BATCH_SIZE], keys[start:start + LLM_BATCH_SIZE]
            if llm_dead:
                labels, src = _rule_labels(bt), "rules"
            else:
                try:
                    labels = _classify_batch(bt)
                    src = "llm"
                except Exception as e:
                    print(f"    batch {start // LLM_BATCH_SIZE}: {e} -> rule fallback")
                    labels, src = _rule_labels(bt), "rules"
                    if any(c in str(e) for c in ("410", "401", "403", "404")):
                        print("    provider unavailable -> using rules for the rest of this run")
                        llm_dead = True
            for k, lab in zip(bk, labels):
                result[k] = lab
                if src == "llm":
                    to_persist.append({"key": k, "label_version": LLM_LABEL_VERSION, **lab})
            print(f"    {min(start + LLM_BATCH_SIZE, len(texts))}/{len(texts)} ({src})")
            if src == "llm" and start + LLM_BATCH_SIZE < len(texts) and LLM_SLEEP > 0:
                time.sleep(LLM_SLEEP)          # pace to respect RPM limits
        _append_cache(to_persist)

        # deferred posts: rule-based for THIS run (not persisted -> LLM next run)
        for i, k in deferred:
            if k not in result:
                result[k] = _rule_labels([str(df.loc[i, "raw_text"])])[0]

    return pd.DataFrame([result[k] for k in key], index=df.index)[LABEL_COLS]
