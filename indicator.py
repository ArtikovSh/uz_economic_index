"""
Core index construction: turn labelled messages into two economic indices.

Per message (labels from the Gemini classifier, llm_classifier.py):
  * primary_topic + ad / digest / foreign flags
  * relevance R in [0,1], sentiment s in [-1,1]
  * weight     w = log engagement, channel-normalised

A post counts toward the indices (in_index) only if it is labelled, economic and
not an ad, a news digest or a foreign-macro story. Posts the channel itself marks
as advertising are excluded whatever the model said.

  EAI = attention-weighted mean relevance over ALL posts (non-counted -> 0)
  ESI = attention-weighted mean sentiment over counted economic posts

A day with posts still waiting for a label gets no index value (NaN); a later run
fills it once the labels exist. See METHODOLOGY.md.
"""
import re

import numpy as np
import pandas as pd

from config import FORWARD_WEIGHT, TZ_OFFSET_HOURS

# The channel's own sponsorship marker: "(реклама)" anywhere, "на правах рекламы",
# "#реклама", or "Реклама"/"Reklama" as the post's last word (Daryo, Kun.uz style).
# A bare "реклама" inside a sentence (news about advertising) does not match.
AD_MARKER_RE = re.compile(
    r"\(\s*(?:реклама|reklama)\s*\)"
    r"|#\s?(?:реклама|reklama)\b"
    r"|на\s+правах\s+рекламы|reklama\s+huquqida"
    r"|(?:^|\s)[*_]*(?:реклама|reklama)[*_]*\s*$",
    re.IGNORECASE)

FLAG_COLS = ["is_economic", "is_ad", "is_digest", "is_foreign"]


def has_ad_marker(text) -> bool:
    return isinstance(text, str) and bool(AD_MARKER_RE.search(text.strip()))


def score_messages(df: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["labeled"] = labels["is_economic"].notna().astype(int).values
    for c in FLAG_COLS:
        df[c] = labels[c].fillna(0).astype(int).values
    df["primary_topic"] = labels["primary_topic"].fillna("unlabeled").astype(str).values
    df["relevance"] = labels["relevance"].astype(float).values
    df["sentiment"] = labels["sentiment"].astype(float).values
    df["label_model"] = labels["label_model"].values

    df["ad_marker"] = df["raw_text"].apply(has_ad_marker).astype(int)
    df["is_ad"] = (df["is_ad"] | df["ad_marker"]).astype(int)
    df["sent_label"] = np.select([df["sentiment"] > 0.15, df["sentiment"] < -0.15],
                                 ["pos", "neg"], default="neu")
    df.loc[df["labeled"] == 0, "sent_label"] = ""

    df["views"] = pd.to_numeric(df["views"], errors="coerce").fillna(0)
    df["forwards"] = pd.to_numeric(df["forwards"], errors="coerce").fillna(0)
    df["engagement"] = np.log1p(df["views"] + FORWARD_WEIGHT * df["forwards"])
    ch_mean = df.groupby("channel")["engagement"].transform("mean").replace(0, np.nan)
    df["eng_weight"] = (df["engagement"] / ch_mean).fillna(0.0)

    # A post drives the indices only if it is labelled, domestic economic, non-ad, non-digest.
    df["in_index"] = ((df["labeled"] == 1) & (df["is_economic"] == 1) & (df["is_ad"] == 0)
                      & (df["is_digest"] == 0) & (df["is_foreign"] == 0)).astype(int)
    df["relevance_eff"] = np.where(df["in_index"] == 1, df["relevance"].fillna(0.0), 0.0)

    # Stored dates are UTC (naive); group by the Tashkent calendar day.
    df["date_only"] = (pd.to_datetime(df["date"], errors="coerce")
                       + pd.Timedelta(hours=TZ_OFFSET_HOURS)).dt.date
    return df


def wmean(values, weights):
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    wsum = weights.sum()
    if wsum <= 0:
        return float(values.mean()) if len(values) else 0.0
    return float((values * weights).sum() / wsum)


DAILY_COLS = ["date_only", "total_messages", "economic_messages", "counted_messages",
              "econ_share", "EAI", "EAI_z", "EAI_100", "ESI", "ESI_z", "ESI_100",
              "avg_engagement", "unlabeled_messages"]


def build_daily_index(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for day, g in df.groupby("date_only"):
        unlabeled = int((g["labeled"] == 0).sum())
        row = {"date_only": day, "total_messages": len(g),
               "avg_engagement": g["engagement"].mean(), "unlabeled_messages": unlabeled}
        if unlabeled == 0:                       # publish a day only when fully labelled
            counted = g[g["in_index"] == 1]
            row.update({
                "economic_messages": int(g["is_economic"].sum()),
                "counted_messages": len(counted),
                "econ_share": g["is_economic"].mean(),
                "EAI": wmean(g["relevance_eff"], g["eng_weight"]),     # over ALL posts
                "ESI": wmean(counted["sentiment"], counted["eng_weight"]) if len(counted) else 0.0,
            })
        rows.append(row)
    daily = pd.DataFrame(rows).reindex(columns=DAILY_COLS)
    if daily.empty:
        return daily
    daily = daily.sort_values("date_only").reset_index(drop=True)

    for col in ("EAI", "ESI"):
        x = daily[col].astype(float)
        sd = x.std(ddof=0)
        daily[f"{col}_z"] = (x - x.mean()) / sd if x.count() >= 2 and sd > 0 else 0.0
        daily.loc[x.isna(), f"{col}_z"] = np.nan
    eai_mean = daily["EAI"].mean()
    daily["EAI_100"] = 100.0 * daily["EAI"] / (eai_mean if eai_mean else 1.0)
    daily["ESI_100"] = 50.0 * (daily["ESI"] + 1.0)
    counts = ["total_messages", "economic_messages", "counted_messages", "unlabeled_messages"]
    daily[counts] = daily[counts].astype("Int64")
    return daily[DAILY_COLS]
