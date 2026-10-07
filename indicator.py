"""
Index construction by plain counts (see METHODOLOGY.md).

For any period (day, week, month, quarter, year), over ALL channels together:

  nonad = posts that are not advertising
  econ  = non-ad posts about the domestic Uzbek economy
          (economic, not a news digest, not a foreign-macro story)
  EAI   = 100 * econ / nonad                    (% of non-ad news that is economic)
  ESI   = 100 * (positive - negative) / econ    (balance, -100 .. +100)

Posts the channel itself marks as advertising count as ads whatever the model said.

A day is FINAL when all its posts are labelled and either every channel was collected
or the pipeline has moved on to a later day. Final days are appended to the posts
table in date order (oldest first, never skipping an earlier open day); a period's
index row is appended once its last day is final, or once no more data can arrive.
Nothing already appended is ever changed.
"""
import re
from datetime import timedelta

import numpy as np
import pandas as pd

from config import TONE_THRESHOLD, TZ_OFFSET_HOURS, LLM_LABEL_VERSION
from store import LEDGER_COLS, INDEX_COLS, post_keys

# The channel's own sponsorship marker: "(реклама)" anywhere, "на правах рекламы",
# "#реклама", or "Реклама"/"Reklama" as the post's last word (Daryo, Kun.uz style).
# A bare "реклама" inside a sentence (news about advertising) does not match.
AD_MARKER_RE = re.compile(
    r"\(\s*(?:реклама|reklama)\s*\)"
    r"|#\s?(?:реклама|reklama)\b"
    r"|на\s+правах\s+рекламы|reklama\s+huquqida"
    r"|(?:^|\s)[*_]*(?:реклама|reklama)[*_]*\s*$",
    re.IGNORECASE)

PERIOD_TYPES = ["kun", "hafta", "oy", "chorak", "yil"]


def has_ad_marker(text) -> bool:
    return isinstance(text, str) and bool(AD_MARKER_RE.search(text.strip()))


def local_day(utc_dates):
    """Tashkent calendar day of naive-UTC timestamps."""
    return (pd.to_datetime(utc_dates, errors="coerce") + pd.Timedelta(hours=TZ_OFFSET_HOURS)).dt.date


# ------------------------------------------------------------- post flags ----
def ledger_rows(df):
    """Labelled pending posts -> rows of the posts table, with the index flags frozen in."""
    df = df.copy()
    local = pd.to_datetime(df["date"], errors="coerce") + pd.Timedelta(hours=TZ_OFFSET_HOURS)
    df["date_local"] = local.dt.strftime("%Y-%m-%d %H:%M")
    flags = ["is_economic", "is_ad", "is_digest", "is_foreign"]
    df[flags] = df[flags].astype(float).fillna(0).astype(int)
    df["ad_marker"] = df["raw_text"].apply(has_ad_marker).astype(int)
    df["is_ad"] = (df["is_ad"] | df["ad_marker"]).astype(int)
    topics = df["topics"] if "topics" in df else pd.Series(index=df.index, dtype=object)
    df["topics"] = topics.where(topics.notna() & (topics.astype(str) != ""), df["primary_topic"])
    df["nonad"] = 1 - df["is_ad"]
    df["econ"] = ((df["nonad"] == 1) & (df["is_economic"] == 1)
                  & (df["is_digest"] == 0) & (df["is_foreign"] == 0)).astype(int)
    s = df["sentiment"].astype(float)
    tone = np.where(s > TONE_THRESHOLD, 1, np.where(s < -TONE_THRESHOLD, -1, 0))
    df["tone"] = pd.Series(tone, index=df.index).where(df["econ"] == 1)   # only for counted posts
    df["tone"] = df["tone"].astype("Int64")
    return df.sort_values(["date", "channel", "message_id"])[LEDGER_COLS]


# ------------------------------------------------------------ finalising -----
def finalize_days(pending, ledger, target_day, channels):
    """Move final days from pending to the posts table, oldest first.

    Returns (new_ledger_rows, remaining_pending, finalized_days)."""
    if pending.empty:
        return pending.iloc[0:0], pending, []
    pending = pending[~post_keys(pending).isin(set(post_keys(ledger)))]   # crash-safe
    days = local_day(pending["date"])
    labelled = pending["label_version"].astype(str) == LLM_LABEL_VERSION
    final, done_mask = [], pd.Series(False, index=pending.index)
    for day in sorted(days.dropna().unique()):
        in_day = days == day
        if not labelled[in_day].all():
            break                                   # FIFO: a later day never jumps the queue
        have = set(pending.loc[in_day, "channel"]) | set(
            ledger.loc[ledger["date_local"].astype(str).str[:10] == str(day), "channel"])
        if day >= target_day and not set(channels) <= have:
            break                                   # today's day still waits for a channel
        final.append(day)
        done_mask |= in_day
    rows = ledger_rows(pending[done_mask]) if final else pending.iloc[0:0]
    return rows, pending[~done_mask], final


# --------------------------------------------------------------- periods -----
def period_of(day, ptype):
    """(label, start, end) of the period of type ptype containing day."""
    if ptype == "kun":
        return str(day), day, day
    if ptype == "hafta":
        start = day - timedelta(days=day.weekday())
        iso = start.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}", start, start + timedelta(days=6)
    if ptype == "oy":
        start = day.replace(day=1)
        nxt = (start + timedelta(days=32)).replace(day=1)
        return f"{day.year}-{day.month:02d}", start, nxt - timedelta(days=1)
    if ptype == "chorak":
        q = (day.month - 1) // 3 + 1
        start = day.replace(month=3 * q - 2, day=1)
        nxt = (start + timedelta(days=95)).replace(day=1)
        return f"{day.year}-Q{q}", start, nxt - timedelta(days=1)
    start = day.replace(month=1, day=1)
    return str(day.year), start, day.replace(month=12, day=31)


def index_row(ptype, label, start, end, posts, channels):
    """One index row from the posts of the period."""
    days = posts["day"].nunique()
    nonad, econ = int(posts["nonad"].sum()), int(posts["econ"].sum())
    tone = posts.loc[posts["econ"] == 1, "tone"]
    pos, neg = int((tone == 1).sum()), int((tone == -1).sum())
    expected = (end - start).days + 1
    if ptype == "kun":
        missing = sorted(set(channels) - set(posts["channel"]))
        note = ("yig'ilmagan kanal: " + ", ".join(missing)) if missing else ""
    else:
        note = f"{expected - days} kun ma'lumotsiz" if days < expected else ""
    return {
        "period_type": ptype, "period": label, "start": str(start), "end": str(end),
        "days": days, "days_expected": expected, "posts": len(posts),
        "nonad": nonad, "econ": econ, "pos": pos, "neu": econ - pos - neg, "neg": neg,
        "EAI": round(100.0 * econ / nonad, 1) if nonad else np.nan,
        "ESI": round(100.0 * (pos - neg) / econ, 1) if econ else np.nan,
        "note": note,
    }


def new_index_rows(ledger, indices, pending, target_day, channels):
    """Index rows for every closed period not yet in the indices table, in date order."""
    if ledger.empty:
        return pd.DataFrame(columns=INDEX_COLS)
    posts = ledger.copy()
    posts["day"] = pd.to_datetime(posts["date_local"].astype(str).str[:10]).dt.date
    posts["tone"] = pd.to_numeric(posts["tone"], errors="coerce")
    emitted = set(zip(indices["period_type"].astype(str), indices["period"].astype(str)))
    last_final = posts["day"].max()
    pend_days = local_day(pending["date"]).dropna() if len(pending) else pd.Series([], dtype=object)
    first_open = pend_days.min() if len(pend_days) else None

    rows = []
    for t, ptype in enumerate(PERIOD_TYPES):
        periods = {period_of(d, ptype) for d in posts["day"].unique()}
        for label, start, end in periods:
            if (ptype, label) in emitted:
                continue
            closed = end <= last_final or (end < target_day and (first_open is None or first_open > end))
            if not closed:
                continue
            sel = posts[(posts["day"] >= start) & (posts["day"] <= end)]
            rows.append((end, t, index_row(ptype, label, start, end, sel, channels)))
    rows.sort(key=lambda r: (r[0], r[1]))
    return pd.DataFrame([r[2] for r in rows], columns=INDEX_COLS)
