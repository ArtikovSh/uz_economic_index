import asyncio
from datetime import datetime, timedelta, timezone

import pandas as pd
from telethon import TelegramClient
from telethon.sessions import StringSession

from config import (API_ID, API_HASH, CHANNELS, PROXY, SESSION_STRING,
                    SCRAPE_DAYS_BACK, TZ_OFFSET_HOURS, SCRAPE_HARD_LIMIT, TARGET_DATE)

RAW_COLS = ["channel", "message_id", "date", "views", "forwards", "raw_text"]
TASHKENT = timezone(timedelta(hours=TZ_OFFSET_HOURS))


def target_day_range():
    """Return (start_utc, end_utc, target_date) for the Tashkent day to scrape."""
    if TARGET_DATE:
        target = datetime.strptime(TARGET_DATE, "%Y-%m-%d").date()
    else:
        target = (datetime.now(TASHKENT) - timedelta(days=SCRAPE_DAYS_BACK)).date()
    start_local = datetime(target.year, target.month, target.day, 0, 0, 0, tzinfo=TASHKENT)
    end_local = start_local + timedelta(days=1)          # exclusive next-midnight
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc), target


async def fetch_channel_day(client, channel, start_utc, end_utc):
    """All text messages posted within [start_utc, end_utc) for one channel."""
    out = []
    # iter_messages(offset_date=end_utc) walks newest->oldest from just before end_utc.
    async for msg in client.iter_messages(channel, offset_date=end_utc, limit=SCRAPE_HARD_LIMIT):
        if msg.date < start_utc:
            break                                        # gone past the target day
        if msg.date >= end_utc or not msg.text:
            continue
        out.append({
            "channel": channel,
            "message_id": msg.id,
            "date": msg.date.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),  # UTC
            "views": msg.views or 0,
            "forwards": msg.forwards or 0,
            "raw_text": msg.text,
        })
    return out


async def run_scraper(limit_per_channel=None):   # signature kept for main.py compat
    session = StringSession(SESSION_STRING) if SESSION_STRING else "session_lda_index"
    start_utc, end_utc, target = target_day_range()
    print(f"Session mode: {'StringSession (env)' if SESSION_STRING else 'local file session'}")
    print(f"Connection mode: {'SOCKS5 proxy ' + str(PROXY[1:]) if PROXY else 'DIRECT (no proxy)'}")
    print(f"Target day (Tashkent): {target}  |  UTC window "
          f"[{start_utc:%Y-%m-%d %H:%M} .. {end_utc:%Y-%m-%d %H:%M})")

    async with TelegramClient(session, API_ID, API_HASH, proxy=PROXY) as client:
        all_messages = []
        for ch in CHANNELS:
            print(f"Scraping {ch} for {target}...")
            try:
                msgs = await fetch_channel_day(client, ch, start_utc, end_utc)
                print(f"  -> collected {len(msgs)} messages")
                all_messages.extend(msgs)
            except Exception as e:
                print(f"  !! skipped {ch}: {e}")

        if not all_messages:
            # Not fatal: the day may be genuinely empty, or every handle failed.
            # main/store handle an empty frame (index recomputes over the master).
            print(f"WARNING: no messages collected for {target}.")
        return pd.DataFrame(all_messages, columns=RAW_COLS)
