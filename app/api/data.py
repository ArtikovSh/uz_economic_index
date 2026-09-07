"""
Mini App data API — Vercel Python serverless function.

The Mini App calls GET /api/data with the Telegram WebApp initData in the
`X-Telegram-Init-Data` header. This verifies that initData against the bot token
(so the caller is a real Telegram user), looks up the user's admin-approved role,
and returns role-gated dashboard JSON. RLS keeps the DB backend-only; this
function is the only way the app reads data.
"""
from http.server import BaseHTTPRequestHandler
import hashlib
import hmac
import json
import os
from urllib.parse import parse_qsl

import psycopg

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ADMIN_ID = os.getenv("BOT_ADMIN_ID", "").strip()
DB_URL = os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL") or ""
TZ = "5 hours"
FULL_ROLES = {"admin", "cb_analyst", "economist"}
TOPICS = {
    "prices_inflation": "Narx/inflatsiya", "currency_fx": "Valyuta/kurs",
    "fiscal": "Byudjet/soliq", "trade": "Tashqi savdo", "macro": "Makro",
    "banking_finance": "Bank/moliya", "labour_income": "Mehnat/daromad",
    "energy_utility": "Energetika", "business": "Biznes", "construction_realty": "Qurilish",
}


def verify_init_data(init_data):
    """Return the Telegram user dict if initData is authentic, else None."""
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


def q(sql, params=(), one=False):
    with psycopg.connect(DB_URL, prepare_threshold=None) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        if cur.description is None:
            return None
        cols = [c.name for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        return (rows[0] if rows else None) if one else rows


def role_of(uid, user):
    if ADMIN_ID and str(uid) == str(ADMIN_ID):
        return "admin", "active"
    rec = q("select role, status from app_users where telegram_id=%s", (uid,), one=True)
    if rec:
        return rec["role"], rec["status"]
    # first contact via the app -> register as pending
    q("""insert into app_users (telegram_id, username, full_name, role, status)
         values (%s,%s,%s,'public','pending') on conflict (telegram_id) do nothing""",
      (uid, user.get("username"), user.get("first_name")))
    return "public", "pending"


def build_payload(role):
    is_full = role in FULL_ROLES
    daily = q("""select date_only::text d, eai_100, esi_100, economic_messages, total_messages
                 from daily_index order by date_only desc limit 60""") or []
    daily = list(reversed(daily))
    monthly = q("""select month, eai_100, esi_100, economic_messages, total_messages
                   from monthly_index order by month""") or []
    day = q("select max(date_only) as d from daily_index", one=True)
    day = day["d"] if day else None
    topics, top = [], []
    if day:
        topics = q(f"""select primary_topic, count(*) n, round(avg(sentiment)::numeric,2) s
                       from posts where (date_utc + interval '{TZ}')::date=%s
                         and is_economic and not is_ad and not is_foreign and not is_digest
                       group by primary_topic order by n desc""", (day,)) or []
        for t in topics:
            t["name"] = TOPICS.get(t["primary_topic"], t["primary_topic"])
            t["s"] = float(t["s"])
        top = q(f"""select channel, sentiment, views, forwards, raw_text
                    from posts where (date_utc + interval '{TZ}')::date=%s
                      and is_economic and not is_ad and not is_foreign and not is_digest
                    order by relevance*ln(1+views+2*forwards) desc limit %s""",
                (day, 12 if is_full else 3)) or []
        for p in top:
            p["raw_text"] = " ".join(str(p["raw_text"]).split())[:220]
            p["sentiment"] = float(p["sentiment"])
    return {
        "role": role, "is_full": is_full, "date": str(day) if day else None,
        "latest": daily[-1] if daily else None,
        "prev": daily[-2] if len(daily) > 1 else None,
        "daily": daily, "monthly": monthly,
        "topics": topics if is_full else [], "top": top,
    }


class handler(BaseHTTPRequestHandler):
    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        init = self.headers.get("X-Telegram-Init-Data", "")
        user = verify_init_data(init)
        if not user or "id" not in user:
            return self._json(401, {"error": "unauthorized"})
        role, status = role_of(user["id"], user)
        if status != "active":
            return self._json(200, {"status": status, "role": role})
        try:
            return self._json(200, {"status": "active", **build_payload(role)})
        except Exception as e:
            print("data error:", e)
            return self._json(500, {"error": "server"})
