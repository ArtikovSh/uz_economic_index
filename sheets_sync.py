"""
Mirror the pipeline's results into a Google Sheet, so the data is always
up to date in one place that can be viewed and shared from any device.

The backend stays the single source of truth: everything is computed in Python
from data/*.csv and only WRITTEN to the sheet (no formulas). Tabs:
  * Kunlik indeks – the daily EAI/ESI series (rewritten each run, small)
  * Oylik indeks  – the monthly series (rewritten each run, tiny)
  * Xabarlar      – every labelled post with its topic/flags/scores; append-only
                    (a post is written once it has a label), newest first. Fully
                    rewritten only when LLM_LABEL_VERSION changes.
  * Info          – last update time, label version, coverage

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

from config import DAILY_CSV, MONTHLY_CSV, LLM_LABEL_VERSION, TZ_OFFSET_HOURS
from indicator import score_messages
from llm_classifier import label_messages, post_keys
from store import load_master

SA_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
SHEET_ID = os.getenv("GSHEET_ID", "").strip()
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]     # this sheet only

TAB_DAILY, TAB_MONTHLY, TAB_POSTS, TAB_INFO = "Kunlik indeks", "Oylik indeks", "Xabarlar", "Info"
POST_HEADER = ["sana (Toshkent)", "kanal", "havola", "mavzu", "iqtisodiy", "indeksda",
               "reklama", "dayjest", "xorijiy", "relevance", "sentiment", "views",
               "forwards", "matn", "model", "o'lchangan (UTC)", "post_id"]
ID_COL = len(POST_HEADER)                # post_id is the last column
CHUNK = 2000                             # rows per append request


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


def _col_letter(n):
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def post_rows(scored):
    """Sheet rows for labelled posts, newest first."""
    df = scored[scored["labeled"] == 1].copy()
    local = pd.to_datetime(df["date"], errors="coerce") + pd.Timedelta(hours=TZ_OFFSET_HOURS)
    df["_local"] = local.dt.strftime("%Y-%m-%d %H:%M")
    df["_link"] = ("https://t.me/" + df["channel"].astype(str).str.lstrip("@")
                   + "/" + df["message_id"].astype(str))
    df["_id"] = post_keys(df)
    df = df.sort_values("_local", ascending=False)
    cols = ["_local", "channel", "_link", "primary_topic", "is_economic", "in_index",
            "is_ad", "is_digest", "is_foreign", "relevance", "sentiment", "views",
            "forwards", "raw_text", "label_model", "scraped_at", "_id"]
    return [[_cell(v) for v in row] for row in df[cols].itertuples(index=False)]


def table_rows(df):
    return [list(df.columns)] + [[_cell(v) for v in row] for row in df.itertuples(index=False)]


# ------------------------------------------------------------------ sheet ops -
def _tab(sh, title, header=None, index=None):
    import gspread
    try:
        return sh.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=100, cols=max(len(header or []), 2), index=index)
        if header:
            ws.update([header], range_name="A1")
            ws.freeze(rows=1)
        return ws


def _rewrite(ws, rows):
    """Replace a whole tab with rows (header first)."""
    ws.clear()
    ws.resize(rows=max(len(rows), 2), cols=max(len(rows[0]), 2))
    ws.update(rows, range_name="A1")
    ws.freeze(rows=1)


def sync_posts(ws, rows, full):
    """Append posts not yet in the tab (or rewrite all). Returns rows written."""
    if full:
        ws.clear()
        ws.resize(rows=2, cols=len(POST_HEADER))
        ws.update([POST_HEADER], range_name="A1")
        ws.freeze(rows=1)
        new = rows
        existing = 0
    else:
        ids = ws.col_values(ID_COL)[1:]
        known = set(ids)
        existing = len(ids)
        new = [r for r in rows if r[-1] not in known]
    for i in range(0, len(new), CHUNK):
        ws.append_rows(new[i:i + CHUNK], value_input_option="RAW")
    total = existing + len(new)
    if new and total > 1:
        ws.sort((1, "des"), range=f"A2:{_col_letter(ID_COL)}{total + 1}")
    return len(new)


def main() -> int:
    if not SA_JSON or not SHEET_ID:
        print("GOOGLE_SERVICE_ACCOUNT_JSON / GSHEET_ID not set -> skipping Google Sheets sync.")
        return 0
    import gspread

    master = load_master()
    labels, status = label_messages(master, allow_calls=False)    # cache only
    scored = score_messages(master, labels)
    rows = post_rows(scored)

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

    tabs = {title: _tab(sh, title, header, index=i) for i, (title, header) in enumerate(
        [(TAB_DAILY, None), (TAB_MONTHLY, None), (TAB_POSTS, POST_HEADER), (TAB_INFO, None)])}
    info, posts = tabs[TAB_INFO], tabs[TAB_POSTS]
    stored_version = (info.acell("B2").value or "").strip()
    full = stored_version != LLM_LABEL_VERSION
    n = sync_posts(posts, rows, full)
    print(f"  {TAB_POSTS}: {'rewrote' if full else 'appended'} {n} posts")

    for title, path in ((TAB_DAILY, DAILY_CSV), (TAB_MONTHLY, MONTHLY_CSV)):
        if os.path.exists(path):
            _rewrite(tabs[title], table_rows(pd.read_csv(path)))
            print(f"  {title}: updated")

    daily = pd.read_csv(DAILY_CSV) if os.path.exists(DAILY_CSV) else pd.DataFrame()
    last_full = (str(daily.loc[daily["EAI"].notna(), "date_only"].max())
                 if len(daily) and "EAI" in daily else "")
    now = datetime.now(timezone(timedelta(hours=TZ_OFFSET_HOURS))).strftime("%Y-%m-%d %H:%M")
    _rewrite(info, [
        ["Ko'rsatkich", "Qiymat"],
        ["Label versiyasi", LLM_LABEL_VERSION],          # read back as B2 next run
        ["Oxirgi yangilanish (Toshkent)", now],
        ["Jami postlar", len(master)],
        ["Belgilangan postlar", len(rows)],
        ["Belgilash kutilmoqda", status["pending"]],
        ["Indeksi bor oxirgi kun", last_full],
        ["Manba", "https://github.com/ArtikovSh/uz_economic_index"],
    ])
    print("Google Sheets sync done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
