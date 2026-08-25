"""
Text normalization and transliteration helpers.

Two independent jobs:
  * normalize_text()  -> a cleaned, lower-cased string used for LEXICON matching
    (economic relevance + sentiment). Keeps both Latin and Cyrillic characters,
    because the corpus mixes Uzbek-Latin, Uzbek-Cyrillic and Russian and the
    lexicons carry terms in every script.
  * to_latin_tokens() -> transliterated, boilerplate-free tokens used only by the
    secondary LDA topic model, so the same word written in different scripts
    collapses to one token.
"""
import re

# --- apostrophe / quote variants used for Uzbek o' g' -> unify to a plain "'"
_APOSTROPHES = ["‘", "’", "ʻ", "ʼ", "`", "´"]

# Boilerplate the channels append to almost every post (social footers, CTAs,
# "read more", ad markers). These dominate word frequencies and must go before
# any modelling. Matched case-insensitively as substrings/lines.
BOILERPLATE_PATTERNS = [
    r"https?://\S+", r"www\.\S+", r"t\.me/\S+", r"@[\w_]+",
    r"telegram", r"instagram", r"youtube", r"facebook", r"tiktok",
    r"obuna\s+bo\W?l\w*", r"batafsil", r"havola", r"\bling\b",
    r"подписаться", r"подпис\w+", r"реклама", r"\breklama\b",
    r"o\W?qing", r"читать\s+далее", r"подробнее",
]
_BOILERPLATE_RE = re.compile("|".join(BOILERPLATE_PATTERNS), re.IGNORECASE)

# Uzbek Cyrillic -> Latin (longest keys first matters, handled below).
_CYR2LAT = {
    "ғ": "g", "ў": "o", "қ": "q", "ҳ": "h", "ч": "ch", "ш": "sh",
    "ё": "yo", "ю": "yu", "я": "ya", "ж": "j", "х": "x", "ц": "s",
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "ъ": "", "ь": "", "э": "e", "щ": "sh",
    "ы": "i",
}


def unify_apostrophes(text: str) -> str:
    for a in _APOSTROPHES:
        text = text.replace(a, "'")
    return text


def normalize_light(text: str) -> str:
    """Lower-cased, apostrophe-unified, whitespace-collapsed — but boilerplate KEPT.
    Used for flag detection (ads/digests/off-topic/foreign) that must still see
    words like 'реклама'/'aksiya' which normalize_text() strips."""
    if not isinstance(text, str):
        return ""
    text = unify_apostrophes(text).lower()
    return re.sub(r"\s+", " ", text).strip()


def normalize_text(text: str) -> str:
    """Lower-cased, boilerplate-free string for lexicon matching (script kept)."""
    if not isinstance(text, str):
        return ""
    text = unify_apostrophes(text).lower()
    text = _BOILERPLATE_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def cyr_to_lat(text: str) -> str:
    return "".join(_CYR2LAT.get(ch, ch) for ch in text)


def to_latin_tokens(text: str, stopwords: set, min_len: int = 3) -> list:
    """Transliterated, boilerplate-free tokens for the LDA topic model."""
    norm = normalize_text(text)
    norm = cyr_to_lat(norm)
    norm = re.sub(r"[^a-z'\s]", " ", norm)          # drop digits/punct for topics
    tokens = re.findall(r"[a-z']{%d,}" % min_len, norm)
    return [t for t in tokens if t not in stopwords and len(t) > min_len - 1]
