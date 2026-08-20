import asyncio
import pandas as pd
from telethon import TelegramClient
from telethon.sessions import StringSession
from config import API_ID, API_HASH, CHANNELS, PROXY, SESSION_STRING

async def fetch_channel_messages(client, channel, limit=500):
    messages_data = []
    async for msg in client.iter_messages(channel, limit=limit):
        if msg.text:
            messages_data.append({
                'channel': channel,
                'message_id': msg.id,
                'date': msg.date.strftime('%Y-%m-%d %H:%M:%S'),
                'views': msg.views or 0,
                'forwards': msg.forwards or 0,
                'raw_text': msg.text
            })
    return messages_data

async def run_scraper(limit_per_channel=500):
    # Use an in-memory StringSession when provided (CI / headless), otherwise the
    # local file-based session 'session_lda_index.session'.
    session = StringSession(SESSION_STRING) if SESSION_STRING else 'session_lda_index'
    print(f"Session mode: {'StringSession (env)' if SESSION_STRING else 'local file session'}")
    print(f"Connection mode: {'SOCKS5 proxy ' + str(PROXY[1:]) if PROXY else 'DIRECT (no proxy)'}")
    async with TelegramClient(session, API_ID, API_HASH, proxy=PROXY) as client:
        all_messages = []
        for ch in CHANNELS:
            print(f"Scraping {ch}...")
            try:
                msgs = await fetch_channel_messages(client, ch, limit=limit_per_channel)
                print(f"  -> collected {len(msgs)} messages")
                all_messages.extend(msgs)
            except Exception as e:
                print(f"  !! skipped {ch}: {e}")

        if not all_messages:
            raise RuntimeError(
                "No messages collected. Check your internet/proxy, API credentials, "
                "or that the Telegram session is authorized."
            )
        return pd.DataFrame(all_messages)