"""Integration tests for the login / admin-panel backend (app/api), against a local Postgres."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import sys
import threading
import time
from datetime import date
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
        c.execute("drop table if exists accounts, access_requests, auth_failures, channels, "
                  "bot_users, bot_settings, bot_cards cascade")
    index._SCHEMA_READY = False
    index._EMOJI_IDS = None
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
    assert call(server, U(11))[1] == {"auth": "login", "lang": None, "request_open": False}
    acc = admin_create(server)
    login, pw = acc["account"]["login"], acc["password"]
    assert login == "analyst.01" and "delivered" not in acc

    code, r = call(server, U(11), "login", {"login": login, "password": pw + "x"})
    assert code == 401 and r["error"] == "invalid"
    code, r = call(server, U(11), "login", {"login": " Analyst.01 ", "password": pw})
    assert code == 200 and r == {"ok": True}
    chat, text, kw = fresh_db[-1]                                   # the bot confirms in the chat
    assert chat == 11 and "Hisob faollashtirildi" in text and login in text
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
    assert chat == OWNER and "Yangi murojaat" in text and "Ali Valiyev" in text
    assert "&lt;b&gt;salom&lt;/b&gt;" in text                       # escaped for HTML mode
    assert kw["reply_markup"]["inline_keyboard"][0][0]["web_app"]["url"].endswith("/?screen=requests")
    assert call(server, U(44))[1] == {"auth": "login", "lang": None, "request_open": True}

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


# -------------------------------------------------------------- the bot --
def upd(uid, text, lang="uz"):
    return {"message": {"chat": {"id": uid, "type": "private"}, "from": {**U(uid), "language_code": lang},
                        "text": text}}


def press(uid, data, mid=7):
    return {"callback_query": {"id": "cb", "data": data, "from": U(uid),
                               "message": {"message_id": mid, "chat": {"id": uid}}}}


def test_bot_first_visit_language_and_gate(fresh_db, monkeypatch):
    edits = []
    monkeypatch.setattr(index, "edit", lambda chat, mid, text, kb=None: edits.append((chat, text, kb)))
    monkeypatch.setattr(index, "answer_cb", lambda cb_id, text=None: None)
    index.handle_update(upd(501, "/start", lang="ru"))
    chat, text, kw = fresh_db[-1]                                   # first visit: about + language choice
    assert chat == 501 and "Индекс экономических новостей" in text and "Choose a language" in text
    assert [b["callback_data"] for b in kw["reply_markup"]["inline_keyboard"][0]] == ["lang:uz:w", "lang:ru:w", "lang:en:w"]
    index.handle_update(press(501, "lang:en:w"))
    assert "Uzbekistan economic news index" in edits[-1][1] and "Choose" not in edits[-1][1]
    chat, text, kw = fresh_db[-1]                                   # then how to sign in, in English
    assert chat == 501 and "Sign in" in text
    button = kw["reply_markup"]["inline_keyboard"][0][0]
    assert button["text"] == "Sign in" and button["style"] == "primary" and "icon_custom_emoji_id" not in button
    index.handle_update(upd(501, "/today"))
    assert "Sign in" in fresh_db[-1][1]                             # every command is gated
    index.handle_update(upd(501, "/start"))
    assert "Sign in" in fresh_db[-1][1]                             # the language is remembered
    index.handle_update({"message": {"chat": {"id": -5, "type": "group"}, "from": U(7), "text": "/start"}})
    assert fresh_db[-1][0] != -5                                    # groups are ignored
    assert not any(ord(ch) > 0x2600 for _, t, _ in fresh_db for ch in t)   # no emoji without Premium icons


def test_bot_account_commands(fresh_db, monkeypatch):
    edits, answers = [], []
    monkeypatch.setattr(index, "edit", lambda chat, mid, text, kb=None: edits.append((chat, text, kb)))
    monkeypatch.setattr(index, "answer_cb", lambda cb_id, text=None: answers.append(text))
    index.handle_update(upd(OWNER, "/approve 5 economist"))
    assert "admin panelida" in fresh_db[-1][1]
    acc = _auth.create_account(index.q, OWNER, "analyst", "30")
    assert _auth.login(index.q, U(502), acc["account"]["login"], acc["password"])["ok"]
    index.handle_update(upd(502, "/me"))
    chat, text, kw = fresh_db[-1]
    assert "analyst.01" in text and "Analitik" in text and "Kunlik xulosa: yoqilgan" in text
    index.handle_update(press(502, "me:digest"))
    assert answers[-1] == "Kunlik xulosa o‘chirildi" and "o‘chirilgan" in edits[-1][1]
    assert index.bot.user_row(index.q, 502)["digest"] is False
    index.handle_update(press(502, "me:lang"))
    index.handle_update(press(502, "lang:ru:m"))
    assert "Мой аккаунт" in edits[-1][1] and "Итоги дня: выключены" in edits[-1][1]
    index.handle_update(upd(502, "/help"))
    assert "/week" in fresh_db[-1][1] and "Команды" in fresh_db[-1][1]
    index.handle_update(upd(502, "/today"))
    assert fresh_db[-1][1] == "Данных пока нет."                   # no index rows in this database
    index.handle_update(press(502, "me:logout"))
    assert "Выйти из аккаунта?" in edits[-1][1]
    index.handle_update(press(502, "me:out"))
    assert "Вход" in edits[-1][1] and _auth.principal(index.q, 502, OWNER)[0] == "login"
    index.handle_update(upd(OWNER, "/logout"))
    assert "Bot egasi" in fresh_db[-1][1]


def test_bot_owner_sees_setup_only(fresh_db, monkeypatch):
    ran = []
    monkeypatch.setattr(index, "setup", lambda chat, lang: ran.append((chat, lang)))
    index.ensure_schema()
    acc = _auth.create_account(index.q, OWNER, "admin", "30")
    assert _auth.login(index.q, U(503), acc["account"]["login"], acc["password"])["ok"]
    index.handle_update(upd(503, "/setup"))
    assert ran == [] and "tushunilmadi" in fresh_db[-1][1]          # an admin account is not the owner
    index.handle_update(upd(OWNER, "/setup"))
    assert ran == [(OWNER, "uz")]


def test_admin_types_login_and_password(server, fresh_db):
    admin = lambda action, body=None: call(server, U(OWNER), action, body)
    assert _auth.password_problems("short1") == ["length"]
    assert _auth.password_problems("only letters here", "x") == ["mix", "space"]
    assert _auth.password_problems("Karimov2026", "karimov") == ["login"]
    assert _auth.password_problems("Пароль2026") == []                 # any alphabet counts as letters

    assert admin("check_login", {"login": " A.Karimov "})[1] == {"ok": True, "state": "free"}
    for bad in ("ab", "1abc", "a b c", "admin", "x" * 40, "ali@uz"):
        assert admin("check_login", {"login": bad})[1]["state"] == "bad", bad
    code, r = admin("create", {"role": "economist", "term": "90", "login": "A.Karimov", "password": "Sirli-parol7"})
    assert code == 200 and r["account"]["login"] == "a.karimov" and r["password"] == "Sirli-parol7"
    assert admin("check_login", {"login": "a.karimov"})[1]["state"] == "taken"
    assert admin("create", {"role": "analyst", "term": "30", "login": "a.karimov"}) == (409, {"ok": False, "error": "login_taken"})
    assert admin("create", {"role": "analyst", "term": "30", "login": "1x"})[1]["error"] == "bad_login"
    assert admin("create", {"role": "analyst", "term": "30", "password": "weak"})[1]["error"] == "weak_password"
    assert admin("create", {"role": "analyst", "term": "30", "login": "b.ali", "password": "b.ali-2026x"})[1]["error"] == "weak_password"
    assert call(server, U(301), "login", {"login": "a.karimov", "password": "Sirli-parol7"})[0] == 200

    ov = admin("admin")[1]
    assert ov["next_login"] == {"analyst": "analyst.01", "economist": "economist.01", "admin": "admin.01"}
    aid = ov["accounts"][0]["id"]
    assert admin("reset", {"id": aid, "password": "a.karimov99"})[1]["error"] == "weak_password"
    code, r = admin("reset", {"id": aid, "password": "Yangi-parol8"})
    assert code == 200 and r["password"] == "Yangi-parol8"
    assert call(server, U(301), "login", {"login": "a.karimov", "password": "Yangi-parol8"})[0] == 200


def test_extend_counts_from_the_current_end(server):
    acc = admin_create(server, term="90")
    aid = acc["account"]["id"]
    until = lambda: call(server, U(OWNER), "admin")[1]["accounts"][0]["expires_at"][:10]
    first = until()
    assert call(server, U(OWNER), "extend", {"id": aid, "term": "30"})[0] == 200
    days = (date.fromisoformat(until()) - date.fromisoformat(first)).days
    assert days == 30                                               # 90 + 30 days, not 30 from today
    with psycopg.connect(DB, autocommit=True) as c:
        c.execute("update accounts set expires_at = now() - interval '10 days' where id=%s", (aid,))
    assert call(server, U(OWNER), "extend", {"id": aid, "term": "30"})[0] == 200
    assert (date.fromisoformat(until()) - date.today()).days in (29, 30, 31)   # expired: from today


def test_requests_history_and_language(server, fresh_db):
    assert call(server, U(70), "request", {"full_name": "Aziz K"})[0] == 200
    rq = call(server, U(OWNER), "admin")[1]["requests"][0]
    assert call(server, U(OWNER), "close", {"request_id": rq["id"]})[0] == 200
    ov = call(server, U(OWNER), "admin")[1]
    assert ov["requests"] == [] and [(h["full_name"], h["status"]) for h in ov["handled"]] == [("Aziz K", "done")]

    assert call(server, U(71), "lang", {"lang": "ru"})[1] == {"ok": True}      # before signing in too
    assert call(server, U(71), "lang", {"lang": "de"})[0] == 400
    assert call(server, U(71))[1]["lang"] == "ru"
    assert call(server, U(71), "request", {"full_name": "Olga P"})[0] == 200
    rq = call(server, U(OWNER), "admin")[1]["requests"][0]
    assert call(server, U(OWNER), "reject", {"request_id": rq["id"]})[0] == 200
    assert fresh_db[-1] == (71, "Ваш запрос на доступ отклонён.", {})


def test_summaries_and_morning_digest(server, fresh_db, monkeypatch):
    schema = (Path(REPO_API).parents[1] / "db" / "schema.sql").read_text(encoding="utf-8")
    try:
        with psycopg.connect(DB, autocommit=True) as c:
            c.execute(DATA_TABLES)
            c.execute(schema)
            for ch, mid, at, topic, s in [("@daryo", 1, "2026-10-04 06:00+00", "trade", 0.6),
                                          ("@daryo", 2, "2026-10-04 07:00+00", "prices_inflation", -0.5),
                                          ("@kunuzofficial", 3, "2026-10-04 08:00+00", "trade", 0.4)]:
                c.execute("insert into messages values (%s,%s,%s,100,0,%s)", (ch, mid, at, f"Post {mid}"))
                c.execute("insert into labels values (%s,%s,true,%s,0.5,%s,false,false,false,'v5')", (ch, mid, topic, s))
            c.execute("""insert into indices (period_type, period, start_date, end_date, days, days_expected,
                                              posts, nonad, econ, pos, neg, eai, esi) values
                         ('kun', '2026-10-03', '2026-10-03', '2026-10-03', 1, 1, 10, 9, 4, 2, 1, 44.4, 25),
                         ('kun', '2026-10-04', '2026-10-04', '2026-10-04', 1, 1, 8, 6, 3, 2, 1, 50, 33.3),
                         ('hafta', '2026-W40', '2026-09-28', '2026-10-04', 2, 7, 18, 15, 7, 4, 2, 46.7, 28.6)""")
        day = index.bot.summary(index.q, "kun")
        assert (day["start"], day["d_eai"], day["d_esi"], day["channels"]) == ("2026-10-04", 5.6, 8.3, 2)
        assert [x["start"] for x in day["series"]] == ["2026-10-03", "2026-10-04"]    # no leading gap
        assert [(x["t"], x["n"]) for x in day["topics"]] == [("trade", 2), ("prices_inflation", 1)]
        text = index.bot.caption(day, "uz")
        assert "Kunlik xulosa · 4-oktabr 2026" in text and "<b>50,0%</b>  ▲ 5,6 f.b." in text
        assert "<b>+33,3</b>  ▲ 8,3" in text and "Tashqi savdo (2)" in text
        assert "ESI ni ko‘targan: Tashqi savdo" in text and "ESI ni tushirgan: Narx va inflatsiya" in text
        assert "Итоги недели · 28 сентября – 4 октября 2026" in index.bot.caption(index.bot.summary(index.q, "hafta"), "ru")

        cards = []
        monkeypatch.setattr(index, "send_card", lambda chat, data, lang, caption, kb: cards.append((chat, data["kind"], lang)) or True)
        acc = admin_create(server)
        call(server, U(150), "login", {"login": acc["account"]["login"], "password": acc["password"]})
        call(server, U(150), "lang", {"lang": "en"})
        off = admin_create(server)
        call(server, U(151), "login", {"login": off["account"]["login"], "password": off["password"]})
        index.bot.toggle_digest(index.q, 151)                       # this one turned the summaries off

        assert index.run_digest()["sent"] == 4
        assert sorted(cards) == [(150, "hafta", "en"), (150, "kun", "en"), (OWNER, "hafta", "uz"), (OWNER, "kun", "uz")]
        assert index.run_digest()["sent"] == 0                      # each goes once
        assert call(server.replace("/api/index", "/api/index?cron=digest"), U(1), init="")[0] == 401
        monkeypatch.setattr(index, "CRON_SECRET", "s3cret")
        req = urllib.request.Request(server + "?cron=digest", headers={"Authorization": "Bearer s3cret"})
        with urllib.request.urlopen(req, timeout=20) as r:
            assert json.loads(r.read()) == {"ok": True, "sent": 0, "day": "2026-10-04", "week": "2026-09-28"}
    finally:
        with psycopg.connect(DB, autocommit=True) as c:
            c.execute(DATA_TABLES)


def test_setup_profile_and_premium_icons(fresh_db):
    index.ensure_schema()
    calls, sets = [], {}

    def fake(method, params=None, files=None):
        calls.append(method)
        if method == "getMe":
            return {"username": "uzei_bot"}
        if method == "getStickerSet":
            if params["name"] not in sets:
                raise index.botsetup.TgError("Bad Request: STICKERSET_INVALID")
            return {"stickers": [{"custom_emoji_id": f"{params['name']}-{i}"} for i in range(sets[params["name"]])]}
        if method == "createNewStickerSet":
            assert params["sticker_type"] == "custom_emoji" and params["user_id"] == OWNER
            assert params["stickers"][0]["sticker"].startswith("https://uzei.example.app/bot/emoji/")
            sets[params["name"]] = len(params["stickers"])
        if method == "sendMessage":                                  # Telegram kept the custom emoji
            return {"message_id": 9, "entities": [{"type": "custom_emoji", "offset": 0, "length": 2}]}
        return True

    run = lambda: index.botsetup.run(fake, index.q, lambda url: b"PNG", str(OWNER), "uz",
                                     "https://uzei.example.app", False)
    report = run()
    assert calls.count("setMyDescription") == 3 and calls.count("setMyCommands") == 4
    assert "setMyProfilePhoto" in calls and "Premium ikonkalar — ishlaydi (28 ta)" in report
    assert "Ertalabki xulosa — Vercel'da CRON_SECRET" in report
    em = index.emoji()
    assert em["t"]["logo"] == "uzei_t2_by_uzei_bot-0" and em["t"]["fall"] == "uzei_t2_by_uzei_bot-14"
    assert em["g"]["down"] == "uzei_g_by_uzei_bot-12" and calls.count("deleteStickerSet") == 1
    text = index.bot.caption({"kind": "kun", "start": "2026-10-04", "end": "2026-10-04", "eai": 50.0, "esi": 10.0,
                              "d_eai": None, "d_esi": None, "nonad": 6, "econ": 3, "channels": 5,
                              "channels_total": 5, "topics": []}, "en", em)
    assert text.startswith('<tg-emoji emoji-id="uzei_t2_by_uzei_bot-0">')
    calls.clear()
    assert "Avatar — o‘zgarmagan" in run()                          # same picture, sets already there
    assert "setMyProfilePhoto" not in calls and "createNewStickerSet" not in calls


def test_top_posts_headline_and_short_text():
    raw = ("**Eksport 9 oyda 18% oshdi**\n\nStatistika agentligi ma'lumotiga ko'ra, yanvar–sentabrda eksport "
           "hajmi 21,4 mlrd dollarga yetdi va o'tgan yilning shu davridan ancha yuqori bo'ldi.\n\n@kunuzofficial")
    head, body = index.post_parts(raw)
    assert head == "Eksport 9 oyda 18% oshdi" and body.endswith("…") and len(body) <= 101
    assert index.post_parts("Sarlavhasiz bitta qatorli post. Davomi shu yerda.") == ("Sarlavhasiz bitta qatorli post.", "Davomi shu yerda.")
    rows = [{"channel": "@kunuzofficial", "message_id": 5, "primary_topic": "trade", "tone": "pos", "raw_text": raw}]
    data = {"kind": "kun", "start": "2026-10-05", "end": "2026-10-05"}
    text = index.bot.top_text(rows, data, "uz", {"@kunuzofficial": "Kun.uz"}, index.post_parts)
    assert ('1. <i><a href="https://t.me/kunuzofficial/5">Kun.uz</a> · Tashqi savdo · ijobiy</i>\n'
            '<b>Eksport 9 oyda 18% oshdi</b>\nStatistika') in text


# --------------------------------------------------------------- channels --
def test_admin_manages_channels(server, monkeypatch):
    looked_up = []

    def lookup(handle):
        looked_up.append(handle)
        if handle == "@somegroup":
            return {"ok": False, "error": "not_channel"}
        return {"ok": True, "title": "Spot Uz News"}
    monkeypatch.setattr(index, "channel_info", lookup)
    admin = lambda action, body=None: call(server, U(OWNER), action, body)

    code, ov = admin("admin")
    assert code == 200 and [c["handle"] for c in ov["channels"]] == [
        "@gazetauz", "@kunuzofficial", "@daryo", "@spotuz", "@uzdaily"]
    assert all(c["active"] for c in ov["channels"])

    assert admin("channel_add", {"handle": "not a handle!"}) == (400, {"ok": False, "error": "bad_handle"})
    assert admin("channel_add", {"handle": "@Daryo"})[1]["error"] == "exists"
    assert admin("channel_add", {"handle": "somegroup"})[1]["error"] == "not_channel"
    code, r = admin("channel_add", {"handle": "https://t.me/Spot_UZ_News?x=1"})
    assert code == 200 and r["channel"] == {"handle": "@spot_uz_news", "title": "Spot Uz News"}
    assert looked_up == ["@somegroup", "@spot_uz_news"]          # existing ones are not looked up

    assert admin("channel_pause", {"handle": "@daryo"})[0] == 200
    chans = {c["handle"]: c["active"] for c in admin("admin")[1]["channels"]}
    assert chans["@daryo"] is False and chans["@spot_uz_news"] is True
    assert admin("channel_resume", {"handle": "@daryo"})[0] == 200
    for h in ("@gazetauz", "@kunuzofficial", "@daryo", "@spotuz", "@uzdaily"):
        assert admin("channel_pause", {"handle": h})[0] == 200
    assert admin("channel_pause", {"handle": "@spot_uz_news"}) == (409, {"ok": False, "error": "last_channel"})
    assert admin("channel_pause", {"handle": "@nobody"})[1]["error"] == "not_found"

    acc = admin_create(server)
    call(server, U(150), "login", {"login": acc["account"]["login"], "password": acc["password"]})
    assert call(server, U(150), "channel_add", {"handle": "@x_news"})[0] == 403   # admins only

