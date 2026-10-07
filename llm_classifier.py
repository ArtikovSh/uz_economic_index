"""
LLM message classifier for the posts waiting in pending.csv — OpenAI or Gemini.

* The provider is config.LLM_PROVIDER: OpenAI when a real OpenAI key is set (unless
  LLM_PROVIDER=gemini), else Gemini. Both get the same prompt and schema (prompts.py).
* Posts without a label for the current LLM_LABEL_VERSION are sent oldest first,
  so days can be finalised in date order.
* Posts go in batches with a JSON response schema; requests are paced
  (LLM_RPM), up to LLM_WORKERS run at once, and they are capped per run
  (LLM_MAX_REQUESTS).
* Every label comes back with its post number; a reply whose numbers do not match
  is rejected, so a label can never land on the wrong post.
* No rule-based fallback: a post the model could not label keeps waiting and is
  retried on the next run, so the index never mixes labelling methods. Only a post
  that fails on its own in two runs is stored as non-economic (marked in
  label_model), so it cannot hold back every later day.
* Short outages (HTTP 429/5xx, timeouts) are retried with growing pauses; labelling
  stops for the run only after three batches in a row fail, after a daily quota
  is used up, or when the time budget (LLM_TIME_BUDGET_MIN) is spent.
* The model is "sticky": GEMINI_MODEL / OPENAI_MODEL if set, else the model of the
  latest labels (if it belongs to the provider), else the provider's default. Each
  label records the model that produced it.
"""
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from config import (GEMINI_API_KEY, GEMINI_MODEL, OPENAI_API_KEY, OPENAI_MODEL,
                    OPENAI_REASONING_EFFORT, LLM_PROVIDER, LLM_BATCH_SIZE, LLM_MAX_CHARS,
                    LLM_RPM, LLM_WORKERS, LLM_MAX_REQUESTS, LLM_TIME_BUDGET_MIN,
                    LLM_LABEL_VERSION)
from prompts import (SYSTEM_PROMPT, RESPONSE_SCHEMA, OPENAI_SCHEMA, CATEGORIES,
                     build_user_prompt)
from store import LABEL_COLS, post_keys

API = "https://generativelanguage.googleapis.com/v1beta"
FALLBACK_MODELS = ["gemini-3.5-flash", "gemini-3.1-flash-lite"]   # if /models can't be listed
_STABLE_FLASH = re.compile(r"^gemini-(\d+(?:\.\d+)?)-flash(-lite)?$")
# news about crime or war must not be blocked: a blocked post could never be labelled
SAFETY_OFF = [{"category": c, "threshold": "BLOCK_NONE"} for c in (
    "HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT")]

OPENAI_API = "https://api.openai.com/v1"
# gpt-6-luna: OpenAI's model for high-volume classification; gpt-5-mini if it is not
# available to the key. The first one that works stays (sticky).
OPENAI_DEFAULTS = ["gpt-6-luna", "gpt-5-mini"]
OPENAI_MAX_OUTPUT = 32000          # a cap on reasoning + answer tokens per request

UNLABELLED = {"is_economic": 0, "primary_topic": "non_economic", "topics": "non_economic", "relevance": 0.0,
              "sentiment": 0.0, "is_ad": 0, "is_digest": 0, "is_foreign": 0}


class ProviderError(Exception):
    """Needs a human: bad/missing key, API disabled, no credit, no usable model."""


class ModelUnavailable(Exception):
    """This model can't be used with this key (not found / no free quota)."""


class QuotaExhausted(Exception):
    """Daily quota used up — the rest is labelled on a later run."""


class TransientError(Exception):
    """Server/network trouble that outlasted the retries."""


class OutOfTime(TransientError):
    """Waiting any longer would exceed the run's labelling time budget."""


def provider_of(model):
    return "gemini" if model.startswith("gemini") else "openai"


def _timeout(deadline, cap):
    """HTTP timeout for one request: `cap`, but never past the deadline."""
    return cap if not deadline else max(10.0, min(cap, deadline - time.time()))


def _wait(seconds, deadline, what):
    """Sleep before a retry, unless that would cross the run's time budget."""
    if deadline and time.time() + seconds > deadline:
        raise OutOfTime(f"time budget spent while waiting ({what})")
    time.sleep(seconds)


# ------------------------------------------------------------------ Gemini -----
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
    """Gemini model ids this key can call with generateContent."""
    r = requests.get(f"{API}/models", headers=_headers(), params={"pageSize": 1000}, timeout=60)
    if r.status_code != 200:
        raise ProviderError(f"cannot list models: HTTP {r.status_code}: {_error_info(r)[0]}")
    return [m["name"].removeprefix("models/") for m in r.json().get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])]


def _flash_rank(model):
    m = _STABLE_FLASH.match(model)
    version = tuple(int(x) for x in m.group(1).split("."))
    return version, m.group(2) is None          # newer first, Flash before Flash-Lite


def candidate_models(sticky=None, provider=None):
    """Models to try, in order. An explicit GEMINI_MODEL / OPENAI_MODEL is the only
    candidate; otherwise the model of the latest labels comes first if it belongs to
    this provider."""
    provider = provider or LLM_PROVIDER
    if sticky:
        sticky = sticky.split(":")[0]              # "<model>:unlabelled" marks a stored default
        if provider_of(sticky) != provider:
            sticky = None
    if provider == "openai":
        if OPENAI_MODEL:
            return [OPENAI_MODEL]
        return list(dict.fromkeys(([sticky] if sticky else []) + OPENAI_DEFAULTS))
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


# --------------------------------------------------------------- parsing ------
def _parse_text(text, n):
    """The model's JSON answer -> n labels, checking count and post ids."""
    text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text.strip())
    obj = json.loads(text)
    arr = obj.get("results") if isinstance(obj, dict) else obj
    if not isinstance(arr, list) or len(arr) != n:
        raise ValueError(f"expected {n} results, got {len(arr) if isinstance(arr, list) else '?'}")
    if any(not isinstance(x, dict) for x in arr):
        raise ValueError("result items are not objects")
    ids = [x.get("id") for x in arr]
    if any(i is not None for i in ids):                 # ids are required by the schema
        try:
            ok = [int(i) for i in ids] == list(range(n))
        except (TypeError, ValueError):
            ok = False
        if not ok:
            raise ValueError("post ids in the reply do not match the request")
    return [_to_label(x) for x in arr]


def _parse(data, n):
    """Gemini generateContent reply -> labels."""
    cands = data.get("candidates") or []
    if not cands:
        block = (data.get("promptFeedback") or {}).get("blockReason")
        raise ValueError(f"no candidates (blockReason={block})")
    parts = (cands[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    if not text:
        raise ValueError(f"empty reply (finishReason={cands[0].get('finishReason')})")
    return _parse_text(text, n)


def _openai_text(data):
    """OpenAI Responses reply -> the answer text."""
    if data.get("status") == "incomplete":
        reason = (data.get("incomplete_details") or {}).get("reason")
        raise ValueError(f"incomplete reply ({reason})")
    for item in data.get("output") or []:
        if item.get("type") != "message":
            continue
        for c in item.get("content") or []:
            if c.get("type") == "refusal":
                raise ValueError(f"refused: {str(c.get('refusal'))[:100]}")
            if c.get("type") == "output_text" and c.get("text"):
                return c["text"]
    raise ValueError("reply has no output text")


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
    others = [t for t in (d.get("other_topics") or []) if t in CATEGORIES and t != "non_economic"]
    topics = list(dict.fromkeys([topic] + others))[:3] if econ else ["non_economic"]
    return {
        "is_economic": int(econ),
        "primary_topic": topic if econ else "non_economic",
        "topics": ",".join(topics),
        "headline": " ".join(str(d.get("headline") or "").split())[:240] or None,
        "relevance": _num(d.get("relevance"), 0.0, 1.0) if econ else 0.0,
        "sentiment": _num(d.get("sentiment"), -1.0, 1.0) if econ else 0.0,
        "is_ad": int(bool(d.get("is_ad"))),
        "is_digest": int(bool(d.get("is_digest"))),
        "is_foreign": int(bool(d.get("is_foreign"))),
    }


# --------------------------------------------------------------- classify -----
def classify_batch(model, texts, channels=None, deadline=None, meta=None):
    """Label one batch with `model` (OpenAI or Gemini, by its name). Raises ValueError
    on unusable output, else a typed error. If `meta` is a dict, the reply's token
    usage is stored in meta["usage"]."""
    if provider_of(model) == "openai":
        return _openai_batch(model, texts, channels, deadline, meta)
    return _gemini_batch(model, texts, channels, deadline, meta)


def _gemini_batch(model, texts, channels=None, deadline=None, meta=None):
    gen = {"responseMimeType": "application/json", "responseSchema": RESPONSE_SCHEMA}
    if model.startswith("gemini-2"):
        gen["temperature"] = 0      # Gemini 3+: Google advises keeping the default
    last = ""
    for attempt in range(5):
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user",
                          "parts": [{"text": build_user_prompt(texts, channels)}]}],
            "generationConfig": gen,
            "safetySettings": SAFETY_OFF,
        }
        try:
            r = requests.post(f"{API}/models/{model}:generateContent",
                              headers=_headers(), json=payload, timeout=_timeout(deadline, 300))
        except requests.RequestException as e:
            last = f"{type(e).__name__}: {str(e)[:200]}"
            _wait(min(15 * 2 ** attempt, 120), deadline, f"{model}: {last}")
            continue
        if r.status_code == 200:
            data = r.json()
            if meta is not None:
                meta["usage"] = data.get("usageMetadata")
            return _parse(data, len(texts))
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
            _wait(min(max(delay or 0, 20) + 2, 120), deadline, f"{model}: {last}")
            continue
        if r.status_code in (500, 502, 503, 504):
            _wait(min(15 * 2 ** attempt, 120), deadline, f"{model}: {last}")  # 15 .. 120 s
            continue
        if r.status_code == 404:
            raise ModelUnavailable(f"{model}: {msg}")
        raise ProviderError(last)                   # 400 bad key, 403 API disabled, ...
    raise TransientError(f"{model}: {last}")


# ------------------------------------------------------------------ OpenAI -----
def _openai_error(resp):
    """(message, code) of an OpenAI error reply."""
    try:
        err = resp.json().get("error") or {}
    except ValueError:
        return resp.text[:300], ""
    return str(err.get("message", ""))[:300], str(err.get("code") or err.get("type") or "")


def _retry_after(resp):
    headers = getattr(resp, "headers", None) or {}
    try:
        if headers.get("retry-after-ms"):
            return float(headers["retry-after-ms"]) / 1000
        if headers.get("retry-after"):
            return float(headers["retry-after"])
    except (TypeError, ValueError):
        pass
    return None


def _openai_batch(model, texts, channels=None, deadline=None, meta=None):
    body = {
        "model": model,
        "instructions": SYSTEM_PROMPT,
        "input": build_user_prompt(texts, channels),
        "text": {"format": {"type": "json_schema", "name": "post_labels",
                            "schema": OPENAI_SCHEMA, "strict": True}},
        "reasoning": {"effort": OPENAI_REASONING_EFFORT},
        "max_output_tokens": OPENAI_MAX_OUTPUT,
        "store": False,                             # posts are not kept on OpenAI's side
    }
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    last = ""
    for attempt in range(5):
        try:
            r = requests.post(f"{OPENAI_API}/responses", headers=headers, json=body,
                              timeout=_timeout(deadline, 600))
        except requests.RequestException as e:
            last = f"{type(e).__name__}: {str(e)[:200]}"
            _wait(min(15 * 2 ** attempt, 120), deadline, f"{model}: {last}")
            continue
        if r.status_code == 200:
            data = r.json()
            if meta is not None:
                meta["usage"] = data.get("usage")
            return _parse_text(_openai_text(data), len(texts))
        msg, code = _openai_error(r)
        last = f"HTTP {r.status_code}: {msg}"
        low = msg.lower()
        if r.status_code == 400 and "reasoning" in body and "reasoning" in low:
            body.pop("reasoning")                   # a model without reasoning effort
            continue
        if (r.status_code == 400 and body["text"]["format"]["type"] == "json_schema"
                and ("schema" in low or "text.format" in low)):
            body["text"] = {"format": {"type": "json_object"}}   # schema rejected -> JSON mode
            continue
        if r.status_code == 429:
            if code == "insufficient_quota" or "insufficient_quota" in low or "billing" in low:
                raise ProviderError(f"OpenAI: no credit left on the account ({msg})")
            if "per day" in low or "(rpd)" in low or "(tpd)" in low:
                raise QuotaExhausted(f"{model}: daily limit reached")
            _wait(min(max(_retry_after(r) or 0, 20) + 2, 120), deadline, f"{model}: {last}")
            continue
        if r.status_code in (500, 502, 503, 504):
            _wait(min(15 * 2 ** attempt, 120), deadline, f"{model}: {last}")
            continue
        if r.status_code == 404 or (r.status_code == 403 and "model" in low):
            raise ModelUnavailable(f"{model}: {msg}")
        raise ProviderError(f"OpenAI: {last}")      # 401 bad key, 403 region/permissions, ...
    raise TransientError(f"{model}: {last}")


# --------------------------------------------------------------- public --------
def _failed_before(value):
    return isinstance(value, str) and value.strip() != ""


def label_pending(pending, save=None, sticky=None):
    """Label every post in `pending` without a current-version label, oldest first.

    Labels are written into pending's LABEL_COLS (+ label_version, label_model);
    `save(pending)` is called every few batches and at the end, so progress survives
    a timeout. Up to LLM_WORKERS batches are in flight at once (OpenAI); their results
    are handled one by one, in queue order. Returns (pending, status) with status =
    {"error", "warnings", "new", "todo", "quota"}: "error" is set only for problems that
    need a human, "quota" when the daily quota ran out (expected while a backlog is
    being labelled).
    """
    status = {"error": None, "warnings": [], "new": 0, "todo": 0, "quota": False}
    for c in ("primary_topic", "topics", "headline"):     # text labels into possibly empty columns
        pending[c] = (pending[c] if c in pending else None)
        pending[c] = pending[c].astype(object)
    todo = pending[pending["label_version"].astype(str) != LLM_LABEL_VERSION]
    status["todo"] = len(todo)
    if todo.empty:
        return pending, status
    key_name = "OPENAI_API_KEY" if LLM_PROVIDER == "openai" else "GEMINI_API_KEY"
    if not (OPENAI_API_KEY if LLM_PROVIDER == "openai" else GEMINI_API_KEY):
        status["error"] = f"{key_name} is not set"
        return pending, status
    try:
        models = candidate_models(sticky)
    except ProviderError as e:
        status["error"] = str(e)
        return pending, status
    model = models.pop(0)
    todo = todo.sort_values("date")
    print(f"  {LLM_PROVIDER} model: {model} | {len(todo)} posts to label "
          f"(batch {LLM_BATCH_SIZE}, {LLM_WORKERS} at a time, max {LLM_MAX_REQUESTS} requests this run)")

    texts = todo["raw_text"].fillna("").astype(str).str.slice(0, LLM_MAX_CHARS).tolist()
    chans = todo["channel"].astype(str).tolist()
    idx = todo.index.tolist()
    queue = [(idx[i:i + LLM_BATCH_SIZE], chans[i:i + LLM_BATCH_SIZE], texts[i:i + LLM_BATCH_SIZE])
             for i in range(0, len(texts), LLM_BATCH_SIZE)]
    interval = 60.0 / LLM_RPM if LLM_RPM > 0 else 0.0
    deadline = time.time() + 60 * LLM_TIME_BUDGET_MIN
    requests_used, since_save, failures_in_row = 0, 0, 0
    retried, changed = set(), False                # single posts already retried this run
    pace, last_call = threading.Lock(), [0.0]

    def call(use_model, batch_texts, batch_chans):
        with pace:                                 # start requests at most LLM_RPM a minute
            wait = interval - (time.time() - last_call[0])
            if wait > 0:
                time.sleep(wait)
            last_call[0] = time.time()
        return classify_batch(use_model, batch_texts, batch_chans, deadline)

    def keep(bidx, labels, label_model):
        nonlocal since_save, changed
        for i, lab in zip(bidx, labels):
            for c in LABEL_COLS:
                pending.at[i, c] = lab.get(c)
            pending.at[i, "label_version"] = LLM_LABEL_VERSION
            pending.at[i, "label_model"] = label_model
            pending.at[i, "label_error"] = None
        status["new"] += len(labels)
        since_save += len(labels)
        changed = True

    stop = False                                   # finish the batches in flight, then stop
    try:
        with ThreadPoolExecutor(max_workers=LLM_WORKERS) as pool:
            while queue and not stop:
                if requests_used >= LLM_MAX_REQUESTS:
                    status["warnings"].append(
                        f"request cap ({LLM_MAX_REQUESTS}) reached — the rest is labelled next run")
                    break
                if time.time() > deadline:
                    status["warnings"].append(f"time budget ({LLM_TIME_BUDGET_MIN:g} min) spent "
                                              "— the rest is labelled next run")
                    break
                wave = []
                while queue and len(wave) < LLM_WORKERS and requests_used < LLM_MAX_REQUESTS:
                    job = queue.pop(0)
                    wave.append((job, model, pool.submit(call, model, job[2], job[1])))
                    requests_used += 1
                pause = False
                for (bidx, bchans, btexts), used_model, fut in wave:
                    try:
                        labels = fut.result()
                    except ModelUnavailable as e:
                        queue.insert(0, (bidx, bchans, btexts))
                        if used_model != model:    # already switched for an earlier batch
                            continue
                        if not models:
                            status["error"] = f"no usable {LLM_PROVIDER} model ({e})"
                            stop = True
                            continue
                        model = models.pop(0)
                        status["warnings"].append(f"model switched {used_model} -> {model} ({e})")
                        print(f"  !! {e} -> switching model {used_model} -> {model}")
                        continue
                    except OutOfTime as e:
                        status["warnings"].append(f"{e} — the rest is labelled next run")
                        stop = True
                        continue
                    except TransientError as e:    # outlasted the retries inside the call
                        failures_in_row += 1
                        queue.insert(0, (bidx, bchans, btexts))
                        if failures_in_row >= 3 or time.time() + 60 > deadline:
                            if not stop:
                                status["warnings"].append(f"{LLM_PROVIDER} unavailable ({e}) — retry next run")
                            stop = True
                        else:
                            print(f"  !! {e} -> pausing a minute, then retrying")
                            pause = True
                        continue
                    except QuotaExhausted as e:
                        status["quota"] = True
                        status["warnings"].append(f"{e} — the rest is labelled next run")
                        stop = True
                        continue
                    except ProviderError as e:
                        status["error"] = str(e)
                        stop = True
                        continue
                    except ValueError as e:        # bad output: retry as two halves
                        failures_in_row = 0
                        if len(bidx) > 1:
                            half = len(bidx) // 2
                            queue[:0] = [(bidx[:half], bchans[:half], btexts[:half]),
                                         (bidx[half:], bchans[half:], btexts[half:])]
                            print(f"  batch of {len(bidx)} unusable ({e}) -> split")
                            continue
                        i, key = bidx[0], post_keys(pending.loc[bidx]).iloc[0]
                        if i not in retried:       # once more, at the end of this run
                            retried.add(i)
                            queue.append((bidx, bchans, btexts))
                        elif _failed_before(pending.at[i, "label_error"]):
                            keep([i], [UNLABELLED], f"{used_model}:unlabelled")
                            status["warnings"].append(f"post {key} could not be labelled in two runs "
                                                      f"({e}) — stored as non-economic")
                        else:
                            pending.at[i, "label_error"] = str(e)[:200]
                            changed = True
                            status["warnings"].append(f"post {key} could not be labelled ({e}) "
                                                      "— retried next run")
                        continue
                    failures_in_row = 0
                    keep(bidx, labels, used_model)
                    print(f"    labelled {status['new']}/{len(texts)}")
                if save and since_save >= 5 * LLM_BATCH_SIZE:   # flush often: survive timeouts
                    save(pending)
                    since_save = 0
                if pause and not stop:
                    time.sleep(60)
    finally:
        if save and changed:
            save(pending)
    return pending, status
