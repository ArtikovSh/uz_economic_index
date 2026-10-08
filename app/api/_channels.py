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
alter table channels enable row level security;
"""
# the channels the index started with (config.CHANNELS in the pipeline)
SEED = [("@gazetauz", "Gazeta.uz"), ("@kunuzofficial", "Kun.uz"), ("@daryo", "Daryo"),
        ("@spotuz", "Spot"), ("@uzdaily", "UzDaily")]
NAMES = dict(SEED)
_HANDLE = re.compile(r"^@[a-z][a-z0-9_]{3,31}$")


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


def listing(q):
    return q("""select handle, title, active, added_at, changed_at from channels
                order by active desc, added_at, handle""") or []


def titles(q):
    rows = q("select handle, title from channels") or []
    return {**NAMES, **{r["handle"]: r["title"] for r in rows if r["title"]}}


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
