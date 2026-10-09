"""
Single Vercel Python entrypoint (api/index.py) — the new Vercel runtime looks for
a default entrypoint name, so both endpoints live here and are dispatched by HTTP
method and header:
  * POST  /api/index             -> Telegram webhook (the bot)
  * POST  /api/index?action=...  -> Mini App actions: sign in, access request, admin panel
                                    (needs the X-Telegram-Init-Data header)
  * GET   /api/index             -> Mini App data JSON (needs X-Telegram-Init-Data),
                                    or a health message in a plain browser.
  * GET   /api/index?cron=digest -> morning summaries (Vercel cron, needs CRON_SECRET)

Index figures come from the `indices` table (one row per closed day / week / month /
quarter / year): EAI = % of non-ad posts that are economic, ESI = 100*(pos-neg)/econ.

Access: only accounts an admin created (login + password, see _auth.py) can use the bot
and the Mini App; BOT_ADMIN_ID is always the owner-admin. Roles: analyst / economist / admin.
Admins also manage the channel list the pipeline collects (_channels.py). The bot's words in
three languages are in _bot.py; /setup (_botsetup.py) configures its profile and icons.

Env: TELEGRAM_BOT_TOKEN, BOT_ADMIN_ID, SUPABASE_DB_URL, [WEBAPP_URL], [WEBHOOK_SECRET], [CRON_SECRET].
"""
from http.server import BaseHTTPRequestHandler
import hashlib
import hmac
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from html import escape
from urllib.parse import parse_qs, parse_qsl, urlparse

import psycopg
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _auth as auth  # noqa: E402  (helper modules next to this file, not endpoints)
import _bot as bot  # noqa: E402
import _botsetup as botsetup  # noqa: E402
import _channels as channels  # noqa: E402

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ADMIN_ID = os.getenv("BOT_ADMIN_ID", "").strip()
DB_URL = os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL") or ""
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
CRON_SECRET = os.getenv("CRON_SECRET", "").strip()     # Vercel sends it with its cron calls
DIGEST_MAX_AGE = 5                     # days: an older latest day is history, not news
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
TZ = "5 hours"
INIT_DATA_MAX_AGE = 24 * 3600          # Mini App initData older than this is rejected
TOPICS = {
    "prices_inflation": "Narx/inflatsiya", "currency_fx": "Valyuta/kurs",
    "fiscal": "Byudjet/soliq", "trade": "Tashqi savdo", "macro": "Makro",
    "central_bank": "Markaziy bank", "banking_finance": "Bank/moliya", "labour_income": "Mehnat/daromad",
    "energy_utility": "Energetika", "business": "Biznes", "construction_realty": "Qurilish",
}
COUNTED = "is_economic and not is_ad and not is_foreign and not is_digest"
# Tashkent calendar day of a post, whatever the session time zone is
DAY = f"((date_utc at time zone 'UTC') + interval '{TZ}')::date"
# Tone as indicator.py sets it (labels.sentiment is a real, so compare as real)
POS, NEG = "sentiment > 0.15::real", "sentiment < -0.15::real"
# Days the pipeline has finalised (posts of other days may still carry old labels)
FINAL_DAYS = "(select start_date from indices where period_type='kun')"


# ------------------------------------------------------------------ database ---
_CONN = None


def _rows(cur):
    cols = [c.name for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _run(work):
    """work(cursor) on the process's one database connection. Opening a connection costs several
    round trips, more than the queries themselves, so it is kept while the instance lives; a
    connection the pooler dropped is reopened once. Autocommit: every statement stands alone."""
    global _CONN
    for attempt in (0, 1):
        if _CONN is None or _CONN.closed:
            _CONN = psycopg.connect(DB_URL, prepare_threshold=None, autocommit=True, connect_timeout=10)
        try:
            with _CONN.cursor() as cur:
                return work(cur)
        except psycopg.OperationalError:
            try:
                _CONN.close()
            except Exception:
                pass
            _CONN = None
            if attempt:
                raise


def q(sql, params=(), one=False):
    def work(cur):
        cur.execute(sql, params)
        if cur.description is None:
            return None
        rows = _rows(cur)
        return (rows[0] if rows else None) if one else rows
    return _run(work)


def q_many(*queries):
    """Several (sql, params) -> list of row lists."""
    def work(cur):
        out = []
        for sql, params in queries:
            cur.execute(sql, params)
            out.append(_rows(cur))
        return out
    return _run(work)


_SCHEMA_READY = False
# labels v6 carry every topic of a post (sync_to_db.py adds them too; whichever runs first)
POSTS_DDL = """
do $$ begin
  if to_regclass('labels') is not null and to_regclass('messages') is not null then
    alter table labels add column if not exists topics text[];
    alter table labels add column if not exists headline text;
    create or replace view posts as
      select m.*, l.is_economic, l.primary_topic, l.relevance, l.sentiment,
             l.is_ad, l.is_digest, l.is_foreign, l.label_version, l.topics, l.headline
      from messages m left join labels l
        on m.channel = l.channel and m.message_id = l.message_id;
  end if;
end $$"""
TOPICS_OF = "coalesce(topics, array[primary_topic])"


def ensure_schema():
    """Create the access-control and channel tables once per cold start (idempotent DDL)."""
    global _SCHEMA_READY
    if not _SCHEMA_READY:
        q(auth.SCHEMA)
        q(bot.SCHEMA)
        q(POSTS_DDL)
        channels.ensure(q)
        _SCHEMA_READY = True


def who(tg_user):
    """(state, account) of a verified Telegram user: ok | login | blocked | expired."""
    ensure_schema()
    return auth.principal(q, tg_user["id"], ADMIN_ID)


def me_json(acc):
    return {"login": acc["login"], "role": acc["role"], "is_admin": bool(acc.get("is_admin")),
            "owner": bool(acc.get("owner")), "expires_at": acc.get("expires_at")}


# ------------------------------------------------------------------- telegram --
def send(chat_id, text, **kw):
    """Send a message; returns whether Telegram accepted it."""
    if not BOT_TOKEN:
        print("SEND SKIPPED: TELEGRAM_BOT_TOKEN is empty"); return False
    kw = {k: v for k, v in kw.items() if v is not None}   # drop None (e.g. reply_markup)
    try:
        r = requests.post(f"{API}/sendMessage", timeout=15, json={
            "chat_id": chat_id, "text": text, "parse_mode": "HTML",
            "disable_web_page_preview": True, **kw})
        if not r.ok:
            print(f"Telegram sendMessage FAILED {r.status_code}: {r.text[:300]}")
            if r.status_code == 403:                     # the user blocked the bot: stop the summaries
                q("update bot_users set blocked_bot=true where telegram_id=%s", (chat_id,))
        return r.ok
    except Exception as e:
        print("send error:", e)
        return False


def tg(method, params=None, files=None, timeout=30):
    """Any Bot API method -> its result; raises TgError with Telegram's description."""
    data = {k: json.dumps(v) if isinstance(v, (dict, list, bool)) else v for k, v in (params or {}).items()}
    try:
        r = requests.post(f"{API}/{method}", data=data, files=files, timeout=timeout)
        out = r.json()
    except (requests.RequestException, ValueError) as e:
        raise botsetup.TgError(type(e).__name__)
    if not out.get("ok"):
        raise botsetup.TgError(out.get("description") or str(r.status_code))
    return out["result"]


def edit(chat_id, mid, text, kb=None):
    if not BOT_TOKEN:
        return
    payload = {"chat_id": chat_id, "message_id": mid, "text": text,
               "parse_mode": "HTML", "disable_web_page_preview": True}
    if kb:
        payload["reply_markup"] = kb
    try:
        r = requests.post(f"{API}/editMessageText", json=payload, timeout=15)
        if not r.ok and "not modified" not in r.text:
            print("edit failed:", r.status_code, r.text[:200])
    except Exception as e:
        print("edit error:", e)


def answer_cb(cb_id, text=None):
    try:
        requests.post(f"{API}/answerCallbackQuery", timeout=10,
                      json={"callback_query_id": cb_id, **({"text": text} if text else {})})
    except Exception as e:
        print("answer_cb error:", e)


_EMOJI_IDS, _EMOJI_AT = None, 0.0
EMOJI_TTL = 300                        # seconds; /setup in one instance reaches the others this soon


def emoji():
    """Custom emoji ids saved by /setup, only if Telegram let the bot use them."""
    global _EMOJI_IDS, _EMOJI_AT
    if _EMOJI_IDS is None or time.time() - _EMOJI_AT > EMOJI_TTL:
        _EMOJI_AT = time.time()
        try:
            row = q("select value from bot_settings where key='emoji'", one=True)
        except psycopg.errors.UndefinedTable:
            row = None
        value = row["value"] if row else {}
        _EMOJI_IDS = value if value.get("ok") else {}
    return _EMOJI_IDS


def app_url(screen=""):
    """The Mini App, optionally on a screen (?screen=admin). A query parameter, not a #fragment:
    Telegram passes its launch data in the URL fragment."""
    return WEBAPP_URL.rstrip("/") + "/" + (f"?screen={screen}" if screen else "")


def app_kb(text, screen="", em=None, glyph="dashboard"):
    """One button that opens the Mini App."""
    if not WEBAPP_URL:
        return None
    return {"inline_keyboard": [[bot.button(text, em, glyph, "primary", web_app={"url": app_url(screen)})]]}


def main_kb(lang, em):
    # Telegram makes a row of two buttons as wide as twice its longest label: paired buttons
    # carry short labels so they never stick out of the message above them
    tr = lambda k: bot.tr(lang, k)
    rows = [[bot.button(tr("today_s"), em, "esi", callback_data="nav:today"),
             bot.button(tr("week_s"), em, "week", callback_data="nav:week")],
            [bot.button(tr("topics"), em, "topics", callback_data="nav:topics"),
             bot.button(tr("top_s"), em, "news", callback_data="nav:top")]]
    if WEBAPP_URL:
        rows.append([bot.button(tr("app"), em, "dashboard", "primary", web_app={"url": app_url()})])
    return {"inline_keyboard": rows}


def summary_kb(data, lang, em):
    """Under a daily or weekly card: the dashboard, its topics and posts, the other summary."""
    tr = lambda k: bot.tr(lang, k)
    rows = []
    if WEBAPP_URL:
        rows.append([bot.button(tr("open_app"), em, "dashboard", "primary", web_app={"url": app_url()})])
    ref = f"{data['kind']}:{data['start']}"
    rows.append([bot.button(tr("topics"), em, "topics", callback_data=f"nav:topics:{ref}"),
                 bot.button(tr("top_s"), em, "news", callback_data=f"nav:top:{ref}")])
    other = ("week", "week", "nav:week") if data["kind"] == "kun" else ("today", "esi", "nav:today")
    rows.append([bot.button(tr(other[0]), em, other[1], callback_data=other[2])])
    return {"inline_keyboard": rows}


def lang_kb(src):
    """Language choice; src says where it was opened: w = welcome, m = /me, p = /lang."""
    return {"inline_keyboard": [[{"text": bot.LANG_NAMES[c], "callback_data": f"lang:{c}:{src}"}]
                                for c in bot.LANGS]}         # one a row: three in a row outgrow /lang


def me_kb(lang, em, digest, owner):
    tr = lambda k: bot.tr(lang, k)
    rows = [[bot.button(tr("digest_turn_off" if digest else "digest_turn_on"), em, "bell", callback_data="me:digest")],
            [bot.button(tr("lang_btn"), em, "globe", callback_data="me:lang")]]
    if not owner:
        rows.append([bot.button(tr("logout_btn"), callback_data="me:logout")])
    return {"inline_keyboard": rows}


# ------------------------------------------------------------- summaries -----
CARD_VERSION = 2                       # bump when the card design changes: cached uploads are per version
CARD_KEYS = ("kind", "start", "end", "eai", "esi", "d_eai", "d_esi", "nonad", "econ", "channels", "series")


def render_card(data, lang):
    """The summary card as PNG bytes, or None (no renderer or it failed): the text goes alone."""
    try:
        import _card
        return _card.render({**{k: data[k] for k in CARD_KEYS}, "lang": lang})
    except Exception as e:
        print("card error:", repr(e))
        return None


def send_card(chat_id, data, lang, caption, kb):
    """The card with its caption; each (period, language) card is uploaded once, then reused."""
    key = (data["kind"], f"{data['period']}#v{CARD_VERSION}", lang)
    row = q("select file_id from bot_cards where kind=%s and period=%s and lang=%s", key, one=True)
    payload = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML", "reply_markup": kb}
    try:
        if row:
            return bool(tg("sendPhoto", {**payload, "photo": row["file_id"]}))
        png = render_card(data, lang)
        if png is None:
            return send(chat_id, caption, reply_markup=kb)
        msg = tg("sendPhoto", payload, files={"photo": ("card.png", png, "image/png")})
        q("""insert into bot_cards (kind, period, lang, file_id) values (%s,%s,%s,%s)
             on conflict (kind, period, lang) do nothing""", (*key, msg["photo"][-1]["file_id"]))
        return True
    except botsetup.TgError as e:
        print("sendPhoto failed:", e)
        if "blocked" in str(e) or "deactivated" in str(e):
            q("update bot_users set blocked_bot=true where telegram_id=%s", (chat_id,))
        return False


def summary(kind, start=None):
    try:
        return bot.summary(q, kind, start)
    except psycopg.errors.UndefinedTable:              # before the pipeline's first DB sync
        return None


def send_summary(chat_id, kind, lang, em):
    data = summary(kind)
    if not data:
        return send(chat_id, bot.tr(lang, "no_data"))
    return send_card(chat_id, data, lang, bot.caption(data, lang, em), summary_kb(data, lang, em))


def send_details(chat_id, what, ref, lang, em):
    """Topics or top posts of a summary's period (ref = 'kun:2026-10-05'), or of the latest day."""
    kind, _, start = (ref or "kun:").partition(":")
    data = summary(kind if kind in ("kun", "hafta") else "kun", _date(start) if start else None)
    if not data:
        return send(chat_id, bot.tr(lang, "no_data"))
    if what == "topics":
        return send(chat_id, bot.topics_text(data, lang, em))
    try:
        names = channels.titles(q)
    except psycopg.errors.UndefinedTable:
        names = channels.NAMES
    rows = bot.top_posts(q, data["start"], data["end"])
    return send(chat_id, bot.top_text(rows, data, lang, names, post_parts, em))


def run_digest():
    """Morning summaries (Vercel cron): the latest closed day, and the latest closed week when
    it is new, to every signed-in user and the owner who keep them on. Each goes once."""
    ensure_schema()
    day, week = summary("kun"), summary("hafta")
    # only fresh periods: while the history is built month by month the latest day is old
    fresh = (datetime.now(timezone.utc) + timedelta(hours=5)).date() - timedelta(days=DIGEST_MAX_AGE)
    day = day if day and _date(day["start"]) >= fresh else None
    week = week if week and _date(week["end"]) >= fresh else None
    if not day and not week:
        return {"ok": True, "sent": 0}
    people = q("""select t.tg, b.lang, b.digest_day, b.digest_week
                  from (select telegram_id tg from accounts
                        where telegram_id is not null and status='active' and (expires_at is null or expires_at > now())
                        union select %s::bigint) t
                  left join bot_users b on b.telegram_id = t.tg
                  where t.tg is not null and coalesce(b.digest, true) and not coalesce(b.blocked_bot, false)""",
               (int(ADMIN_ID) if ADMIN_ID else None,)) or []
    em, sent = emoji(), 0
    for p in people:
        lang = p["lang"] or "uz"
        for data, col in ((day, "digest_day"), (week, "digest_week")):
            start = _date(data["start"]) if data else None
            if not data or (p[col] and p[col] >= start):
                continue
            if send_card(p["tg"], data, lang, bot.caption(data, lang, em), summary_kb(data, lang, em)):
                sent += 1
                q(f"""insert into bot_users (telegram_id, {col}) values (%s, %s)
                      on conflict (telegram_id) do update set {col} = excluded.{col}""", (p["tg"], start))
    return {"ok": True, "sent": sent, "day": day and day["start"], "week": week and week["start"]}


# ------------------------------------------------------------- access ----------
OLD_ADMIN_CMDS = ("/pending", "/approve", "/setrole", "/block", "/users")


def gate(chat_id, state, lang, em=None):
    """Not signed in, blocked or expired: what to do next, with the button that does it."""
    if not WEBAPP_URL:
        return send(chat_id, bot.gate_text(state, lang, em) + "\n\n" + bot.tr(lang, "no_app"))
    label, glyph = (bot.tr(lang, "login_btn"), "login") if state == "login" else (bot.tr(lang, "contact_btn"), "user")
    return send(chat_id, bot.gate_text(state, lang, em), reply_markup=app_kb(label, em=em, glyph=glyph))


def home(chat_id, state, acc, lang, em):
    if state != "ok":
        return gate(chat_id, state, lang, em)
    return send(chat_id, bot.home_text(lang, em), reply_markup=main_kb(lang, em))


def digest_on(tg_id):
    row = bot.user_row(q, tg_id)
    return row["digest"] if row else True


def notify_new_request(req):
    """Tell the owner-admin about a new access request."""
    if not ADMIN_ID:
        return
    lang, em = bot.lang_of(q, {"id": int(ADMIN_ID)}), emoji()
    name = escape(req["full_name"]) + (f" · {escape(req['organization'])}" if req.get("organization") else "")
    who_ = f"@{escape(req['tg_username'])}" if req.get("tg_username") else escape(req.get("tg_name") or "")
    text = (f"{bot.ic(em, 'user')}<b>{escape(bot.tr(lang, 'new_request'))}</b>\n{name} · "
            f"{who_} · {escape(bot.tr(lang, 'reasons').get(req['reason'], ''))}")   # one line: wide as the button
    if req.get("message"):
        text += f"\n\n{escape(req['message'])}"
    send(int(ADMIN_ID), text, reply_markup=app_kb(bot.tr(lang, "requests_btn"), "requests", em, "user"))


def deliver_credentials(req, account, password):
    """Send the new login to the requester; it works only from their Telegram account."""
    lang, em = bot.lang_of(q, {"id": req["telegram_id"]}), emoji()
    return send(req["telegram_id"],
                f"{bot.ic(em, 'lock')}<b>{escape(bot.tr(lang, 'creds_title'))}</b>\n"
                f"Login: <code>{escape(account['login'])}</code>\n"
                + bot.tr(lang, "creds_password", x=f"<code>{escape(password)}</code>") + "\n\n"
                + escape(bot.tr(lang, "creds_note")),
                reply_markup=app_kb(bot.tr(lang, "login_btn"), em=em, glyph="login"))


def welcome_after_login(user):
    """The bot confirms a successful sign-in in the Mini App and shows what comes next."""
    state, acc = who(user)
    if state != "ok":
        return
    bot.remember(q, user["id"])
    lang, em = bot.lang_of(q, user), emoji()
    kb = {"inline_keyboard": [[bot.button(bot.tr(lang, "today_s"), em, "esi", callback_data="nav:today")]
                              + ([bot.button(bot.tr(lang, "app"), em, "dashboard", "primary",
                                             web_app={"url": app_url()})] if WEBAPP_URL else [])]}
    send(user["id"], bot.activated_text(acc, lang, em), reply_markup=kb)


def handle_callback(cq):
    data = cq.get("data", "")
    frm = cq["from"]
    m = cq.get("message", {})
    chat_id = m.get("chat", {}).get("id")
    mid = m.get("message_id")
    ensure_schema()
    em = emoji()
    parts = data.split(":")
    if parts[0] == "lang":                               # anyone, signed in or not
        answer_cb(cq["id"])
        code, src = (parts + ["", ""])[1:3]
        if not bot.set_lang(q, frm["id"], code):
            return
        state, acc = who(frm)
        if src == "w":                                   # the welcome, now in that language; then next step
            edit(chat_id, mid, bot.welcome_text(code, em, with_pick=False))
            return home(chat_id, state, acc, code, em)
        if src == "m" and state == "ok":
            on = digest_on(frm["id"])
            return edit(chat_id, mid, bot.me_text(acc, on, code, em), me_kb(code, em, on, acc.get("owner")))
        return edit(chat_id, mid, f"{escape(bot.tr(code, 'lang_title'))}: {bot.LANG_NAMES[code]}")
    state, acc = who(frm)
    lang = bot.lang_of(q, frm)
    if state != "ok":
        answer_cb(cq["id"])
        return gate(chat_id, state, lang, em)
    if data == "me:digest":
        on = bot.toggle_digest(q, frm["id"])
        answer_cb(cq["id"], bot.tr(lang, "digest_done_on" if on else "digest_done_off"))
        return edit(chat_id, mid, bot.me_text(acc, on, lang, em), me_kb(lang, em, on, acc.get("owner")))
    answer_cb(cq["id"])
    if parts[0] == "nav":
        what = parts[1] if len(parts) > 1 else "today"
        if what in ("topics", "top"):
            return send_details(chat_id, what, ":".join(parts[2:4]), lang, em)
        return send_summary(chat_id, "hafta" if what == "week" else "kun", lang, em)   # also old "nav:chart"
    if data == "me:lang":
        return edit(chat_id, mid, bot.welcome_text(lang, em).rsplit("\n\n", 1)[1], lang_kb("m"))
    if data == "me:logout" and not acc.get("owner"):
        kb = {"inline_keyboard": [[bot.button(bot.tr(lang, "logout_yes"), style="danger", callback_data="me:out"),
                                   bot.button(bot.tr(lang, "cancel"), callback_data="me:back")]]}
        return edit(chat_id, mid, escape(bot.tr(lang, "logout_ask")), kb)
    if data == "me:out" and not acc.get("owner"):
        auth.logout(q, frm["id"])
        return edit(chat_id, mid, bot.gate_text("login", lang, em),
                    app_kb(bot.tr(lang, "login_btn"), em=em, glyph="login"))
    if data == "me:back":
        on = digest_on(frm["id"])
        return edit(chat_id, mid, bot.me_text(acc, on, lang, em), me_kb(lang, em, on, acc.get("owner")))


def setup(chat_id, lang):
    """/setup: the bot's profile, menus and icons (owner only)."""
    global _EMOJI_IDS

    def fetch(url):
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        return r.content
    report = botsetup.run(tg, q, fetch, ADMIN_ID, lang, WEBAPP_URL.rstrip("/"), bool(CRON_SECRET))
    _EMOJI_IDS = None                                    # pick up the new icons
    send(chat_id, report)


def handle_update(update):
    if "callback_query" in update:
        return handle_callback(update["callback_query"])
    msg = update.get("message") or update.get("edited_message")
    if not msg or "text" not in msg or msg.get("chat", {}).get("type") != "private":
        return
    chat_id, user = msg["chat"]["id"], msg["from"]
    text = msg["text"].strip()
    cmd = text.split()[0].lower().split("@")[0] if text else ""
    ensure_schema()
    em = emoji()
    if cmd == "/start":
        row = bot.user_row(q, user["id"])
        if not row or not row["lang"]:                   # first visit: introduce the bot, ask the language
            bot.remember(q, user["id"])
            return send(chat_id, bot.welcome_text(bot.detect(user), em), reply_markup=lang_kb("w"))
        state, acc = who(user)
        return home(chat_id, state, acc, row["lang"], em)
    lang = bot.lang_of(q, user)
    if cmd == "/lang":
        return send(chat_id, bot.welcome_text(lang, em).rsplit("\n\n", 1)[1], reply_markup=lang_kb("p"))
    state, acc = who(user)
    if state != "ok":
        return gate(chat_id, state, lang, em)

    if cmd == "/help":
        return send(chat_id, bot.tr(lang, "help"))
    if cmd == "/me":
        on = digest_on(user["id"])
        return send(chat_id, bot.me_text(acc, on, lang, em), reply_markup=me_kb(lang, em, on, acc.get("owner")))
    if cmd == "/logout":
        if acc.get("owner"):
            return send(chat_id, bot.tr(lang, "owner_stays"))
        auth.logout(q, user["id"])
        return gate(chat_id, "login", lang, em)
    if cmd == "/setup" and acc.get("owner"):
        return setup(chat_id, lang)
    if cmd in OLD_ADMIN_CMDS and acc.get("is_admin"):
        return send(chat_id, bot.tr(lang, "admin_moved"),
                    reply_markup=app_kb(bot.tr(lang, "admin_btn"), "admin", em, "user"))
    if cmd == "/app":
        return send(chat_id, bot.home_text(lang, em), reply_markup=main_kb(lang, em))
    if cmd in ("/today", "/index"):
        return send_summary(chat_id, "kun", lang, em)
    if cmd == "/week":
        return send_summary(chat_id, "hafta", lang, em)
    if cmd in ("/top", "/topics"):
        return send_details(chat_id, cmd[1:], None, lang, em)
    send(chat_id, bot.tr(lang, "unknown"))


# ----------------------------------------------------------- Mini App data -----
def verify_init_data(init_data):
    if not init_data or not BOT_TOKEN:
        return None
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    recv = pairs.pop("hash", None)
    if not recv:
        return None
    check = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, recv):
        return None
    try:
        if time.time() - int(pairs.get("auth_date", "0")) > INIT_DATA_MAX_AGE:
            return None                            # stale: a replayed old initData
        return json.loads(pairs.get("user", "{}"))
    except (ValueError, TypeError):
        return None


def _post_link(channel, mid):
    return f"https://t.me/{str(channel).lstrip('@')}/{mid}"


_STATS = (None, None)                  # (fingerprint, stats): the data changes about once a day


def build_stats():
    """Counts of every final day and their split by topic, kept while the final days and the
    active channels stay the same."""
    global _STATS
    try:
        mark = q("""select (select (count(*), max(period), sum(econ), sum(pos), sum(neg))::text
                             from indices where period_type='kun') i,
                           (select (count(*), max(coalesce(changed_at, added_at)))::text
                             from channels where active) c""", one=True)
    except psycopg.errors.UndefinedTable:
        mark = None
    if mark is not None and _STATS[0] == mark:
        return _STATS[1]
    out = _build_stats()
    if mark is not None:
        _STATS = (mark, out)
    return out


def _build_stats():
    """The Mini App sums days into weeks, months, quarters and years exactly as indicator.py
    does, so each figure equals the published Indekslar row (and open periods use the same
    arithmetic)."""
    try:
        days, chans, topics = q_many(
            ("""select period d, posts, nonad, econ, pos, neg from indices
                where period_type='kun' order by period""", None),
            (f"""select {DAY}::text d, channel, count(*) n, count(*) filter (where {COUNTED}) e
                 from posts where {DAY} in {FINAL_DAYS} group by 1, 2""", None),
            # a post counts in each of its topics; its share of ESI (wp, wg) is split between them
            (f"""select {DAY}::text d, t, count(*) n,
                        count(*) filter (where {POS}) p, count(*) filter (where {NEG}) g,
                        round(sum(case when {POS} then 1.0 / k else 0 end), 4)::float wp,
                        round(sum(case when {NEG} then 1.0 / k else 0 end), 4)::float wg
                 from (select *, cardinality({TOPICS_OF}) k from posts
                       where {COUNTED} and {DAY} in {FINAL_DAYS}) x, unnest({TOPICS_OF}) t
                 group by 1, 2""", None))
    except psycopg.errors.UndefinedTable:
        return {"days": [], "topics": [], "channels": [], "channels_total": 0}
    day_ix = {r["d"]: i for i, r in enumerate(days)}
    recent = {r["d"] for r in days[-30:]}
    per_day, per_channel, recent_channels = {}, {}, set()
    for r in chans:
        per_day[r["d"]] = per_day.get(r["d"], 0) + 1
        per_channel[r["channel"]] = per_channel.get(r["channel"], 0) + r["n"]
        if r["d"] in recent:
            recent_channels.add(r["channel"])
    try:
        names = channels.titles(q)
        active = [r["handle"] for r in channels.listing(q) if r["active"]]
    except psycopg.errors.UndefinedTable:
        names, active = channels.NAMES, []
    # every active channel is offered in the filters, also one added after the last final day
    for c in active:
        per_channel.setdefault(c, 0)
    chan_order = [c for c, _ in sorted(per_channel.items(), key=lambda x: -x[1])]
    chan_ix = {c: i for i, c in enumerate(chan_order)}
    return {
        # [day, posts, nonad, econ, pos, neg, channels collected]
        "days": [[r["d"], r["posts"], r["nonad"], r["econ"], r["pos"], r["neg"], per_day.get(r["d"], 0)]
                 for r in days],
        # [index into days, topic, counted posts, positive, negative, ESI share: positive, negative]
        "topics": [[day_ix[r["d"]], r["t"], r["n"], r["p"], r["g"], r["wp"], r["wg"]]
                   for r in topics if r["d"] in day_ix],
        "channels": [{"id": c, "name": names.get(c, str(c).lstrip("@"))} for c in chan_order],
        # [index into days, index into channels, economic posts] (what the posts list shows)
        "chan_days": [[day_ix[r["d"]], chan_ix[r["channel"]], r["e"]] for r in chans if r["d"] in day_ix and r["e"]],
        "channels_total": len(recent_channels),
    }


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


def clean_text(raw, limit=420):
    """Post text for reading: no markdown, links, emoji or channel footers."""
    lines = _clean_lines(raw)
    # a headline has no full stop; add one so it does not run into the body
    text = " ".join(l if l[-1] in ".!?…:;»\"”)" or i == len(lines) - 1 else l + "."
                    for i, l in enumerate(lines))
    return _cut(" ".join(text.split()), limit)


POST_ORDER = {"new": "date_utc desc, message_id desc", "old": "date_utc, message_id",
              "views": "views desc, date_utc desc"}
PAGE = 30


def _date(v):
    try:
        return date.fromisoformat(str(v))
    except ValueError:
        return None


def posts_page(body):
    """Counted (economic) posts of final days, filtered and sorted, 30 per page."""
    lo, hi = _date(body.get("from")), _date(body.get("to"))
    if not lo or not hi:
        return {"ok": False, "error": "bad_input"}
    lo, hi = min(lo, hi), max(lo, hi)
    where, params = [COUNTED, f"{DAY} between %s and %s", f"{DAY} in {FINAL_DAYS}"], [lo, hi]
    topics = [t for t in body.get("topics") or [] if t in TOPICS]
    if topics:
        where.append(f"{TOPICS_OF} && %s::text[]"); params.append(topics)
    channels = [str(c) for c in body.get("channels") or [] if isinstance(c, str)][:20]
    if channels:
        where.append("channel = any(%s)"); params.append(channels)
    tone = body.get("tone")
    if tone in ("pos", "neg"):
        where.append(POS if tone == "pos" else NEG)
    elif tone == "neu":
        where.append(f"not ({POS}) and not ({NEG})")
    cond = " and ".join(where)
    offset = max(0, _int(body.get("offset")) or 0)
    queries = [(f"select count(*) n from posts where {cond}", params)]
    if not body.get("count_only"):
        queries.append((f"""select channel, message_id, date_utc, views, primary_topic, raw_text,
                                   {TOPICS_OF} ts, headline,
                                   case when {POS} then 1 when {NEG} then -1 else 0 end tone
                            from posts where {cond}
                            order by {POST_ORDER.get(body.get("sort"), POST_ORDER["new"])}
                            limit {PAGE} offset %s""", params + [offset]))
    try:
        total, *rows = q_many(*queries)
    except psycopg.errors.UndefinedTable:              # before the pipeline's first DB sync
        return {"ok": True, "total": 0, "items": [], "more": False}
    total = total[0]["n"]
    if body.get("count_only"):
        return {"ok": True, "total": total}
    items = []
    for r in rows[0]:
        local = r["date_utc"].astimezone(timezone.utc) + timedelta(hours=5)
        head, text = post_parts(r["raw_text"], 320, r["headline"])
        items.append({"ch": r["channel"], "at": local.strftime("%Y-%m-%dT%H:%M"), "v": r["views"],
                      "t": r["primary_topic"], "ts": list(r["ts"]), "s": r["tone"], "head": head, "text": text,
                      "link": _post_link(r["channel"], r["message_id"])})
    return {"ok": True, "total": total, "items": items, "more": offset + len(items) < total}


# ------------------------------------------------------- Mini App actions -----
def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _password(body):
    """The password an admin typed, or None for a random one."""
    pw = body.get("password")
    return pw if isinstance(pw, str) and pw else None


ERROR_CODES = {"invalid": 401, "locked": 429, "too_many": 429, "blocked": 403, "expired": 403,
               "other_account": 403, "forbidden": 403, "not_found": 404, "no_request": 404,
               "no_account": 404, "exists": 409, "last_channel": 409, "not_channel": 404,
               "tg_unavailable": 503, "login_taken": 409, "self": 409}


def channel_info(handle):
    """Title of a public Telegram channel, from the Bot API (it answers for any public one)."""
    if not BOT_TOKEN:
        return {"ok": False, "error": "tg_unavailable"}
    try:
        r = requests.get(f"{API}/getChat", params={"chat_id": handle}, timeout=10)
        data = r.json()
    except (requests.RequestException, ValueError):
        return {"ok": False, "error": "tg_unavailable"}
    if not data.get("ok"):
        return {"ok": False, "error": "not_channel" if r.status_code in (400, 403) else "tg_unavailable"}
    chat = data["result"]
    if chat.get("type") != "channel":
        return {"ok": False, "error": "not_channel"}
    return {"ok": True, "title": chat.get("title") or handle}


def app_action(user, action, body):
    """One Mini App action for a verified Telegram user -> (http code, json)."""
    if action == "login":
        r = auth.login(q, user, body.get("login"), body.get("password"))
        if r["ok"]:
            welcome_after_login(user)
    elif action == "lang":                            # the Mini App's language is the bot's too
        r = {"ok": bot.set_lang(q, user["id"], body.get("lang"))}
    elif action == "logout":
        r = auth.logout(q, user["id"])
    elif action == "request":
        r = auth.create_request(q, user, body)
        if r["ok"]:
            notify_new_request(r.pop("request"))
    else:
        state, acc = who(user)
        if state != "ok":
            r = {"ok": False, "error": "forbidden"}
        elif action == "posts":                       # any signed-in user
            r = posts_page(body)
        elif not acc.get("is_admin"):
            r = {"ok": False, "error": "forbidden"}
        elif action == "admin":
            r = {**auth.overview(q), "channels": channels.listing(q)}
        elif action == "channel_add":
            r = channels.add(q, user["id"], body.get("handle"), channel_info)
        elif action == "channel_rename":
            r = channels.rename(q, str(body.get("handle") or ""), body.get("name"))
        elif action == "channel_delete":
            r = channels.remove(q, str(body.get("handle") or ""))
        elif action in ("channel_pause", "channel_resume"):
            r = channels.set_active(q, str(body.get("handle") or ""), action == "channel_resume")
        elif action == "check_login":
            r = {"ok": True, "state": auth.login_status(q, auth.normalize_login(body.get("login")))}
        elif action == "create":
            r = auth.create_account(q, user["id"], body.get("role"), str(body.get("term")),
                                    _int(body.get("request_id")), body.get("login") or None, _password(body))
            req = r.pop("request", None)
            if r["ok"] and req:
                r["delivered"] = deliver_credentials(req, r["account"], r["password"])
        elif action == "reset":                      # an account, or the requester's own login
            r = auth.reset_password(q, _int(body.get("id")), user["id"], _int(body.get("request_id")),
                                    _password(body))
            req = r.pop("request", None)
            if r["ok"] and req:
                r["delivered"] = deliver_credentials(req, r["account"], r["password"])
        elif action in ("block", "unblock"):
            r = auth.set_status(q, _int(body.get("id")), "blocked" if action == "block" else "active")
        elif action == "delete":
            r = auth.delete_account(q, _int(body.get("id")), user["id"])
        elif action == "extend":
            r = auth.extend(q, _int(body.get("id")), str(body.get("term")))
        elif action in ("reject", "close"):           # close = handled, the requester is not told
            r = auth.finish_request(q, user["id"], _int(body.get("request_id")),
                                    "rejected" if action == "reject" else "done")
            req = r.pop("request", None)
            if r["ok"] and action == "reject":
                send(req["telegram_id"], bot.tr(bot.lang_of(q, {"id": req["telegram_id"]}), "rejected"))
        else:
            r = {"ok": False, "error": "unknown_action"}
    code = 200 if r.get("ok") else ERROR_CODES.get(r.get("error"), 400)
    return code, r


# ------------------------------------------------------ Vercel entry point -----
def _jsonable(v):
    """JSON value for what psycopg returns. Times go out as ISO 8601 with a 'T' and
    milliseconds: iOS Safari cannot parse str(datetime) ('2026-10-06 10:00:00+00:00')."""
    if isinstance(v, datetime):
        return v.isoformat(timespec="milliseconds")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return str(v)


class handler(BaseHTTPRequestHandler):
    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False, default=_jsonable).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _user(self, init):
        user = verify_init_data(init)
        return user if user and "id" in user else None

    def do_POST(self):
        init = self.headers.get("X-Telegram-Init-Data")
        if init is not None:                       # Mini App action
            return self._app_action(init)
        if WEBHOOK_SECRET and self.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
            self.send_response(401); self.end_headers(); self.wfile.write(b"unauthorized"); return
        try:
            n = int(self.headers.get("content-length", 0))
            update = json.loads(self.rfile.read(n) or b"{}")
            msg = update.get("message") or {}
            print(f"UPDATE from {msg.get('from', {}).get('id')} "
                  f"| token={'set' if BOT_TOKEN else 'MISSING'} db={'set' if DB_URL else 'MISSING'} "
                  f"admin={'set' if ADMIN_ID else 'MISSING'}")
            handle_update(update)
        except Exception as e:
            import traceback
            print("HANDLE ERROR:", repr(e))
            traceback.print_exc()
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")

    def _app_action(self, init):
        try:
            n = int(self.headers.get("content-length", 0) or 0)
        except ValueError:
            n = 0
        if n > 16384:
            return self._json(413, {"ok": False, "error": "too_large"})
        raw = self.rfile.read(n) if n else b""     # read it before replying, or the client sees a reset
        user = self._user(init)
        if not user:
            return self._json(401, {"ok": False, "error": "unauthorized"})
        try:
            body = json.loads(raw or b"{}")
            if not isinstance(body, dict):
                raise ValueError("body must be an object")
        except ValueError:
            return self._json(400, {"ok": False, "error": "bad_json"})
        action = parse_qs(urlparse(self.path).query).get("action", [""])[0] or str(body.get("action", ""))
        try:
            ensure_schema()
            code, out = app_action(user, action, body)
            return self._json(code, out)
        except Exception as e:
            print("ACTION ERROR:", action, repr(e))    # never logs the body (passwords)
            return self._json(500, {"ok": False, "error": "server"})

    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        if query.get("cron") == ["digest"]:
            return self._cron()
        if "health" in query:                     # .github/workflows/health.yml: is the database reachable?
            try:
                q("select 1")
                return self._json(200, {"ok": True})
            except Exception as e:
                print("health error:", repr(e))
                return self._json(503, {"ok": False})
        init = self.headers.get("X-Telegram-Init-Data", "")
        if not init:
            self.send_response(200); self.end_headers()
            self.wfile.write(b"UZ Economic Index bot is running.")
            return
        user = self._user(init)
        if not user:
            return self._json(401, {"error": "unauthorized"})
        try:
            state, acc = who(user)
            lang = (bot.user_row(q, user["id"]) or {}).get("lang")
            if state != "ok":
                return self._json(200, {"auth": state, "lang": lang,
                                        "request_open": auth.has_open_request(q, user["id"])})
            return self._json(200, {"auth": "ok", "lang": lang, "me": me_json(acc), "stats": build_stats()})
        except Exception as e:
            print("data error:", repr(e))
            return self._json(500, {"error": "server"})

    def _cron(self):
        """Vercel cron (vercel.json): the morning summaries. Only with the CRON_SECRET it sends."""
        if not CRON_SECRET or not hmac.compare_digest(self.headers.get("Authorization", ""),
                                                      f"Bearer {CRON_SECRET}"):
            return self._json(401, {"ok": False, "error": "unauthorized"})
        try:
            return self._json(200, run_digest())
        except Exception as e:
            import traceback
            print("DIGEST ERROR:", repr(e))
            traceback.print_exc()
            return self._json(500, {"ok": False, "error": "server"})
