"""
Core index construction: turn raw messages into two economic indices.

Per message we compute three primitives:
  * relevance R  – how economic the post is (lexicon hit count -> saturating 0..1)
  * sentiment  s – net economic tone in [-1, 1]  (lexicon polarity)
  * weight     w – attention it received (log engagement, channel-normalised)

Two daily indices (kept separate on purpose – they measure different things):
  * EAI – Economic Attention Index  = attention-weighted mean relevance   (0..1)
  * ESI – Economic Sentiment Index  = attention-weighted mean sentiment
                                       over economic posts               (-1..1)

See METHODOLOGY.md for the formulas, their provenance and reliability.
"""
import numpy as np
import pandas as pd

from text_utils import normalize_text
from lexicons import econ_hits, pos_hits, neg_hits
from config import (
    FORWARD_WEIGHT, RELEVANCE_TAU, ECON_MIN_HITS,
)


def _score_row(text):
    norm = normalize_text(text)
    n_tokens = max(len(norm.split()), 1)
    e = econ_hits(norm)
    p = pos_hits(norm)
    ng = neg_hits(norm)
    relevance = 1.0 - np.exp(-e / RELEVANCE_TAU)          # concave, saturates to 1
    sentiment = (p - ng) / (p + ng) if (p + ng) > 0 else 0.0
    return pd.Series({
        "norm_tokens": n_tokens,
        "econ_hits": e,
        "pos_hits": p,
        "neg_hits": ng,
        "is_economic": int(e >= ECON_MIN_HITS),
        "relevance": relevance,
        "sentiment": sentiment,
        "sent_strength": p + ng,
    })


def score_messages(df: pd.DataFrame) -> pd.DataFrame:
    """Add per-message relevance / sentiment / engagement columns."""
    df = df.copy()
    scored = df["raw_text"].apply(_score_row)
    df = pd.concat([df, scored], axis=1)

    # Engagement: log-compressed, forwards weighted heavier than views.
    df["views"] = pd.to_numeric(df["views"], errors="coerce").fillna(0)
    df["forwards"] = pd.to_numeric(df["forwards"], errors="coerce").fillna(0)
    df["engagement"] = np.log1p(df["views"] + FORWARD_WEIGHT * df["forwards"])

    # Channel-normalised attention weight so a large-audience channel does not
    # dominate the index (each channel's average engagement -> 1.0).
    ch_mean = df.groupby("channel")["engagement"].transform("mean").replace(0, np.nan)
    df["eng_weight"] = (df["engagement"] / ch_mean).fillna(0.0)

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
    """Aggregate scored messages into the daily EAI / ESI time series."""
    rows = []
    for day, g in df.groupby("date_only"):
        econ = g[g["is_economic"] == 1]
        eai = _wmean(g["relevance"], g["eng_weight"])
        esi = _wmean(econ["sentiment"], econ["eng_weight"]) if len(econ) else 0.0
        rows.append({
            "date_only": day,
            "total_messages": len(g),
            "economic_messages": int(g["is_economic"].sum()),
            "econ_share": g["is_economic"].mean(),
            "EAI": eai,
            "ESI": esi,
            "avg_engagement": g["engagement"].mean(),
        })
    daily = pd.DataFrame(rows).sort_values("date_only").reset_index(drop=True)

    # Normalisation for comparability across days.
    if len(daily) >= 2 and daily["EAI"].std(ddof=0) > 0:
        daily["EAI_z"] = (daily["EAI"] - daily["EAI"].mean()) / daily["EAI"].std(ddof=0)
    else:
        daily["EAI_z"] = 0.0
    if len(daily) >= 2 and daily["ESI"].std(ddof=0) > 0:
        daily["ESI_z"] = (daily["ESI"] - daily["ESI"].mean()) / daily["ESI"].std(ddof=0)
    else:
        daily["ESI_z"] = 0.0

    eai_mean = daily["EAI"].mean() or 1.0
    daily["EAI_100"] = 100.0 * daily["EAI"] / eai_mean       # avg day = 100
    daily["ESI_100"] = 50.0 * (daily["ESI"] + 1.0)           # [-1,1] -> [0,100], 50 = neutral

    # tidy column order
    cols = ["date_only", "total_messages", "economic_messages", "econ_share",
            "EAI", "EAI_z", "EAI_100", "ESI", "ESI_z", "ESI_100", "avg_engagement"]
    return daily[cols]
