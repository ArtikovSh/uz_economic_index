import os
import socks

# =============================================================================
# Telegram access
# =============================================================================
# Override without editing the file via env vars (get your own at my.telegram.org).
API_ID = int(os.getenv("TG_API_ID", "38779507"))
API_HASH = os.getenv("TG_API_HASH", "5aecf3da3a4ffb546880457afe76e26d")

# Headless session for CI (an authorized Telethon StringSession). Empty locally,
# where the file-based 'session_lda_index.session' is used instead.
SESSION_STRING = os.getenv("TG_SESSION_STRING", "").strip()

# News channels to track. The scraper logs "collected N" / "skipped" per channel,
# so a wrong/renamed handle is skipped gracefully (never fatal) — check the run log
# and prune/adjust. (t.me could not be auto-verified from this machine: the corporate
# proxy blocks the page body.)
CHANNELS = [
    # original general + economy news
    "@gazetauz", "@kunuzofficial", "@daryo", "@spotuz",
    # added business / economy-focused media
    "@Review_uz", "@uzdaily", "@qalampir_uz", "@yuz_uz", "@repost_uz",
]
# Candidate official / economy channels — VERIFY the exact handle on Telegram, then
# move into CHANNELS above (kept out until confirmed to avoid scraping a wrong channel):
#   "@cbu_uz"          # Markaziy bank (Central Bank)
#   "@soliqqomitasi"   # Soliq qo'mitasi (Tax Committee)
#   "@stat_uz"         # Statistika agentligi
#   "@norma_uz"        # Norma.uz (soliq / buxgalteriya)

MESSAGES_PER_CHANNEL = int(os.getenv("MSG_PER_CHANNEL", "400"))

# =============================================================================
# Paths / storage
# =============================================================================
OUTPUT_DIR = "output"          # rendered Excel reports (ephemeral)
DATA_DIR = "data"              # persistent master store + daily time series
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

MASTER_CSV = os.path.join(DATA_DIR, "messages.csv")        # raw, deduped, growing
DAILY_CSV = os.path.join(DATA_DIR, "daily_index.csv")      # the index time series

# =============================================================================
# Index parameters (see METHODOLOGY.md)
# =============================================================================
FORWARD_WEIGHT = 2.0     # a forward counts as N views inside the engagement log
RELEVANCE_TAU = 2.0      # saturation constant for relevance = 1 - exp(-hits/TAU)
ECON_MIN_HITS = 2        # a post is "economic" only with >= this many econ hits
                         # (raised from 1: a single stem hit was a coin-flip; see
                         #  METHODOLOGY §7 / the classification-quality audit)

# =============================================================================
# Secondary LDA topic model (exploratory / diagnostic only, NOT the index)
# =============================================================================
NUM_TOPICS = 6
PASSES = 15
LDA_NO_BELOW = 5         # drop tokens appearing in < N docs
LDA_NO_ABOVE = 0.4       # drop tokens appearing in > 40% of docs

# =============================================================================
# Proxy (local runs only). Default: DIRECT. Telegram is DPI-reset on some UZ
# networks, so local runs usually need USE_PROXY=1 with a SOCKS5 client;
# GitHub Actions runs outside that network and needs no proxy.
# =============================================================================
USE_PROXY = os.getenv("USE_PROXY", "0") == "1"
PROXY_HOST = os.getenv("PROXY_HOST", "127.0.0.1")
PROXY_PORT = int(os.getenv("PROXY_PORT", "10808"))
PROXY = (socks.SOCKS5, PROXY_HOST, PROXY_PORT) if USE_PROXY else None
