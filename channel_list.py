"""Read active channels from the admin database, with a local fallback."""
import os

import psycopg

import config


def _normalize(handles):
    handles = ["".join(handle.split()).lstrip("@").lower() for handle in handles]
    return list(dict.fromkeys(f"@{handle}" for handle in handles if handle))


def active_channels(db_url=None, fallback=None):
    """Use SUPABASE_DB_URL (or DATABASE_URL) when no URL is passed explicitly."""
    if db_url is None:
        db_url = os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL") or ""
    if not db_url.strip():
        reason = "database URL is not configured"
    else:
        try:
            with psycopg.connect(db_url, prepare_threshold=None, connect_timeout=10) as conn:
                with conn.cursor() as cur:
                    cur.execute("select handle from channels where active order by added_at, handle")
                    channels = _normalize(row[0] for row in cur.fetchall())
            if channels:
                return channels
            reason = "no active channels"
        except psycopg.errors.UndefinedTable:
            reason = "channels table is missing"
        except psycopg.Error as exc:
            # Driver messages may contain credentials or the connection URL.
            reason = f"database read failed ({type(exc).__name__})"
    print(f"Channels: {reason}; using fallback.")
    return _normalize(config.CHANNELS if fallback is None else fallback)
