"""Mirror readable report tables to Google Sheets; --full rebuilds every managed tab.

Normal runs append missing keys. Changed headers also trigger a rebuild. Credentials
are GOOGLE_SERVICE_ACCOUNT_JSON and GSHEET_ID; missing credentials make this a no-op.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd

from config import TZ_OFFSET_HOURS, LLM_LABEL_VERSION
from report_tables import build_tables
from store import load_ledger, load_indices, load_pending

SA_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
SHEET_ID = os.getenv("GSHEET_ID", "").strip()
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
LEGACY_TABS = ["Indekslar", "Kunlik indeks", "Oylik indeks"]
CHUNK = 2000
KEYS = {"Kunlik": ["Sana"], "Haftalik": ["Davr"], "Oylik": ["Davr"],
        "Choraklik": ["Davr"], "Yillik": ["Davr"], "Mavzular": ["Sana", "Mavzu"],
        "Xabarlar": ["Havola"]}


def _rows(frame):
    return [["" if pd.isna(value) else value for value in row]
            for row in frame.itertuples(index=False, name=None)]


def _missing(ws, rows, key_cols):
    from gspread.utils import rowcol_to_a1

    # One request for all key columns; tuple keys cannot collide on a delimiter.
    first, last = min(key_cols), max(key_cols)
    key_range = f"{rowcol_to_a1(2, first)}:{rowcol_to_a1(1, last)[:-1]}"
    present = {tuple(str(row[c - first]) if c - first < len(row) else "" for c in key_cols)
               for row in ws.get(key_range)}
    new = []
    for row in rows:
        key = tuple(str(row[c - 1]) for c in key_cols)
        if key not in present:
            new.append(row)
            present.add(key)
    return new


def _format_requests(ws, header, row_count, index, old_rules):
    sheet_id = ws.id
    requests = [{"updateSheetProperties": {
        "properties": {"sheetId": sheet_id, "index": index, "gridProperties": {
            "rowCount": row_count, "columnCount": len(header), "frozenRowCount": 1}},
        "fields": "index,gridProperties.rowCount,gridProperties.columnCount,gridProperties.frozenRowCount"}},
        {"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                        "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                        "fields": "userEnteredFormat.textFormat.bold"}},
        {"setBasicFilter": {"filter": {"range": {"sheetId": sheet_id, "startRowIndex": 0,
                                                "endRowIndex": row_count, "endColumnIndex": len(header)}}}}]
    # Replace our rules instead of accumulating duplicates on every daily run.
    requests.extend({"deleteConditionalFormatRule": {"sheetId": sheet_id, "index": i}}
                    for i in reversed(range(old_rules)))
    for i, column in enumerate(header):
        cell_range = {"sheetId": sheet_id, "startRowIndex": 1, "startColumnIndex": i, "endColumnIndex": i + 1}
        if "EAI" in column or "ESI" in column:
            requests.append({"repeatCell": {"range": cell_range, "cell": {"userEnteredFormat": {
                "numberFormat": {"type": "NUMBER", "pattern": "0.0"}}},
                "fields": "userEnteredFormat.numberFormat"}})
        if "ESI" in column:
            for condition, rgb in (("NUMBER_GREATER", (14, 116, 144)), ("NUMBER_LESS", (194, 65, 12))):
                color = dict(zip(("red", "green", "blue"), (c / 255 for c in rgb)))
                requests.append({"addConditionalFormatRule": {"index": 0, "rule": {
                    "ranges": [cell_range], "booleanRule": {
                        "condition": {"type": condition, "values": [{"userEnteredValue": "0"}]},
                        "format": {"textFormat": {"foregroundColor": color}}}}}})
    return requests


def sync_tables(sh, tables, full=False):
    """Read keys once per tab, batch formatting, then write at most CHUNK rows at a time."""
    existing = {ws.title: ws for ws in sh.worksheets()}
    metadata = sh.fetch_sheet_metadata(params={"fields": "sheets(properties(sheetId),conditionalFormats)"})
    rule_counts = {sheet["properties"]["sheetId"]: len(sheet.get("conditionalFormats", []))
                   for sheet in metadata["sheets"]}
    requests, plans = [], []
    for index, (title, frame) in enumerate(tables.items()):
        header, rows = list(frame.columns), _rows(frame)
        ws = existing.get(title)
        created = ws is None
        if created:
            ws = sh.add_worksheet(title=title, rows=max(2, len(rows) + 1), cols=len(header))
        rebuild = created or full or title == "Info" or ws.row_values(1) != header
        if rebuild:
            new = rows
            row_count = max(2, len(rows) + 1)
        else:
            new = _missing(ws, rows, [header.index(key) + 1 for key in KEYS[title]])
            row_count = max(ws.row_count, len(rows) + 1) + len(new)
        requests.extend(_format_requests(ws, header, row_count, index, rule_counts.get(ws.id, 0)))
        plans.append((ws, header, new, rebuild, created))
    # New tabs exist before deletion, so migration also works when only legacy tabs exist.
    requests.extend({"deleteSheet": {"sheetId": existing[title].id}}
                    for title in LEGACY_TABS if title in existing)
    sh.batch_update({"requests": requests})
    for ws, header, new, rebuild, created in plans:
        if rebuild:
            if not created:
                ws.clear()
            ws.update([header], range_name="A1", value_input_option="RAW")
        for i in range(0, len(new), CHUNK):
            ws.append_rows(new[i:i + CHUNK], value_input_option="RAW")
        print(f"  {ws.title}: +{len(new)} rows" + (" (rebuilt)" if rebuild else ""))


def main(full=False) -> int:
    if not SA_JSON or not SHEET_ID:
        print("GOOGLE_SERVICE_ACCOUNT_JSON / GSHEET_ID not set -> skipping Google Sheets sync.")
        return 0
    import gspread

    try:
        creds = json.loads(SA_JSON)
    except ValueError:
        print("::error::GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON — paste the whole key file.")
        return 1
    gc = gspread.service_account_from_dict(creds, scopes=SCOPES)
    try:
        sh = gc.open_by_key(SHEET_ID)
    except (gspread.SpreadsheetNotFound, gspread.exceptions.APIError):
        print("::error::Cannot open the sheet: check GSHEET_ID and the service account's Editor access.")
        return 1
    print(f"--- Sync to Google Sheet '{sh.title}' ---")
    ledger, indices, pending = load_ledger(), load_indices(), load_pending()
    tables = build_tables(indices, ledger)
    now = datetime.now(timezone(timedelta(hours=TZ_OFFSET_HOURS))).strftime("%Y-%m-%d %H:%M")
    last_day = indices.loc[indices["period_type"] == "kun", "period"]
    tables["Info"] = pd.DataFrame([
        ["Oxirgi yangilanish (Toshkent)", now],
        ["Indekslar qatorlari", len(indices)],
        ["Xabarlar qatorlari", len(ledger)],
        ["Oxirgi yakunlangan kun", last_day.max() if len(last_day) else ""],
        ["Kun yakunlanishini kutayotgan xabarlar", len(pending)],
        ["Label versiyasi", LLM_LABEL_VERSION],
        ["Manba", "https://github.com/ArtikovSh/uz_economic_index"],
    ], columns=["Ko'rsatkich", "Qiymat"])
    sync_tables(sh, tables, full=full)
    print("Google Sheets sync done.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="Clear and rebuild every report tab")
    sys.exit(main(full=parser.parse_args().full))
