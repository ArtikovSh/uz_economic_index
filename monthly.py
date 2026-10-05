"""
Monthly economic index: aggregate the already-collected daily data into a
per-month EAI/ESI series.

Run on the 3rd of each month for the PREVIOUS calendar month. By then the daily
run has collected the whole previous month (its last day is collected two days
later). Days that were never collected stay missing (no late backfill); the row
records how complete the month is (days_covered vs days_expected).
"""
import calendar
import os
from datetime import datetime, timedelta, timezone

import pandas as pd

from config import TZ_OFFSET_HOURS, MONTHLY_CSV
from indicator import wmean
from store import write_csv

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


def build_monthly(scored, y, m, label):
    """Aggregate the scored messages of one Tashkent month into an index row."""
    dt = pd.to_datetime(scored["date_only"])
    d = scored[(dt.dt.year == y) & (dt.dt.month == m)]
    if d.empty:
        return None, d
    labeled = d[d["labeled"] == 1]
    counted = labeled[labeled["in_index"] == 1]
    days_expected = calendar.monthrange(y, m)[1]
    days_covered = int(d["date_only"].nunique())
    unlabeled = int(len(d) - len(labeled))
    eai = wmean(labeled["relevance_eff"], labeled["eng_weight"])
    esi = wmean(counted["sentiment"], counted["eng_weight"]) if len(counted) else 0.0
    topics = counted["primary_topic"].value_counts().head(5).to_dict()
    row = {
        "month": label,
        "days_covered": days_covered,
        "total_messages": int(len(d)),
        "economic_messages": int(labeled["is_economic"].sum()),
        "counted_messages": int(len(counted)),
        "econ_share": round(float(labeled["is_economic"].mean()), 4) if len(labeled) else 0.0,
        "EAI": round(eai, 4),
        "ESI": round(esi, 4),
        "ESI_100": round(50.0 * (esi + 1.0), 2),
        "avg_engagement": round(float(d["engagement"].mean()), 3),
        "top_topics": ";".join(f"{k}:{v}" for k, v in topics.items()),
        "days_expected": days_expected,
        "unlabeled_messages": unlabeled,
        "complete": int(days_covered == days_expected and unlabeled == 0),
    }
    if not row["complete"]:
        print(f"::warning::Month {label} is incomplete: {days_covered}/{days_expected} days "
              f"collected, {unlabeled} posts unlabelled.")
    return row, d


def save_monthly(row):
    """Append/update the monthly time series and recompute EAI_100 across months."""
    new = pd.DataFrame([row])
    if os.path.exists(MONTHLY_CSV):
        new = pd.concat([pd.read_csv(MONTHLY_CSV), new], ignore_index=True)
    new = new.drop_duplicates(subset=["month"], keep="last").sort_values("month").reset_index(drop=True)
    ints = [c for c in ("days_expected", "unlabeled_messages", "complete") if c in new.columns]
    new[ints] = new[ints].astype("Int64")         # older rows predate these columns
    mean_eai = new["EAI"].mean() or 1.0
    new["EAI_100"] = (100.0 * new["EAI"] / mean_eai).round(2)     # avg month = 100
    write_csv(new, MONTHLY_CSV)
    print(f"Monthly index: {len(new)} months -> {MONTHLY_CSV}")
    return new
