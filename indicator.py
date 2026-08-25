"""
Core index construction: turn raw messages into two economic indices.

Per message:
  * primary_topic + flags   (categorizer.py)
  * relevance R = 1 - exp(-econ_hits / TAU)          (0..1, saturating)
  * sentiment  s in [-1,1]  (aspect-based, sentiment.py)
  * weight     w = log engagement, channel-normalised

A post counts toward the indices (in_index) only if it is economic AND not an
ad/promo, not a news digest, and not a foreign-macro story — so the indices track
DOMESTIC economic news, not attention-grabbing noise.

  EAI = attention-weighted mean relevance over ALL posts (ad/digest/foreign -> 0)
  ESI = attention-weighted mean sentiment over counted economic posts

See METHODOLOGY.md for formulas, provenance and reliability.
"""
import numpy as np
import pandas as pd

from categorizer import classify
from sentiment import aspect_sentiment
from config import FORWARD_WEIGHT, RELEVANCE_TAU, ECON_MIN_HITS


def _score_row(text):
    c = classify(text)
    s, label = aspect_sentiment(text)
    e = c["econ_hits"]
    return pd.Series({
        "econ_hits": e,
        "is_economic": int(e >= ECON_MIN_HITS),
        "primary_topic": c["primary_topic"],
        "secondary_topics": c["secondary_topics"],
        "is_ad": c["is_ad"],
        "is_digest": c["is_digest"],
        "is_foreign": c["is_foreign"],
        "relevance": 1.0 - np.exp(-e / RELEVANCE_TAU),
        "sentiment": s,
        "sent_label": label,
    })


def score_messages(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    scored = df["raw_text"].apply(_score_row)
    df = pd.concat([df, scored], axis=1)

    df["views"] = pd.to_numeric(df["views"], errors="coerce").fillna(0)
    df["forwards"] = pd.to_numeric(df["forwards"], errors="coerce").fillna(0)
    df["engagement"] = np.log1p(df["views"] + FORWARD_WEIGHT * df["forwards"])

    ch_mean = df.groupby("channel")["engagement"].transform("mean").replace(0, np.nan)
    df["eng_weight"] = (df["engagement"] / ch_mean).fillna(0.0)

    # A post drives the indices only if it is domestic economic, non-ad, non-digest.
    df["in_index"] = ((df["is_economic"] == 1) & (df["is_ad"] == 0)
                      & (df["is_digest"] == 0) & (df["is_foreign"] == 0)).astype(int)
    df["relevance_eff"] = np.where(df["in_index"] == 1, df["relevance"], 0.0)

    df["date_only"] = pd.to_datetime(df["date"]).dt.date
    return df


def _wmean(values, weights):
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    wsum = weights.sum()
    if wsum <= 0:
        return float(values.mean()) if len(values) else 0.0
    return float((values * weights).sum() / wsum)


def build_daily_index(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for day, g in df.groupby("date_only"):
        counted = g[g["in_index"] == 1]
        eai = _wmean(g["relevance_eff"], g["eng_weight"])                 # over ALL posts
        esi = _wmean(counted["sentiment"], counted["eng_weight"]) if len(counted) else 0.0
        rows.append({
            "date_only": day,
            "total_messages": len(g),
            "economic_messages": int(g["is_economic"].sum()),
            "counted_messages": int(g["in_index"].sum()),
            "econ_share": g["is_economic"].mean(),
            "EAI": eai,
            "ESI": esi,
            "avg_engagement": g["engagement"].mean(),
        })
    daily = pd.DataFrame(rows).sort_values("date_only").reset_index(drop=True)

    if len(daily) >= 2 and daily["EAI"].std(ddof=0) > 0:
        daily["EAI_z"] = (daily["EAI"] - daily["EAI"].mean()) / daily["EAI"].std(ddof=0)
    else:
        daily["EAI_z"] = 0.0
    if len(daily) >= 2 and daily["ESI"].std(ddof=0) > 0:
        daily["ESI_z"] = (daily["ESI"] - daily["ESI"].mean()) / daily["ESI"].std(ddof=0)
    else:
        daily["ESI_z"] = 0.0

    eai_mean = daily["EAI"].mean() or 1.0
    daily["EAI_100"] = 100.0 * daily["EAI"] / eai_mean
    daily["ESI_100"] = 50.0 * (daily["ESI"] + 1.0)

    cols = ["date_only", "total_messages", "economic_messages", "counted_messages",
            "econ_share", "EAI", "EAI_z", "EAI_100", "ESI", "ESI_z", "ESI_100",
            "avg_engagement"]
    return daily[cols]
