"""Post excerpts; keep these helpers identical to app/api/index.py."""
import re

_MD_LINK = re.compile(r"\[([^\]]*)\]\((?:https?|tg)://[^)]*\)")
_URL = re.compile(r"(?:https?://|t\.me/)\S+")
_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D\u20E3]")
_BOILERPLATE = re.compile(r"^(batafsil|подробнее|подробно|читайте|читать далее|obuna|подпис|subscribe|"
                          r"kanalimiz|bizni kuzating|@\w+$)", re.IGNORECASE)


def _clean_lines(raw):
    """Lines of a post for reading: no markdown, links, emoji or channel footers."""
    lines = []
    for line in _EMOJI.sub("", str(raw or "")).splitlines():
        if not re.sub(r"[\s|•·*_—–-]+", "", _URL.sub("", _MD_LINK.sub("", line))):
            continue                          # links only: "Telegram | Instagram", "Read more"
        line = re.sub(r"\*\*|__|~~|`", "", _MD_LINK.sub(r"\1", line))
        line = re.sub(r"[\s—–:|]+$", "", _URL.sub("", line)).strip()
        if line and not _BOILERPLATE.match(line):
            lines.append(" ".join(line.split()))
    return lines


def _cut(text, limit):
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0].rstrip(".,;:—– ") + "…"


def post_parts(raw, body_limit=100):
    """(headline, text) of a post: the first line in full (or the first sentence of a one-line
    post), and at most `body_limit` characters of the rest."""
    lines = _clean_lines(raw)
    if not lines:
        return "", ""
    head, rest = lines[0], " ".join(lines[1:])
    if not rest:
        m = re.match(r"(.{20,200}?[.!?…])\s+(.+)", head)
        if m:
            head, rest = m.group(1), m.group(2)
    return _cut(head, 240), _cut(rest, body_limit)
