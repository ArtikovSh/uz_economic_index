"""
Telegram bot — Vercel Python serverless webhook.

Self-contained: reads the Supabase Postgres DB (SUPABASE_DB_URL), enforces
admin-approved roles, and replies via the Telegram Bot API. Deploy on Vercel with
Root Directory = app/. Set the webhook to https://<app>.vercel.app/api/bot.

Env: TELEGRAM_BOT_TOKEN, BOT_ADMIN_ID, SUPABASE_DB_URL, [WEBHOOK_SECRET].
Roles: admin / cb_analyst / economist / public (full = the first three).
"""
from http.server import BaseHTTPRequestHandler
import json
import os

import psycopg
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ADMIN_ID = os.getenv("BOT_ADMIN_ID", "").strip()
DB_URL = os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL") or ""
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


# ----------------------------------------------------------------- telegram ----
def send(chat_id, text, **kw):
    try:
        requests.post(f"{API}/sendMessage", timeout=15, json={
            "chat_id": chat_id, "text": text, "parse_mode": "HTML",
            "disable_web_page_preview": True, **kw})
    except Exception as e:
        print("send error:", e)


# ----------------------------------------------------------------- database ----
def q(sql, params=(), one=False):
    with psycopg.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        if cur.description is None:
            return None
        cols = [c.name for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        return (rows[0] if rows else None) if one else rows


def get_user(uid):
    if ADMIN_ID and str(uid) == str(ADMIN_ID):
        return {"telegram_id": uid, "role": "admin", "status": "active"}
    return q("select telegram_id, role, status from app_users where telegram_id=%s",
             (uid,), one=True)


def ensure_user(u):
    """Insert a new user as pending; return the (possibly new) record."""
    existing = get_user(u["id"])
    if existing:
        return existing
    q("""insert into app_users (telegram_id, username, full_name, role, status)
         values (%s,%s,%s,'public','pending') on conflict (telegram_id) do nothing""",
      (u["id"], u.get("username"), " ".join(filter(None, [u.get("first_name"), u.get("last_name")]))))
    return {"telegram_id": u["id"], "role": "public", "status": "pending"}


# ------------------------------------------------------------------- stats -----
def latest_daily():
    return q("select * from daily_index order by date_only desc limit 2")


def fmt_index():
    rows = latest_daily()
    if not rows:
        return "Hozircha ma'lumot yo'q. Quvur birinchi kunni yig'ishini kuting."
    d = rows[0]
    prev = rows[1] if len(rows) > 1 else None
    darrow = ""
    if prev and prev.get("eai_100") is not None:
        de = (d["eai_100"] or 0) - (prev["eai_100"] or 0)
        ds = (d["esi_100"] or 0) - (prev["esi_100"] or 0)
        darrow = f"\nO'zgarish: e'tibor {de:+.0f}, kayfiyat {ds:+.0f} (oldingi kunga)"
    return (f"📊 <b>{d['date_only']} (Toshkent)</b>\n"
            f"E'tibor indeksi (EAI): <b>{d['eai_100']:.0f}</b> (o'rtacha=100)\n"
            f"Kayfiyat indeksi (ESI): <b>{d['esi_100']:.0f}</b> (50=neytral)\n"
            f"Iqtisodiy xabarlar: {d['economic_messages']}/{d['total_messages']}"
            f"{darrow}")


def _day():
    r = q("select max(date_only) as d from daily_index", one=True)
    return r["d"] if r else None


def fmt_top(n):
    day = _day()
    if not day:
        return "Ma'lumot yo'q."
    rows = q(f"""
        select channel, sentiment, relevance, views, forwards, raw_text
        from posts
        where (date_utc + interval '{TZ}')::date = %s
          and is_economic and not is_ad and not is_foreign and not is_digest
        order by relevance * ln(1 + views + 2*forwards) desc
        limit %s""", (day, n))
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
    rows = q(f"""
        select primary_topic, count(*) n, round(avg(sentiment)::numeric,2) s
        from posts
        where (date_utc + interval '{TZ}')::date = %s
          and is_economic and not is_ad and not is_foreign and not is_digest
        group by primary_topic order by n desc""", (day,))
    if not rows:
        return "Ma'lumot yo'q."
    out = [f"🗂 <b>Mavzular — {day}</b>\n"]
    for r in rows:
        name = TOPICS.get(r["primary_topic"], r["primary_topic"])
        mood = "🟢" if r["s"] > 0.15 else ("🔴" if r["s"] < -0.15 else "⚪")
        out.append(f"{mood} {name}: <b>{r['n']}</b> post (kayfiyat {r['s']:+.2f})")
    return "\n".join(out)


def fmt_topic(key):
    day = _day()
    rows = q(f"""
        select channel, sentiment, views, raw_text from posts
        where (date_utc + interval '{TZ}')::date=%s and primary_topic=%s
          and is_economic and not is_ad and not is_foreign and not is_digest
        order by relevance*ln(1+views+2*forwards) desc limit 5""", (day, key))
    if not rows:
        return f"'{TOPICS.get(key, key)}' bo'yicha bu kun post topilmadi."
    out = [f"🗂 <b>{TOPICS.get(key, key)} — {day}</b>\n"]
    for r in rows:
        t = " ".join(str(r["raw_text"]).split())[:150]
        out.append(f"• <i>{r['channel']}</i>: {t}\n")
    return "\n".join(out)


# ------------------------------------------------------------------ admin -------
def admin_cmd(text):
    parts = text.split()
    cmd = parts[0]
    if cmd == "/pending":
        rows = q("select telegram_id, username, full_name from app_users where status='pending'")
        if not rows:
            return "Kutayotgan foydalanuvchi yo'q."
        return "⏳ <b>Tasdiq kutayotganlar:</b>\n" + "\n".join(
            f"{r['telegram_id']} — {r.get('full_name') or ''} @{r.get('username') or ''}" for r in rows)
    if cmd == "/users":
        rows = q("select telegram_id, role, status from app_users order by created_at desc limit 30")
        return "👥 <b>Foydalanuvchilar:</b>\n" + "\n".join(
            f"{r['telegram_id']} — {ROLE_NAMES.get(r['role'], r['role'])} ({r['status']})" for r in rows)
    if cmd in ("/approve", "/setrole") and len(parts) >= 3:
        uid, role = parts[1], parts[2]
        if role not in ("cb_analyst", "economist", "public", "admin"):
            return "Rol: cb_analyst | economist | public | admin"
        q("""insert into app_users (telegram_id, role, status, approved_at)
             values (%s,%s,'active', now())
             on conflict (telegram_id) do update set role=excluded.role, status='active', approved_at=now()""",
          (int(uid), role))
        send(int(uid), f"✅ Sizga <b>{ROLE_NAMES.get(role, role)}</b> roli berildi. /today bilan boshlang.")
        return f"✅ {uid} → {ROLE_NAMES.get(role, role)} (active)"
    if cmd == "/block" and len(parts) >= 2:
        q("update app_users set status='blocked' where telegram_id=%s", (int(parts[1]),))
        return f"🚫 {parts[1]} bloklandi."
    return None


# --------------------------------------------------------------- dispatch ------
HELP = ("🤖 <b>UZ Economic Index bot</b>\n\n"
        "/today — kunlik iqtisodiy manzara\n"
        "/index — sarlavha indekslar (EAI/ESI)\n"
        "/top — kunning top iqtisodiy postlari\n"
        "/topics — mavzular kesimi\n"
        "/topic &lt;nom&gt; — bitta mavzu (masalan: /topic currency_fx)\n"
        "/me — mening rolim\n/help — yordam")

ADMIN_HELP = ("\n\n<b>Admin:</b>\n/pending — kutayotganlar\n/approve &lt;id&gt; &lt;rol&gt;\n"
              "/setrole &lt;id&gt; &lt;rol&gt;\n/block &lt;id&gt;\n/users")


def handle_update(update):
    msg = update.get("message") or update.get("edited_message")
    if not msg or "text" not in msg:
        return
    chat_id = msg["chat"]["id"]
    text = msg["text"].strip()
    frm = msg["from"]
    user = ensure_user(frm)
    role, status = user["role"], user["status"]
    is_admin = role == "admin"
    is_full = role in FULL_ROLES
    cmd = text.split()[0].lower().split("@")[0]

    if cmd == "/start":
        if status == "pending":
            send(chat_id, "👋 Xush kelibsiz! Arizangiz qabul qilindi — admin tasdig'ini "
                          "kuting. Tasdiqlangach xabar beramiz.\n\n" + HELP)
            if ADMIN_ID:
                send(int(ADMIN_ID), f"🔔 Yangi foydalanuvchi: {frm['id']} "
                                    f"@{frm.get('username','')} — /approve {frm['id']} economist")
        else:
            send(chat_id, HELP + (ADMIN_HELP if is_admin else ""))
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

    # active users
    if cmd == "/today" or cmd == "/index":
        send(chat_id, fmt_index()); return
    if cmd == "/top":
        send(chat_id, fmt_top(8 if is_full else 3)); return
    if cmd == "/topics":
        send(chat_id, fmt_topics() if is_full else "Bu bo'lim to'liq rol uchun. /today ni sinang."); return
    if cmd == "/topic":
        parts = text.split()
        if len(parts) < 2:
            send(chat_id, "Masalan: /topic currency_fx\nMavzular: " + ", ".join(TOPICS)); return
        if not is_full:
            send(chat_id, "Bu bo'lim to'liq rol uchun."); return
        send(chat_id, fmt_topic(parts[1])); return
    send(chat_id, "Buyruq tushunilmadi. /help")


# ------------------------------------------------------ Vercel entry point -----
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if WEBHOOK_SECRET and self.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
            self.send_response(401); self.end_headers(); self.wfile.write(b"unauthorized"); return
        try:
            n = int(self.headers.get("content-length", 0))
            update = json.loads(self.rfile.read(n) or b"{}")
            handle_update(update)
        except Exception as e:
            print("handle error:", e)
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")

    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"UZ Economic Index bot is running.")
