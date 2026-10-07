"""
Single Vercel Python entrypoint (api/index.py) — the new Vercel runtime looks for
a default entrypoint name, so both endpoints live here and are dispatched by HTTP
method and header:
  * POST  /api/index             -> Telegram webhook (the bot)
  * POST  /api/index?action=...  -> Mini App actions: sign in, access request, admin panel
                                    (needs the X-Telegram-Init-Data header)
  * GET   /api/index             -> Mini App data JSON (needs X-Telegram-Init-Data),
                                    or a health message in a plain browser.

Index figures come from the `indices` table (one row per closed day / week / month /
quarter / year): EAI = % of non-ad posts that are economic, ESI = 100*(pos-neg)/econ.

Access: only accounts an admin created (login + password, see _auth.py) can use the bot
and the Mini App; BOT_ADMIN_ID is always the owner-admin. Roles: analyst / economist / admin.
Admins also manage the channel list the pipeline collects (_channels.py).

Env: TELEGRAM_BOT_TOKEN, BOT_ADMIN_ID, SUPABASE_DB_URL, [WEBAPP_URL], [WEBHOOK_SECRET].
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
from urllib.parse import parse_qs, parse_qsl, quote, urlparse

import psycopg
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _auth as auth  # noqa: E402  (helper modules next to this file, not endpoints)
import _channels as channels  # noqa: E402

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ADMIN_ID = os.getenv("BOT_ADMIN_ID", "").strip()
DB_URL = os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL") or ""
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
TZ = "5 hours"
INIT_DATA_MAX_AGE = 24 * 3600          # Mini App initData older than this is rejected
ROLE_NAMES = {"admin": "Admin", "analyst": "Analitik", "economist": "Iqtisodchi"}
REASON_NAMES = {"access": "Kirish olish", "reset": "Parolni tiklash", "other": "Boshqa"}
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
def q(sql, params=(), one=False):
    with psycopg.connect(DB_URL, prepare_threshold=None) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        if cur.description is None:
            return None
        cols = [c.name for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        return (rows[0] if rows else None) if one else rows


def q_many(*queries):
    """Several (sql, params) on one connection -> list of row lists (saves a pooler round trip)."""
    out = []
    with psycopg.connect(DB_URL, prepare_threshold=None) as conn, conn.cursor() as cur:
        for sql, params in queries:
            cur.execute(sql, params)
            cols = [c.name for c in cur.description]
            out.append([dict(zip(cols, r)) for r in cur.fetchall()])
    return out


_SCHEMA_READY = False


def ensure_schema():
    """Create the access-control and channel tables once per cold start (idempotent DDL)."""
    global _SCHEMA_READY
    if not _SCHEMA_READY:
        q(auth.SCHEMA)
        channels.ensure(q)
        _SCHEMA_READY = True


def who(tg_user):
    """(state, account) of a verified Telegram user: ok | login | blocked | expired."""
    ensure_schema()
    return auth.principal(q, tg_user["id"], ADMIN_ID)


def me_json(acc):
    return {"login": acc["login"], "role": acc["role"], "is_admin": bool(acc.get("is_admin")),
            "owner": bool(acc.get("owner")), "expires_at": acc.get("expires_at")}


def index_rows(ptype, n):
    """Latest n rows of one period type, oldest first ([] until the table exists)."""
    try:
        rows = q("""select period, start_date::text s, end_date::text e, days, days_expected,
                           nonad, econ, pos, neg, eai, esi, note
                    from indices where period_type=%s order by end_date desc limit %s""", (ptype, n)) or []
    except psycopg.errors.UndefinedTable:
        return []                          # created by the pipeline's first DB sync
    return list(reversed(rows))


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
        return r.ok
    except Exception as e:
        print("send error:", e)
        return False


def main_kb():
    """Interactive navigation keyboard shown under bot messages."""
    rows = [
        [{"text": "Bugun", "callback_data": "nav:today"},
         {"text": "Asosiy xabarlar", "callback_data": "nav:top"}],
        [{"text": "Mavzular", "callback_data": "nav:topics"},
         {"text": "Grafik", "callback_data": "nav:chart"}],
    ]
    if WEBAPP_URL:
        rows.append([{"text": "Dashboard", "web_app": {"url": WEBAPP_URL}}])
    return {"inline_keyboard": rows}


def app_kb(text, screen=""):
    """One button that opens the Mini App, optionally on a screen (?screen=admin). A query
    parameter, not a #fragment: Telegram passes its launch data in the URL fragment."""
    if not WEBAPP_URL:
        return None
    url = WEBAPP_URL.rstrip("/") + "/" + (f"?screen={screen}" if screen else "")
    return {"inline_keyboard": [[{"text": text, "web_app": {"url": url}}]]}


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


def send_photo(chat_id, url, caption="", kb=None):
    if not BOT_TOKEN:
        return
    payload = {"chat_id": chat_id, "photo": url, "caption": caption, "parse_mode": "HTML"}
    if kb:
        payload["reply_markup"] = kb
    try:
        r = requests.post(f"{API}/sendPhoto", json=payload, timeout=25)
        if not r.ok:
            print("sendPhoto failed:", r.status_code, r.text[:200])
    except Exception as e:
        print("send_photo error:", e)


def sparkline(vals):
    blocks = "▁▂▃▄▅▆▇█"
    vals = [v for v in vals if v is not None]
    if not vals:
        return ""
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1
    return "".join(blocks[min(7, int(7 * (v - lo) / rng))] for v in vals)


def quickchart_url(n=30):
    d = index_rows("kun", n)
    cfg = {"type": "line",
           "data": {"labels": [x["period"][5:] for x in d],
                    "datasets": [
                        {"label": "E'tibor (EAI, %)", "data": [x["eai"] for x in d], "yAxisID": "y",
                         "borderColor": "#3b82f6", "backgroundColor": "rgba(59,130,246,.15)",
                         "fill": True, "tension": 0.35, "pointRadius": 0},
                        {"label": "Kayfiyat (ESI)", "data": [x["esi"] for x in d], "yAxisID": "y1",
                         "borderColor": "#22c55e", "fill": False, "tension": 0.35, "pointRadius": 0}]},
           "options": {"plugins": {"title": {"display": True, "text": f"UZ Economic Index — {len(d)} kun"}},
                       "scales": {"y": {"min": 0, "max": 100, "position": "left",
                                        "title": {"display": True, "text": "EAI, %"}},
                                  "y1": {"min": -100, "max": 100, "position": "right",
                                         "grid": {"drawOnChartArea": False},
                                         "title": {"display": True, "text": "ESI"}}}}}
    return "https://quickchart.io/chart?v=4&w=640&h=360&bkg=white&c=" + quote(json.dumps(cfg))


# --------------------------------------------------------------------- stats ---
def _day():
    rows = index_rows("kun", 1)
    return rows[-1]["period"] if rows else None


def _arrow(v):
    return "▲" if v > 0 else ("▼" if v < 0 else "▬")


def _mood(esi):
    if esi is None:
        return "⚪"
    return "🟢 ijobiy" if esi >= 10 else ("🔴 salbiy" if esi <= -10 else "🟡 neytral")


def _num(v, fmt):
    return "—" if v is None else format(v, fmt)


def fmt_index():
    hist = index_rows("kun", 14)
    if not hist:
        return "Hozircha ma'lumot yo'q. Quvur birinchi kunni yakunlashini kuting."
    d = hist[-1]
    prev = hist[-2] if len(hist) > 1 else None
    de = (d["eai"] - prev["eai"]) if prev and d["eai"] is not None and prev["eai"] is not None else 0
    ds = (d["esi"] - prev["esi"]) if prev and d["esi"] is not None and prev["esi"] is not None else 0
    week = (index_rows("hafta", 1) or [None])[-1]
    month = (index_rows("oy", 1) or [None])[-1]
    lines = [f"📊 <b>Iqtisodiy manzara — {d['period']}</b> <i>(Toshkent)</i>",
             "<i>2 kun oldingi to'liq kun</i>", "",
             f"🎯 <b>E'tibor (EAI): {_num(d['eai'], '.1f')}%</b>  {_arrow(de)}{abs(de):.1f}",
             "   <i>iqtisodiy xabarlar ulushi</i>",
             f"   <code>{sparkline([r['eai'] for r in hist])}</code>",
             f"💬 <b>Kayfiyat (ESI): {_num(d['esi'], '+.0f')}</b>  {_arrow(ds)}{abs(ds):.0f}  <i>({_mood(d['esi'])})</i>",
             "   <i>ijobiy − salbiy, foiz punkt</i>",
             f"   <code>{sparkline([r['esi'] for r in hist])}</code>", "",
             f"📰 Iqtisodiy xabarlar: <b>{d['econ']}</b> / {d['nonad']}"]
    if week:
        lines.append(f"📅 Hafta {week['s'][5:]}–{week['e'][5:]}: EAI {_num(week['eai'], '.1f')}%, "
                     f"ESI {_num(week['esi'], '+.0f')}")
    if month:
        lines.append(f"🗓 Oy {month['period']}: EAI {_num(month['eai'], '.1f')}%, "
                     f"ESI {_num(month['esi'], '+.0f')} ({month['days']}/{month['days_expected']} kun)")
    lines.append("<i>ESI: 0 = neytral · so'nggi 14 kun trendi</i>")
    return "\n".join(lines)


def fmt_top(n):
    day = _day()
    if not day:
        return "Ma'lumot yo'q."
    rows = q(f"""select channel, sentiment, views, raw_text from posts
                 where {DAY}=%s and {COUNTED}
                 order by relevance*ln(1+views+2*forwards) desc limit %s""", (day, n))
    if not rows:
        return "Bu kun uchun iqtisodiy post topilmadi."
    out = [f"🔝 <b>Top {len(rows)} iqtisodiy post — {day}</b>\n"]
    for i, r in enumerate(rows, 1):
        t = escape(" ".join(str(r["raw_text"]).split())[:160])
        mood = "🟢" if r["sentiment"] > 0.15 else ("🔴" if r["sentiment"] < -0.15 else "⚪")
        out.append(f"{i}. {mood} <i>{escape(str(r['channel']))}</i> · 👁{r['views']}\n{t}\n")
    return "\n".join(out)


def fmt_topics():
    day = _day()
    rows = q(f"""select primary_topic, count(*) n, round(avg(sentiment)::numeric,2) s
                 from posts where {DAY}=%s and {COUNTED}
                 group by primary_topic order by n desc""", (day,))
    if not rows:
        return "Ma'lumot yo'q."
    out = [f"🗂 <b>Mavzular — {day}</b>\n"]
    for r in rows:
        mood = "🟢" if r["s"] > 0.15 else ("🔴" if r["s"] < -0.15 else "⚪")
        out.append(f"{mood} {escape(TOPICS.get(r['primary_topic'], str(r['primary_topic'])))}: "
                   f"<b>{r['n']}</b> post (kayfiyat {r['s']:+.2f})")
    return "\n".join(out)


def fmt_topic(key):
    day = _day()
    name = escape(TOPICS.get(key, key))
    rows = q(f"""select channel, raw_text from posts
                 where {DAY}=%s and primary_topic=%s and {COUNTED}
                 order by relevance*ln(1+views+2*forwards) desc limit 5""", (day, key))
    if not rows:
        return f"'{name}' bo'yicha bu kun post topilmadi."
    out = [f"🗂 <b>{name} — {day}</b>\n"]
    for r in rows:
        out.append(f"• <i>{escape(str(r['channel']))}</i>: "
                   f"{escape(' '.join(str(r['raw_text']).split())[:150])}\n")
    return "\n".join(out)


# ------------------------------------------------------------- access ----------
GATE = {
    "login": "<b>UZ Economic Index</b>\nO‘zbekiston iqtisodiy yangiliklar indeksi.\n\n"
             "Kirish uchun quyidagi tugmani bosing.",
    "blocked": "Hisobingiz bloklangan. Kirish uchun administratorga murojaat qiling.",
    "expired": "Kirish muddati tugagan. Uzaytirish uchun administratorga murojaat qiling.",
}
HELP = ("<b>UZ Economic Index</b>\n\n"
        "/today — kunlik iqtisodiy manzara\n/top — kunning asosiy postlari\n"
        "/topics — mavzular kesimi\n/topic &lt;nom&gt; — bitta mavzu (masalan: /topic currency_fx)\n"
        "/app — dashboard\n/me — hisobim\n/logout — hisobdan chiqish\n/help — yordam")
OLD_ADMIN_CMDS = ("/pending", "/approve", "/setrole", "/block", "/users")


def gate(chat_id, state):
    send(chat_id, GATE[state] if WEBAPP_URL else GATE[state] + "\n\nMini App hali ulanmagan.",
         reply_markup=app_kb("Kirish"))


def fmt_me(acc):
    if acc.get("owner"):
        return "<b>Hisobim</b>\nAdmin (bot egasi)"
    until = acc["expires_at"].strftime("%d.%m.%Y") if acc.get("expires_at") else "muddatsiz"
    return (f"<b>Hisobim</b>\nLogin: <code>{escape(acc['login'])}</code>\n"
            f"Rol: {ROLE_NAMES.get(acc['role'], acc['role'])}\nAmal qiladi: {until}")


def notify_new_request(req):
    """Tell the owner-admin about a new access request."""
    if not ADMIN_ID:
        return
    name = escape(req["full_name"]) + (f" · {escape(req['organization'])}" if req.get("organization") else "")
    tg = f"@{escape(req['tg_username'])}" if req.get("tg_username") else escape(req.get("tg_name") or "")
    text = f"<b>Yangi kirish so‘rovi</b>\n{name}\n{tg} · {REASON_NAMES.get(req['reason'], '')}"
    if req.get("message"):
        text += f"\n\n{escape(req['message'])}"
    send(int(ADMIN_ID), text, reply_markup=app_kb("Admin panelini ochish", "admin"))


def deliver_credentials(req, account, password):
    """Send the new login to the requester; it works only from their Telegram account."""
    return send(req["telegram_id"],
                "<b>Kirish ma’lumoti</b>\n"
                f"Login: <code>{escape(account['login'])}</code>\n"
                f"Parol: <code>{escape(password)}</code>\n\n"
                "Kirish uchun quyidagi tugmani bosing. Login faqat shu Telegram hisobida ishlaydi.",
                reply_markup=app_kb("Kirish"))


def handle_callback(cq):
    data = cq.get("data", "")
    frm = cq["from"]
    m = cq.get("message", {})
    chat_id = m.get("chat", {}).get("id")
    mid = m.get("message_id")
    answer_cb(cq["id"])
    state, acc = who(frm)
    if state != "ok":
        gate(chat_id, state)
        return
    kb = main_kb()
    if data == "nav:today":
        edit(chat_id, mid, fmt_index(), kb)
    elif data == "nav:top":
        edit(chat_id, mid, fmt_top(8), kb)
    elif data == "nav:topics":
        edit(chat_id, mid, fmt_topics(), kb)
    elif data == "nav:chart":
        send_photo(chat_id, quickchart_url(), "<b>EAI va ESI — 30 kunlik trend</b>", kb)


def handle_update(update):
    if "callback_query" in update:
        return handle_callback(update["callback_query"])
    msg = update.get("message") or update.get("edited_message")
    if not msg or "text" not in msg or msg.get("chat", {}).get("type") != "private":
        return
    chat_id = msg["chat"]["id"]
    text = msg["text"].strip()
    cmd = text.split()[0].lower().split("@")[0] if text else ""
    state, acc = who(msg["from"])
    if state != "ok":
        gate(chat_id, state)
        return

    if cmd == "/start":
        send(chat_id, "<b>UZ Economic Index</b>\nO‘zbekiston iqtisodiy yangiliklar indeksi.\n"
                      "Quyidagi tugmalar orqali indeks, mavzular va asosiy xabarlarni ko‘ring.",
             reply_markup=main_kb()); return
    if cmd == "/help":
        send(chat_id, HELP); return
    if cmd == "/me":
        send(chat_id, fmt_me(acc)); return
    if cmd == "/logout":
        if acc.get("owner"):
            send(chat_id, "Bot egasi hisobdan chiqmaydi."); return
        auth.logout(q, msg["from"]["id"])
        gate(chat_id, "login"); return
    if cmd in OLD_ADMIN_CMDS and acc.get("is_admin"):
        send(chat_id, "Foydalanuvchilar endi Mini App’dagi admin panelida boshqariladi.",
             reply_markup=app_kb("Admin panelini ochish", "admin")); return
    if cmd == "/app":
        send(chat_id, "Dashboard:" if WEBAPP_URL else "Mini App hali ulanmagan.",
             reply_markup=main_kb()); return
    if cmd in ("/today", "/index"):
        send(chat_id, fmt_index(), reply_markup=main_kb()); return
    if cmd == "/top":
        send(chat_id, fmt_top(8)); return
    if cmd == "/topics":
        send(chat_id, fmt_topics()); return
    if cmd == "/topic":
        pp = text.split()
        if len(pp) < 2:
            send(chat_id, "Masalan: /topic currency_fx\nMavzular: " + ", ".join(TOPICS))
        else:
            send(chat_id, fmt_topic(pp[1]))
        return
    send(chat_id, "Buyruq tushunilmadi. /help")


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


def build_stats():
    """Counts of every final day and their split by topic. The Mini App sums days into
    weeks, months, quarters and years exactly as indicator.py does, so each figure equals
    the published Indekslar row (and open periods use the same arithmetic)."""
    try:
        days, chans, topics = q_many(
            ("""select period d, posts, nonad, econ, pos, neg from indices
                where period_type='kun' order by period""", None),
            (f"select {DAY}::text d, channel, count(*) n from posts where {DAY} in {FINAL_DAYS} group by 1, 2",
             None),
            (f"""select {DAY}::text d, primary_topic t, count(*) n,
                        count(*) filter (where {POS}) p, count(*) filter (where {NEG}) g
                 from posts where {COUNTED} and {DAY} in {FINAL_DAYS} group by 1, 2""", None))
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
    except psycopg.errors.UndefinedTable:
        names = channels.NAMES
    return {
        # [day, posts, nonad, econ, pos, neg, channels collected]
        "days": [[r["d"], r["posts"], r["nonad"], r["econ"], r["pos"], r["neg"], per_day.get(r["d"], 0)]
                 for r in days],
        # [index into days, topic, counted posts, positive, negative]
        "topics": [[day_ix[r["d"]], r["t"], r["n"], r["p"], r["g"]] for r in topics if r["d"] in day_ix],
        "channels": [{"id": c, "name": names.get(c, str(c).lstrip("@"))}
                     for c, _ in sorted(per_channel.items(), key=lambda x: -x[1])],
        "channels_total": len(recent_channels),
    }


_MD_LINK = re.compile(r"\[([^\]]*)\]\((?:https?|tg)://[^)]*\)")
_URL = re.compile(r"(?:https?://|t\.me/)\S+")
_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D\u20E3]")
_BOILERPLATE = re.compile(r"^(batafsil|подробнее|подробно|читайте|читать далее|obuna|подпис|subscribe|"
                          r"kanalimiz|bizni kuzating|@\w+$)", re.IGNORECASE)


def clean_text(raw, limit=420):
    """Post text for reading: no markdown, links, emoji or channel footers."""
    lines = []
    for line in _EMOJI.sub("", str(raw or "")).splitlines():
        if not re.sub(r"[\s|•·*_—–-]+", "", _URL.sub("", _MD_LINK.sub("", line))):
            continue                          # links only: "Telegram | Instagram", "Read more"
        line = re.sub(r"\*\*|__|~~|`", "", _MD_LINK.sub(r"\1", line))
        line = re.sub(r"[\s—–:|]+$", "", _URL.sub("", line)).strip()
        if line and not _BOILERPLATE.match(line):
            lines.append(line)
    # a headline has no full stop; add one so it does not run into the body
    text = " ".join(l if l[-1] in ".!?…:;»\"”)" or i == len(lines) - 1 else l + "."
                    for i, l in enumerate(lines))
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0].rstrip(".,;:—– ") + "…"


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
        where.append("primary_topic = any(%s)"); params.append(topics)
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
        items.append({"ch": r["channel"], "at": local.strftime("%Y-%m-%dT%H:%M"), "v": r["views"],
                      "t": r["primary_topic"], "s": r["tone"], "text": clean_text(r["raw_text"]),
                      "link": _post_link(r["channel"], r["message_id"])})
    return {"ok": True, "total": total, "items": items, "more": offset + len(items) < total}


# ------------------------------------------------------- Mini App actions -----
def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


ERROR_CODES = {"invalid": 401, "locked": 429, "too_many": 429, "blocked": 403, "expired": 403,
               "other_account": 403, "forbidden": 403, "not_found": 404, "no_request": 404,
               "no_account": 404, "exists": 409, "last_channel": 409, "not_channel": 404,
               "tg_unavailable": 503}


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
        elif action in ("channel_pause", "channel_resume"):
            r = channels.set_active(q, str(body.get("handle") or ""), action == "channel_resume")
        elif action == "create":
            r = auth.create_account(q, user["id"], body.get("role"), str(body.get("term")),
                                    _int(body.get("request_id")))
            req = r.pop("request", None)
            if r["ok"] and req:
                r["delivered"] = deliver_credentials(req, r["account"], r["password"])
        elif action == "reset":                      # an account, or the requester's own login
            r = auth.reset_password(q, _int(body.get("id")), user["id"], _int(body.get("request_id")))
            req = r.pop("request", None)
            if r["ok"] and req:
                r["delivered"] = deliver_credentials(req, r["account"], r["password"])
        elif action in ("block", "unblock"):
            r = auth.set_status(q, _int(body.get("id")), "blocked" if action == "block" else "active")
        elif action == "extend":
            r = auth.extend(q, _int(body.get("id")), str(body.get("term")))
        elif action in ("reject", "close"):           # close = handled, the requester is not told
            r = auth.finish_request(q, user["id"], _int(body.get("request_id")),
                                    "rejected" if action == "reject" else "done")
            req = r.pop("request", None)
            if r["ok"] and action == "reject":
                send(req["telegram_id"], "Kirish so‘rovingiz rad etildi.")
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
            if state != "ok":
                return self._json(200, {"auth": state,
                                        "request_open": auth.has_open_request(q, user["id"])})
            return self._json(200, {"auth": "ok", "me": me_json(acc), "stats": build_stats()})
        except Exception as e:
            print("data error:", repr(e))
            return self._json(500, {"error": "server"})
