"""
Rebuild the whole history with the current labelling rules (config.LLM_LABEL_VERSION).

Every final or waiting post whose label is older than the current version is labelled again
(posts that already carry a current label are kept, so nothing is paid for twice); the posts
table and the indices table are computed from scratch; pending keeps the posts whose day is
not final yet. This is the one exception to "a published row is never changed": run it when
the methodology changes (workflow input `rebuild`), followed by `sync_to_db.py --full` and
`sheets_sync.py --full`.

The tables are written only when every post has a current label. A stopped run (quota,
timeout) keeps the labels it got in data/relabel.csv, and the next run starts from them.
"""
import os
import sys

import pandas as pd

from config import DATA_DIR, INDICES_CSV, LLM_LABEL_VERSION
from excel_exporter import export_results
from indicator import ledger_rows, new_index_rows
from llm_classifier import label_pending
from store import (INDEX_COLS, LABEL_COLS, PENDING_COLS, RAW_COLS, load_indices, load_ledger, load_pending,
                   post_keys, save_pending, typed, write_csv, write_ledger)

RELABEL_CSV = os.path.join(DATA_DIR, "relabel.csv")      # labels a stopped rebuild already got
LABELLED = ["channel", "message_id"] + LABEL_COLS + ["label_version", "label_model"]


def target_day():
    from scraper import target_day_range           # telethon is imported only when needed
    return target_day_range()[2]


def fix_day_notes(indices, ledger):
    """A channel counts as missing on a day only from its first collected day on, so a channel
    added later does not mark every earlier day as incomplete."""
    days = ledger["date_local"].astype(str).str[:10]
    first = days.groupby(ledger["channel"]).min()
    present = ledger.groupby(days)["channel"].apply(set)
    out = indices.copy()
    for i, r in out[out["period_type"] == "kun"].iterrows():
        day = str(r["period"])
        missing = sorted(c for c, d in first.items() if d <= day and c not in present.get(day, set()))
        out.at[i, "note"] = ("yig'ilmagan kanal: " + ", ".join(missing)) if missing else ""
    return out


def save_progress(work):
    current = work[work["label_version"].astype(str) == LLM_LABEL_VERSION]
    write_csv(current[LABELLED], RELABEL_CSV)


def relabel(ledger, pending):
    """All posts (final and waiting) as one pending-like table; the ones without a current label
    (here or in the progress of a stopped run) are labelled with the current rules."""
    keep = RAW_COLS + LABEL_COLS + ["label_version", "label_model"]
    work = pd.concat([ledger[keep], pending[keep]], ignore_index=True)
    work = work[~post_keys(work).duplicated()].reset_index(drop=True)
    work = typed(work.reindex(columns=PENDING_COLS))
    work[LABEL_COLS + ["label_version", "label_model"]] = \
        work[LABEL_COLS + ["label_version", "label_model"]].astype(object)   # take booleans and text
    if os.path.exists(RELABEL_CSV):
        got = pd.read_csv(RELABEL_CSV)
        got = got[got["label_version"].astype(str) == LLM_LABEL_VERSION].set_index(post_keys(got))
        keys = post_keys(work)
        hit = keys.isin(got.index) & (work["label_version"].astype(str) != LLM_LABEL_VERSION)
        cols = LABELLED[2:]
        work.loc[hit, cols] = got.loc[keys[hit], cols].to_numpy()
        print(f"  {int(hit.sum())} labels from the stopped run ({RELABEL_CSV})")
    used = ledger["label_model"].dropna()
    used = used[~used.astype(str).str.endswith(":unlabelled")]
    return label_pending(work, save=save_progress, sticky=used.iloc[-1] if len(used) else None)


def summary(old, new):
    """Monthly EAI/ESI before and after, for the run log."""
    pick = lambda df: df[df["period_type"] == "oy"].set_index("period")[["EAI", "ESI"]]
    both = pick(old).join(pick(new), lsuffix=" (old)", rsuffix=" (new)", how="outer")
    return both.to_string()


def main() -> int:
    ledger, pending, old_indices = load_ledger(), load_pending(), load_indices()
    final = set(post_keys(ledger))
    print(f"--- Rebuild with labels {LLM_LABEL_VERSION}: {len(ledger)} final + {len(pending)} waiting posts ---")
    work, status = relabel(ledger, pending)
    for w in status["warnings"]:
        print(f"::warning::{w}")
    left = int((work["label_version"].astype(str) != LLM_LABEL_VERSION).sum())
    if status["error"] or left:
        save_progress(work)
        print(f"::error::Rebuild stopped, the tables were not changed: {left} posts without a "
              f"{LLM_LABEL_VERSION} label ({status['error'] or 'see the warnings'}). Run it again: "
              f"the labels got so far are kept in {RELABEL_CSV}.")
        return 1

    is_final = post_keys(work).isin(final)
    new_ledger = ledger_rows(work[is_final]).reset_index(drop=True)
    new_pending = work[~is_final]
    channels = sorted(new_ledger["channel"].unique())
    indices = new_index_rows(new_ledger, typed(pd.DataFrame(columns=INDEX_COLS)), new_pending,
                             target_day(), channels)
    indices = fix_day_notes(indices, new_ledger)

    write_ledger(new_ledger)
    write_csv(indices[INDEX_COLS], INDICES_CSV)
    save_pending(new_pending)
    export_results(indices, new_ledger, len(new_pending))
    if os.path.exists(RELABEL_CSV):
        os.remove(RELABEL_CSV)
    print(f"Rebuilt: {len(new_ledger)} posts, {len(indices)} index rows, {len(new_pending)} still waiting")
    print(summary(old_indices, indices))
    return 0


if __name__ == "__main__":
    sys.exit(main())
