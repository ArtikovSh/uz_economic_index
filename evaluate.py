"""
Quality check of the LLM labels on a fixed sample of real posts. No table is touched:
the labels go to eval/ (committed by eval.yml) so they can be read and judged by hand.

Sample: the 27 control posts of gold_set.py + EVAL_SIZE random posts (fixed seed, so
every run labels the same posts). With OpenAI every reasoning effort in EVAL_EFFORTS
is run, to compare accuracy, speed and cost.

Output:
  eval/<provider>_<effort>.csv   one row per post: text, labels, outcome (+ expected)
  eval/REPORT.md                 control-set score, mistakes, speed, tokens, cost
"""
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pandas as pd

import config
import llm_classifier as lc
from gold_set import GOLD, outcome
from store import load_ledger, load_pending

OUT = "eval"
SIZE = int(os.getenv("EVAL_SIZE", "174"))
EFFORTS = [e.strip() for e in os.getenv("EVAL_EFFORTS", "low,medium").split(",") if e.strip()]
PARALLEL = int(os.getenv("EVAL_PARALLEL", "4"))
BUDGET_MIN = float(os.getenv("EVAL_BUDGET_MIN", "10"))     # per setting
SEED = 2026
PRICES = {"gpt-6-luna": (0.10, 0.50), "gpt-5-mini": (0.25, 2.00)}   # $ per 1M tokens in/out
LABELS = ["is_ad", "is_digest", "is_economic", "is_foreign", "primary_topic", "relevance",
          "sentiment"]


def sample():
    """The control posts first, then SIZE random stored posts in date order."""
    posts = pd.concat([load_ledger(), load_pending()], ignore_index=True)
    posts = posts[posts["raw_text"].fillna("").astype(str).str.strip() != ""]
    rnd = posts.sample(n=min(SIZE, len(posts)), random_state=SEED).sort_values("date")
    rows = [{"set": "gold", "channel": ch, "message_id": "", "date": "", "text": text,
             "expected": want, "why": why} for ch, want, why, text in GOLD]
    rows += [{"set": "sample", "channel": r.channel, "message_id": r.message_id, "date": r.date,
              "text": str(r.raw_text)[:config.LLM_MAX_CHARS], "expected": "", "why": ""}
             for r in rnd.itertuples()]
    return pd.DataFrame(rows)


def tokens(usage):
    """(input, output incl. reasoning, reasoning) tokens of one reply."""
    u = usage or {}
    if "input_tokens" in u:                                   # OpenAI
        return (u.get("input_tokens", 0), u.get("output_tokens", 0),
                (u.get("output_tokens_details") or {}).get("reasoning_tokens", 0))
    thoughts = u.get("thoughtsTokenCount", 0)                 # Gemini
    return u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0) + thoughts, thoughts


def label(df, model):
    """Label df in parallel batches; returns (df with labels, per-request stats)."""
    size = config.LLM_BATCH_SIZE
    batches = [df.index[i:i + size] for i in range(0, len(df), size)]
    deadline = time.time() + 60 * BUDGET_MIN

    def one(ix):
        meta, t0 = {}, time.time()
        try:
            labs = lc.classify_batch(model, df.loc[ix, "text"].tolist(),
                                     df.loc[ix, "channel"].tolist(), deadline, meta)
            return ix, labs, time.time() - t0, meta.get("usage"), None
        except Exception as e:                                # noqa: BLE001 — reported
            return ix, None, time.time() - t0, meta.get("usage"), f"{type(e).__name__}: {e}"

    df = df.copy()
    for c in LABELS + ["outcome", "error"]:
        df[c] = None
    stats = []
    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        for ix, labs, secs, usage, err in pool.map(one, batches):
            stats.append({"posts": len(ix), "seconds": secs, "tokens": tokens(usage), "error": err})
            if err:
                df.loc[ix, "error"] = err[:300]
                continue
            for i, lab in zip(ix, labs):
                for c in LABELS:
                    df.at[i, c] = lab[c]
                df.at[i, "outcome"] = outcome(lab)
    return df, stats


def summary(name, model, df, stats):
    ok = df["outcome"].notna()
    gold = df[(df["set"] == "gold") & ok]
    wrong = gold[gold["outcome"] != gold["expected"]]
    smp = df[(df["set"] == "sample") & ok]
    t_in = sum(s["tokens"][0] for s in stats)
    t_out = sum(s["tokens"][1] for s in stats)
    t_reason = sum(s["tokens"][2] for s in stats)
    secs = [s["seconds"] for s in stats if not s["error"]]
    price = PRICES.get(model)
    lines = [f"## {name} — `{model}`", "",
             f"- Nazorat to'plami: **{len(gold) - len(wrong)}/{len(GOLD)}** to'g'ri"
             + (f" ({len(GOLD) - len(gold)} ta javob yo'q)" if len(gold) < len(GOLD) else ""),
             f"- So'rovlar: {len(stats)} ta, har birida {config.LLM_BATCH_SIZE} tagacha post, "
             f"{PARALLEL} tadan parallel; xato: {sum(1 for s in stats if s['error'])}",
             f"- Javob vaqti: o'rtacha {sum(secs) / len(secs):.0f} s, eng uzoq {max(secs):.0f} s"
             if secs else "- Javob vaqti: —",
             f"- Tokenlar: kirish {t_in:,}, chiqish {t_out:,} (shundan reasoning {t_reason:,})"]
    if price and (t_in or t_out):
        cost = (t_in * price[0] + t_out * price[1]) / 1e6
        per_post = cost / max(1, ok.sum())
        lines.append(f"- Narx: ${cost:.4f} ({ok.sum()} post) — 1 000 post uchun ~${1000 * per_post:.2f}")
    if len(smp):
        dist = smp["outcome"].value_counts().to_dict()
        lines.append("- Tasodifiy namunada: " + ", ".join(f"{k} {v}" for k, v in sorted(dist.items())))
    errs = sorted({s["error"] for s in stats if s["error"]})
    if errs:
        lines += ["", "Xatolar:"] + [f"- {e[:300]}" for e in errs]
    if len(wrong):
        lines += ["", "Nazorat to'plamidagi xatolar:"]
        lines += [f"- {r.why}: kutilgan {r.expected}, javob {r.outcome}" for r in wrong.itertuples()]
    return "\n".join(lines) + "\n"


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    provider = config.LLM_PROVIDER
    df = sample()
    print(f"provider {provider}; {len(df)} posts ({(df['set'] == 'gold').sum()} control)", flush=True)
    model = lc.candidate_models(None, provider)[0]
    settings = EFFORTS if provider == "openai" else ["default"]
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    report = [f"# LLM baholash — {stamp}", "",
              f"Namuna: {len(GOLD)} ta nazorat posti + {len(df) - len(GOLD)} ta tasodifiy post "
              f"(seed {SEED}). Belgilar `{OUT}/` dagi CSV fayllarda.", ""]
    failed = False
    for effort in settings:
        if provider == "openai":
            lc.OPENAI_REASONING_EFFORT = effort
        name = f"{provider}_{effort}"
        print(f"--- {name}: {model}", flush=True)
        try:
            out, stats = label(df, model)
        except Exception as e:                                # noqa: BLE001 — reported
            report.append(f"## {name}\n\nIshlamadi: {type(e).__name__}: {e}\n")
            failed = True
            continue
        out.to_csv(os.path.join(OUT, f"{name}.csv"), index=False, encoding="utf-8",
                   lineterminator="\n")
        part = summary(name, model, out, stats)
        print(part, flush=True)
        report.append(part)
        failed |= out["outcome"].isna().all()
    with open(os.path.join(OUT, "REPORT.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(report))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
