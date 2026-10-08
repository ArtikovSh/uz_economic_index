"""
Push the pipeline's tables to the Supabase (Postgres) database, so the bot and the
Mini App can serve them. Run after the daily pipeline.

  * messages / labels – posts of the posts table not yet in the DB (or labelled
                        differently there); labels carry the FINAL flags (ad marker incl.)
  * indices           – the indices table (created here if missing)

`--indices` (history.py adds months): the indices table is replaced, since every period may
have changed, and the bot's cached summary cards are dropped; posts are upserted as usual.
`--full` (rebuild.py, or history.py --fresh): posts are replaced too, so the database holds
exactly the posts table — nothing from an earlier archive stays.

Connection string comes from env SUPABASE_DB_URL (or DATABASE_URL) — use the
Supabase "Connection pooler" URI (Transaction mode, port 6543). If neither is
set, this is a no-op, so local runs without a DB still work.
"""
import os
import sys

import pandas as pd

from store import load_ledger, load_indices

DB_URL = os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL") or ""

INDICES_DDL = """
create table if not exists indices (
    period_type    text    not null,          -- kun | hafta | oy | chorak | yil
    period         text    not null,          -- 2026-10-04 | 2026-W40 | 2026-10 | 2026-Q4 | 2026
    start_date     date    not null,
    end_date       date    not null,
    days           integer,
    days_expected  integer,
    posts          integer,
    nonad          integer,
    econ           integer,
    pos            integer,
    neu            integer,
    neg            integer,
    eai            real,                      -- % of non-ad posts that are economic
    esi            real,                      -- 100 * (pos - neg) / econ
    note           text,
    primary key (period_type, period)
);
alter table indices enable row level security;
"""
# labels v6 carry every topic of a post; the view the app reads exposes them
TOPICS_DDL = """
do $$ begin
  if to_regclass('labels') is not null and to_regclass('messages') is not null then
    alter table labels add column if not exists topics text[];
    alter table labels add column if not exists headline text;
    create or replace view posts as
      select m.*, l.is_economic, l.primary_topic, l.relevance, l.sentiment,
             l.is_ad, l.is_digest, l.is_foreign, l.label_version, l.topics, l.headline
      from messages m left join labels l
        on m.channel = l.channel and m.message_id = l.message_id;
  end if;
end $$"""
# tables of the pre-ledger layout, no longer read or written by anything
LEGACY_DDL = "drop table if exists subscriptions, app_users, daily_index, monthly_index cascade"


def _connect():
    import psycopg
    # prepare_threshold=None -> no server-side prepared statements, so the
    # Supabase transaction pooler (pgbouncer) works fine.
    conn = psycopg.connect(DB_URL, autocommit=False, prepare_threshold=None)
    with conn.cursor() as cur:
        cur.execute("SET TIME ZONE 'UTC'")
    return conn


def _py(v):
    """Plain Python value for psycopg (None for missing, no numpy scalars)."""
    if v is None or v is pd.NA or (isinstance(v, float) and pd.isna(v)):
        return None
    return v.item() if hasattr(v, "item") else v


def _topic_list(r):
    raw = _py(getattr(r, "topics", None))
    return [t for t in str(raw).split(",") if t] if raw else [_py(r.primary_topic)]


def sync_posts(conn, ledger):
    if ledger.empty:
        print("  messages/labels: nothing to sync")
        return
    with conn.cursor() as cur:
        cur.execute("select channel, message_id, label_version from labels")
        db = {(c, int(m)): v for c, m, v in cur.fetchall()}
    keys = list(zip(ledger["channel"].astype(str), ledger["message_id"].astype(int)))
    todo = ledger[[db.get(k) != v for k, v in zip(keys, ledger["label_version"].astype(str))]]
    if todo.empty:
        print("  messages/labels: up to date")
        return
    msg = [(_py(r.channel), int(r.message_id), _py(r.date), int(r.views), int(r.forwards),
            _py(r.raw_text)) for r in todo.itertuples()]
    lab = [(_py(r.channel), int(r.message_id), bool(r.is_economic), _py(r.primary_topic),
            _py(r.sentiment), bool(r.is_ad), bool(r.is_digest),
            bool(r.is_foreign), _py(r.label_version), _topic_list(r), _py(getattr(r, "headline", None)))
           for r in todo.itertuples()]
    with conn.cursor() as cur:
        cur.executemany("""
            insert into messages (channel, message_id, date_utc, views, forwards, raw_text)
            values (%s,%s,%s,%s,%s,%s)
            on conflict (channel, message_id) do update set
              date_utc=excluded.date_utc, views=excluded.views,
              forwards=excluded.forwards, raw_text=excluded.raw_text""", msg)
        cur.executemany("""
            insert into labels (channel, message_id, is_economic, primary_topic,
                                sentiment, is_ad, is_digest, is_foreign, label_version, topics, headline)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            on conflict (channel, message_id) do update set
              is_economic=excluded.is_economic, primary_topic=excluded.primary_topic,
              sentiment=excluded.sentiment,
              is_ad=excluded.is_ad, is_digest=excluded.is_digest,
              is_foreign=excluded.is_foreign, label_version=excluded.label_version,
              topics=excluded.topics, headline=excluded.headline""", lab)
    conn.commit()
    print(f"  messages/labels: synced {len(todo)} posts")


def sync_indices(conn, indices, replace=False):
    with conn.cursor() as cur:
        cur.execute(INDICES_DDL)
        if replace:
            cur.execute("delete from indices")
            cur.execute("""do $$ begin
                             if to_regclass('bot_cards') is not null then delete from bot_cards; end if;
                           end $$""")
            print("  indices: replaced; cached bot cards dropped")
    conn.commit()
    if indices.empty:
        print("  indices: nothing to sync")
        return
    rows = [(r.period_type, str(r.period), r.start, r.end, _py(r.days), _py(r.days_expected),
             _py(r.posts), _py(r.nonad), _py(r.econ), _py(r.pos), _py(r.neu), _py(r.neg),
             _py(r.EAI), _py(r.ESI), _py(r.note)) for r in indices.itertuples()]
    with conn.cursor() as cur:
        cur.executemany("""
            insert into indices (period_type, period, start_date, end_date, days, days_expected,
                                 posts, nonad, econ, pos, neu, neg, eai, esi, note)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            on conflict (period_type, period) do nothing""", rows)
    conn.commit()
    print(f"  indices: {len(rows)} rows checked")


def main(full=False, indices=False) -> int:
    if not DB_URL:
        print("SUPABASE_DB_URL not set -> skipping DB sync.")
        return 0
    print("--- Sync to Supabase" + (" (full)" if full else " (indices replaced)" if indices else "") + " ---")
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(LEGACY_DDL)
            cur.execute(TOPICS_DDL)
            if full:
                cur.execute("""do $$ begin
                                 if to_regclass('labels') is not null then delete from labels; end if;
                                 if to_regclass('messages') is not null then delete from messages; end if;
                               end $$""")
                print("  messages/labels: cleared (full)")
        conn.commit()
        sync_posts(conn, load_ledger())
        sync_indices(conn, load_indices(), full or indices)
    finally:
        conn.close()
    print("DB sync done.")
    return 0


if __name__ == "__main__":
    sys.exit(main(full="--full" in sys.argv[1:], indices="--indices" in sys.argv[1:]))
