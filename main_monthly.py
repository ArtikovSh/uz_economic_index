"""
Build the monthly economic index from the already-collected daily data.
Run on the 3rd of each month (for the previous month). No scraping; labels any
post still missing a Gemini label first.
"""
import os
import sys

from config import MASTER_CSV
from excel_exporter import export_monthly
from indicator import score_messages
from llm_classifier import label_messages
from monthly import target_month, build_monthly, save_monthly
from store import load_master


def main() -> int:
    if not os.path.exists(MASTER_CSV):
        print("No master data yet — run the daily pipeline first.")
        return 0
    master = load_master()
    y, m, label = target_month(os.getenv("TARGET_MONTH", "").strip())
    print(f"--- Monthly index for {label} ({len(master)} messages in master) ---")

    labels, status = label_messages(master)
    for w in status["warnings"]:
        print(f"::warning::{w}")
    scored = score_messages(master, labels)
    row, month_df = build_monthly(scored, y, m, label)
    if row is None:
        print(f"No messages found for {label}; nothing to build.")
    else:
        series = save_monthly(row)
        export_monthly(series, month_df, label)
        print(series.tail(1).to_string(index=False))

    if status["error"]:
        print(f"::error::Gemini: {status['error']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
