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
LLM_LABELS_CSV = os.path.join(DATA_DIR, "llm_labels.csv")  # cached LLM labels

# =============================================================================
# LLM classifier (optional, high quality). Each NEW message is classified by an
# LLM (cached in llm_labels.csv, so only unseen posts cost a call); any error
# falls back to the rule-based classifier per-batch, so the pipeline never breaks.
#
# Provider (LLM_PROVIDER):
#   "github" — GitHub Models (FREE, no separate key: uses GITHUB_TOKEN in Actions;
#              GPT models like openai/gpt-4o-mini). Needs `permissions: models: read`.
#   "gemini" — Google Gemini API (needs GEMINI_API_KEY; low free quota).
#   "rules"  — no LLM, deterministic classifier only.
# Auto-default: github if a token is present, else gemini if a key is present, else rules.
# =============================================================================
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_MODEL = (os.getenv("GITHUB_MODEL") or "openai/gpt-4o-mini")   # or openai/gpt-4o
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = (os.getenv("GEMINI_MODEL") or "gemini-2.5-flash")     # or gemini-2.5-pro

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").strip().lower()
if not LLM_PROVIDER:
    LLM_PROVIDER = "github" if GITHUB_TOKEN else ("gemini" if GEMINI_API_KEY else "rules")
USE_LLM = LLM_PROVIDER in ("github", "gemini")

LLM_BATCH_SIZE = int(os.getenv("LLM_BATCH_SIZE", "20"))     # messages per API call
LLM_MAX_CHARS = int(os.getenv("LLM_MAX_CHARS", "700"))      # truncate each post
LLM_MAX_PER_RUN = int(os.getenv("LLM_MAX_PER_RUN", "600"))  # cap new posts/run (rate limits)
LLM_LABEL_VERSION = "v1"                                    # bump to invalidate cache

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
