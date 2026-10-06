"""Integration tests for the login / admin-panel backend (app/api), against a local Postgres."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from urllib.parse import urlencode

import psycopg
import pytest

REPO_API = str(Path(__file__).resolve().parents[2] / "app" / "api")
DB = os.environ.get("TEST_DATABASE_URL")
if not DB:
    pytest.skip("TEST_DATABASE_URL is not set", allow_module_level=True)
TOKEN = "123456:TEST-TOKEN"
OWNER = 1000
os.environ.update({"SUPABASE_DB_URL": DB, "TELEGRAM_BOT_TOKEN": TOKEN, "BOT_ADMIN_ID": str(OWNER),
                   "WEBAPP_URL": "https://uzei.example.app", "WEBHOOK_SECRET": ""})
sys.path.insert(0, REPO_API)
import index  # noqa: E402
import _auth  # noqa: E402

index.API = "http://127.0.0.1:9"


def sign(user, auth_date=None, token=TOKEN):
    data = {"auth_date": str(auth_date or int(time.time())), "query_id": "AAQ",
            "user": json.dumps(user, separators=(",", ":"), ensure_ascii=False)}
    check = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


def U(uid, username=None):
    return {"id": uid, "first_name": f"User{uid}", "username": username or f"user{uid}", "language_code": "uz"}


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch):
    with psycopg.connect(DB, autocommit=True) as c:
        c.execute("drop table if exists accounts, access_requests, auth_failures cascade")
    index._SCHEMA_READY = False
    sent = []
    monkeypatch.setattr(index, "send", lambda chat, text, **kw: sent.append((chat, text, kw)) or True)
    return sent


@pytest.fixture(scope="module")
def server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), index.handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/api/index"
    srv.shutdown()


def call(url, user, action=None, body=None, init=None):
    headers = {"X-Telegram-Init-Data": init if init is not None else sign(user)}
    data = None
    if action:
        url += "?action=" + action
        data = json.dumps(body or {}).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if action else "GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def admin_create(server, role="analyst", term="30", request_id=None):
    code, r = call(server, U(OWNER), "create", {"role": role, "term": term, "request_id": request_id})
    assert code == 200 and r["ok"], r
    return r


# ------------------------------------------------------------------ units --
def test_password_hash_and_format():
    h = _auth.hash_password("K7m4-Qx2p-9Ldw")
    assert h.startswith("scrypt$") and _auth.check_password("K7m4-Qx2p-9Ldw", h)
    assert not _auth.check_password("k7m4-Qx2p-9Ldw", h) and not _auth.check_password("x", "garbage")
    pw = _auth.new_password()
    assert len(pw) == 14 and pw.count("-") == 2 and not set(pw) & set("0O1lI")


# ------------------------------------------------------------- end to end --
def test_login_binds_to_one_telegram_account(server, fresh_db):
    assert call(server, U(11))[1] == {"auth": "login", "request_open": False}
    acc = admin_create(server)
    login, pw = acc["account"]["login"], acc["password"]
    assert login == "analyst.01" and "delivered" not in acc

    code, r = call(server, U(11), "login", {"login": login, "password": pw + "x"})
    assert code == 401 and r["error"] == "invalid"
    code, r = call(server, U(11), "login", {"login": " Analyst.01 ", "password": pw})
    assert code == 200 and r == {"ok": True}
    code, r = call(server, U(11))
    assert r["auth"] == "ok" and r["me"]["login"] == login and r["me"]["role"] == "analyst"
    assert r["me"]["is_admin"] is False
    assert "T" in r["me"]["expires_at"]                             # ISO 8601: iOS Safari parses it

    code, r = call(server, U(22), "login", {"login": login, "password": pw})
    assert code == 403 and r["error"] == "other_account"           # bound to user 11

    assert call(server, U(11), "logout")[1] == {"ok": True}
    assert call(server, U(11))[1]["auth"] == "login"
    assert call(server, U(22), "login", {"login": login, "password": pw})[0] == 200  # free again


def test_failed_logins_are_rate_limited(server):
    acc = admin_create(server)
    for _ in range(5):
        assert call(server, U(33), "login", {"login": "nobody", "password": "x"})[0] == 401
    code, r = call(server, U(33), "login", {"login": acc["account"]["login"], "password": acc["password"]})
    assert code == 429 and r["error"] == "locked"                   # even the right password
    assert call(server, U(34), "login", {"login": acc["account"]["login"],
                                         "password": acc["password"]})[0] == 200


def test_access_request_reserved_account_and_delivery(server, fresh_db):
    code, r = call(server, U(44, "tahlilchi"), "request",
                   {"full_name": "  Ali   Valiyev ", "organization": "Bo‘lim", "reason": "access",
                    "message": "<b>salom</b>"})
    assert code == 200 and r == {"ok": True}
    chat, text, kw = fresh_db[-1]
    assert chat == OWNER and "Yangi kirish so‘rovi" in text and "Ali Valiyev" in text
    assert "&lt;b&gt;salom&lt;/b&gt;" in text                       # escaped for HTML mode
    assert kw["reply_markup"]["inline_keyboard"][0][0]["web_app"]["url"].endswith("/?screen=admin")
    assert call(server, U(44))[1] == {"auth": "login", "request_open": True}

    code, ov = call(server, U(OWNER), "admin")
    assert code == 200 and len(ov["requests"]) == 1 and ov["requests"][0]["full_name"] == "Ali Valiyev"
    acc = admin_create(server, role="economist", term="90", request_id=ov["requests"][0]["id"])
    assert acc["delivered"] is True and acc["account"]["login"] == "economist.01"
    chat, text, kw = fresh_db[-1]
    assert chat == 44 and acc["password"] in text and "economist.01" in text

    creds = {"login": "economist.01", "password": acc["password"]}
    assert call(server, U(55), "login", creds)[1]["error"] == "other_account"   # reserved for 44
    assert call(server, U(44), "login", creds)[0] == 200
    code, ov = call(server, U(OWNER), "admin")
    assert ov["requests"] == [] and ov["count"]["active"] == 1
    a = ov["accounts"][0]
    assert a["full_name"] == "Ali Valiyev" and a["state"] == "active" and a["bound"] is True


def test_request_limits_and_reject(server, fresh_db):
    assert call(server, U(66), "request", {"full_name": "AB"})[1]["error"] == "name"
    for _ in range(3):
        assert call(server, U(66), "request", {"full_name": "Aziz K", "reason": "zzz"})[0] == 200
    assert call(server, U(66), "request", {"full_name": "Aziz K"})[0] == 429
    ov = call(server, U(OWNER), "admin")[1]
    assert {r["reason"] for r in ov["requests"]} == {"other"}
    code, r = call(server, U(OWNER), "reject", {"request_id": ov["requests"][0]["id"]})
    assert code == 200 and fresh_db[-1][0] == 66 and "rad etildi" in fresh_db[-1][1]
    assert len(call(server, U(OWNER), "admin")[1]["requests"]) == 2
    assert call(server, U(OWNER), "reject", {"request_id": 999})[0] == 404


def test_reset_request_goes_to_the_users_own_login(server, fresh_db):
    acc = admin_create(server)
    creds = {"login": acc["account"]["login"], "password": acc["password"]}
    assert call(server, U(120), "login", creds)[0] == 200
    assert call(server, U(120), "logout")[0] == 200                 # signed out, then forgot it
    assert call(server, U(120), "request", {"full_name": "Aziz K", "reason": "reset"})[0] == 200
    rq = call(server, U(OWNER), "admin")[1]["requests"][0]
    assert rq["account"] == {"id": acc["account"]["id"], "login": creds["login"], "state": "pending"}
    code, r = call(server, U(OWNER), "reset", {"request_id": rq["id"]})
    assert code == 200 and r["delivered"] is True and r["account"]["login"] == creds["login"]
    chat, text, kw = fresh_db[-1]
    assert chat == 120 and r["password"] in text
    assert call(server, U(OWNER), "admin")[1]["requests"] == []     # closed by the reset
    new = {"login": creds["login"], "password": r["password"]}
    assert call(server, U(121), "login", new)[1]["error"] == "other_account"   # reserved for 120
    assert call(server, U(120), "login", creds)[0] == 401
    assert call(server, U(120), "login", new)[0] == 200

    assert call(server, U(122), "request", {"full_name": "Nodir B", "reason": "reset"})[0] == 200
    rq = call(server, U(OWNER), "admin")[1]["requests"][0]
    assert rq["account"] is None
    assert call(server, U(OWNER), "reset", {"request_id": rq["id"]})[1]["error"] == "no_account"
    n = len(fresh_db)
    assert call(server, U(OWNER), "close", {"request_id": rq["id"]})[0] == 200
    assert len(fresh_db) == n                                       # closed without a message
    assert call(server, U(OWNER), "admin")[1]["requests"] == []
    assert call(server, U(OWNER), "close", {"request_id": rq["id"]})[0] == 404


def test_block_expire_extend_reset(server):
    acc = admin_create(server)
    aid, creds = acc["account"]["id"], {"login": acc["account"]["login"], "password": acc["password"]}
    assert call(server, U(77), "login", creds)[0] == 200
    assert call(server, U(OWNER), "block", {"id": aid})[0] == 200
    assert call(server, U(77))[1]["auth"] == "blocked"
    assert call(server, U(OWNER), "unblock", {"id": aid})[0] == 200
    assert call(server, U(77))[1]["auth"] == "ok"
    with psycopg.connect(DB, autocommit=True) as c:
        c.execute("update accounts set expires_at = now() - interval '1 day' where id=%s", (aid,))
    assert call(server, U(77))[1]["auth"] == "expired"
    assert call(server, U(OWNER), "admin")[1]["count"]["expired"] == 1
    assert call(server, U(OWNER), "extend", {"id": aid, "term": "0"})[0] == 200
    assert call(server, U(77))[1]["auth"] == "ok"

    code, r = call(server, U(OWNER), "reset", {"id": aid})
    assert code == 200 and r["password"] != creds["password"]
    assert call(server, U(77))[1]["auth"] == "login"                # unbound by the reset
    assert call(server, U(77), "login", creds)[0] == 401
    assert call(server, U(77), "login", {"login": creds["login"], "password": r["password"]})[0] == 200


def test_admin_actions_need_an_admin(server):
    acc = admin_create(server)
    call(server, U(88), "login", {"login": acc["account"]["login"], "password": acc["password"]})
    for action in ("admin", "create", "reset", "block", "extend", "reject", "close"):
        assert call(server, U(88), action, {"id": 1, "role": "admin", "term": "0"})[0] == 403
    assert call(server, U(99), "admin")[0] == 403                   # not signed in
    adm = admin_create(server, role="admin")
    call(server, U(90), "login", {"login": adm["account"]["login"], "password": adm["password"]})
    code, ov = call(server, U(90), "admin")                         # an admin account may manage
    assert code == 200 and len(ov["accounts"]) == 2
    assert call(server, U(OWNER), "create", {"role": "boss", "term": "30"})[0] == 400
    assert call(server, U(OWNER), "nope")[0] == 400


def test_logins_are_numbered_per_role(server):
    names = [admin_create(server, role=r)["account"]["login"]
             for r in ("analyst", "analyst", "economist", "analyst")]
    assert names == ["analyst.01", "analyst.02", "economist.01", "analyst.03"]


def test_bad_or_stale_init_data(server):
    assert call(server, U(11), init="user=%7B%22id%22%3A1%7D&hash=abc")[0] == 401
    assert call(server, U(11), init=sign(U(11), auth_date=int(time.time()) - 2 * 86400))[0] == 401
    assert call(server, U(11), init=sign(U(11), token="999:OTHER"))[0] == 401
    assert call(server, U(11), "login", {"login": "a"}, init="")[0] == 401


def test_bot_gate(fresh_db, monkeypatch):
    monkeypatch.setattr(index, "fmt_index", lambda: "INDEX")
    upd = lambda uid, text: {"message": {"chat": {"id": uid, "type": "private"},
                                         "from": U(uid), "text": text}}
    index.handle_update(upd(501, "/start"))
    chat, text, kw = fresh_db[-1]
    assert chat == 501 and "Kirish uchun" in text
    assert kw["reply_markup"]["inline_keyboard"][0][0]["text"] == "Kirish"
    index.handle_update(upd(501, "/today"))
    assert "Kirish uchun" in fresh_db[-1][1]                        # every command is gated
    index.handle_update(upd(OWNER, "/today"))
    assert fresh_db[-1][1] == "INDEX"
    index.handle_update(upd(OWNER, "/approve 5 economist"))
    assert "admin panelida" in fresh_db[-1][1]
    index.handle_update({"message": {"chat": {"id": -5, "type": "group"}, "from": U(7), "text": "/start"}})
    assert fresh_db[-1][0] != -5                                    # groups are ignored
    acc = _auth.create_account(index.q, OWNER, "analyst", "30")
    assert _auth.login(index.q, U(502), acc["account"]["login"], acc["password"])["ok"]
    index.handle_update(upd(502, "/me"))
    assert "analyst.01" in fresh_db[-1][1] and "Analitik" in fresh_db[-1][1]
    index.handle_update(upd(502, "/logout"))
    assert "Kirish uchun" in fresh_db[-1][1]
    assert _auth.principal(index.q, 502, OWNER)[0] == "login"


# ---------------------------------------------------------- dashboard data --
DATA_TABLES = ("drop view if exists posts; drop table if exists labels, messages, indices, daily_index, "
               "monthly_index, subscriptions, app_users cascade")


def test_posts_need_a_signed_in_user(server):
    body = {"from": "2026-09-01", "to": "2026-09-30", "tone": "neg", "topics": ["trade"]}
    assert call(server, U(130), "posts", body)[0] == 403            # not signed in
    acc = admin_create(server)
    call(server, U(131), "login", {"login": acc["account"]["login"], "password": acc["password"]})
    code, r = call(server, U(131), "posts", body)
    assert code == 200 and r["ok"] and r["total"] >= 0
    assert call(server, U(131), "posts", {"from": "x", "to": "2026-09-30"})[0] == 400


def test_dashboard_stats_and_posts(server):
    # (channel, id, UTC time, views, topic, sentiment, economic, ad)
    posts = [
        ("@daryo", 1, "2026-09-01 20:30+00", 100, "trade", 0.5, True, False),     # 2 Sep 01:30 in Tashkent
        ("@daryo", 2, "2026-09-02 10:00+00", 300, "trade", 0.15, True, False),    # on the threshold: neutral
        ("@kunuzofficial", 3, "2026-09-02 11:00+00", 200, "fiscal", -0.4, True, False),
        ("@daryo", 4, "2026-09-02 12:00+00", 50, "non_economic", 0.0, False, False),
        ("@daryo", 5, "2026-09-02 13:00+00", 10, "business", 0.9, True, True),    # an ad is not counted
        ("@daryo", 6, "2026-09-03 09:00+00", 10, "trade", 0.9, True, False),      # a day not final yet
    ]
    schema = (Path(REPO_API).parents[1] / "db" / "schema.sql").read_text(encoding="utf-8")
    try:
        with psycopg.connect(DB, autocommit=True) as c:
            c.execute(DATA_TABLES)
            c.execute(schema)
            for ch, mid, at, views, topic, s, econ, ad in posts:
                c.execute("insert into messages values (%s,%s,%s,%s,0,%s)", (ch, mid, at, views, f"**Post {mid}**\nText."))
                c.execute("insert into labels values (%s,%s,%s,%s,0.5,%s,%s,false,false,'v4')", (ch, mid, econ, topic, s, ad))
            c.execute("""insert into indices (period_type, period, start_date, end_date, posts, nonad, econ, pos, neg)
                         values ('kun', '2026-09-02', '2026-09-02', '2026-09-02', 5, 4, 3, 1, 1)""")
        acc = admin_create(server)
        call(server, U(140), "login", {"login": acc["account"]["login"], "password": acc["password"]})

        stats = call(server, U(140))[1]["stats"]
        assert stats["days"] == [["2026-09-02", 5, 4, 3, 1, 1, 2]]         # two channels collected
        assert sorted(stats["topics"]) == [[0, "fiscal", 1, 0, 1], [0, "trade", 2, 1, 0]]
        assert stats["channels_total"] == 2

        page = lambda **kw: call(server, U(140), "posts", {"from": "2026-09-01", "to": "2026-09-30", **kw})[1]
        r = page()
        assert r["total"] == 3 and [p["link"][-1] for p in r["items"]] == ["3", "2", "1"]
        assert r["items"][2]["at"] == "2026-09-02T01:30" and r["items"][2]["text"] == "Post 1. Text."
        assert [p["s"] for p in r["items"]] == [-1, 0, 1]
        assert page(tone="neu")["total"] == 1 and page(tone="pos")["total"] == 1
        assert page(sort="views")["items"][0]["v"] == 300
        assert page(channels=["@kunuzofficial"])["total"] == 1
        assert page(topics=["trade"], count_only=True) == {"ok": True, "total": 2}
    finally:
        with psycopg.connect(DB, autocommit=True) as c:
            c.execute(DATA_TABLES)
