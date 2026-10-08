"""
Storage: two append-only tables plus a small staging file.

  data/messages.csv – "Xabarlar": every collected post with its labels and index
                      flags, in date order. A post is appended once its day is final
                      and the row is never changed afterwards.
  data/indices.csv  – "Indekslar": one row per closed day, week, month, quarter and
                      year. Append-only as well.
  data/pending.csv  – posts already collected whose day is not final yet (waiting for
                      a label or a missing channel). Usually empty after a run.

Each post is measured once: if it is collected again, the first measurement wins.
"""
import os

import pandas as pd

from config import MASTER_CSV, MESSAGES_DIR, INDICES_CSV, PENDING_CSV

RAW_COLS = ["channel", "message_id", "date", "views", "forwards", "raw_text", "scraped_at"]
LABEL_COLS = ["is_economic", "primary_topic", "topics", "headline", "sentiment",
              "is_ad", "is_digest", "is_foreign"]
PENDING_COLS = RAW_COLS + LABEL_COLS + ["label_version", "label_model", "label_error"]
LEDGER_COLS = ["date_local", "channel", "message_id", "date", "views", "forwards", "scraped_at",
               "primary_topic", "topics", "headline", "is_economic", "sentiment", "is_ad", "ad_marker",
               "is_digest", "is_foreign", "nonad", "econ", "tone", "label_version", "label_model",
               "raw_text"]
INDEX_COLS = ["period_type", "period", "start", "end", "days", "days_expected", "posts",
              "nonad", "econ", "pos", "neu", "neg", "EAI", "ESI", "note"]



def write_csv(df: pd.DataFrame, path: str) -> None:
    """Write via a temp file + rename, so a crash never leaves a half-written CSV."""
    tmp = path + ".tmp"
    df.to_csv(tmp, index=False, encoding="utf-8", lineterminator="\n")
    os.replace(tmp, path)


TEXT_COLS = {"channel", "date", "raw_text", "scraped_at", "primary_topic", "topics", "headline", "label_version",
             "label_model", "label_error", "date_local", "period_type", "period", "start", "end",
             "note"}


def typed(df):
    """Text columns as object dtype, so an empty (all-NaN) column can later take strings."""
    for c in df.columns:
        if c in TEXT_COLS:
            df[c] = df[c].astype(object)
    return df


def _read(path, cols):
    if not os.path.exists(path):
        return typed(pd.DataFrame(columns=cols))
    df = pd.read_csv(path)
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return typed(df[cols].copy())


def post_keys(df):
    return df["channel"].astype(str) + "|" + df["message_id"].astype(str)


def _month_files():
    if not os.path.isdir(MESSAGES_DIR):
        return []
    return sorted(os.path.join(MESSAGES_DIR, f) for f in os.listdir(MESSAGES_DIR)
                  if len(f) == 11 and f.endswith(".csv"))         # 2026-01.csv


def load_ledger():
    """The posts table: data/messages/YYYY-MM.csv (or the older single messages.csv)."""
    files = _month_files()
    if not files:
        return _read(MASTER_CSV, LEDGER_COLS)
    parts = [_read(f, LEDGER_COLS) for f in files]
    return typed(pd.concat(parts, ignore_index=True)) if len(parts) > 1 else parts[0]


def _month_path(month):
    return os.path.join(MESSAGES_DIR, f"{month}.csv")


def write_ledger(df):
    """The whole posts table, rewritten one file per month in date order (history, rebuild).
    Months no longer present are removed, and so is the older single file."""
    os.makedirs(MESSAGES_DIR, exist_ok=True)
    df = df[LEDGER_COLS].sort_values(["date", "channel", "message_id"], kind="stable")
    months = df["date_local"].astype(str).str[:7]
    for month, part in df.groupby(months, sort=True):
        write_csv(part, _month_path(month))
    for f in _month_files():
        if os.path.basename(f)[:7] not in set(months):
            os.remove(f)
    if os.path.exists(MASTER_CSV):
        os.remove(MASTER_CSV)


def append_ledger(ledger, rows):
    """New final posts at the end of their month's file (the daily run)."""
    if rows.empty:
        return ledger
    if not _month_files() and os.path.exists(MASTER_CSV):
        write_ledger(ledger)                               # move to monthly files once
    months = rows["date_local"].astype(str).str[:7]
    for month, part in rows.groupby(months, sort=True):
        os.makedirs(MESSAGES_DIR, exist_ok=True)
        append_rows(_month_path(month), part.iloc[0:0], part, LEDGER_COLS)
    return rows if ledger.empty else pd.concat([ledger, rows[LEDGER_COLS]], ignore_index=True)


def load_pending():
    return _read(PENDING_CSV, PENDING_COLS)


def load_indices():
    return _read(INDICES_CSV, INDEX_COLS)


def save_pending(df):
    write_csv(df[PENDING_COLS], PENDING_CSV)


def append_rows(path, existing, new, cols):
    """Append rows at the end of a table file. Bytes already in the file are never
    read back or rewritten, so a published row stays exactly as it was written."""
    if new.empty:
        return existing
    new = new[cols]
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        write_csv(new, path)
    else:
        with open(path, "rb") as f:
            header = f.readline().decode("utf-8").strip()
            f.seek(-1, os.SEEK_END)
            ends_with_newline = f.read(1) == b"\n"
        if header != ",".join(cols):
            have = header.split(",")
            if not set(have) < set(cols):
                raise RuntimeError(f"{path}: unexpected header, refusing to append")
            # a column added to the layout: rewrite once with it (blank in old rows), values unchanged
            write_csv(pd.read_csv(path, dtype=str, keep_default_na=False).reindex(columns=cols, fill_value=""), path)
            ends_with_newline = True
        with open(path, "a", encoding="utf-8", newline="") as f:
            if not ends_with_newline:
                f.write("\n")
            new.to_csv(f, header=False, index=False, lineterminator="\n")
    return new if existing.empty else pd.concat([existing, new], ignore_index=True)


def add_to_pending(pending, ledger, new):
    """Queue freshly collected posts, skipping any post already stored (first measurement wins)."""
    if new.empty:
        return pending
    known = set(post_keys(ledger)) | set(post_keys(pending))
    fresh = new[~post_keys(new).isin(known)].drop_duplicates(subset=["channel", "message_id"])
    if fresh.empty:
        return pending
    fresh = typed(fresh.reindex(columns=PENDING_COLS))
    out = fresh if pending.empty else pd.concat([pending, fresh], ignore_index=True)
    print(f"Queued {len(fresh)} new posts ({len(out)} waiting to be finalised)")
    return out
