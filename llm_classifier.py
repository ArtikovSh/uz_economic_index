"""
Gemini message classifier for the posts waiting in pending.csv.

* Posts without a label for the current LLM_LABEL_VERSION are sent oldest first,
  so days can be finalised in date order.
* Posts go in batches with a JSON response schema; requests are paced to the
  free-tier per-minute limit and capped per run (LLM_MAX_REQUESTS).
* No rule-based fallback: a post Gemini could not label keeps waiting and is
  retried on the next run, so the index never mixes labelling methods.
* The model is "sticky": GEMINI_MODEL if set, else the model of the latest labels,
  else the newest stable Flash model available to the key. Each label records the
  model that produced it.
"""
import json
import re
import time

import requests

from config import (GEMINI_API_KEY, GEMINI_MODEL, LLM_BATCH_SIZE, LLM_MAX_CHARS,
                    LLM_RPM, LLM_MAX_REQUESTS, LLM_LABEL_VERSION)
from prompts import SYSTEM_PROMPT, RESPONSE_SCHEMA, CATEGORIES, build_user_prompt
from store import LABEL_COLS, post_keys

API = "https://generativelanguage.googleapis.com/v1beta"
FALLBACK_MODELS = ["gemini-3.5-flash", "gemini-3.1-flash-lite"]   # if /models can't be listed
_STABLE_FLASH = re.compile(r"^gemini-(\d+(?:\.\d+)?)-flash(-lite)?$")


class ProviderError(Exception):
    """Needs a human: bad/missing key, API disabled, no usable model."""


class ModelUnavailable(Exception):
    """This model can't be used with this key (not found / no free quota)."""


class QuotaExhausted(Exception):
    """Daily quota used up — the rest is labelled on a later run."""


class TransientError(Exception):
    """Server/network trouble that outlasted the retries."""


# ------------------------------------------------------------------ HTTP -------
def _headers():
    return {"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"}


def _error_info(resp):
    """(message, quota ids, retry delay seconds, quota limit is zero)."""
    try:
        err = resp.json().get("error", {})
    except ValueError:
        return resp.text[:300], [], None, False
    msg = str(err.get("message", ""))[:300]
    quota_ids, delay, limit_zero = [], None, "limit: 0" in msg
    for d in err.get("details", []) or []:
        for v in d.get("violations", []) or []:
            quota_ids.append(str(v.get("quotaId", "")))
            if str(v.get("quotaValue", "")) == "0":
                limit_zero = True
        m = re.fullmatch(r"([\d.]+)s", str(d.get("retryDelay", "")))
        if m:
            delay = float(m.group(1))
    return msg, quota_ids, delay, limit_zero


def list_models():
    """Model ids this key can call with generateContent."""
    r = requests.get(f"{API}/models", headers=_headers(), params={"pageSize": 1000}, timeout=60)
    if r.status_code != 200:
        raise ProviderError(f"cannot list models: HTTP {r.status_code}: {_error_info(r)[0]}")
    return [m["name"].removeprefix("models/") for m in r.json().get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])]


def _flash_rank(model):
    m = _STABLE_FLASH.match(model)
    version = tuple(int(x) for x in m.group(1).split("."))
    return version, m.group(2) is None          # newer first, Flash before Flash-Lite


def candidate_models(sticky=None):
    """Models to try, in order. An explicit GEMINI_MODEL is the only candidate."""
    if GEMINI_MODEL:
        return [GEMINI_MODEL]
    try:
        flash = sorted((m for m in list_models() if _STABLE_FLASH.match(m)),
                       key=_flash_rank, reverse=True)
    except (ProviderError, requests.RequestException) as e:
        print(f"  (model list unavailable: {e}); using defaults")
        flash = list(FALLBACK_MODELS)
    order = ([sticky] if sticky else []) + flash
    return list(dict.fromkeys(order))           # dedupe, keep order


# --------------------------------------------------------------- classify -----
def _parse(data, n):
    cands = data.get("candidates") or []
    if not cands:
        block = (data.get("promptFeedback") or {}).get("blockReason")
        raise ValueError(f"no candidates (blockReason={block})")
    parts = (cands[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    if not text:
        raise ValueError(f"empty reply (finishReason={cands[0].get('finishReason')})")
    text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text)
    obj = json.loads(text)
    arr = obj.get("results") if isinstance(obj, dict) else obj
    if not isinstance(arr, list) or len(arr) != n:
        raise ValueError(f"expected {n} results, got {len(arr) if isinstance(arr, list) else '?'}")
    return [_to_label(x) for x in arr]


def _num(x, lo, hi):
    try:
        return max(lo, min(hi, float(x)))
    except (TypeError, ValueError):
        return 0.0


def _to_label(d):
    topic = d.get("topic", "non_economic")
    if topic not in CATEGORIES:
        topic = "non_economic"
    econ = bool(d.get("economic")) and topic != "non_economic"
    return {
        "is_economic": int(econ),
        "primary_topic": topic if econ else "non_economic",
        "relevance": _num(d.get("relevance"), 0.0, 1.0) if econ else 0.0,
        "sentiment": _num(d.get("sentiment"), -1.0, 1.0) if econ else 0.0,
        "is_ad": int(bool(d.get("is_ad"))),
        "is_digest": int(bool(d.get("is_digest"))),
        "is_foreign": int(bool(d.get("is_foreign"))),
    }


def classify_batch(model, texts):
    """Label one batch. Raises ValueError on unusable output, else a typed error."""
    gen = {"responseMimeType": "application/json", "responseSchema": RESPONSE_SCHEMA}
    if model.startswith("gemini-2"):
        gen["temperature"] = 0      # Gemini 3+: Google advises keeping the default
    last = ""
    for attempt in range(4):
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": build_user_prompt(texts)}]}],
            "generationConfig": gen,
        }
        try:
            r = requests.post(f"{API}/models/{model}:generateContent",
                              headers=_headers(), json=payload, timeout=180)
        except requests.RequestException as e:
            time.sleep(10 * (attempt + 1))
            last = str(e)
            continue
        if r.status_code == 200:
            return _parse(r.json(), len(texts))
        msg, quota_ids, delay, limit_zero = _error_info(r)
        last = f"HTTP {r.status_code}: {msg}"
        if r.status_code == 400 and "responseSchema" in gen and "schema" in msg.lower():
            gen.pop("responseSchema")               # schema rejected -> plain JSON mode
            continue
        if r.status_code == 429:
            if limit_zero:
                raise ModelUnavailable(f"{model}: no free quota ({msg})")
            if any("PerDay" in q for q in quota_ids):
                raise QuotaExhausted(f"{model}: daily quota reached")
            time.sleep(min(delay or 20 * (attempt + 1), 90))
            continue
        if r.status_code in (500, 502, 503, 504):
            time.sleep(10 * (attempt + 1))
            continue
        if r.status_code == 404:
            raise ModelUnavailable(f"{model}: {msg}")
        raise ProviderError(last)                   # 400 bad key, 403 API disabled, ...
    raise TransientError(f"{model}: {last}")


# --------------------------------------------------------------- public --------
def label_pending(pending, save=None, sticky=None):
    """Label every post in `pending` without a current-version label, oldest first.

    Labels are written into pending's LABEL_COLS (+ label_version, label_model);
    `save(pending)` is called every few batches and at the end, so progress survives
    a timeout. Returns (pending, status) with status = {"error", "warnings", "new"},
    where "error" is set only for problems that need a human.
    """
    status = {"error": None, "warnings": [], "new": 0}
    todo = pending[pending["label_version"].astype(str) != LLM_LABEL_VERSION]
    if todo.empty:
        return pending, status
    if not GEMINI_API_KEY:
        status["error"] = "GEMINI_API_KEY is not set"
        return pending, status
    try:
        models = candidate_models(sticky)
    except ProviderError as e:
        status["error"] = str(e)
        return pending, status
    model = models.pop(0)
    todo = todo.sort_values("date")
    print(f"  Gemini model: {model} | {len(todo)} posts to label "
          f"(batch {LLM_BATCH_SIZE}, max {LLM_MAX_REQUESTS} requests this run)")

    texts = todo["raw_text"].fillna("").astype(str).str.slice(0, LLM_MAX_CHARS).tolist()
    idx = todo.index.tolist()
    queue = [(idx[i:i + LLM_BATCH_SIZE], texts[i:i + LLM_BATCH_SIZE])
             for i in range(0, len(texts), LLM_BATCH_SIZE)]
    interval = 60.0 / LLM_RPM if LLM_RPM > 0 else 0.0
    requests_used, last_call, since_save = 0, 0.0, 0

    def call(batch_texts):
        nonlocal requests_used, last_call
        wait = interval - (time.time() - last_call)
        if wait > 0:
            time.sleep(wait)                       # pace to the per-minute limit
        last_call = time.time()
        requests_used += 1
        return classify_batch(model, batch_texts)

    try:
        while queue:
            if requests_used >= LLM_MAX_REQUESTS:
                status["warnings"].append(
                    f"request cap ({LLM_MAX_REQUESTS}) reached — the rest is labelled next run")
                break
            bidx, btexts = queue.pop(0)
            try:
                labels = call(btexts)
            except ModelUnavailable as e:
                if not models:
                    status["error"] = f"no usable Gemini model ({e})"
                    break
                old, model = model, models.pop(0)
                status["warnings"].append(f"model switched {old} -> {model} ({e})")
                print(f"  !! {e} -> switching model {old} -> {model}")
                queue.insert(0, (bidx, btexts))
                continue
            except ValueError as e:                # bad output: retry as two halves
                if len(bidx) > 1:
                    half = len(bidx) // 2
                    queue[:0] = [(bidx[:half], btexts[:half]), (bidx[half:], btexts[half:])]
                    print(f"  batch of {len(bidx)} unusable ({e}) -> split")
                else:
                    key = post_keys(pending.loc[bidx]).iloc[0]
                    status["warnings"].append(f"post {key} could not be labelled ({e})")
                continue
            for i, lab in zip(bidx, labels):
                for c in LABEL_COLS:
                    pending.at[i, c] = lab[c]
                pending.at[i, "label_version"] = LLM_LABEL_VERSION
                pending.at[i, "label_model"] = model
            status["new"] += len(labels)
            since_save += len(labels)
            print(f"    labelled {status['new']}/{len(texts)}")
            if save and since_save >= 5 * LLM_BATCH_SIZE:   # flush often: survive timeouts
                save(pending)
                since_save = 0
    except QuotaExhausted as e:
        status["warnings"].append(f"{e} — the rest is labelled next run")
    except TransientError as e:
        status["warnings"].append(f"Gemini temporarily unavailable ({e}) — retry next run")
    except ProviderError as e:
        status["error"] = str(e)
    finally:
        if save and status["new"]:
            save(pending)
    return pending, status
