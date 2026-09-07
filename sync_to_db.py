"""
Push the pipeline's CSV outputs to the Supabase (Postgres) database, so the bot
and mini app can serve them. Run after the daily/monthly pipeline.

Connection string comes from env SUPABASE_DB_URL (or DATABASE_URL) — use the
Supabase "Connection pooler" URI (Transaction mode, port 6543). If neither is
set, this is a no-op, so local runs without a DB still work.
"""
import os
import sys

import pandas as pd

from config import MASTER_CSV, DAILY_CSV, MONTHLY_CSV, LLM_LABELS_CSV

DB_URL = os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL") or ""


def _connect():
    import psycopg
    # prepare_threshold=None -> no server-side prepared statements, so the
    # Supabase transaction pooler (pgbouncer) works fine.
    conn = psycopg.connect(DB_URL, autocommit=False, prepare_threshold=None)
    with conn.cursor() as cur:
        cur.execute("SET TIME ZONE 'UTC'")
    return conn


def _upsert(conn, sql, rows, label):
    if not rows:
        print(f"  {label}: nothing to sync")
        return
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    conn.commit()
    print(f"  {label}: synced {len(rows)} rows")


def sync_messages(conn):
    if not os.path.exists(MASTER_CSV):
        return
    df = pd.read_csv(MASTER_CSV)
    rows = [(r.channel, int(r.message_id), r.date, int(r.views or 0),
             int(r.forwards or 0), str(r.raw_text))
            for r in df.itertuples()]
    _upsert(conn, """
        insert into messages (channel, message_id, date_utc, views, forwards, raw_text)
        values (%s,%s,%s,%s,%s,%s)
        on conflict (channel, message_id) do update set
          date_utc=excluded.date_utc, views=excluded.views,
          forwards=excluded.forwards, raw_text=excluded.raw_text
    """, rows, "messages")


def sync_labels(conn):
    if not os.path.exists(LLM_LABELS_CSV):
        return
    df = pd.read_csv(LLM_LABELS_CSV)
    rows = []
    for r in df.itertuples():
        ch, _, mid = str(r.key).partition("|")
        rows.append((ch, int(mid), bool(r.is_economic), str(r.primary_topic),
                     float(r.relevance), float(r.sentiment), bool(r.is_ad),
                     bool(r.is_digest), bool(r.is_foreign),
                     getattr(r, "label_version", None)))
    _upsert(conn, """
        insert into labels (channel, message_id, is_economic, primary_topic, relevance,
                            sentiment, is_ad, is_digest, is_foreign, label_version)
        values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        on conflict (channel, message_id) do update set
          is_economic=excluded.is_economic, primary_topic=excluded.primary_topic,
          relevance=excluded.relevance, sentiment=excluded.sentiment,
          is_ad=excluded.is_ad, is_digest=excluded.is_digest,
          is_foreign=excluded.is_foreign, label_version=excluded.label_version
    """, rows, "labels")


def sync_daily(conn):
    if not os.path.exists(DAILY_CSV):
        return
    df = pd.read_csv(DAILY_CSV)
    df.columns = [c.lower() for c in df.columns]
    cols = ["date_only", "total_messages", "economic_messages", "counted_messages",
            "econ_share", "eai", "eai_z", "eai_100", "esi", "esi_z", "esi_100",
            "avg_engagement"]
    df = df.reindex(columns=cols)
    rows = [tuple(None if pd.isna(v) else v for v in row) for row in df.itertuples(index=False)]
    _upsert(conn, f"""
        insert into daily_index ({','.join(cols)})
        values ({','.join(['%s']*len(cols))})
        on conflict (date_only) do update set
          {','.join(f'{c}=excluded.{c}' for c in cols[1:])}
    """, rows, "daily_index")


def sync_monthly(conn):
    if not os.path.exists(MONTHLY_CSV):
        return
    df = pd.read_csv(MONTHLY_CSV)
    df.columns = [c.lower() for c in df.columns]
    cols = ["month", "days_covered", "total_messages", "economic_messages",
            "counted_messages", "econ_share", "eai", "eai_100", "esi", "esi_100",
            "avg_engagement", "top_topics"]
    df = df.reindex(columns=cols)
    rows = [tuple(None if pd.isna(v) else v for v in row) for row in df.itertuples(index=False)]
    _upsert(conn, f"""
        insert into monthly_index ({','.join(cols)})
        values ({','.join(['%s']*len(cols))})
        on conflict (month) do update set
          {','.join(f'{c}=excluded.{c}' for c in cols[1:])}
    """, rows, "monthly_index")


def main():
    if not DB_URL:
        print("SUPABASE_DB_URL not set -> skipping DB sync.")
        return
    print("--- Sync to Supabase ---")
    conn = _connect()
    try:
        sync_messages(conn)
        sync_labels(conn)
        sync_daily(conn)
        sync_monthly(conn)
    finally:
        conn.close()
    print("DB sync done.")


if __name__ == "__main__":
    main()
