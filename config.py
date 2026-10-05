import os
import socks

# =============================================================================
# Telegram access — from env only (GitHub secrets TG_API_ID / TG_API_HASH /
# TG_SESSION_STRING; get the API pair at my.telegram.org). Validated where used,
# so scripts that never touch Telegram (DB and Sheets sync) run without them.
# =============================================================================
API_ID = os.getenv("TG_API_ID", "").strip()
API_HASH = os.getenv("TG_API_HASH", "").strip()

# Headless session for CI (an authorized Telethon StringSession). Empty locally,
# where the file-based 'session_lda_index.session' is used instead.
SESSION_STRING = os.getenv("TG_SESSION_STRING", "").strip()

# News channels to track. To add one, paste its EXACT @username from the Telegram
# app. Candidates to verify: Review.uz, Qalampir, Yuz.uz, Repost.uz, @cbu_uz,
# @stat_uz, @soliqqomitasi, Norma.uz.
CHANNELS = [
    "@gazetauz", "@kunuzofficial", "@daryo", "@spotuz", "@uzdaily",
]

# --- Scrape window ---------------------------------------------------------
# Each run collects ONE full Tashkent calendar day: SCRAPE_DAYS_BACK days before
# "today" in Tashkent. The workflow starts right after Tashkent midnight, so the
# last post of the target day has been public for >= 24h when its views/forwards
# are measured. Each post is measured once (the first measurement is kept).
SCRAPE_DAYS_BACK = int(os.getenv("SCRAPE_DAYS_BACK", "2"))
TZ_OFFSET_HOURS = int(os.getenv("TZ_OFFSET_HOURS", "5"))          # Tashkent = UTC+5

# =============================================================================
# Paths / storage (see store.py). Both tables are append-only: a row is added once
# it is final and is never changed afterwards.
# =============================================================================
OUTPUT_DIR = "output"          # rendered Excel report
DATA_DIR = "data"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

MASTER_CSV = os.path.join(DATA_DIR, "messages.csv")    # "Xabarlar": every final post with its labels
INDICES_CSV = os.path.join(DATA_DIR, "indices.csv")    # "Indekslar": day/week/month/quarter/year rows
PENDING_CSV = os.path.join(DATA_DIR, "pending.csv")    # posts whose day is not final yet

# =============================================================================
# Gemini classifier. Every post is labelled once. There is no rule-based fallback:
# a post Gemini could not label waits in pending.csv and is retried on the next
# run, so the index never mixes labelling methods.
# =============================================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
# Empty = automatic and "sticky": keep the model that produced the cached labels,
# else the newest stable Flash model available to the key.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "").strip()

LLM_BATCH_SIZE = int(os.getenv("LLM_BATCH_SIZE", "40"))      # posts per request (daily quota is per request)
LLM_MAX_CHARS = int(os.getenv("LLM_MAX_CHARS", "1000"))      # truncate each post
LLM_RPM = float(os.getenv("LLM_RPM", "5"))                   # free-tier requests/minute
LLM_MAX_REQUESTS = int(os.getenv("LLM_MAX_REQUESTS", "60"))  # per run (daily quota)
LLM_LABEL_VERSION = "v3"     # bump to re-label everything (v3: Gemini + protocol/ad rules)

# =============================================================================
# Index parameters (see METHODOLOGY.md)
# =============================================================================
TONE_THRESHOLD = 0.15    # sentiment above +0.15 is positive, below -0.15 negative

# =============================================================================
# Proxy (local runs only — e.g. export_session.py). Telegram is DPI-reset on some
# UZ networks; GitHub Actions needs no proxy.
# =============================================================================
USE_PROXY = os.getenv("USE_PROXY", "0") == "1"
PROXY_HOST = os.getenv("PROXY_HOST", "127.0.0.1")
PROXY_PORT = int(os.getenv("PROXY_PORT", "10808"))
PROXY = (socks.SOCKS5, PROXY_HOST, PROXY_PORT) if USE_PROXY else None
