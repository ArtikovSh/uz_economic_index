"""
Persistent master store. Each run appends the freshly scraped messages to a
growing, de-duplicated CSV so the index becomes a real, comparable time series
instead of a one-shot snapshot (which biased older days downward). Committed by
CI, so history accumulates across runs.
"""
import os
import pandas as pd
from config import MASTER_CSV, DAILY_CSV

RAW_COLS = ["channel", "message_id", "date", "views", "forwards", "raw_text"]


def merge_master(new_df: pd.DataFrame) -> pd.DataFrame:
    """Append new messages to the master store, de-duping on (channel, id)."""
    new_df = new_df[RAW_COLS].copy()
    if os.path.exists(MASTER_CSV):
        old = pd.read_csv(MASTER_CSV)
        combined = pd.concat([old, new_df], ignore_index=True)
    else:
        combined = new_df
    # keep='last' -> refreshed view/forward counts overwrite the older snapshot
    combined = combined.drop_duplicates(subset=["channel", "message_id"], keep="last")
    combined = combined.sort_values(["channel", "message_id"]).reset_index(drop=True)
    combined.to_csv(MASTER_CSV, index=False, encoding="utf-8")
    print(f"Master store: {len(combined)} unique messages (+{len(new_df)} scraped this run)")
    return combined


def save_daily(daily_df: pd.DataFrame) -> None:
    daily_df.to_csv(DAILY_CSV, index=False, encoding="utf-8")
    print(f"Daily index time series: {len(daily_df)} days -> {DAILY_CSV}")
