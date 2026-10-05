"""
Persistent master store. Each run adds the freshly collected messages to a
growing, de-duplicated CSV so the index is a real, comparable time series.
Committed by CI, so history accumulates across runs.

Each post is measured ONCE: if a post is collected again, the first measurement
(views/forwards at ~24h+ of age) is kept, so every day is measured alike.
"""
import os

import pandas as pd

from config import MASTER_CSV, DAILY_CSV

RAW_COLS = ["channel", "message_id", "date", "views", "forwards", "raw_text", "scraped_at"]


def write_csv(df: pd.DataFrame, path: str) -> None:
    """Write via a temp file + rename, so a crash never leaves a half-written CSV."""
    tmp = path + ".tmp"
    df.to_csv(tmp, index=False, encoding="utf-8")
    os.replace(tmp, path)


def load_master() -> pd.DataFrame:
    if not os.path.exists(MASTER_CSV):
        return pd.DataFrame(columns=RAW_COLS)
    df = pd.read_csv(MASTER_CSV)
    for c in RAW_COLS:
        if c not in df.columns:
            df[c] = pd.NA          # e.g. scraped_at for posts collected before v3
    return df[RAW_COLS]


def merge_master(master: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
    """Add new messages to the master store, de-duping on (channel, message_id)."""
    if new_df.empty:
        print(f"Master store: {len(master)} messages (nothing new)")
        return master
    combined = new_df[RAW_COLS] if master.empty else pd.concat(
        [master, new_df[RAW_COLS]], ignore_index=True)
    combined = combined.drop_duplicates(subset=["channel", "message_id"], keep="first")
    combined = combined.sort_values(["channel", "message_id"]).reset_index(drop=True)
    write_csv(combined, MASTER_CSV)
    print(f"Master store: {len(combined)} unique messages (+{len(combined) - len(master)} new)")
    return combined


def save_daily(daily_df: pd.DataFrame) -> None:
    write_csv(daily_df, DAILY_CSV)
    print(f"Daily index time series: {len(daily_df)} days -> {DAILY_CSV}")
