"""
Telegram channels the index is built from. An admin adds or pauses them in the Mini App;
the pipeline collects the active ones (channel_list.py), so a change applies from the
next daily collection and finished days never change.

All functions take `q(sql, params=(), one=False)`, the app's query helper.
"""
import re

SCHEMA = """
create table if not exists channels (
    handle      text primary key,          -- '@daryo': always '@' and lower case
    title       text,
    active      boolean not null default true,
    added_at    timestamptz not null default now(),
    added_by    bigint,
    changed_at  timestamptz
);
alter table channels add column if not exists name text;   -- a short name the admin chose
alter table channels enable row level security;
"""
# the channels the index started with (config.CHANNELS in the pipeline)
SEED = [("@gazetauz", "Gazeta.uz"), ("@kunuzofficial", "Kun.uz"), ("@daryo", "Daryo"),
        ("@spotuz", "Spot"), ("@uzdaily", "UzDaily")]
NAMES = dict(SEED)
_HANDLE = re.compile(r"^@[a-z][a-z0-9_]{3,31}$")
_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D\u20E3]")
# words that only advertise a channel ("official", "breaking news"): the name ends before them
_NOISE = re.compile(r"\s+(?:rasmiy|расмий|расмий|официальн\w*|official|tezkor|тезкор|новости|"
                    r"yangilik\w*|янгилик\w*|xabarlar\w*|хабарлар\w*|kanal\w*|канал\w*|channel)\b.*$",
                    re.IGNORECASE)


def short_name(title, handle="", split=True):
    """A channel's name without slogans: 'QORAXABAR - Tezkor xabarlar | Rasmiy kanal' -> 'Qoraxabar',
    'Qalampir.uz I расмий канал' -> 'Qalampir.uz', 'Oblakouz – Новости Узбекистана' -> 'Oblakouz'."""
    name = _EMOJI.sub("", str(title or ""))
    parts = re.split(r"\s+[|–—\-]\s*|\s*\|\s*|\s+I\s+", name.strip())
    name = parts[0] if split else " ".join(parts)           # the whole title when the first part repeats
    name = _NOISE.sub("", " ".join(name.split())).strip(" .,:;-–—|")
    if len(name) > 4 and name.upper() == name:              # 'DARAKCHI.UZ' -> 'Darakchi.uz'
        name = name[0] + name[1:].lower()
    elif name.lower() == name:                               # 'bakiroo' -> 'Bakiroo'
        name = name[:1].upper() + name[1:]
    return name[:28] or str(handle).lstrip("@")


def ensure(q):
    q(SCHEMA)
    for i, (handle, title) in enumerate(SEED):  # first start only: a paused seed stays paused
        q("""insert into channels (handle, title, added_at)
             values (%s, %s, '2026-09-01 00:00+05'::timestamptz + make_interval(secs => %s))
             on conflict (handle) do nothing""", (handle, title, i))


def normalize(raw):
    """'@Daryo', 'daryo' or 'https://t.me/daryo' -> '@daryo'; None if it cannot be a handle."""
    s = re.sub(r"^(https?://)?(t\.me|telegram\.me)/", "", str(raw or "").strip(), flags=re.IGNORECASE)
    s = "@" + s.split("?")[0].strip("/").lstrip("@").lower()
    return s if _HANDLE.match(s) else None


def _names(rows):
    """handle -> the name shown in the app: the admin's, else the cleaned Telegram title; a cleaned
    name two channels share ('Daryo' and 'Daryo | Dunyo') keeps more of the later one's title."""
    out, seen = {}, set()
    for r in sorted(rows, key=lambda r: (r.get("added_at") is None, r.get("added_at") or 0, r["handle"])):
        name = r["name"] or short_name(r["title"], r["handle"])
        if not r["name"] and name.lower() in seen:
            name = short_name(r["title"], r["handle"], split=False)
        seen.add(name.lower())
        out[r["handle"]] = name
    return out


def listing(q):
    rows = q("""select handle, title, name, active, added_at, changed_at from channels
                order by active desc, added_at, handle""") or []
    names = _names(rows)
    for r in rows:
        r["display"] = names[r["handle"]]
    return rows


def titles(q):
    """handle -> the name shown in the app (see _names)."""
    rows = q("select handle, title, name, added_at from channels") or []
    return {**NAMES, **_names([r for r in rows if r["name"] or r["title"]])}


def rename(q, handle, name):
    """The admin's short name for a channel; an empty one goes back to the cleaned title."""
    name = " ".join(str(name or "").split())[:28] or None
    row = q("update channels set name=%s where handle=%s returning handle", (name, handle), one=True)
    return {"ok": True} if row else {"ok": False, "error": "not_found"}


def add(q, admin_tg, raw, lookup):
    """Add (or switch back on) a public channel; `lookup(handle)` asks Telegram for its title."""
    handle = normalize(raw)
    if not handle:
        return {"ok": False, "error": "bad_handle"}
    row = q("select active from channels where handle=%s", (handle,), one=True)
    if row and row["active"]:
        return {"ok": False, "error": "exists"}
    info = lookup(handle)
    if not info.get("ok"):
        return {"ok": False, "error": info.get("error") or "not_channel"}
    q("""insert into channels (handle, title, added_by) values (%s, %s, %s)
         on conflict (handle) do update set active=true, title=excluded.title, changed_at=now()""",
      (handle, info["title"], admin_tg))
    return {"ok": True, "channel": {"handle": handle, "title": info["title"]}}


def remove(q, handle):
    """Remove a channel from the list; posts already collected stay in the archive."""
    row = q("select active from channels where handle=%s", (handle,), one=True)
    if not row:
        return {"ok": False, "error": "not_found"}
    if row["active"] and not q("select 1 x from channels where active and handle<>%s limit 1", (handle,), one=True):
        return {"ok": False, "error": "last_channel"}
    q("delete from channels where handle=%s", (handle,))
    return {"ok": True}


def set_active(q, handle, active):
    if not active:
        n = q("select count(*) n from channels where active and handle<>%s", (handle,), one=True)["n"]
        if n == 0:
            return {"ok": False, "error": "last_channel"}    # the index needs a channel
    row = q("update channels set active=%s, changed_at=now() where handle=%s returning handle",
            (bool(active), handle), one=True)
    return {"ok": True} if row else {"ok": False, "error": "not_found"}
