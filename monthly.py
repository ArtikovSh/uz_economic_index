"""
Monthly economic index: aggregate the already-collected daily data into a
per-month EAI/ESI series.

Run on the 3rd of each month for the PREVIOUS calendar month. By the 3rd the
daily T-2 scraper has collected the whole previous month (its last day, e.g.
Aug 31, is scraped on Sep 2), so the month is complete. No scraping and (if the
daily runs kept the LLM cache warm) no new LLM calls — it re-uses cached labels.
"""
import os
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from config import DATA_DIR, TZ_OFFSET_HOURS, MONTHLY_CSV

TASHKENT = timezone(timedelta(hours=TZ_OFFSET_HOURS))


def target_month(override=""):
    """(year, month, 'YYYY-MM') to build — default previous Tashkent month;
    override with TARGET_MONTH=YYYY-MM."""
    if override:
        y, m = (int(x) for x in override.split("-")[:2])
    else:
        first_of_this = datetime.now(TASHKENT).date().replace(day=1)
        last_prev = first_of_this - timedelta(days=1)
        y, m = last_prev.year, last_prev.month
    return y, m, f"{y:04d}-{m:02d}"


def _wmean(v, w):
    v, w = np.asarray(v, float), np.asarray(w, float)
    s = w.sum()
    return float((v * w).sum() / s) if s > 0 else (float(v.mean()) if len(v) else 0.0)


def build_monthly(scored, y, m, label):
    """Aggregate the scored messages of one Tashkent month into an index row."""
    dt = pd.to_datetime(scored["date_only"])
    d = scored[(dt.dt.year == y) & (dt.dt.month == m)]
    if d.empty:
        return None, d
    counted = d[d["in_index"] == 1]
    eai = _wmean(d["relevance_eff"], d["eng_weight"])
    esi = _wmean(counted["sentiment"], counted["eng_weight"]) if len(counted) else 0.0
    topics = counted["primary_topic"].value_counts().head(5).to_dict()
    row = {
        "month": label,
        "days_covered": int(d["date_only"].nunique()),
        "total_messages": int(len(d)),
        "economic_messages": int(d["is_economic"].sum()),
        "counted_messages": int(len(counted)),
        "econ_share": round(float(d["is_economic"].mean()), 4),
        "EAI": round(eai, 4),
        "ESI": round(esi, 4),
        "ESI_100": round(50.0 * (esi + 1.0), 2),
        "avg_engagement": round(float(d["engagement"].mean()), 3),
        "top_topics": ";".join(f"{k}:{v}" for k, v in topics.items()),
    }
    return row, d


def save_monthly(row):
    """Append/update the monthly time series and recompute EAI_100 across months."""
    new = pd.DataFrame([row])
    if os.path.exists(MONTHLY_CSV):
        new = pd.concat([pd.read_csv(MONTHLY_CSV), new], ignore_index=True)
    new = new.drop_duplicates(subset=["month"], keep="last").sort_values("month").reset_index(drop=True)
    mean_eai = new["EAI"].mean() or 1.0
    new["EAI_100"] = (100.0 * new["EAI"] / mean_eai).round(2)     # avg month = 100
    new.to_csv(MONTHLY_CSV, index=False, encoding="utf-8")
    print(f"Monthly index: {len(new)} months -> {MONTHLY_CSV}")
    return new
