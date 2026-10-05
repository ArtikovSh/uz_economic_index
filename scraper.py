"""
Telegram collection: one full Tashkent day per run.

The session is checked explicitly before scraping, so an expired/revoked
TG_SESSION_STRING fails with a clear message instead of Telethon prompting for a
phone number (which crashes headless CI with EOFError).
"""
import os
from datetime import datetime, timedelta, timezone

import pandas as pd
from telethon import TelegramClient
from telethon.sessions import StringSession

from config import (API_ID, API_HASH, PROXY, SESSION_STRING,
                    SCRAPE_DAYS_BACK, TZ_OFFSET_HOURS)
from store import RAW_COLS

TASHKENT = timezone(timedelta(hours=TZ_OFFSET_HOURS))
LOCAL_SESSION = "session_lda_index"


class SessionError(RuntimeError):
    """The Telegram session cannot be used — a new TG_SESSION_STRING is needed."""


def target_day_range(now=None):
    """Return (start_utc, end_utc, target_date) for the Tashkent day to collect."""
    now = (now or datetime.now(TASHKENT)).astimezone(TASHKENT)
    target = (now - timedelta(days=SCRAPE_DAYS_BACK)).date()
    start_local = datetime(target.year, target.month, target.day, tzinfo=TASHKENT)
    end_local = start_local + timedelta(days=1)          # exclusive next-midnight
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc), target


def collected_channels(master, start_utc, end_utc):
    """Channels that already have posts for the target day in the master store."""
    if master is None or master.empty:
        return set()
    dt = pd.to_datetime(master["date"], errors="coerce")       # stored as naive UTC
    lo, hi = start_utc.replace(tzinfo=None), end_utc.replace(tzinfo=None)
    return set(master.loc[(dt >= lo) & (dt < hi), "channel"].astype(str))


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


async def fetch_channel_day(client, channel, start_utc, end_utc):
    """All text messages posted within [start_utc, end_utc) for one channel."""
    out = []
    scraped_at = _utc_now()
    # iter_messages(offset_date=end_utc) walks newest->oldest from just before end_utc;
    # the day boundary (break below) is the only stop.
    async for msg in client.iter_messages(channel, offset_date=end_utc):
        if msg.date < start_utc:
            break
        if msg.date >= end_utc or not msg.text:
            continue
        out.append({
            "channel": channel,
            "message_id": msg.id,
            "date": msg.date.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),  # UTC
            "views": msg.views or 0,
            "forwards": msg.forwards or 0,
            "raw_text": msg.text,
            "scraped_at": scraped_at,
        })
    return out


async def open_client():
    """A connected, authorized client — or SessionError with a clear reason."""
    if not API_ID or not API_HASH:
        raise SessionError("TG_API_ID / TG_API_HASH are not set.")
    if not API_ID.isdigit():
        raise SessionError("TG_API_ID must be a number.")
    if not SESSION_STRING and not os.path.exists(LOCAL_SESSION + ".session"):
        raise SessionError("TG_SESSION_STRING is not set and there is no local session file.")

    session = StringSession(SESSION_STRING) if SESSION_STRING else LOCAL_SESSION
    print(f"Session: {'StringSession (env)' if SESSION_STRING else 'local file'} | "
          f"connection: {'SOCKS5 proxy ' + str(PROXY[1:]) if PROXY else 'direct'}")
    client = TelegramClient(session, int(API_ID), API_HASH, proxy=PROXY)
    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        raise SessionError(
            "Telegram session is not authorized (expired or revoked). "
            "Create a new TG_SESSION_STRING with export_session.py and update the secret.")
    return client


async def run_scraper(channels, start_utc, end_utc):
    """Collect `channels` for the window. Returns (DataFrame, {channel: error})."""
    client = await open_client()
    try:
        rows, failures = [], {}
        for ch in channels:
            try:
                msgs = await fetch_channel_day(client, ch, start_utc, end_utc)
                print(f"  {ch}: collected {len(msgs)} messages")
                rows.extend(msgs)
            except Exception as e:                       # one bad handle never stops the rest
                failures[ch] = f"{type(e).__name__}: {e}"
                print(f"  {ch}: FAILED — {failures[ch]}")
        return pd.DataFrame(rows, columns=RAW_COLS), failures
    finally:
        await client.disconnect()
