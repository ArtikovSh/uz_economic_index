"""
Rebuild the whole history with the current labelling rules (config.LLM_LABEL_VERSION).

Every final post and every waiting post is labelled again; the posts table and the indices
table are computed from scratch; pending keeps the posts whose day is not final yet. This is
the one exception to "a published row is never changed": run it when the methodology
changes (workflow input `rebuild`), followed by `sync_to_db.py --full` and
`sheets_sync.py --full`.

Nothing is written unless every post got a current label, so a failed run (quota, timeout)
leaves the tables exactly as they were and can simply be run again.
"""
import sys

import pandas as pd

from config import INDICES_CSV, LLM_LABEL_VERSION
from excel_exporter import export_results
from indicator import ledger_rows, new_index_rows
from llm_classifier import label_pending
from store import (INDEX_COLS, LABEL_COLS, PENDING_COLS, RAW_COLS, load_indices, load_ledger, load_pending,
                   post_keys, save_pending, typed, write_csv, write_ledger)


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


def relabel(ledger, pending):
    """All posts (final and waiting) as a fresh pending table, labelled with the current rules."""
    work = pd.concat([ledger[RAW_COLS], pending[RAW_COLS]], ignore_index=True)
    work = work[~post_keys(work).duplicated()].reset_index(drop=True)
    work = typed(work.reindex(columns=PENDING_COLS))
    work[LABEL_COLS] = work[LABEL_COLS].astype(object)   # empty columns must take booleans and text
    used = ledger["label_model"].dropna()
    used = used[~used.astype(str).str.endswith(":unlabelled")]
    return label_pending(work, save=None, sticky=used.iloc[-1] if len(used) else None)


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
        print(f"::error::Rebuild stopped, nothing was changed: {left} posts without a {LLM_LABEL_VERSION} "
              f"label ({status['error'] or 'see the warnings'}). Run it again.")
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
    print(f"Rebuilt: {len(new_ledger)} posts, {len(indices)} index rows, {len(new_pending)} still waiting")
    print(summary(old_indices, indices))
    return 0


if __name__ == "__main__":
    sys.exit(main())
