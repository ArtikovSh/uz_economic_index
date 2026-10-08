"""Post excerpts; keep these helpers identical to app/api/index.py."""
import re

_MD_LINK = re.compile(r"\[([^\]]*)\]\((?:https?|tg)://[^)]*\)")
_URL = re.compile(r"(?:https?://|t\.me/)\S+")
_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D\u20E3]")
_BOILERPLATE = re.compile(r"^(batafsil|батафсил|подробнее|подробно|читайте|читать далее|obuna|обуна бўл|подпис|"
                          r"subscribe|kanalimiz|каналимиз|bizni kuzating|бизни кузатинг|расмий саҳифа|"
                          r"катталар канали|распространите|будьте в курсе|яқинларингиз соғ|"
                          r"«?\w+»? канали обуначилари|@\w+$)", re.IGNORECASE)
# a channel's slogan after the text of a line: "@OPER_UZ – ОПЕРАТИВ ... КАНАЛИ!", "@SHOPIRLAR KANALI",
# "ДунёУз - Тв да кўрсатмайдиган хабарлар канали!", "Катталар канали @SHOPIRLAR га обуна бўлинг", "Батафсил ..."
_TAIL = re.compile(r"\s*(?:@\w{4,}\s*(?:[-–—][^\n]{0,80})?\s(?:kanali|канали)\W*|ДунёУз\s*-\s*Тв[^\n]*|"
                   r"Катталар канали[^\n]*|(?:^|(?<=[.!?…])\s)(?-i:Батафсил|Batafsil)\b[^\n]*)$", re.IGNORECASE)
_TAGS = re.compile(r"(?:^|\s)#\w+")                                  # "#Тезкор #Диққат" labels
# short lines that only ask to share the post or name the channel: "Яқинларга ҳам улашинг!",
# "Бу видеони аёлларга юбориб қўйинг.", "ГРУППАЛАРГА ТАРҚАТИБ ҚЎЯМИЗ.", "новостей вместе с @oblakouz"
_SHARE = re.compile(r"(?:юбориб|тарқатиб|yuborib|tarqatib)\W+(?:\w+\W+)?(?:қўй|қўя|qo.y|qo.ya)|"
                    r"\b(?:улашинг|юборинг|ulashing|yuboring)\b|@\w+\W*$", re.IGNORECASE)


def _clean_lines(raw):
    """Lines of a post for reading: no markdown, links, emoji, hashtags or channel footers."""
    lines = []
    for line in _EMOJI.sub("", str(raw or "")).splitlines():
        if not re.sub(r"[\s|•·*_—–-]+", "", _URL.sub("", _MD_LINK.sub("", line))):
            continue                          # links only: "Telegram | Instagram", "Read more"
        line = re.sub(r"\*\*|__|~~|`", "", _MD_LINK.sub(r"\1", line))
        line = _TAGS.sub(" ", _TAIL.sub("", _URL.sub("", line)))
        line = re.sub(r"^[\s|]+|[\s—–:|]+$", "", line)                # "#BREAKING | ..." -> "..."
        if len(re.sub(r"\W", "", line)) < 2:
            continue                          # what a footer left: "К" of "ККатталар канали"
        if not _BOILERPLATE.match(line) and not (len(line) < 90 and _SHARE.search(line)):
            lines.append(" ".join(line.split()))
    return lines


def _cut(text, limit):
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0].rstrip(".,;:—– ") + "…"


def _same(a, b):
    key = lambda s: re.sub(r"[\W_]+", "", str(s)).lower()
    return bool(key(a)) and key(a) == key(b)


def post_parts(raw, body_limit=100, headline=None):
    """(headline, text) of a post, with at most `body_limit` characters of text. The model's
    headline (labels v6) wins: when it is the post's own first line the text is the rest, else
    the text is the whole post. Without one: the first line (or the first sentence of a
    one-line post) and the rest."""
    lines = _clean_lines(raw)
    head = _TAGS.sub(" ", " ".join(str(headline or "").split())).strip(" |:—–-")   # "#Тезкор" is no headline
    if head:
        head = " ".join(head.split())
        rest = lines[1:] if lines and _same(lines[0], head) else lines
        return _cut(head, 240), _cut(" ".join(rest), body_limit)
    if not lines:
        return "", ""
    head, rest = lines[0], " ".join(lines[1:])
    if not rest:
        m = re.match(r"(.{20,200}?[.!?…])\s+(.+)", head)
        if m:
            head, rest = m.group(1), m.group(2)
    return _cut(head, 240), _cut(rest, body_limit)
