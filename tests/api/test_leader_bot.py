"""Leader bot routing, personal digest, cache, and card rendering with fake Telegram."""
from datetime import datetime
from io import BytesIO
from html import unescape

import pytest
from PIL import Image

from test_auth import U, admin_create, call, fresh_db, index, press, server, upd  # noqa: F401
from test_leader import account, fresh_leader_db, news  # noqa: F401


def _fake_tg(monkeypatch):
    events = []

    def fake(method, params=None, files=None, timeout=30):
        events.append((method, params or {}, files))
        return {"photo": [{"file_id": "small"}, {"file_id": "file-large"}]} if method == "sendPhoto" else True

    monkeypatch.setattr(index, "tg", fake)
    monkeypatch.setattr(index, "answer_cb", lambda *_: events.append(("answerCallbackQuery", {}, None)))
    return events


@pytest.mark.parametrize("lang,open_label,menu_label", [
    ("uz", "Ilovani ochish", "Ilova"), ("ru", "Открыть приложение", "Приложение"),
    ("en", "Open the app", "App"),
])
def test_leader_home_commands_callbacks_and_menu(account, fresh_db, monkeypatch, lang, open_label, menu_label):
    events = _fake_tg(monkeypatch)
    index.bot.set_lang(index.q, 701, lang)
    for cmd in ("/start", "/app", "/index", "/top", "/topics", "/me", "/help", "hello"):
        index.handle_update(upd(701, cmd))
        chat, text, kw = fresh_db[-1]
        assert chat == 701 and text.startswith("<b>Sentiment Monitor</b>")
        assert len(kw["reply_markup"]["inline_keyboard"]) == 1
        button = kw["reply_markup"]["inline_keyboard"][0][0]
        assert button["text"] == open_label and button["web_app"]["url"] == index.app_url()
    menu = next(e[1]["menu_button"] for e in events if e[0] == "setChatMenuButton")
    assert menu == {"type": "web_app", "text": menu_label, "web_app": {"url": index.app_url()}}
    cmds = next(e[1] for e in events if e[0] == "setMyCommands")
    assert cmds["scope"] == {"type": "chat", "chat_id": 701}
    assert [c["command"] for c in cmds["commands"]] == ["today", "week", "app", "lang"]
    assert cmds["commands"][2]["description"] == menu_label
    for cb in ("nav:today", "nav:topics:kun:2026-05-02", "me:digest", "me:out", "unknown"):
        index.handle_update(press(701, cb))
        assert fresh_db[-1][1].startswith("<b>Sentiment Monitor</b>")
    assert len([e for e in events if e[0] == "answerCallbackQuery"]) == 5
    assert index.bot.user_row(index.q, 701)["digest"] is True
    index.q("update bot_users set digest=false where telegram_id=701")
    index.handle_update(upd(701, "/start"))
    assert index.bot.tr(lang, "leader_home_off") in unescape(fresh_db[-1][1])
    index.handle_update(upd(701, "/lang"))
    assert "Sentiment Monitor" not in fresh_db[-1][1]


def test_leader_login_and_role_change_reset_menu(account, fresh_db, monkeypatch):
    events = _fake_tg(monkeypatch)
    index.welcome_after_login(U(701))
    assert fresh_db[-1][1].startswith("<b>Sentiment Monitor</b>")
    assert events[-1][1]["menu_button"]["type"] == "web_app"
    index.bot.set_lang(index.q, 701, "uz")
    index.q("update accounts set role='analyst' where id=%s", (account,))
    index.handle_update(upd(701, "/start"))
    assert index.bot.home_text("uz") == fresh_db[-1][1]
    assert events[-1][1] == {"chat_id": 701}


def _card_data(topics=None, lang="uz"):
    topics = topics if topics is not None else [["trade", 8, 2, 1], ["business", 3, 1, 0],
                                               ["transport", 1, 1, 1]]
    return {"kind": "kun", "start": "2026-05-28", "end": "2026-05-28", "posts": 150,
            "econ": 39, "tones": [32, 4, 3], "shares": [82, 10, 8], "mood": 74,
            "previous_start": "2026-05-27", "previous_end": "2026-05-27", "previous_mood": 56,
            "change": 18, "topics": topics, "channels": ["@daryo", "@kunuzofficial"],
            "selected_topics": ["business", "trade", "transport"], "topic_count": 3, "lang": lang}


@pytest.mark.parametrize("lang", ["uz", "ru", "en"])
def test_card_png_and_caption_languages(lang):
    import _card

    data = _card_data(lang=lang)
    png = _card.render_leader(data)
    im = Image.open(BytesIO(png))
    assert im.format == "PNG" and im.mode == "RGB" and im.width == 1600 and 900 <= im.height <= 1050
    assert len(im.getcolors(1600 * im.height) or []) > 10
    caption = index.bot.leader_caption(data, lang)
    assert "<b>" in caption and "39" in caption and "82%" in caption and "150" in caption
    assert index.bot.visible_len(caption) < 1024


def test_caption_single_topic_zero_and_previous_states():
    data = _card_data(topics=[["trade", 1, 0, 0]])
    data["topic_count"] = 1
    assert "Ko'p yozilgan mavzular" not in index.bot.leader_caption(data, "uz")
    data["change"] = 0
    assert "oldingi kun darajasida" in index.bot.leader_caption(data, "uz")
    data["previous_mood"] = None
    assert "xabar yo'q" in index.bot.leader_caption(data, "uz")
    data["econ"] = 0
    assert index.bot.leader_caption(data, "uz").count("\n") == 1


def test_leader_card_cache_by_preferences(account, monkeypatch):
    events = _fake_tg(monkeypatch)
    data = _card_data()
    caption = index.bot.leader_caption(data, "uz")
    assert index.send_leader_card(701, data, "uz", caption)
    assert index.send_leader_card(702, data, "uz", caption)
    photos = [e for e in events if e[0] == "sendPhoto"]
    assert photos[0][2] and photos[1][1]["photo"] == "file-large" and photos[1][2] is None
    rows = index.q("select * from bot_cards where kind='leader'")
    assert len(rows) == 1 and rows[0]["period"].startswith("kun:2026-05-28#v")
    changed = {**data, "selected_topics": ["trade"]}
    assert index.send_leader_card(703, changed, "uz", caption)
    assert len(index.q("select * from bot_cards where kind='leader'")) == 2


def test_day_card_at_nine_week_text_at_ten(account, news, fresh_db, monkeypatch):
    events = _fake_tg(monkeypatch)
    index.q("insert into leader_prefs (account_id, channels, topics) values (%s, %s, %s)",
            (account, ["@daryo"], []))
    monkeypatch.setattr(index, "DIGEST_MAX_AGE", 100000)
    day = {"kind": "kun", "start": "2026-05-03", "end": "2026-05-03"}
    week = {"kind": "hafta", "start": "2026-04-27", "end": "2026-05-03"}
    monkeypatch.setattr(index, "summary", lambda kind, start=None: week if kind == "hafta" else day)
    monkeypatch.setattr(index.bot, "caption", lambda *_: "analytic")
    monkeypatch.setattr(index, "send_card", lambda *_: True)
    monday = lambda hour: datetime(2026, 5, 4, hour, 5)
    assert index.run_digest(monday(9))["sent"] == 3  # owner analytic day + week, the leader's day card
    photos = [e for e in events if e[0] == "sendPhoto"]
    assert len(photos) == 1 and photos[0][1]["chat_id"] == 701
    row = index.bot.user_row(index.q, 701)
    assert str(row["digest_day"]) == "2026-05-03" and row["digest_week"] is None
    assert index.run_digest(monday(9))["sent"] == 0
    assert index.run_digest(monday(10))["sent"] == 1  # the leader's weekly, as a separate text
    assert fresh_db[-1][0] == 701 and "O'tgan hafta" in unescape(fresh_db[-1][1])
    assert len([e for e in events if e[0] == "sendPhoto"]) == 1
    assert str(index.bot.user_row(index.q, 701)["digest_week"]) == "2026-04-27"
    assert index.run_digest(monday(13))["sent"] == 0
    day = {"kind": "kun", "start": "2026-05-05", "end": "2026-05-05"}
    monkeypatch.setattr(index, "summary", lambda kind, start=None: None if kind == "hafta" else day)
    assert index.run_digest(datetime(2026, 5, 6, 9, 5))["sent"] == 2  # owner analytic and leader text-only
    assert "iqtisodiy xabar bo'lmadi" in unescape(fresh_db[-1][1])
    assert index.run_digest(datetime(2026, 5, 6, 13, 5))["sent"] == 0


def test_missed_morning_sends_day_and_week_at_one(account, news, fresh_db, monkeypatch):
    events = _fake_tg(monkeypatch)
    monkeypatch.setattr(index, "DIGEST_MAX_AGE", 100000)
    day = {"kind": "kun", "start": "2026-05-03", "end": "2026-05-03"}
    week = {"kind": "hafta", "start": "2026-04-27", "end": "2026-05-03"}
    monkeypatch.setattr(index, "summary", lambda kind, start=None: week if kind == "hafta" else day)
    monkeypatch.setattr(index.bot, "caption", lambda *_: "analytic")
    monkeypatch.setattr(index, "send_card", lambda *_: True)
    assert index.run_digest(datetime(2026, 5, 4, 13, 5))["sent"] == 4  # owner day + week, leader day + week
    row = index.bot.user_row(index.q, 701)
    assert str(row["digest_day"]) == "2026-05-03" and str(row["digest_week"]) == "2026-04-27"


def test_blocked_leader_skipped(account, news, fresh_db, monkeypatch):
    monkeypatch.setattr(index, "DIGEST_MAX_AGE", 100000)
    day = {"kind": "kun", "start": "2026-05-03", "end": "2026-05-03"}
    monkeypatch.setattr(index, "summary", lambda kind, start=None: None if kind == "hafta" else day)
    monkeypatch.setattr(index.bot, "caption", lambda *_: "analytic")
    monkeypatch.setattr(index, "send_card", lambda *_: True)
    index.q("update bot_users set blocked_bot=true where telegram_id=701")
    assert index.run_digest()["sent"] == 1  # owner only
    assert len([r for r in fresh_db if r[0] == 701]) == 1  # login home


def test_daily_card_matches_mini_app_counts(account, news, fresh_db, monkeypatch):
    events = _fake_tg(monkeypatch)
    index.q("insert into leader_prefs (account_id, channels, topics) values (%s, %s, %s)",
            (account, [], ["central_bank", "trade"]))
    monkeypatch.setattr(index, "DIGEST_MAX_AGE", 100000)
    day = {"kind": "kun", "start": "2026-05-02", "end": "2026-05-02"}
    monkeypatch.setattr(index, "summary", lambda kind, start=None: None if kind == "hafta" else day)
    monkeypatch.setattr(index.bot, "caption", lambda *_: "analytic")
    monkeypatch.setattr(index, "send_card", lambda *_: True)
    assert index.run_digest()["sent"] == 2  # owner analytic and the leader's card
    method, params, files = [e for e in events if e[0] == "sendPhoto"][-1]
    assert params["chat_id"] == 701 and files["photo"][2] == "image/png"
    assert params["reply_markup"]["inline_keyboard"][0][0]["text"] == "Batafsil — ilovada"
    # 2-may: central bank +0.6 and the boundary 0.15 (neutral), trade -0.6; ad/foreign/digest/non-economic
    # posts count only in the total of 7. Shares 33.3 each: the largest remainder goes to the first.
    caption = unescape(params["caption"])
    n = len(index.leader.active(index.q))
    assert caption.startswith(f"<b>2-may, shanba · {n} ta kanal</b>\n")
    assert "Iqtisodiy xabarlar: <b>3 ta</b> (jami 7 ta)" in caption
    assert "Ijobiy <b>34%</b> · Neytral <b>33%</b> · Salbiy <b>33%</b>" in caption
    assert "Kayfiyat: <b>0</b> (1-may: xabar yo'q)" in caption
    names = [index.bot.topic_name("uz", t) for t in ("central_bank", "trade")]
    assert caption.endswith(f"Ko'p yozilgan mavzular: {names[0]} 2, {names[1]} 1")
    assert str(index.bot.user_row(index.q, 701)["digest_day"]) == "2026-05-02"
    assert index.run_digest()["sent"] == 0  # the 13:00 rerun


def test_language_change_moves_leader_menu(account, fresh_db, monkeypatch):
    events = _fake_tg(monkeypatch)
    index.handle_update(press(701, "lang:ru:p"))
    menu = [e[1] for e in events if e[0] == "setChatMenuButton"][-1]
    assert menu["menu_button"]["text"] == "Приложение"


def test_leader_today_and_week_are_personal(account, news, fresh_db, monkeypatch):
    events = _fake_tg(monkeypatch)
    index.q("insert into leader_prefs (account_id, channels, topics) values (%s, %s, %s)",
            (account, [], ["central_bank", "trade"]))
    day = {"kind": "kun", "start": "2026-05-02", "end": "2026-05-02"}
    week = {"kind": "hafta", "start": "2026-04-27", "end": "2026-05-03"}
    monkeypatch.setattr(index, "summary", lambda kind, start=None: week if kind == "hafta" else day)
    index.handle_update(upd(701, "/today"))
    method, params, files = [e for e in events if e[0] == "sendPhoto"][-1]
    assert params["chat_id"] == 701 and files and "Iqtisodiy xabarlar: <b>3 ta</b>" in params["caption"]
    index.handle_update(upd(701, "/week"))
    assert fresh_db[-1][0] == 701 and "O'tgan hafta" in unescape(fresh_db[-1][1])
    assert len([e for e in events if e[0] == "sendPhoto"]) == 1  # the week is text
    assert index.bot.user_row(index.q, 701)["digest_day"] is None  # on demand, not the morning digest
    monkeypatch.setattr(index, "summary", lambda kind, start=None: None)
    index.handle_update(upd(701, "/today"))
    assert fresh_db[-1][1] == index.bot.tr("uz", "no_data")


def test_leader_logout_restores_default_menu(account, fresh_db, monkeypatch):
    events = _fake_tg(monkeypatch)
    index.bot.set_lang(index.q, 701, "uz")
    index.handle_update(upd(701, "/logout"))
    assert [e[0] for e in events[-2:]] == ["deleteMyCommands", "setChatMenuButton"]
    assert events[-1][1] == {"chat_id": 701}
