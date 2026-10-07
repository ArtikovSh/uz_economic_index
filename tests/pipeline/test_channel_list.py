"""Channel selection with a fake database connection (no network)."""
from contextlib import contextmanager
from types import SimpleNamespace

import psycopg
import pytest

import channel_list as cl


DB_URL = "postgresql://test:FAKE-PASSWORD@db.invalid/example"


@pytest.fixture(autouse=True)
def database(monkeypatch):
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(cl.config, "CHANNELS", ["@fallback"])
    state = SimpleNamespace(rows=[], calls=[], queries=[], error=None, fail_at=None,
                            cursor_closed=False, connection_closed=False)

    class Cursor:
        def execute(self, query):
            state.queries.append(query)
            if state.fail_at == "execute":
                raise state.error

        def fetchall(self):
            if state.fail_at == "fetchall":
                raise state.error
            return state.rows

    @contextmanager
    def cursor():
        try:
            yield Cursor()
        finally:
            state.cursor_closed = True

    @contextmanager
    def connect(url, **kwargs):
        state.calls.append((url, kwargs))
        if state.fail_at == "connect":
            raise state.error
        try:
            yield SimpleNamespace(cursor=cursor)
        finally:
            state.connection_closed = True

    monkeypatch.setattr(cl.psycopg, "connect", connect)
    return state


@pytest.mark.parametrize("db_url", [None, "", " \t "])
def test_missing_url_uses_config_without_connecting(db_url, database, capsys):
    assert cl.active_channels(db_url) == ["@fallback"]
    assert database.calls == []
    assert capsys.readouterr().out.splitlines() == [
        "Channels: database URL is not configured; using fallback."]


@pytest.mark.parametrize("supabase, generic, expected", [
    (DB_URL, "postgresql://unused.invalid/db", DB_URL),
    (None, DB_URL, DB_URL),
    ("", DB_URL, DB_URL),
])
def test_default_url_uses_environment(monkeypatch, database, supabase, generic, expected):
    if supabase is not None:
        monkeypatch.setenv("SUPABASE_DB_URL", supabase)
    monkeypatch.setenv("DATABASE_URL", generic)
    database.rows = [("@from_db",)]
    assert cl.active_channels() == ["@from_db"]
    assert database.calls[0][0] == expected


def test_explicit_url_overrides_environment(monkeypatch, database):
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://unused.invalid/db")
    database.rows = [("@from_db",)]
    assert cl.active_channels(DB_URL) == ["@from_db"]
    assert database.calls[0][0] == DB_URL
    assert cl.active_channels("") == ["@fallback"]
    assert len(database.calls) == 1


def test_database_list_keeps_query_order_and_closes_resources(database, capsys):
    database.rows = [("@zebra",), ("@alpha",)]
    assert cl.active_channels(DB_URL, fallback=["@other"]) == ["@zebra", "@alpha"]
    assert database.calls == [(DB_URL, {"prepare_threshold": None, "connect_timeout": 10})]
    assert database.queries == ["select handle from channels where active order by added_at, handle"]
    assert database.cursor_closed and database.connection_closed
    assert capsys.readouterr().out == ""


def test_empty_result_uses_fallback(database, capsys):
    assert cl.active_channels(DB_URL, fallback=["@custom"]) == ["@custom"]
    assert capsys.readouterr().out.splitlines() == [
        "Channels: no active channels; using fallback."]
    assert database.cursor_closed and database.connection_closed


@pytest.mark.parametrize("fail_at, error, reason", [
    ("execute", psycopg.errors.UndefinedTable, "channels table is missing"),
    ("connect", psycopg.OperationalError, "database read failed (OperationalError)"),
    ("fetchall", psycopg.OperationalError, "database read failed (OperationalError)"),
])
def test_database_failures_use_fallback_without_logging_secrets(database, capsys, fail_at, error, reason):
    database.fail_at = fail_at
    database.error = error(f"Could not read {DB_URL}\npassword=FAKE-PASSWORD")
    assert cl.active_channels(DB_URL) == ["@fallback"]
    assert capsys.readouterr().out.splitlines() == [f"Channels: {reason}; using fallback."]
    if fail_at != "connect":
        assert database.cursor_closed and database.connection_closed


@pytest.mark.parametrize("source", ["database", "fallback"])
def test_handles_are_normalized_and_deduplicated_in_order(database, source):
    handles = ["  DARYO ", "@Kun Uz\t", " @daryo ", "\n@SPOTUZ", "spotuz", "", " @ "]
    original = handles.copy()
    if source == "database":
        database.rows = [(handle,) for handle in handles]
        result = cl.active_channels(DB_URL)
    else:
        result = cl.active_channels("", fallback=handles)
    assert result == ["@daryo", "@kunuz", "@spotuz"]
    assert handles == original


def test_blank_database_handles_use_fallback(database, capsys):
    database.rows = [(" ",), ("@",)]
    assert cl.active_channels(DB_URL) == ["@fallback"]
    assert capsys.readouterr().out.splitlines() == [
        "Channels: no active channels; using fallback."]


def test_explicit_empty_fallback_is_preserved():
    assert cl.active_channels("", fallback=[]) == []
