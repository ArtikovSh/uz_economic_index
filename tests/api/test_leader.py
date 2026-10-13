"""Leadership access, preferences and counts against the isolated test database."""
from pathlib import Path

import pytest

from test_auth import (DATA_TABLES, OWNER, REPO_API, U, _auth, admin_create, call,
                       fresh_db, index, server)  # noqa: F401 (shared fixtures)


@pytest.fixture(autouse=True)
def fresh_leader_db(fresh_db):
    # Dropping accounts CASCADE drops its incoming FK, not the referencing table.
    index.q("drop table if exists leader_prefs")
    yield
    index.q("drop table if exists leader_prefs")
    index._SCHEMA_READY = False


@pytest.fixture
def account(server, fresh_db):
    result = admin_create(server, role="leader", term="0")
    assert result["account"]["login"] == "leader.01"
    assert call(server, U(701), "login", {"login": "leader.01", "password": result["password"]})[0] == 200
    return result["account"]["id"]


@pytest.fixture
def news(fresh_db):
    index.q(DATA_TABLES)
    index.q((Path(REPO_API).parents[1] / "db/schema.sql").read_text(encoding="utf-8"), None)
    index.ensure_schema()
    # Boundary-neutral, excluded posts, two channels, local midnight, and an unfinished day.
    rows = [
        ("@daryo", 1, "2026-05-01 20:00+00", "central_bank", .6, True, False, False, False),
        ("@daryo", 2, "2026-05-02 10:00+00", "central_bank", .15, True, False, False, False),
        ("@kunuzofficial", 3, "2026-05-02 10:00+00", "trade", -.6, True, False, False, False),
        ("@daryo", 4, "2026-05-02 10:00+00", "business", .6, True, True, False, False),
        ("@daryo", 5, "2026-05-02 10:00+00", "business", .6, True, False, True, False),
        ("@daryo", 6, "2026-05-02 10:00+00", "business", .6, True, False, False, True),
        ("@daryo", 7, "2026-05-02 10:00+00", "non_economic", 0, False, False, False, False),
        ("@daryo", 8, "2026-05-03 10:00+00", "central_bank", -.15, True, False, False, False),
        ("@kunuzofficial", 9, "2026-05-04 10:00+00", "trade", .9, True, False, False, False),
    ]
    for ch, mid, at, topic, tone, econ, ad, foreign, digest in rows:
        index.q("insert into messages values (%s,%s,%s,%s,0,'Post')", (ch, mid, at, mid * 100))
        index.q("""insert into labels (channel,message_id,primary_topic,sentiment,is_economic,is_ad,is_foreign,is_digest)
                    values (%s,%s,%s,%s,%s,%s,%s,%s)""", (ch, mid, topic, tone, econ, ad, foreign, digest))
    for day in ("2026-05-02", "2026-05-03", "2026-05-05"):
        index.q("insert into indices (period_type,period,start_date,end_date) values ('kun',%s,%s,%s)", (day, day, day))
    yield
    index.q(DATA_TABLES)
    index._STATS = (None, None)


def test_migrate_existing_roles(fresh_db):
    index.ensure_schema()
    acc = _auth.create_account(index.q, OWNER, "analyst", "0")["account"]
    index.q("""alter table accounts drop constraint accounts_role_check;
               alter table accounts add constraint accounts_role_check check (role in ('analyst','economist','admin'))""")
    for _ in range(2):
        index._SCHEMA_READY = False
        index.ensure_schema()
    assert index.q("select login from accounts where id=%s", (acc["id"],), one=True)["login"] == acc["login"]
    assert _auth.create_account(index.q, OWNER, "leader", "0")["ok"]
    with pytest.raises(Exception, match="accounts_role_check"):
        index.q("update accounts set role='unknown'")
    assert index.q("select relrowsecurity r from pg_class where relname='leader_prefs'", one=True)["r"]


def test_bootstrap_preferences_and_cascade(server, account):
    r = call(server, U(701))[1]
    assert r["me"]["role"] == "leader" and r["me"]["is_admin"] is False
    assert "stats" not in r and r["leader"]["ok"]
    assert r["prefs"] == {"channels": [], "topics": ["central_bank"], "onboarded": False, "digest": True}
    body = {"channels": ["@daryo"], "topics": [], "onboarded": True}
    assert call(server, U(701), "prefs_set", body)[1] == {"ok": True, "prefs": {**body, "digest": True}}
    assert call(server, U(701), "prefs_set", {"topics": ["trade"]})[1]["prefs"] == {
        **body, "topics": ["trade"], "digest": True}
    assert call(server, U(701))[1]["prefs"]["onboarded"] is True
    index.q("delete from accounts where id=%s", (account,))
    assert not index.q("select * from leader_prefs")


@pytest.mark.parametrize("body", [
    {"channels": []}, {"channels": "@daryo"}, {"channels": ["@unknown"]}, {"channels": [None]},
    {"topics": ["unknown"]}, {"topics": None}, {"topics": "trade"}, {"topics": [{}]},
    {"onboarded": 1}, {"onboarded": "true"},
])
def test_invalid_preferences(server, account, body):
    assert call(server, U(701), "prefs_set", body) == (400, {"ok": False, "error": "bad_input"})
    assert not index.q("select * from leader_prefs")


def test_paused_channel_and_deduplication(server, account):
    index.q("update channels set active=false where handle='@daryo'")
    assert call(server, U(701), "prefs_set", {"channels": ["@daryo"]})[0] == 400
    assert call(server, U(701), "leader_stats", {"channels": ["@daryo"]})[0] == 400
    r = call(server, U(701), "prefs_set", {"channels": ["@kunuzofficial"] * 2, "topics": ["trade"] * 2})[1]
    assert r["prefs"]["channels"] == ["@kunuzofficial"] and r["prefs"]["topics"] == ["trade"]


def test_counts_and_selected_channels(server, news, account):
    r = call(server, U(701), "leader_stats", {"channels": []})[1]
    assert r["days"] == [["2026-05-02", 7, 2], ["2026-05-03", 1, 1], ["2026-05-05", 0, 0]]
    assert r["topics"] == [[0, "central_bank", 1, 1, 0], [0, "trade", 0, 0, 1], [1, "central_bank", 0, 1, 0]]
    assert r["channel_days"] == [[0, "@daryo"], [0, "@kunuzofficial"], [1, "@daryo"]]
    assert [c["id"] for c in r["channels"]][:2] == ["@daryo", "@kunuzofficial"]
    one = call(server, U(701), "leader_stats", {"channels": ["@kunuzofficial"]})[1]
    assert one["days"] == [["2026-05-02", 1, 1], ["2026-05-03", 0, 0], ["2026-05-05", 0, 0]]
    assert one["topics"] == [[0, "trade", 0, 0, 1]]
    assert one["channels"] == r["channels"]


def test_digest_insert_update_and_validation(server, account):
    index.q("delete from bot_users where telegram_id=701")
    for on in (False, True, False):
        assert call(server, U(701), "digest", {"on": on}) == (200, {"ok": True, "digest": on})
        assert call(server, U(701))[1]["prefs"]["digest"] is on
    for on in (None, 0, "false", []):
        assert call(server, U(701), "digest", {"on": on})[0] == 400


def test_role_permissions(server, account):
    for action in ("admin", "create", "role", "delete", "channel_add", "channel_pause"):
        assert call(server, U(701), action)[0] == 403
    for role, uid in (("analyst", 702), ("economist", 703), ("admin", 704)):
        acc = admin_create(server, role=role)
        assert call(server, U(uid), "login", {"login": acc["account"]["login"], "password": acc["password"]})[0] == 200
        for action in ("prefs_set", "leader_stats", "digest"):
            assert call(server, U(uid), action)[0] == 403
    for action in ("prefs_set", "leader_stats", "digest"):
        assert call(server, U(OWNER), action)[0] == 403
        assert call(server, U(799), action)[0] == 403


def test_posts_allow_fifty_leader_channels(server, news, account):
    # The matching channel is number 50, beyond the analyst limit.
    selected = [f"@unused{i}" for i in range(49)] + ["@kunuzofficial"]
    body = {"from": "2026-05-02", "to": "2026-05-03", "channels": selected}
    assert call(server, U(701), "posts", body)[1]["total"] == 1
    assert call(server, U(OWNER), "posts", body)[1]["total"] == 0
