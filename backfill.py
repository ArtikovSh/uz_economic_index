"""
Collect Tashkent days the daily run missed, e.g. 2026-09-28..2026-10-03.

It only collects: the posts go to pending.csv, and the daily run labels and finalises
them together with the other days, in date order. A day and channel already collected
is skipped, so running it twice is harmless. Days up to the last finalised day are
refused, because their week and month rows are already published. The index counts
posts, so a late collection does not change it (only the views kept for the Mini App
are older).

    python backfill.py 2026-09-28..2026-10-03
"""
import asyncio
import sys
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from config import CHANNELS
from scraper import TASHKENT, SessionError, collected_channels, run_scraper
from store import RAW_COLS, add_to_pending, load_ledger, load_pending, save_pending


def days_in(spec):
    """'2026-09-28..2026-10-03' (or a single day) -> list of dates."""
    a, _, b = spec.partition("..")
    start, end = date.fromisoformat(a.strip()), date.fromisoformat((b or a).strip())
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def window(day):
    """[start, end) in UTC of a Tashkent calendar day."""
    start = datetime(day.year, day.month, day.day, tzinfo=TASHKENT)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


def main(spec):
    ledger, pending = load_ledger(), load_pending()
    last_final = pd.to_datetime(ledger["date_local"].astype(str).str[:10]).max().date() if len(ledger) else None
    refused, failed = [], []
    for day in days_in(spec):
        if last_final and day <= last_final:
            refused.append(f"{day}: not collected — days up to {last_final} are final")
            continue
        start, end = window(day)
        seen = pd.concat([ledger[RAW_COLS], pending[RAW_COLS]], ignore_index=True)
        todo = [ch for ch in CHANNELS if ch not in collected_channels(seen, start, end)]
        if not todo:
            print(f"{day}: already collected")
            continue
        print(f"{day}: collecting {todo}")
        try:
            new, failures = asyncio.run(run_scraper(todo, start, end))
        except SessionError as e:
            print(f"::error::Telegram: {e}")
            return 1
        pending = add_to_pending(pending, ledger, new)
        save_pending(pending)
        failed += [f"{day} {ch}: {err}" for ch, err in failures.items()]
    for p in refused + failed:
        print(f"::warning::{p}")
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) != 2 or not sys.argv[1].strip():
        sys.exit("usage: python backfill.py YYYY-MM-DD[..YYYY-MM-DD]")
    sys.exit(main(sys.argv[1]))
