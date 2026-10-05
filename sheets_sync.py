"""
Mirror the two tables into a Google Sheet, so they can be viewed and shared from
any device. Everything is computed by the pipeline; the sheet only receives values.

  * Indekslar – data/indices.csv, append-only
  * Xabarlar  – data/messages.csv, append-only
  * Info      – last update, rows, posts still waiting

Only rows not yet in the sheet are appended at the bottom, in the same order as the
CSV; nothing already in the sheet is rewritten. A tab whose header does not match
the current layout is rebuilt once.

Credentials (GitHub secrets): GOOGLE_SERVICE_ACCOUNT_JSON (the service account's
JSON key) and GSHEET_ID (from the sheet URL). The sheet must be shared with the
service account's e-mail as Editor. If either secret is missing this is a no-op.
"""
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd

from config import TZ_OFFSET_HOURS, LLM_LABEL_VERSION
from store import load_ledger, load_indices, load_pending, post_keys

SA_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
SHEET_ID = os.getenv("GSHEET_ID", "").strip()
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]     # this sheet only
LEGACY_TABS = ["Kunlik indeks", "Oylik indeks"]
CHUNK = 2000                                                   # rows per append request

INDEX_HEADER = ["davr turi", "davr", "boshlanish", "tugash", "kunlar", "kunlar (jami)",
                "jami xabarlar", "reklama emas", "iqtisodiy", "ijobiy", "neytral", "salbiy",
                "EAI, %", "ESI (balans)", "izoh"]
INDEX_FIELDS = ["period_type", "period", "start", "end", "days", "days_expected", "posts",
                "nonad", "econ", "pos", "neu", "neg", "EAI", "ESI", "note"]
POST_HEADER = ["sana (Toshkent)", "kanal", "havola", "mavzu", "iqtisodiy (LLM)", "reklama",
               "dayjest", "xorijiy", "indeksda", "ohang", "sentiment", "relevance",
               "ko'rishlar", "forwardlar", "matn", "model", "o'lchangan (UTC)", "post_id"]


def _cell(v):
    """A JSON-safe sheet value: blanks for missing, Python numbers, else text."""
    if v is None or v is pd.NA or v is pd.NaT:
        return ""
    if hasattr(v, "item"):               # numpy scalar
        v = v.item()
    if isinstance(v, float):
        return "" if math.isnan(v) else round(v, 4)
    if isinstance(v, (bool, int, str)):
        return v
    return str(v)


def index_rows(indices):
    """Sheet rows for the indices table; the key (type|period) is columns 1-2."""
    return [[_cell(v) for v in r] for r in indices[INDEX_FIELDS].itertuples(index=False)]


def post_rows(ledger):
    """Sheet rows for the posts table; the key is the last column."""
    df = ledger.copy()
    df["_link"] = ("https://t.me/" + df["channel"].astype(str).str.lstrip("@")
                   + "/" + df["message_id"].astype(str))
    df["_id"] = post_keys(df)
    cols = ["date_local", "channel", "_link", "primary_topic", "is_economic", "is_ad",
            "is_digest", "is_foreign", "econ", "tone", "sentiment", "relevance", "views",
            "forwards", "raw_text", "label_model", "scraped_at", "_id"]
    return [[_cell(v) for v in r] for r in df[cols].itertuples(index=False)]


# ------------------------------------------------------------------ sheet ops -
def _tab(sh, title, header, index):
    """The tab with this header; created, or rebuilt once if its header changed."""
    import gspread
    try:
        ws = sh.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=100, cols=len(header), index=index)
    first = ws.row_values(1)
    if first != header:
        ws.clear()
        ws.resize(rows=2, cols=len(header))
        ws.update([header], range_name="A1")
        ws.freeze(rows=1)
    return ws


def append_missing(ws, rows, key_cols):
    """Append the rows that come after the last row already in the tab.

    key_cols: 1-based sheet columns that together identify a row."""
    cols = [ws.col_values(c)[1:] for c in key_cols]
    present = ["|".join(map(str, k)) for k in zip(*cols)]
    start = 0
    if present:
        pos = {"|".join(str(r[c - 1]) for c in key_cols): i for i, r in enumerate(rows)}
        last = next((pos[k] for k in reversed(present) if k in pos), None)
        start = 0 if last is None else last + 1
    new = rows[start:]
    for i in range(0, len(new), CHUNK):
        ws.append_rows(new[i:i + CHUNK], value_input_option="RAW")
    return len(new)


def main() -> int:
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
    except (gspread.SpreadsheetNotFound, gspread.exceptions.APIError) as e:
        print(f"::error::Cannot open the sheet {SHEET_ID}: share it as Editor with "
              f"{creds.get('client_email')} and check GSHEET_ID ({e})")
        return 1
    print(f"--- Sync to Google Sheet '{sh.title}' ---")

    ledger, indices, pending = load_ledger(), load_indices(), load_pending()
    idx_ws = _tab(sh, "Indekslar", INDEX_HEADER, 0)
    n = append_missing(idx_ws, index_rows(indices), [1, 2])      # key: type + period
    print(f"  Indekslar: +{n} rows")
    post_ws = _tab(sh, "Xabarlar", POST_HEADER, 1)
    n = append_missing(post_ws, post_rows(ledger), [len(POST_HEADER)])   # key: post_id
    print(f"  Xabarlar: +{n} rows")

    for title in LEGACY_TABS:                       # tabs of the old layout
        try:
            sh.del_worksheet(sh.worksheet(title))
            print(f"  removed old tab '{title}'")
        except gspread.WorksheetNotFound:
            pass

    info = _tab(sh, "Info", ["Ko'rsatkich", "Qiymat"], 2)
    now = datetime.now(timezone(timedelta(hours=TZ_OFFSET_HOURS))).strftime("%Y-%m-%d %H:%M")
    last_day = indices.loc[indices["period_type"] == "kun", "period"]
    info.resize(rows=20, cols=2)
    info.batch_clear(["A2:B20"])
    info.update([
        ["Oxirgi yangilanish (Toshkent)", now],
        ["Indekslar qatorlari", len(indices)],
        ["Xabarlar qatorlari", len(ledger)],
        ["Oxirgi yakunlangan kun", last_day.iloc[-1] if len(last_day) else ""],
        ["Kun yakunlanishini kutayotgan xabarlar", len(pending)],
        ["Label versiyasi", LLM_LABEL_VERSION],
        ["Manba", "https://github.com/ArtikovSh/uz_economic_index"],
    ], range_name="A2")
    print("Google Sheets sync done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
