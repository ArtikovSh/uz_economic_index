"""Posts kept one file per month, and the model's headline (labels v6)."""
import os

import pandas as pd

import store
from llm_classifier import _to_label
from post_text import post_parts


def row(mid, at):
    r = {c: None for c in store.LEDGER_COLS}
    r.update({"date_local": at, "date": at, "channel": "@a", "message_id": mid, "raw_text": "x"})
    return r


def test_posts_live_in_one_file_per_month(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "MESSAGES_DIR", str(tmp_path / "messages"))
    monkeypatch.setattr(store, "MASTER_CSV", str(tmp_path / "messages.csv"))
    pd.DataFrame([row(1, "2026-02-03 10:00")], columns=store.LEDGER_COLS).to_csv(store.MASTER_CSV, index=False)
    ledger = store.load_ledger()                                   # the older single file still reads
    assert len(ledger) == 1
    new = pd.DataFrame([row(2, "2026-03-01 09:00"), row(3, "2026-02-28 23:00")], columns=store.LEDGER_COLS)
    ledger = store.append_ledger(ledger, new)                      # moved to monthly files, then appended
    assert sorted(os.listdir(store.MESSAGES_DIR)) == ["2026-02.csv", "2026-03.csv"]
    assert not os.path.exists(store.MASTER_CSV) and len(store.load_ledger()) == 3 == len(ledger)
    kept = store.load_ledger()
    store.write_ledger(kept[kept["message_id"] == 2])               # history/rebuild rewrite everything
    assert sorted(os.listdir(store.MESSAGES_DIR)) == ["2026-03.csv"]


def test_headline_from_the_model():
    raw = ("Узбекистан и Индия находятся на завершающей стадии переговоров о поставках урана. "
           "Стороны «очень близки» к подписанию документа.")
    head, body = post_parts(raw, 200, headline="Узбекистан и Индия близки к соглашению по урану")
    assert head == "Узбекистан и Индия близки к соглашению по урану" and body.startswith("Узбекистан и Индия находятся")
    own = "**Eksport 18% oshdi**\nStatistika agentligi ma'lumoti."
    assert post_parts(own, 100, headline="Eksport 18% oshdi") == ("Eksport 18% oshdi", "Statistika agentligi ma'lumoti.")
    assert post_parts(own, 100) == ("Eksport 18% oshdi", "Statistika agentligi ma'lumoti.")       # no headline: first line
    assert _to_label({"economic": True, "topic": "trade", "headline": "  Eksport \n oshdi "})["headline"] == "Eksport oshdi"
    assert _to_label({"economic": True, "topic": "trade"})["headline"] is None


def test_hashtags_and_channel_slogans_are_not_text():
    raw = ("#Диққат #Тарқатинг\n**Бензин нархи 300 сўмга ошди**\nЯнги нархлар эртадан амал қилади.\n\n"
           "Яқинларга ҳам улашинг!\n\n@QORAXABAR - Телевизорда кўрсатилмайдиган махфий хабарлар канали!")
    assert post_parts(raw, 200) == ("Бензин нархи 300 сўмга ошди", "Янги нархлар эртадан амал қилади.")
    oper = "Дизель арзонлади. Батафсил видеода\n\n@OPER_UZ – ОПЕРАТИВ ВА ХАВФЛИ ЯНГИЛИКЛАР КАНАЛИ!"
    assert post_parts(oper, 200) == ("Дизель арзонлади.", "")
    shop = ("Нарх ошди\nТафсилоти шу.\nБу видеони аёлларга юбориб қўйинг.\n"
            "ККатталар канали 👉****@SHOPIRLAR**** га обуна бўлинг, зўрлари бизда**")
    assert post_parts(shop, 200) == ("Нарх ошди", "Тафсилоти шу.")
    oblako = ("Курс вырос.\nДанные ЦБ.\n\n**Распространите сообщение**\n\n👉 __Будьте в курсе последних \n"
              "новостей вместе с __[**__@oblakouz__**](https://t.me/+abc)")
    assert post_parts(oblako, 200) == ("Курс вырос.", "Данные ЦБ.")
    # kept: a word cut by a line break, a sentence that only mentions relatives, subscribers' news
    kept = "Йўл-\nтранспорт ҳодисаси\nҲалок бўлганларнинг яқинларига ёрдам юборилди.\nОбуначиларимиз видеони синаб кўришди."
    assert post_parts(kept, 300)[1] == ("транспорт ҳодисаси Ҳалок бўлганларнинг яқинларига ёрдам юборилди. "
                                        "Обуначиларимиз видеони синаб кўришди.")
    # a stored "#Тезкор" headline is a label: the post's own first line is used instead
    assert post_parts("#Тезкор\nЧорсуда ёнғин\nМатн.", 100, headline="#Тезкор") == ("Чорсуда ёнғин", "Матн.")
    assert post_parts("Матн.", 100, headline="#BREAKING | Катта ўзгариш")[0] == "Катта ўзгариш"
    assert _to_label({"economic": False, "headline": "#Тезкор #Даҳшат | Чорсуда ёнғин"})["headline"] == "Чорсуда ёнғин"
    assert _to_label({"economic": False, "headline": "#Тезкор"})["headline"] is None
