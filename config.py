import os
import socks


# Telegram API Configuration
# Defaults keep the original values; override without editing the file by setting
# environment variables TG_API_ID / TG_API_HASH (get your own at https://my.telegram.org).
API_ID = int(os.getenv('TG_API_ID', '38779507'))            # Your Telegram API ID
API_HASH = os.getenv('TG_API_HASH', '5aecf3da3a4ffb546880457afe76e26d')     # Your Telegram API Hash

# Headless session (for CI / GitHub Actions): a Telethon StringSession that is
# already authorized, so no interactive phone-code login is needed on the runner.
# Leave empty for local runs (the file-based 'session_lda_index.session' is used).
# Generate it once with: python export_session.py  (then store as secret TG_SESSION_STRING)
SESSION_STRING = os.getenv('TG_SESSION_STRING', '').strip()

# Target Telegram Channels
CHANNELS = ['@gazetauz', '@kunuzofficial', '@daryo', '@spotuz']

# Directory Paths
OUTPUT_DIR = 'output'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# LDA Model Parameters
NUM_TOPICS = 5
PASSES = 15
TARGET_TOPICS = [0, 2]         # Indices corresponding to Macro/Economic Topics

# Custom Stopwords
STOPWORDS = set([
    "va", "ham", "uchun", "bilan", "da", "ga", "dan", "bu", "o", "shuningdek",
    "в", "и", "на", "с", "по", "для", "что", "это", "как", "из"
])

# --- Proxy configuration ---
# By default the scraper connects DIRECTLY (no proxy) — Telegram is reachable
# directly in Uzbekistan. If you need to route through a local SOCKS5 client
# (v2rayN / Nekoray / Shadowsocks etc.), enable it by setting USE_PROXY=1.
# Host/port default to the common local client 127.0.0.1:10808; override with
# PROXY_HOST / PROXY_PORT if your client listens elsewhere.
USE_PROXY = os.getenv('USE_PROXY', '0') == '1'
PROXY_HOST = os.getenv('PROXY_HOST', '127.0.0.1')
PROXY_PORT = int(os.getenv('PROXY_PORT', '10808'))

PROXY = (socks.SOCKS5, PROXY_HOST, PROXY_PORT) if USE_PROXY else None