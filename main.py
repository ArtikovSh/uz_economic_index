"""
Daily pipeline: collect one Tashkent day -> label new posts with Gemini ->
rebuild the daily index -> Excel report.

Exits non-zero when something needs a human (expired Telegram session, a failed
channel, a Gemini key/model problem) — after saving everything it could, so the
workflow still commits the progress and then sends an alert.
"""
import asyncio
import sys

from config import CHANNELS
from excel_exporter import export_results
from indicator import score_messages, build_daily_index
from llm_classifier import label_messages
from scraper import target_day_range, collected_channels, run_scraper, SessionError
from store import load_master, merge_master, save_daily

PROBLEMS_FILE = "run_problems.txt"     # read by the workflow's alert step


def main() -> int:
    problems = []
    master = load_master()

    start_utc, end_utc, target = target_day_range()
    print(f"--- STEP 1: Collect {target} (Tashkent) | UTC "
          f"[{start_utc:%Y-%m-%d %H:%M} .. {end_utc:%Y-%m-%d %H:%M}) ---")
    done = collected_channels(master, start_utc, end_utc)
    todo = [ch for ch in CHANNELS if ch not in done]
    if not todo:
        print("All channels already collected for this day — nothing to scrape "
              "(each post is measured once).")
    else:
        if done:
            print(f"Already collected: {sorted(done)}; collecting: {todo}")
        try:
            new, failures = asyncio.run(run_scraper(todo, start_utc, end_utc))
            master = merge_master(master, new)
            problems += [f"{ch}: {err}" for ch, err in failures.items()]
        except SessionError as e:
            problems.append(f"Telegram: {e}")

    print("--- STEP 2: Label new posts with Gemini ---")
    labels, status = label_messages(master)
    print(f"  {status['new']} labelled this run, {status['pending']} still pending")
    for w in status["warnings"]:
        print(f"::warning::{w}")
    if status["error"]:
        problems.append(f"Gemini: {status['error']}")

    print("--- STEP 3: Daily EAI / ESI index ---")
    scored = score_messages(master, labels)
    daily = build_daily_index(scored)
    save_daily(daily)

    print("--- STEP 4: Excel report ---")
    export_results(scored, daily)

    if len(daily):
        print("Latest day:")
        print(daily.tail(1).to_string(index=False))
    if problems:
        with open(PROBLEMS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(problems))
        for p in problems:
            print(f"::error::{p}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
