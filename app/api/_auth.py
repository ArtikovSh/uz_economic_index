"""
Access control for the bot and the Mini App: only people with a login issued by an
admin can use them.

* An admin creates an account: login + random password, role and validity. The
  password is shown once and stored only as a scrypt hash.
* The first successful sign-in binds the account to that Telegram account. From then
  on the verified Telegram identity (Mini App initData, bot update) is the session,
  and the login cannot be used from another Telegram account. Signing out unbinds it.
* An account made from an access request is reserved for the requester's Telegram
  account, so its credentials are useless to anyone else. A reset request renews the
  password of the requester's own login (bound, last bound or reserved to them).
* Failed sign-ins are rate-limited per Telegram account and per login.
* BOT_ADMIN_ID is always an admin (the owner) and needs no login.

All functions take `q(sql, params=(), one=False)`, the app's query helper.
"""
import base64
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

ROLES = ("analyst", "economist", "admin")
TERMS = {"30": 30, "90": 90, "0": None}           # days; "0" = no expiry
LOGIN_RE = re.compile(r"[a-z][a-z0-9._-]{2,31}")  # the Mini App checks the same rules as you type
RESERVED_LOGINS = ("admin",)                       # the owner's display name
PASSWORD_MIN, PASSWORD_MAX = 8, 64
REASONS = ("access", "reset", "other")
TG_MAX_FAILS, TG_LOCK_MIN = 5, 15                 # per Telegram account
LOGIN_MAX_FAILS, LOGIN_LOCK_MIN = 10, 30          # per login
OPEN_REQUESTS_MAX = 3
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"   # no 0/O, 1/l/I

SCHEMA = """
create table if not exists accounts (
    id             bigserial primary key,
    login          text        not null unique,
    password_hash  text        not null,
    role           text        not null check (role in ('analyst','economist','admin')),
    status         text        not null default 'active' check (status in ('active','blocked')),
    expires_at     timestamptz,
    telegram_id    bigint      unique,
    last_tg        bigint,                -- last Telegram account it was bound to (kept on sign-out)
    reserved_tg    bigint,
    tg_username    text,
    tg_name        text,
    full_name      text,
    organization   text,
    request_id     bigint,
    created_at     timestamptz not null default now(),
    created_by     bigint,
    bound_at       timestamptz,
    last_seen_at   timestamptz,
    failed_logins  integer     not null default 0,
    locked_until   timestamptz
);
create table if not exists access_requests (
    id             bigserial primary key,
    telegram_id    bigint      not null,
    tg_username    text,
    tg_name        text,
    full_name      text        not null,
    organization   text,
    reason         text        not null check (reason in ('access','reset','other')),
    message        text,
    status         text        not null default 'new' check (status in ('new','done','rejected')),
    created_at     timestamptz not null default now(),
    handled_at     timestamptz,
    handled_by     bigint
);
create index if not exists idx_requests_open on access_requests (status, created_at);
create table if not exists auth_failures (
    telegram_id    bigint primary key,
    failures       integer     not null default 0,
    last_at        timestamptz not null default now(),
    locked_until   timestamptz
);
alter table accounts        enable row level security;
alter table access_requests enable row level security;
alter table auth_failures   enable row level security;
"""


def now():
    return datetime.now(timezone.utc)


# ------------------------------------------------------------ passwords ----
def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return "scrypt$16384$8$1$%s$%s" % (base64.b64encode(salt).decode(), base64.b64encode(digest).decode())


def check_password(password, stored):
    try:
        algo, n, r, p, salt, digest = stored.split("$")
        if algo != "scrypt":
            return False
        calc = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt),
                              n=int(n), r=int(r), p=int(p), dklen=len(base64.b64decode(digest)))
        return hmac.compare_digest(calc, base64.b64decode(digest))
    except (ValueError, TypeError):
        return False


def new_password():
    """12 random characters in three groups of four, e.g. K7m4-Qx2p-9Ldw."""
    raw = "".join(secrets.choice(_ALPHABET) for _ in range(12))
    return "-".join(raw[i:i + 4] for i in range(0, 12, 4))


def password_problems(password, login=""):
    """Rules an admin-typed password breaks: length | mix (letter and digit) | space | login."""
    out = []
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        out.append("length")
    if not (re.search(r"[^\W\d_]", password) and re.search(r"\d", password)):
        out.append("mix")
    if re.search(r"\s", password):
        out.append("space")
    if login and login.lower() in password.lower():
        out.append("login")
    return out


def normalize_login(value):
    return str(value or "").strip().lower()[:64]


def login_status(q, name):
    """free | taken | bad for a login an admin typed (already normalised)."""
    if not LOGIN_RE.fullmatch(name) or name in RESERVED_LOGINS:
        return "bad"
    taken = q("select 1 x from accounts where lower(login)=%s", (name,), one=True)
    return "taken" if taken else "free"


_DUMMY_HASH = None


def _dummy_hash():
    """Checked when the login does not exist, so both cases take the same time."""
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password(secrets.token_hex(8))
    return _DUMMY_HASH


# ------------------------------------------------------------- helpers -----
def _clean(value, limit):
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(value or ""))
    return " ".join(text.split())[:limit]


def _tg_name(user):
    return " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))[:120]


def _expired(acc):
    return bool(acc.get("expires_at")) and acc["expires_at"] <= now()


def account_state(acc):
    """active (bound and valid) | pending (not signed in yet) | expired | blocked."""
    if acc["status"] == "blocked":
        return "blocked"
    if _expired(acc):
        return "expired"
    return "active" if acc.get("telegram_id") else "pending"


def next_login(q, role):
    rows = q("select login from accounts where login like %s", (role + ".%",)) or []
    nums = [int(m.group(1)) for r in rows
            if (m := re.fullmatch(re.escape(role) + r"\.(\d+)", r["login"]))]
    return "%s.%02d" % (role, (max(nums) + 1) if nums else 1)


# ------------------------------------------------------------- identity ----
def principal(q, tg_id, owner_id):
    """(state, account) for a verified Telegram user; state: ok | login | blocked | expired."""
    if owner_id and str(tg_id) == str(owner_id):
        return "ok", {"id": None, "login": "admin", "role": "admin", "is_admin": True,
                      "owner": True, "expires_at": None}
    acc = q("select * from accounts where telegram_id=%s", (tg_id,), one=True)
    if not acc:
        return "login", None
    if acc["status"] == "blocked":
        return "blocked", acc
    if _expired(acc):
        return "expired", acc
    q("""update accounts set last_seen_at=now()
         where id=%s and (last_seen_at is null or last_seen_at < now() - interval '5 minutes')""",
      (acc["id"],))
    acc["is_admin"] = acc["role"] == "admin"
    acc["owner"] = False
    return "ok", acc


def _fail(q, tg_id, acc):
    q("""insert into auth_failures (telegram_id, failures, last_at) values (%s, 1, now())
         on conflict (telegram_id) do update set
           failures = case when auth_failures.last_at < now() - interval '1 hour'
                           then 1 else auth_failures.failures + 1 end,
           last_at = now()""", (tg_id,))
    q("""update auth_failures set locked_until = now() + make_interval(mins => %s)
         where telegram_id=%s and failures >= %s""", (TG_LOCK_MIN, tg_id, TG_MAX_FAILS))
    if acc:
        q("""update accounts set failed_logins = failed_logins + 1,
               locked_until = case when failed_logins + 1 >= %s
                                   then now() + make_interval(mins => %s) else locked_until end
             where id=%s""", (LOGIN_MAX_FAILS, LOGIN_LOCK_MIN, acc["id"]))


def login(q, tg_user, login_name, password):
    """Sign in and bind the account to this Telegram account. Returns {"ok": ..., "error": ...}."""
    tg_id = tg_user["id"]
    login_name = _clean(login_name, 64).lower()
    password = str(password or "")[:128]
    f = q("select locked_until from auth_failures where telegram_id=%s", (tg_id,), one=True)
    if f and f["locked_until"] and f["locked_until"] > now():
        return {"ok": False, "error": "locked"}
    acc = q("select * from accounts where lower(login)=%s", (login_name,), one=True) if login_name else None
    if acc and acc["locked_until"] and acc["locked_until"] > now():
        return {"ok": False, "error": "locked"}
    good = check_password(password, acc["password_hash"] if acc else _dummy_hash())
    if not acc or not good:
        _fail(q, tg_id, acc)
        return {"ok": False, "error": "invalid"}
    if acc["status"] == "blocked":
        return {"ok": False, "error": "blocked"}
    if _expired(acc):
        return {"ok": False, "error": "expired"}
    if (acc["telegram_id"] and acc["telegram_id"] != tg_id) or \
            (acc["reserved_tg"] and acc["reserved_tg"] != tg_id):
        return {"ok": False, "error": "other_account"}
    q("update accounts set telegram_id=null where telegram_id=%s and id<>%s", (tg_id, acc["id"]))
    q("""update accounts set telegram_id=%s, last_tg=%s, tg_username=%s, tg_name=%s, bound_at=now(),
           last_seen_at=now(), failed_logins=0, locked_until=null
         where id=%s""", (tg_id, tg_id, tg_user.get("username"), _tg_name(tg_user), acc["id"]))
    q("delete from auth_failures where telegram_id=%s", (tg_id,))
    return {"ok": True}


def logout(q, tg_id):
    q("update accounts set telegram_id=null where telegram_id=%s", (tg_id,))
    return {"ok": True}


# ------------------------------------------------------ access requests ----
def create_request(q, tg_user, data):
    full_name = _clean(data.get("full_name"), 80)
    if len(full_name) < 3:
        return {"ok": False, "error": "name"}
    reason = data.get("reason") if data.get("reason") in REASONS else "other"
    open_n = q("select count(*) n from access_requests where telegram_id=%s and status='new'",
               (tg_user["id"],), one=True)["n"]
    if open_n >= OPEN_REQUESTS_MAX:
        return {"ok": False, "error": "too_many"}
    row = q("""insert into access_requests
                 (telegram_id, tg_username, tg_name, full_name, organization, reason, message)
               values (%s,%s,%s,%s,%s,%s,%s) returning *""",
            (tg_user["id"], tg_user.get("username"), _tg_name(tg_user), full_name,
             _clean(data.get("organization"), 120) or None, reason,
             _clean(data.get("message"), 500) or None), one=True)
    return {"ok": True, "request": row}


def requester_account(q, tg_id):
    """The login a Telegram user has, last had or was given (to answer their reset request)."""
    return q("""select * from accounts where telegram_id=%s or last_tg=%s or reserved_tg=%s
                order by (telegram_id = %s) desc nulls last, created_at desc limit 1""",
             (tg_id, tg_id, tg_id, tg_id), one=True)


def has_open_request(q, tg_id):
    return bool(q("select 1 x from access_requests where telegram_id=%s and status='new' limit 1",
                  (tg_id,), one=True))


# ---------------------------------------------------------------- admin ----
def overview(q):
    accounts = q("""select id, login, role, status, expires_at, telegram_id, tg_username, tg_name,
                           full_name, organization, created_at, bound_at, last_seen_at
                    from accounts order by created_at desc, id desc""") or []
    for a in accounts:
        a["state"] = account_state(a)
        a["bound"] = bool(a.pop("telegram_id"))
    requests = q("""select id, telegram_id, tg_username, tg_name, full_name, organization,
                           reason, message, created_at
                    from access_requests where status='new' order by created_at desc""") or []
    for r in requests:
        acc = requester_account(q, r["telegram_id"])
        r["account"] = {"id": acc["id"], "login": acc["login"], "state": account_state(acc)} if acc else None
    handled = q("""select id, tg_username, tg_name, full_name, organization, reason, message, status,
                          created_at, handled_at
                   from access_requests where status<>'new'
                   order by handled_at desc nulls last, id desc limit 20""") or []
    count = {s: sum(1 for a in accounts if a["state"] == s)
             for s in ("active", "pending", "expired", "blocked")}
    return {"ok": True, "accounts": accounts, "requests": requests, "handled": handled, "count": count,
            "next_login": {r: _next_from([a["login"] for a in accounts], r) for r in ROLES}}


def _next_from(logins, role):
    nums = [int(m.group(1)) for x in logins if (m := re.fullmatch(re.escape(role) + r"\.(\d+)", x))]
    return "%s.%02d" % (role, (max(nums) + 1) if nums else 1)


def _open_request(q, request_id):
    return q("select * from access_requests where id=%s and status='new'", (request_id,), one=True)


def create_account(q, admin_tg, role, term, request_id=None, login_name=None, password=None):
    """New login + password (returned once). The admin may type either; otherwise the login is
    the role's next number and the password is random. From a request: reserved for the requester."""
    if role not in ROLES or term not in TERMS:
        return {"ok": False, "error": "bad_input"}
    req = None
    if request_id:
        req = _open_request(q, request_id)
        if not req:
            return {"ok": False, "error": "no_request"}
    if login_name:
        login_name = normalize_login(login_name)
        state = login_status(q, login_name)
        if state != "free":
            return {"ok": False, "error": "login_taken" if state == "taken" else "bad_login"}
    name = login_name or next_login(q, role)
    if password is not None and password_problems(str(password), name):
        return {"ok": False, "error": "weak_password"}
    password = str(password) if password is not None else new_password()
    days = TERMS[term]
    expires = now() + timedelta(days=days) if days else None
    for attempt in range(3):                             # retry if two admins race for a login
        if attempt:
            name = next_login(q, role)
        try:
            row = q("""insert into accounts (login, password_hash, role, expires_at, created_by,
                                             reserved_tg, full_name, organization, request_id)
                       values (%s,%s,%s,%s,%s,%s,%s,%s,%s) returning id, login, role, expires_at""",
                    (name, hash_password(password), role, expires, admin_tg,
                     req["telegram_id"] if req else None, req["full_name"] if req else None,
                     req["organization"] if req else None, req["id"] if req else None), one=True)
            break
        except Exception as e:                           # unique violation on login
            if "unique" not in str(e).lower():
                raise
            if login_name:
                return {"ok": False, "error": "login_taken"}
    else:
        return {"ok": False, "error": "busy"}
    if req:
        q("""update access_requests set status='done', handled_at=now(), handled_by=%s
             where id=%s""", (admin_tg, req["id"]))
    return {"ok": True, "account": row, "password": password, "request": req}


def reset_password(q, account_id, admin_tg=None, request_id=None, password=None):
    """New password (typed by the admin or random); the account is unbound so it must be signed in
    again. For a reset request the requester's own login is reset, reserved for them, and the
    request is closed."""
    req = None
    if request_id:
        req = _open_request(q, request_id)
        if not req:
            return {"ok": False, "error": "no_request"}
        acc = requester_account(q, req["telegram_id"])
        if not acc:
            return {"ok": False, "error": "no_account"}
        account_id = acc["id"]
    acc = q("select login from accounts where id=%s", (account_id,), one=True) if account_id else None
    if not acc:
        return {"ok": False, "error": "not_found"}
    if password is not None and password_problems(str(password), acc["login"]):
        return {"ok": False, "error": "weak_password"}
    password = str(password) if password is not None else new_password()
    row = q("""update accounts set password_hash=%s, telegram_id=null, failed_logins=0, locked_until=null,
                 reserved_tg=coalesce(%s, reserved_tg)
               where id=%s returning id, login, role, expires_at""",
            (hash_password(password), req["telegram_id"] if req else None, account_id), one=True)
    if not row:
        return {"ok": False, "error": "not_found"}
    if req:
        finish_request(q, admin_tg, req["id"], "done")
    return {"ok": True, "account": row, "password": password, "request": req}


def set_status(q, account_id, status):
    if status not in ("active", "blocked"):
        return {"ok": False, "error": "bad_input"}
    row = q("update accounts set status=%s where id=%s returning id, telegram_id",
            (status, account_id), one=True)
    return {"ok": bool(row), "account": row} if row else {"ok": False, "error": "not_found"}


def extend(q, account_id, term):
    """Extend from the current end date if it is still ahead, else from today; "0" = no expiry."""
    if term not in TERMS:
        return {"ok": False, "error": "bad_input"}
    days = TERMS[term]
    row = q("""update accounts
               set expires_at = case when %s::int is null then null
                                     else greatest(now(), coalesce(expires_at, now())) + make_interval(days => %s::int) end
               where id=%s returning id, expires_at""", (days, days, account_id), one=True)
    return {"ok": True, "account": row} if row else {"ok": False, "error": "not_found"}


def delete_account(q, account_id, admin_tg):
    """Delete a login for good; an admin cannot delete the login they are signed in with."""
    acc = q("select id, telegram_id from accounts where id=%s", (account_id,), one=True)
    if not acc:
        return {"ok": False, "error": "not_found"}
    if acc["telegram_id"] is not None and str(acc["telegram_id"]) == str(admin_tg):
        return {"ok": False, "error": "self"}
    q("delete from accounts where id=%s", (account_id,))
    return {"ok": True, "account": acc}


def finish_request(q, admin_tg, request_id, status):
    """Close an open request: done (handled, nobody is told) or rejected (the caller tells them)."""
    row = q("""update access_requests set status=%s, handled_at=now(), handled_by=%s
               where id=%s and status='new' returning *""", (status, admin_tg, request_id), one=True)
    return {"ok": True, "request": row} if row else {"ok": False, "error": "no_request"}
