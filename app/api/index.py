"""
Single Vercel Python entrypoint (api/index.py) — the new Vercel runtime looks for
a default entrypoint name, so both endpoints live here and are dispatched by HTTP
method:
  * POST  /api/index  -> Telegram webhook (the bot)
  * GET   /api/index  -> Mini App data JSON (needs X-Telegram-Init-Data header),
                          or a health message in a plain browser.

Env: TELEGRAM_BOT_TOKEN, BOT_ADMIN_ID, SUPABASE_DB_URL, [WEBAPP_URL], [WEBHOOK_SECRET].
Roles: admin / cb_analyst / economist / public (full = the first three).
"""
from http.server import BaseHTTPRequestHandler
import hashlib
import hmac
import json
import os
from urllib.parse import parse_qsl

import psycopg
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ADMIN_ID = os.getenv("BOT_ADMIN_ID", "").strip()
DB_URL = os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL") or ""
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
TZ = "5 hours"
FULL_ROLES = {"admin", "cb_analyst", "economist"}
ROLE_NAMES = {"admin": "Admin", "cb_analyst": "MB analitigi", "economist": "Iqtisodchi",
              "public": "Ommaviy"}
TOPICS = {
    "prices_inflation": "Narx/inflatsiya", "currency_fx": "Valyuta/kurs",
    "fiscal": "Byudjet/soliq", "trade": "Tashqi savdo", "macro": "Makro",
    "banking_finance": "Bank/moliya", "labour_income": "Mehnat/daromad",
    "energy_utility": "Energetika", "business": "Biznes", "construction_realty": "Qurilish",
}


# ------------------------------------------------------------------ database ---
def q(sql, params=(), one=False):
    with psycopg.connect(DB_URL, prepare_threshold=None) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        if cur.description is None:
            return None
        cols = [c.name for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        return (rows[0] if rows else None) if one else rows


def get_or_create_user(uid, user):
    if ADMIN_ID and str(uid) == str(ADMIN_ID):
        return "admin", "active"
    rec = q("select role, status from app_users where telegram_id=%s", (uid,), one=True)
    if rec:
        return rec["role"], rec["status"]
    q("""insert into app_users (telegram_id, username, full_name, role, status)
         values (%s,%s,%s,'public','pending') on conflict (telegram_id) do nothing""",
      (uid, user.get("username"),
       " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))))
    return "public", "pending"


# ------------------------------------------------------------------- telegram --
def send(chat_id, text, **kw):
    if not BOT_TOKEN:
        print("SEND SKIPPED: TELEGRAM_BOT_TOKEN is empty"); return
    try:
        r = requests.post(f"{API}/sendMessage", timeout=15, json={
            "chat_id": chat_id, "text": text, "parse_mode": "HTML",
            "disable_web_page_preview": True, **kw})
        if not r.ok:
            print(f"Telegram sendMessage FAILED {r.status_code}: {r.text[:300]}")
    except Exception as e:
        print("send error:", e)


def app_kb():
    if not WEBAPP_URL:
        return None
    return {"inline_keyboard": [[{"text": "📊 Dashboard (Mini App)",
                                  "web_app": {"url": WEBAPP_URL}}]]}


# --------------------------------------------------------------------- stats ---
def _day():
    r = q("select max(date_only) as d from daily_index", one=True)
    return r["d"] if r else None


def fmt_index():
    rows = q("select * from daily_index order by date_only desc limit 2")
    if not rows:
        return "Hozircha ma'lumot yo'q. Quvur birinchi kunni yig'ishini kuting."
    d = rows[0]
    prev = rows[1] if len(rows) > 1 else None
    chg = ""
    if prev and prev.get("eai_100") is not None:
        chg = (f"\nO'zgarish: e'tibor {(d['eai_100'] or 0) - (prev['eai_100'] or 0):+.0f}, "
               f"kayfiyat {(d['esi_100'] or 0) - (prev['esi_100'] or 0):+.0f} (oldingi kunga)")
    return (f"📊 <b>{d['date_only']} (Toshkent)</b>\n"
            f"E'tibor indeksi (EAI): <b>{d['eai_100']:.0f}</b> (o'rtacha=100)\n"
            f"Kayfiyat indeksi (ESI): <b>{d['esi_100']:.0f}</b> (50=neytral)\n"
            f"Iqtisodiy xabarlar: {d['economic_messages']}/{d['total_messages']}{chg}")


def fmt_top(n):
    day = _day()
    if not day:
        return "Ma'lumot yo'q."
    rows = q(f"""select channel, sentiment, views, raw_text from posts
                 where (date_utc + interval '{TZ}')::date=%s
                   and is_economic and not is_ad and not is_foreign and not is_digest
                 order by relevance*ln(1+views+2*forwards) desc limit %s""", (day, n))
    if not rows:
        return "Bu kun uchun iqtisodiy post topilmadi."
    out = [f"🔝 <b>Top {len(rows)} iqtisodiy post — {day}</b>\n"]
    for i, r in enumerate(rows, 1):
        t = " ".join(str(r["raw_text"]).split())[:160]
        mood = "🟢" if r["sentiment"] > 0.15 else ("🔴" if r["sentiment"] < -0.15 else "⚪")
        out.append(f"{i}. {mood} <i>{r['channel']}</i> · 👁{r['views']}\n{t}\n")
    return "\n".join(out)


def fmt_topics():
    day = _day()
    rows = q(f"""select primary_topic, count(*) n, round(avg(sentiment)::numeric,2) s
                 from posts where (date_utc + interval '{TZ}')::date=%s
                   and is_economic and not is_ad and not is_foreign and not is_digest
                 group by primary_topic order by n desc""", (day,))
    if not rows:
        return "Ma'lumot yo'q."
    out = [f"🗂 <b>Mavzular — {day}</b>\n"]
    for r in rows:
        mood = "🟢" if r["s"] > 0.15 else ("🔴" if r["s"] < -0.15 else "⚪")
        out.append(f"{mood} {TOPICS.get(r['primary_topic'], r['primary_topic'])}: "
                   f"<b>{r['n']}</b> post (kayfiyat {r['s']:+.2f})")
    return "\n".join(out)


def fmt_topic(key):
    day = _day()
    rows = q(f"""select channel, raw_text from posts
                 where (date_utc + interval '{TZ}')::date=%s and primary_topic=%s
                   and is_economic and not is_ad and not is_foreign and not is_digest
                 order by relevance*ln(1+views+2*forwards) desc limit 5""", (day, key))
    if not rows:
        return f"'{TOPICS.get(key, key)}' bo'yicha bu kun post topilmadi."
    out = [f"🗂 <b>{TOPICS.get(key, key)} — {day}</b>\n"]
    for r in rows:
        out.append(f"• <i>{r['channel']}</i>: {' '.join(str(r['raw_text']).split())[:150]}\n")
    return "\n".join(out)


# ------------------------------------------------------------------ admin -------
def admin_cmd(text):
    p = text.split()
    c = p[0]
    if c == "/pending":
        rows = q("select telegram_id, username, full_name from app_users where status='pending'")
        return ("Kutayotgan foydalanuvchi yo'q." if not rows else
                "⏳ <b>Tasdiq kutayotganlar:</b>\n" + "\n".join(
                    f"{r['telegram_id']} — {r.get('full_name') or ''} @{r.get('username') or ''}" for r in rows))
    if c == "/users":
        rows = q("select telegram_id, role, status from app_users order by created_at desc limit 30")
        return "👥 <b>Foydalanuvchilar:</b>\n" + "\n".join(
            f"{r['telegram_id']} — {ROLE_NAMES.get(r['role'], r['role'])} ({r['status']})" for r in rows)
    if c in ("/approve", "/setrole") and len(p) >= 3 and p[2] in ROLE_NAMES:
        q("""insert into app_users (telegram_id, role, status, approved_at)
             values (%s,%s,'active', now())
             on conflict (telegram_id) do update set role=excluded.role, status='active', approved_at=now()""",
          (int(p[1]), p[2]))
        send(int(p[1]), f"✅ Sizga <b>{ROLE_NAMES[p[2]]}</b> roli berildi. /today bilan boshlang.")
        return f"✅ {p[1]} → {ROLE_NAMES[p[2]]} (active)"
    if c in ("/approve", "/setrole"):
        return "Rol: cb_analyst | economist | public | admin"
    if c == "/block" and len(p) >= 2:
        q("update app_users set status='blocked' where telegram_id=%s", (int(p[1]),))
        return f"🚫 {p[1]} bloklandi."
    return None


HELP = ("🤖 <b>UZ Economic Index bot</b>\n\n"
        "/today — kunlik iqtisodiy manzara\n/index — sarlavha indekslar\n"
        "/top — kunning top postlari\n/topics — mavzular kesimi\n"
        "/topic &lt;nom&gt; — bitta mavzu (masalan: /topic currency_fx)\n"
        "/app — Dashboard (Mini App)\n/me — mening rolim\n/help — yordam")
ADMIN_HELP = ("\n\n<b>Admin:</b>\n/pending\n/approve &lt;id&gt; &lt;rol&gt;\n"
              "/setrole &lt;id&gt; &lt;rol&gt;\n/block &lt;id&gt;\n/users")


def handle_update(update):
    msg = update.get("message") or update.get("edited_message")
    if not msg or "text" not in msg:
        return
    chat_id = msg["chat"]["id"]
    text = msg["text"].strip()
    frm = msg["from"]
    role, status = get_or_create_user(frm["id"], frm)
    is_admin = role == "admin"
    is_full = role in FULL_ROLES
    cmd = text.split()[0].lower().split("@")[0]

    if cmd == "/start":
        if status == "pending":
            send(chat_id, "👋 Xush kelibsiz! Arizangiz qabul qilindi — admin tasdig'ini kuting.\n\n" + HELP)
            if ADMIN_ID:
                send(int(ADMIN_ID), f"🔔 Yangi foydalanuvchi: {frm['id']} @{frm.get('username','')} "
                                    f"— /approve {frm['id']} economist")
        else:
            send(chat_id, HELP + (ADMIN_HELP if is_admin else ""), reply_markup=app_kb())
        return
    if cmd == "/help":
        send(chat_id, HELP + (ADMIN_HELP if is_admin else "")); return
    if cmd == "/me":
        send(chat_id, f"🆔 {frm['id']}\nRol: <b>{ROLE_NAMES.get(role, role)}</b>\nHolat: {status}"); return

    if is_admin:
        r = admin_cmd(text)
        if r is not None:
            send(chat_id, r); return

    if status == "blocked":
        send(chat_id, "🚫 Kirish bloklangan."); return
    if status == "pending":
        send(chat_id, "⏳ Hisobingiz hali tasdiqlanmagan. Admin tasdig'ini kuting."); return

    if cmd == "/app":
        send(chat_id, "📊 Dashboard:" if WEBAPP_URL else "Mini App hali ulanmagan.", reply_markup=app_kb()); return
    if cmd in ("/today", "/index"):
        send(chat_id, fmt_index(), reply_markup=app_kb()); return
    if cmd == "/top":
        send(chat_id, fmt_top(8 if is_full else 3)); return
    if cmd == "/topics":
        send(chat_id, fmt_topics() if is_full else "Bu bo'lim to'liq rol uchun."); return
    if cmd == "/topic":
        pp = text.split()
        if len(pp) < 2:
            send(chat_id, "Masalan: /topic currency_fx\nMavzular: " + ", ".join(TOPICS))
        elif not is_full:
            send(chat_id, "Bu bo'lim to'liq rol uchun.")
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
        return json.loads(pairs.get("user", "{}"))
    except Exception:
        return None


def build_payload(role):
    is_full = role in FULL_ROLES
    daily = q("""select date_only::text d, eai_100, esi_100, economic_messages, total_messages
                 from daily_index order by date_only desc limit 60""") or []
    daily = list(reversed(daily))
    monthly = q("""select month, eai_100, esi_100 from monthly_index order by month""") or []
    day = _day()
    topics, top = [], []
    if day:
        topics = q(f"""select primary_topic, count(*) n, round(avg(sentiment)::numeric,2) s
                       from posts where (date_utc + interval '{TZ}')::date=%s
                         and is_economic and not is_ad and not is_foreign and not is_digest
                       group by primary_topic order by n desc""", (day,)) or []
        for t in topics:
            t["name"] = TOPICS.get(t["primary_topic"], t["primary_topic"])
            t["s"] = float(t["s"])
        top = q(f"""select channel, sentiment, views, raw_text from posts
                    where (date_utc + interval '{TZ}')::date=%s
                      and is_economic and not is_ad and not is_foreign and not is_digest
                    order by relevance*ln(1+views+2*forwards) desc limit %s""",
                (day, 12 if is_full else 3)) or []
        for p in top:
            p["raw_text"] = " ".join(str(p["raw_text"]).split())[:220]
            p["sentiment"] = float(p["sentiment"])
    return {"role": role, "is_full": is_full, "date": str(day) if day else None,
            "latest": daily[-1] if daily else None,
            "prev": daily[-2] if len(daily) > 1 else None,
            "daily": daily, "monthly": monthly,
            "topics": topics if is_full else [], "top": top}


# ------------------------------------------------------ Vercel entry point -----
class handler(BaseHTTPRequestHandler):
    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if WEBHOOK_SECRET and self.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
            self.send_response(401); self.end_headers(); self.wfile.write(b"unauthorized"); return
        try:
            n = int(self.headers.get("content-length", 0))
            update = json.loads(self.rfile.read(n) or b"{}")
            msg = update.get("message") or {}
            print(f"UPDATE from {msg.get('from', {}).get('id')}: {msg.get('text')!r} "
                  f"| token={'set' if BOT_TOKEN else 'MISSING'} db={'set' if DB_URL else 'MISSING'} "
                  f"admin={ADMIN_ID or 'MISSING'}")
            handle_update(update)
        except Exception as e:
            import traceback
            print("HANDLE ERROR:", repr(e))
            traceback.print_exc()
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")

    def do_GET(self):
        init = self.headers.get("X-Telegram-Init-Data", "")
        if not init:
            self.send_response(200); self.end_headers()
            self.wfile.write(b"UZ Economic Index bot is running.")
            return
        user = verify_init_data(init)
        if not user or "id" not in user:
            return self._json(401, {"error": "unauthorized"})
        role, status = get_or_create_user(user["id"], user)
        if status != "active":
            return self._json(200, {"status": status, "role": role})
        try:
            return self._json(200, {"status": "active", **build_payload(role)})
        except Exception as e:
            print("data error:", e)
            return self._json(500, {"error": "server"})
