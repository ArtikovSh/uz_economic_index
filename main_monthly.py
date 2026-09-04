"""
Build the monthly economic index from the already-collected daily data.
Run on the 3rd of each month (for the previous month). No scraping.
"""
import os

import pandas as pd

from config import MASTER_CSV
from indicator import score_messages
from monthly import target_month, build_monthly, save_monthly
from excel_exporter import export_monthly
from main import _llm_status


def main():
    print(f">>> {_llm_status()}")
    if not os.path.exists(MASTER_CSV):
        print("No master data yet — run the daily pipeline first.")
        return

    master = pd.read_csv(MASTER_CSV)
    y, m, label = target_month(os.getenv("TARGET_MONTH", "").strip())
    print(f"--- Monthly index for {label} ({len(master)} messages in master) ---")

    scored = score_messages(master)          # re-uses the cached LLM labels
    row, month_df = build_monthly(scored, y, m, label)
    if row is None:
        print(f"No messages found for {label}; nothing to build.")
        return

    series = save_monthly(row)
    export_monthly(series, month_df, label)
    print("Monthly row:")
    print(pd.DataFrame([row]).to_string(index=False))


if __name__ == "__main__":
    main()
