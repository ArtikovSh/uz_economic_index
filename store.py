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

from config import MASTER_CSV, INDICES_CSV, PENDING_CSV, DATA_DIR, LLM_LABEL_VERSION

RAW_COLS = ["channel", "message_id", "date", "views", "forwards", "raw_text", "scraped_at"]
LABEL_COLS = ["is_economic", "primary_topic", "relevance", "sentiment",
              "is_ad", "is_digest", "is_foreign"]
PENDING_COLS = RAW_COLS + LABEL_COLS + ["label_version", "label_model"]
LEDGER_COLS = ["date_local", "channel", "message_id", "date", "views", "forwards", "scraped_at",
               "primary_topic", "is_economic", "relevance", "sentiment", "is_ad", "ad_marker",
               "is_digest", "is_foreign", "nonad", "econ", "tone", "label_version", "label_model",
               "raw_text"]
INDEX_COLS = ["period_type", "period", "start", "end", "days", "days_expected", "posts",
              "nonad", "econ", "pos", "neu", "neg", "EAI", "ESI", "note"]

# files of the pre-ledger layout (converted once by migrate_legacy)
LEGACY_LABELS = os.path.join(DATA_DIR, "llm_labels.csv")
LEGACY_FILES = [LEGACY_LABELS, os.path.join(DATA_DIR, "daily_index.csv"),
                os.path.join(DATA_DIR, "monthly_index.csv")]


def write_csv(df: pd.DataFrame, path: str) -> None:
    """Write via a temp file + rename, so a crash never leaves a half-written CSV."""
    tmp = path + ".tmp"
    df.to_csv(tmp, index=False, encoding="utf-8", lineterminator="\n")
    os.replace(tmp, path)


TEXT_COLS = {"channel", "date", "raw_text", "scraped_at", "primary_topic", "label_version",
             "label_model", "date_local", "period_type", "period", "start", "end", "note"}


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


def load_ledger():
    return _read(MASTER_CSV, LEDGER_COLS)


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
            raise RuntimeError(f"{path}: unexpected header, refusing to append")
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


def migrate_legacy():
    """One-time conversion of the old layout (raw messages.csv + llm_labels.csv +
    daily/monthly CSVs): every stored post moves to pending.csv, keeping any label
    already made with the current LLM_LABEL_VERSION, and messages.csv restarts as the
    empty ledger. The posts are then finalised day by day in date order."""
    if not os.path.exists(MASTER_CSV):
        return False
    head = pd.read_csv(MASTER_CSV, nrows=0).columns
    if "econ" in head:
        return False                                    # already the ledger layout
    raw = pd.read_csv(MASTER_CSV)
    pending = typed(raw.reindex(columns=PENDING_COLS))
    if os.path.exists(LEGACY_LABELS):
        lab = pd.read_csv(LEGACY_LABELS)
        lab = lab[lab["label_version"].astype(str) == LLM_LABEL_VERSION].set_index("key")
        keys = post_keys(pending)
        hit = keys.isin(lab.index)
        for c in LABEL_COLS:
            pending.loc[hit, c] = lab.loc[keys[hit], c].values
        pending.loc[hit, "label_version"] = LLM_LABEL_VERSION
        if "model" in lab.columns:
            pending.loc[hit, "label_model"] = lab.loc[keys[hit], "model"].values
    write_csv(pending, PENDING_CSV)                     # data is safe in pending first
    write_csv(pd.DataFrame(columns=LEDGER_COLS), MASTER_CSV)
    for f in LEGACY_FILES:
        if os.path.exists(f):
            os.remove(f)
    labelled = int((pending["label_version"] == LLM_LABEL_VERSION).sum())
    print(f"Migrated {len(pending)} posts to the new layout ({labelled} already labelled "
          f"with {LLM_LABEL_VERSION}); they are finalised day by day as labels complete.")
    return True
