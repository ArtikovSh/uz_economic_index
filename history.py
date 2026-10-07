"""
Build the archive month by month: every active channel, every Tashkent day of the given
months, labelled with the current rules; then the posts table and every index row are
recomputed. Workflow: history.yml.

    python history.py 2026-01               one month
    python history.py 2026-01..2026-03      several months
    python history.py 2026-01 --fresh       start the archive anew (the tables are emptied first)

Months can come in any order (earlier years later): the posts table is kept in date order and
the indices are computed from it again. Days a channel already has are not collected again,
so a month can be run twice (e.g. the current month later, to collect its remaining days).
Days after the Tashkent day before yesterday are not collected yet. When labelling does not
finish in one run, the collected posts wait in pending.csv and the next run carries on.

Nothing here fails the run for an ordinary reason (a channel without posts, unfinished
labelling): everything goes into history_report.txt, which the workflow sends to the owner.
"""
import asyncio
import sys
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from channel_list import active_channels
from config import INDICES_CSV, LLM_LABEL_VERSION
from excel_exporter import export_results
from indicator import ledger_rows, local_day, new_index_rows
from llm_classifier import label_pending
from rebuild import fix_day_notes
from scraper import TASHKENT, SessionError, run_scraper, target_day_range
from store import (INDEX_COLS, LEDGER_COLS, PENDING_COLS, add_to_pending, load_indices, load_ledger,
                   load_pending, post_keys, save_pending, typed, write_csv, write_ledger)

REPORT = "history_report.txt"


def months_in(spec):
    """'2026-01' or '2026-01..2026-03' -> [(2026, 1), (2026, 2), (2026, 3)]."""
    a, _, b = spec.strip().partition("..")
    y, m = map(int, a.strip().split("-"))
    y2, m2 = map(int, (b or a).strip().split("-"))
    out = []
    while (y, m) <= (y2, m2):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def month_days(y, m, last):
    """Tashkent days of the month up to `last`."""
    first = date(y, m, 1)
    nxt = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
    return [first + timedelta(days=i) for i in range((min(nxt - timedelta(days=1), last) - first).days + 1)]


def utc(day):
    return datetime(day.year, day.month, day.day, tzinfo=TASHKENT).astimezone(timezone.utc)


def missing_windows(days, channels, have):
    """{channel: (start_utc, end_utc)} from the first to the last day the channel has no posts."""
    out = {}
    for ch in channels:
        missing = [d for d in days if (ch, d) not in have]
        if missing:
            out[ch] = (utc(missing[0]), utc(missing[-1] + timedelta(days=1)))
    return out


def channel_days(*tables):
    have = set()
    for t in tables:
        if len(t):
            have |= set(zip(t["channel"].astype(str), local_day(t["date"])))
    return have


def finalize(ledger, pending):
    """Labelled posts join the posts table (date order, each post once); the rest keep waiting."""
    done = pending["label_version"].astype(str) == LLM_LABEL_VERSION
    rows = ledger_rows(pending[done]) if done.any() else ledger.iloc[0:0]
    merged = pd.concat([ledger, rows], ignore_index=True) if len(ledger) else rows
    merged = merged[~post_keys(merged).duplicated()].sort_values(["date", "channel", "message_id"], kind="stable")
    return merged.reset_index(drop=True)[LEDGER_COLS], pending[~done]


def main(spec, fresh=False):
    report, problems = [], []
    channels = active_channels()
    if fresh:
        ledger = typed(pd.DataFrame(columns=LEDGER_COLS))
        pending = typed(pd.DataFrame(columns=PENDING_COLS))
        report.append("Arxiv boshidan boshlandi: oldingi ma'lumot o'chirildi.")
    else:
        ledger, pending = load_ledger(), load_pending()
    old_indices = load_indices()
    target = target_day_range()[2]                       # the latest day that can be collected
    print(f"--- History {spec}: {len(channels)} channels, days up to {target} ---")

    for y, m in months_in(spec):
        label = f"{y}-{m:02d}"
        days = month_days(y, m, target)
        if not days:
            report.append(f"{label}: hali boshlanmagan, o'tkazib yuborildi.")
            continue
        todo = missing_windows(days, channels, channel_days(ledger, pending))
        if not todo:
            report.append(f"{label}: allaqachon yig'ilgan.")
            continue
        got, failed = 0, []
        try:
            for ch, (start, end) in todo.items():        # each channel only over the days it lacks
                new, failures = asyncio.run(run_scraper([ch], start, end))
                pending = add_to_pending(pending, ledger, new)
                got += len(new)
                failed += [f"{ch}: {err}" for err in failures.values()]
            save_pending(pending)
        except SessionError as e:
            save_pending(pending)
            problems.append(f"Telegram sessiyasi ishlamayapti: {e}")
            break
        report.append(f"{label}: {got} post yig'ildi ({len(todo)} kanal)."
                      + (" Yig'ilmadi: " + "; ".join(failed) if failed else ""))

    used = ledger["label_model"].dropna()
    used = used[~used.astype(str).str.endswith(":unlabelled")]
    pending, status = label_pending(pending, save=save_pending, sticky=used.iloc[-1] if len(used) else None)
    if status["error"]:
        problems.append(f"Belgilash: {status['error']}")
    ledger, pending = finalize(ledger, pending)
    indices = new_index_rows(ledger, typed(pd.DataFrame(columns=INDEX_COLS)), pending, target,
                             sorted(ledger["channel"].unique()) if len(ledger) else channels)
    indices = fix_day_notes(indices, ledger) if len(indices) else indices

    write_ledger(ledger)
    write_csv(indices[INDEX_COLS], INDICES_CSV)
    save_pending(pending)
    export_results(indices, ledger, len(pending))

    months = ledger["date_local"].astype(str).str[:7].value_counts().sort_index() if len(ledger) else {}
    report.append(f"Belgilandi: {status['new']} post. Arxivda: {len(ledger)} post, "
                  f"{(indices['period_type'] == 'kun').sum()} kun"
                  + (f" ({months.index[0]} – {months.index[-1]})." if len(months) else "."))
    if len(pending):
        report.append(f"{len(pending)} post hali belgilanmadi: workflow'ni yana ishga tushiring "
                      f"(xuddi shu oy bilan), belgilash davom etadi.")
    changed = len(old_indices) != len(indices)
    print(f"Index rows: {len(old_indices)} -> {len(indices)}{' (changed)' if changed else ''}")
    text = "\n".join(report + (["", "Muammo:"] + problems if problems else []))
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        sys.exit("usage: python history.py YYYY-MM[..YYYY-MM] [--fresh]")
    sys.exit(main(args[0], fresh="--fresh" in sys.argv[1:]))
