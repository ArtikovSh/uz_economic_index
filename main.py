"""
Daily pipeline: collect one Tashkent day -> label new posts with Gemini -> append
final days to the posts table -> append closed periods to the indices table ->
Excel report.

Exits non-zero when something needs a human (expired Telegram session, a failed
channel, a Gemini key/model problem, or Gemini labelling nothing for any reason but
the daily quota) — after saving everything it could, so the workflow still commits
the progress and then sends an alert.
"""
import asyncio
import sys

import pandas as pd

from channel_list import active_channels
from config import INDICES_CSV
from excel_exporter import export_results
from indicator import finalize_days, new_index_rows
from llm_classifier import label_pending
from scraper import target_day_range, collected_channels, run_scraper, SessionError
from store import (RAW_COLS, INDEX_COLS, load_ledger, load_pending, load_indices,
                   save_pending, add_to_pending, append_rows, append_ledger)

PROBLEMS_FILE = "run_problems.txt"     # read by the workflow's alert step


def main() -> int:
    channels = active_channels()
    problems = []
    ledger, pending, indices = load_ledger(), load_pending(), load_indices()

    start_utc, end_utc, target = target_day_range()
    print(f"--- STEP 1: Collect {target} (Tashkent) | UTC "
          f"[{start_utc:%Y-%m-%d %H:%M} .. {end_utc:%Y-%m-%d %H:%M}) ---")
    seen = pd.concat([ledger[RAW_COLS], pending[RAW_COLS]], ignore_index=True)
    done = collected_channels(seen, start_utc, end_utc)
    todo = [ch for ch in channels if ch not in done]
    if not todo:
        print("All channels already collected for this day — nothing to scrape "
              "(each post is measured once).")
    else:
        if done:
            print(f"Already collected: {sorted(done)}; collecting: {todo}")
        try:
            new, failures = asyncio.run(run_scraper(todo, start_utc, end_utc))
            pending = add_to_pending(pending, ledger, new)
            save_pending(pending)
            problems += [f"{ch}: {err}" for ch, err in failures.items()]
        except SessionError as e:
            problems.append(f"Telegram: {e}")

    print("--- STEP 2: Label waiting posts with Gemini ---")
    used = pending["label_model"].dropna().tolist() or ledger["label_model"].dropna().tolist()
    pending, status = label_pending(pending, save=save_pending, sticky=used[-1] if used else None)
    print(f"  {status['new']} labelled this run")
    for w in status["warnings"]:
        print(f"::warning::{w}")
    if status["error"]:
        problems.append(f"Gemini: {status['error']}")
    elif status["todo"] and not status["new"] and not status["quota"]:
        problems.append("Gemini: no post could be labelled this run — "
                        + ("; ".join(status["warnings"]) or "no reason given")[:400])

    print("--- STEP 3: Finalise days and append to the posts table ---")
    rows, pending, days = finalize_days(pending, ledger, target, channels)
    ledger = append_ledger(ledger, rows)                            # ledger first, then pending
    save_pending(pending)
    print(f"  finalised {len(days)} day(s): {', '.join(map(str, days)) or '-'} | "
          f"{len(pending)} posts still waiting")

    print("--- STEP 4: Append closed periods to the indices table ---")
    idx_new = new_index_rows(ledger, indices, pending, target, channels)
    indices = append_rows(INDICES_CSV, indices, idx_new, INDEX_COLS)
    for r in idx_new.itertuples(index=False):
        print(f"  {r.period_type:6} {r.period:10}  EAI {r.EAI:5}%  ESI {r.ESI:+6}  "
              f"({r.econ}/{r.nonad}) {r.note}")

    print("--- STEP 5: Excel report ---")
    export_results(indices, ledger, len(pending))

    if problems:
        with open(PROBLEMS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(problems))
        for p in problems:
            print(f"::error::{p}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
