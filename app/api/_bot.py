"""
The bot's words and messages in three languages (uz / ru / en), its own tables, and the data
behind the daily and weekly summaries. Telegram calls stay in index.py; functions here only read
the database (through `q`, as in _auth.py) and build text and keyboards.

Icons: after /setup has created the bot's custom emoji sets (_botsetup.py) and checked that the
bot may use them (its owner has Telegram Premium), `em` maps icon names to custom emoji ids.
Without them messages carry no icons at all, never plain emoji.
"""
from datetime import date, timedelta
from html import escape

LANGS = ("uz", "ru", "en")
LANG_NAMES = {"uz": "O‘zbekcha", "ru": "Русский", "en": "English"}

SCHEMA = """
create table if not exists bot_users (
    telegram_id   bigint primary key,
    lang          text check (lang in ('uz','ru','en')),
    digest        boolean not null default true,
    digest_day    date,                 -- last daily summary sent
    digest_week   date,                 -- start of the last weekly summary sent
    blocked_bot   boolean not null default false,
    started_at    timestamptz not null default now()
);
create table if not exists bot_settings (
    key        text primary key,
    value      jsonb not null,
    changed_at timestamptz not null default now()
);
create table if not exists bot_cards (     -- Telegram file id of each rendered card, uploaded once
    kind       text not null,
    period     text not null,
    lang       text not null,
    file_id    text not null,
    created_at timestamptz not null default now(),
    primary key (kind, period, lang)
);
alter table bot_users    enable row level security;
alter table bot_settings enable row level security;
alter table bot_cards    enable row level security;
"""

# ------------------------------------------------------------------ texts ---
T = {
    "uz": {
        "brand_tag": "O‘zbekiston iqtisodiy yangiliklar indeksi",
        "about": "Har kuni E’tibor (EAI) va Kayfiyat (ESI) ko‘rsatkichlari, mavzular va asosiy xabarlar.",
        "pick": "Tilni tanlang · Выберите язык · Choose a language",
        "login_title": "Kirish",
        "login_text": "Bot va dashboard faqat ruxsat berilgan foydalanuvchilar uchun. "
                      "Administrator bergan login va parol bilan kiring.",
        "login_note": "Parol chatga yozilmaydi — u himoyalangan oynada kiritiladi.",
        "login_btn": "Kirish",
        "blocked_title": "Hisob bloklangan",
        "blocked_text": "Kirish uchun administratorga murojaat qiling.",
        "expired_title": "Kirish muddati tugagan",
        "expired_text": "Muddatni uzaytirish uchun administratorga murojaat qiling.",
        "contact_btn": "Administratorga murojaat",
        "activated": "Hisob faollashtirildi",
        "morning": "Kunlik xulosa har kuni ertalab shu yerga keladi.",
        "login_role": "Login: {login} · Rol: {role}",
        "today": "Kunlik xulosa", "week": "Haftalik xulosa", "topics": "Mavzular", "top": "Asosiy xabarlar",
        "today_s": "Kunlik", "week_s": "Haftalik", "top_s": "Xabarlar",
        "app": "Dashboard", "open_app": "Dashboardni ochish", "admin_btn": "Admin paneli",
        "requests_btn": "Murojaatlarni ochish",
        "daily_title": "Kunlik xulosa · {d}", "weekly_title": "Haftalik xulosa · {d}",
        "eai": "E’tibor (EAI)", "esi": "Kayfiyat (ESI)", "pp": "f.b.",
        "econ_day": "Iqtisodiy xabarlar: {e} / {n} · {c}/{t} kanal",
        "econ_week": "Iqtisodiy xabarlar: {e} / {n} · {d}/{t} kun",
        "topics_day": "Kun mavzulari: {x}", "topics_week": "Hafta mavzulari: {x}",
        "lifted": "ESI ni ko‘targan: {x}", "pulled": "ESI ni tushirgan: {x}",
        "topics_title": "Mavzular · {d}", "topics_sub": "{n} ta iqtisodiy xabar",
        "top_title": "Asosiy xabarlar · {d}",
        "tone": {"pos": "ijobiy", "neu": "neytral", "neg": "salbiy"},
        "no_data": "Hozircha ma’lumot yo‘q.", "no_posts": "Bu kun uchun iqtisodiy xabar yo‘q.",
        "me_title": "Hisobim", "me_owner": "Admin (bot egasi)", "me_login": "Login: {x}", "me_role": "Rol: {x}",
        "me_until": "Amal qiladi: {x} gacha", "me_forever": "Amal qiladi: muddatsiz",
        "digest_on": "Kunlik xulosa: yoqilgan", "digest_off": "Kunlik xulosa: o‘chirilgan",
        "digest_turn_off": "Kunlik xulosani o‘chirish", "digest_turn_on": "Kunlik xulosani yoqish",
        "digest_done_on": "Kunlik xulosa yoqildi", "digest_done_off": "Kunlik xulosa o‘chirildi",
        "lang_btn": "Tilni o‘zgartirish", "lang_title": "Til", "logout_btn": "Hisobdan chiqish",
        "logout_ask": "Hisobdan chiqasizmi? Qayta kirish uchun login va parol kerak bo‘ladi.",
        "logout_yes": "Chiqish", "cancel": "Bekor qilish",
        "owner_stays": "Bot egasi hisobdan chiqmaydi.",
        "help": "<b>Buyruqlar</b>\n/today — kunlik xulosa\n/week — haftalik xulosa\n/topics — kun mavzulari\n"
                "/top — asosiy xabarlar\n/app — dashboard\n/me — hisobim\n/lang — til\n/help — yordam",
        "unknown": "Buyruq tushunilmadi. Buyruqlar ro‘yxati: /help",
        "admin_moved": "Foydalanuvchilar va murojaatlar admin panelida boshqariladi.",
        "new_request": "Yangi murojaat",
        "creds_title": "Kirish ma’lumoti", "creds_password": "Parol: {x}",
        "creds_note": "Kirish uchun quyidagi tugmani bosing. Login faqat shu Telegram hisobida ishlaydi.",
        "rejected": "Kirish so‘rovingiz rad etildi.",
        "no_app": "Mini App hali ulanmagan.",
        "roles": {"admin": "Admin", "analyst": "Analitik", "economist": "Iqtisodchi"},
        "reasons": {"access": "Kirish olish", "reset": "Parolni tiklash", "other": "Boshqa"},
        "months": ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr",
                   "oktabr", "noyabr", "dekabr"],
        "topic_names": {
            "prices_inflation": "Narx va inflatsiya", "currency_fx": "Valyuta kursi", "fiscal": "Byudjet va soliq",
            "trade": "Tashqi savdo", "macro": "Makroiqtisodiyot", "central_bank": "Markaziy bank",
            "banking_finance": "Bank va moliya", "labour_income": "Mehnat va daromad", "energy_utility": "Energetika",
            "business": "Biznes", "construction_realty": "Qurilish"},
        "cmd": {"today": "Kunlik xulosa", "week": "Haftalik xulosa", "topics": "Kun mavzulari",
                "top": "Asosiy xabarlar", "app": "Dashboard", "me": "Hisobim", "lang": "Til", "help": "Yordam",
                "setup": "Bot sozlamalari"},
        "description": "O‘zbekiston iqtisodiy yangiliklar indeksi.\n\n"
                       "Har kuni yetakchi Telegram kanallaridagi xabarlardan ikki ko‘rsatkich hisoblanadi: "
                       "E’tibor (EAI) — iqtisodiy xabarlar ulushi va Kayfiyat (ESI) — ijobiy va salbiy "
                       "xabarlar balansi.\n\nBot va dashboard administrator bergan login bilan ishlaydi.",
        "short": "O‘zbekiston iqtisodiy yangiliklar indeksi: E’tibor (EAI) va Kayfiyat (ESI) har kuni.",
    },
    "ru": {
        "brand_tag": "Индекс экономических новостей Узбекистана",
        "about": "Каждый день — показатели Внимание (EAI) и Настроение (ESI), темы и главные новости.",
        "pick": "Tilni tanlang · Выберите язык · Choose a language",
        "login_title": "Вход",
        "login_text": "Бот и дашборд доступны только авторизованным пользователям. "
                      "Войдите с логином и паролем, выданными администратором.",
        "login_note": "Пароль не пишется в чат — он вводится в защищённом окне.",
        "login_btn": "Войти",
        "blocked_title": "Аккаунт заблокирован",
        "blocked_text": "Чтобы получить доступ, обратитесь к администратору.",
        "expired_title": "Срок доступа истёк",
        "expired_text": "Чтобы продлить доступ, обратитесь к администратору.",
        "contact_btn": "Написать администратору",
        "activated": "Аккаунт активирован",
        "morning": "Итоги дня будут приходить сюда каждое утро.",
        "login_role": "Логин: {login} · Роль: {role}",
        "today": "Итоги дня", "week": "Итоги недели", "topics": "Темы", "top": "Главные новости",
        "today_s": "За день", "week_s": "За неделю", "top_s": "Новости",
        "app": "Дашборд", "open_app": "Открыть дашборд", "admin_btn": "Админ-панель",
        "requests_btn": "Открыть обращения",
        "daily_title": "Итоги дня · {d}", "weekly_title": "Итоги недели · {d}",
        "eai": "Внимание (EAI)", "esi": "Настроение (ESI)", "pp": "п.п.",
        "econ_day": "Экономических новостей: {e} из {n} · каналов {c}/{t}",
        "econ_week": "Экономических новостей: {e} из {n} · дней {d}/{t}",
        "topics_day": "Темы дня: {x}", "topics_week": "Темы недели: {x}",
        "lifted": "Подняли ESI: {x}", "pulled": "Снизили ESI: {x}",
        "topics_title": "Темы · {d}", "topics_sub": "Экономических новостей: {n}",
        "top_title": "Главные новости · {d}",
        "tone": {"pos": "позитив", "neu": "нейтрально", "neg": "негатив"},
        "no_data": "Данных пока нет.", "no_posts": "За этот день экономических новостей нет.",
        "me_title": "Мой аккаунт", "me_owner": "Админ (владелец бота)", "me_login": "Логин: {x}",
        "me_role": "Роль: {x}", "me_until": "Действует до {x}", "me_forever": "Действует бессрочно",
        "digest_on": "Итоги дня: включены", "digest_off": "Итоги дня: выключены",
        "digest_turn_off": "Выключить итоги дня", "digest_turn_on": "Включить итоги дня",
        "digest_done_on": "Итоги дня включены", "digest_done_off": "Итоги дня выключены",
        "lang_btn": "Сменить язык", "lang_title": "Язык", "logout_btn": "Выйти из аккаунта",
        "logout_ask": "Выйти из аккаунта? Для повторного входа понадобятся логин и пароль.",
        "logout_yes": "Выйти", "cancel": "Отмена",
        "owner_stays": "Владелец бота не выходит из аккаунта.",
        "help": "<b>Команды</b>\n/today — итоги дня\n/week — итоги недели\n/topics — темы дня\n"
                "/top — главные новости\n/app — дашборд\n/me — мой аккаунт\n/lang — язык\n/help — помощь",
        "unknown": "Команда не распознана. Список команд: /help",
        "admin_moved": "Пользователи и обращения управляются в админ-панели.",
        "new_request": "Новое обращение",
        "creds_title": "Данные для входа", "creds_password": "Пароль: {x}",
        "creds_note": "Нажмите кнопку ниже, чтобы войти. Логин работает только в этом аккаунте Telegram.",
        "rejected": "Ваш запрос на доступ отклонён.",
        "no_app": "Mini App ещё не подключено.",
        "roles": {"admin": "Админ", "analyst": "Аналитик", "economist": "Экономист"},
        "reasons": {"access": "Получить доступ", "reset": "Сбросить пароль", "other": "Другое"},
        "months": ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября",
                   "октября", "ноября", "декабря"],
        "topic_names": {
            "prices_inflation": "Цены и инфляция", "currency_fx": "Валютный курс", "fiscal": "Бюджет и налоги",
            "trade": "Внешняя торговля", "macro": "Макроэкономика", "central_bank": "Центральный банк",
            "banking_finance": "Банки и финансы", "labour_income": "Труд и доходы", "energy_utility": "Энергетика",
            "business": "Бизнес", "construction_realty": "Строительство"},
        "cmd": {"today": "Итоги дня", "week": "Итоги недели", "topics": "Темы дня", "top": "Главные новости",
                "app": "Дашборд", "me": "Мой аккаунт", "lang": "Язык", "help": "Помощь",
                "setup": "Настройка бота"},
        "description": "Индекс экономических новостей Узбекистана.\n\n"
                       "Каждый день по сообщениям ведущих Telegram-каналов рассчитываются два показателя: "
                       "Внимание (EAI) — доля экономических новостей и Настроение (ESI) — баланс позитивных "
                       "и негативных новостей.\n\nБот и дашборд работают по логину, выданному администратором.",
        "short": "Индекс экономических новостей Узбекистана: Внимание (EAI) и Настроение (ESI) каждый день.",
    },
    "en": {
        "brand_tag": "Uzbekistan economic news index",
        "about": "Every day: the Attention (EAI) and Sentiment (ESI) indicators, topics and top posts.",
        "pick": "Tilni tanlang · Выберите язык · Choose a language",
        "login_title": "Sign in",
        "login_text": "The bot and dashboard are for authorised users only. "
                      "Sign in with the login and password issued by the administrator.",
        "login_note": "The password is never typed in the chat — it is entered in a protected window.",
        "login_btn": "Sign in",
        "blocked_title": "Account blocked",
        "blocked_text": "Contact the administrator to get access.",
        "expired_title": "Access expired",
        "expired_text": "Contact the administrator to extend your access.",
        "contact_btn": "Contact the administrator",
        "activated": "Account activated",
        "morning": "The daily summary will arrive here every morning.",
        "login_role": "Login: {login} · Role: {role}",
        "today": "Daily summary", "week": "Weekly summary", "topics": "Topics", "top": "Top posts",
        "today_s": "Daily", "week_s": "Weekly", "top_s": "Top posts",
        "app": "Dashboard", "open_app": "Open dashboard", "admin_btn": "Admin panel",
        "requests_btn": "Open requests",
        "daily_title": "Daily summary · {d}", "weekly_title": "Weekly summary · {d}",
        "eai": "Attention (EAI)", "esi": "Sentiment (ESI)", "pp": "pp",
        "econ_day": "Economic posts: {e} of {n} · channels {c}/{t}",
        "econ_week": "Economic posts: {e} of {n} · days {d}/{t}",
        "topics_day": "Topics of the day: {x}", "topics_week": "Topics of the week: {x}",
        "lifted": "Lifted ESI: {x}", "pulled": "Pulled ESI down: {x}",
        "topics_title": "Topics · {d}", "topics_sub": "Economic posts: {n}",
        "top_title": "Top posts · {d}",
        "tone": {"pos": "positive", "neu": "neutral", "neg": "negative"},
        "no_data": "No data yet.", "no_posts": "No economic posts on this day.",
        "me_title": "My account", "me_owner": "Admin (bot owner)", "me_login": "Login: {x}", "me_role": "Role: {x}",
        "me_until": "Valid until {x}", "me_forever": "Valid with no end date",
        "digest_on": "Daily summary: on", "digest_off": "Daily summary: off",
        "digest_turn_off": "Turn off daily summary", "digest_turn_on": "Turn on daily summary",
        "digest_done_on": "Daily summary turned on", "digest_done_off": "Daily summary turned off",
        "lang_btn": "Change language", "lang_title": "Language", "logout_btn": "Sign out",
        "logout_ask": "Sign out? You will need your login and password to sign in again.",
        "logout_yes": "Sign out", "cancel": "Cancel",
        "owner_stays": "The bot owner does not sign out.",
        "help": "<b>Commands</b>\n/today — daily summary\n/week — weekly summary\n/topics — topics of the day\n"
                "/top — top posts\n/app — dashboard\n/me — my account\n/lang — language\n/help — help",
        "unknown": "Command not recognised. List of commands: /help",
        "admin_moved": "Users and requests are managed in the admin panel.",
        "new_request": "New request",
        "creds_title": "Sign-in details", "creds_password": "Password: {x}",
        "creds_note": "Tap the button below to sign in. The login works only in this Telegram account.",
        "rejected": "Your access request was declined.",
        "no_app": "The Mini App is not connected yet.",
        "roles": {"admin": "Admin", "analyst": "Analyst", "economist": "Economist"},
        "reasons": {"access": "Get access", "reset": "Reset password", "other": "Other"},
        "months": ["January", "February", "March", "April", "May", "June", "July", "August", "September",
                   "October", "November", "December"],
        "topic_names": {
            "prices_inflation": "Prices & inflation", "currency_fx": "Exchange rate", "fiscal": "Budget & taxes",
            "trade": "Foreign trade", "macro": "Macroeconomy", "central_bank": "Central bank",
            "banking_finance": "Banking & finance", "labour_income": "Labour & income", "energy_utility": "Energy",
            "business": "Business", "construction_realty": "Construction"},
        "cmd": {"today": "Daily summary", "week": "Weekly summary", "topics": "Topics of the day",
                "top": "Top posts", "app": "Dashboard", "me": "My account", "lang": "Language", "help": "Help",
                "setup": "Bot setup"},
        "description": "Uzbekistan economic news index.\n\n"
                       "Every day two indicators are computed from the posts of leading Telegram channels: "
                       "Attention (EAI), the share of economic news, and Sentiment (ESI), the balance of "
                       "positive and negative news.\n\nThe bot and dashboard work with a login issued by "
                       "the administrator.",
        "short": "Uzbekistan economic news index: Attention (EAI) and Sentiment (ESI), every day.",
    },
}
COMMANDS = ("today", "week", "topics", "top", "app", "me", "lang", "help")

# icon name -> fallback emoji Telegram requires next to a custom emoji (never shown when it works)
TILES = {"logo": "📈", "eai": "🎯", "esi": "💬", "news": "📰", "topics": "🗂", "up": "📈", "down": "📉",
         "week": "📅", "user": "👤", "bell": "🔔", "lock": "🔒", "globe": "🌐", "check": "✅",
         "rise": "\u2197\ufe0f", "fall": "\u2198\ufe0f"}
GLYPHS = {"dashboard": "📊", "topics": "🗂", "news": "📰", "week": "📅", "eai": "🎯", "esi": "💬",
          "user": "👤", "globe": "🌐", "bell": "🔔", "login": "🔑", "back": "◀️", "up": "⬆️",
          "down": "⬇️"}


def tr(lang, key, **kw):
    s = T.get(lang, T["uz"]).get(key, T["uz"].get(key, key))
    return s.format(**kw) if kw else s


def ic(em, name):
    """A tile icon before a line, or nothing when the bot has no usable custom emoji."""
    eid = (em or {}).get("t", {}).get(name) if name else None
    return f'<tg-emoji emoji-id="{eid}">{TILES[name]}</tg-emoji> ' if eid else ""


def button(text, em=None, glyph=None, style=None, **action):
    """Inline button; `action` is callback_data=..., web_app={...} or url=... ."""
    b = {"text": text, **action}
    eid = (em or {}).get("g", {}).get(glyph) if glyph else None
    if eid:
        b["icon_custom_emoji_id"] = eid
    if style:
        b["style"] = style
    return b


# --------------------------------------------------------- language --------
def detect(tg_user):
    code = str((tg_user or {}).get("language_code") or "")[:2]
    return code if code in ("ru", "en") else "uz"


def user_row(q, tg_id):
    return q("select * from bot_users where telegram_id=%s", (tg_id,), one=True)


def lang_of(q, tg_user):
    row = user_row(q, tg_user["id"])
    return (row or {}).get("lang") or detect(tg_user)


def set_lang(q, tg_id, lang):
    if lang not in LANGS:
        return False
    q("""insert into bot_users (telegram_id, lang) values (%s, %s)
         on conflict (telegram_id) do update set lang = excluded.lang, blocked_bot = false""", (tg_id, lang))
    return True


def remember(q, tg_id):
    """First contact: a row with the defaults (daily summary on). Returns whether it was new."""
    row = q("""insert into bot_users (telegram_id) values (%s)
               on conflict (telegram_id) do update set blocked_bot = false
               returning (xmax = 0) as new""", (tg_id,), one=True)
    return bool(row and row["new"])


def toggle_digest(q, tg_id):
    row = q("""insert into bot_users (telegram_id, digest) values (%s, false)
               on conflict (telegram_id) do update set digest = not bot_users.digest
               returning digest""", (tg_id,), one=True)
    return row["digest"]


# ------------------------------------------------------------ formats -------
MINUS = "−"


def num(v, lang, digits=0):
    if v is None:
        return "—"
    s = f"{abs(v):,.{digits}f}"
    if lang != "en":
        s = s.replace(",", " ").replace(".", ",")
    return (MINUS if v < 0 and round(abs(v), digits) else "") + s


def signed(v, lang, digits=1):
    if v is None:
        return "—"
    body = num(abs(v), lang, digits)
    return ("+" if v > 0 and round(v, digits) else MINUS if v < 0 and round(-v, digits) else "") + body


def day_label(d, lang, year=True):
    d = date.fromisoformat(str(d)) if not isinstance(d, date) else d
    m = tr(lang, "months")[d.month - 1]
    s = f"{d.day}-{m}" if lang == "uz" else f"{d.day} {m}"
    return f"{s} {d.year}" if year else s


def range_label(a, b, lang):
    """'21–27-sentabr 2026', '29-sentabr – 5-oktabr 2026' (and the same in ru / en)."""
    a, b = (date.fromisoformat(str(x)) if not isinstance(x, date) else x for x in (a, b))
    if (a.year, a.month) == (b.year, b.month):
        return f"{a.day}–{day_label(b, lang)}"
    return f"{day_label(a, lang, a.year != b.year)} – {day_label(b, lang)}"


def delta(v, lang, unit="", em=None, tone=False):
    """The change since the previous period, as HTML: '▲ 1,7 f.b.' / '▼ 3,0' / '0,0'. With the
    bot's icons the arrow is a custom emoji: in the text colour for EAI (attention is neither good
    nor bad), teal or orange for ESI (tone=True)."""
    if v is None:
        return ""
    v = round(v, 1)
    arrow = "▲ " if v > 0 else "▼ " if v < 0 else ""
    if v and em:
        key, name = ("t", "rise" if v > 0 else "fall") if tone else ("g", "up" if v > 0 else "down")
        eid = em.get(key, {}).get(name)
        if eid:
            arrow = f'<tg-emoji emoji-id="{eid}">{(TILES if tone else GLYPHS)[name]}</tg-emoji> '
    return f"  {arrow}{num(abs(v), lang, 1)}{(' ' + escape(unit)) if unit else ''}"


def topic_name(lang, key):
    return tr(lang, "topic_names").get(key, key)


# --------------------------------------------------------------- data -------
DAY = "((date_utc at time zone 'UTC') + interval '5 hours')::date"
COUNTED = "is_economic and not is_ad and not is_foreign and not is_digest"
POS, NEG = "sentiment > 0.15::real", "sentiment < -0.15::real"
ROW = """period, start_date, end_date, days, days_expected, posts, nonad, econ, pos, neg, eai, esi"""


def _f(v):
    return None if v is None else float(v)


def _topics(q, lo, hi):
    """Per topic: posts touching it (n, p, g) and its share of ESI (wp - wg; a post with k topics
    gives each 1/k, so the shares add up to ESI)."""
    ts = "coalesce(topics, array[primary_topic])"
    rows = q(f"""select t, count(*) n, count(*) filter (where {POS}) p, count(*) filter (where {NEG}) g,
                        sum(case when {POS} then 1.0 / k else 0 end)::float wp,
                        sum(case when {NEG} then 1.0 / k else 0 end)::float wg
                 from (select *, cardinality({ts}) k from posts
                       where {COUNTED} and {DAY} between %s and %s) x, unnest({ts}) t
                 group by 1 order by 2 desc, 1""", (lo, hi)) or []
    return [{"t": r["t"], "n": r["n"], "p": r["p"], "g": r["g"], "wp": r["wp"], "wg": r["wg"]} for r in rows]


def _series(rows, end, step, n):
    """n consecutive periods ending at `end`, None where a period has no row; leading gaps
    before the first observed period are dropped."""
    have = {str(r["start_date"]): r for r in rows}
    out = []
    for i in range(n - 1, -1, -1):
        s = (end - step * i).isoformat()
        r = have.get(s)
        out.append({"start": s, "eai": _f(r["eai"]) if r else None, "esi": _f(r["esi"]) if r else None})
    while len(out) > 1 and out[0]["eai"] is None and out[0]["esi"] is None:
        out.pop(0)
    return out


def summary(q, kind, start=None):
    """Everything a daily ('kun') or weekly ('hafta') summary shows, for the given period start
    or the latest closed one; None when there is none. The dict is also the card's input."""
    if start:
        cur = q(f"select {ROW} from indices where period_type=%s and start_date=%s", (kind, start), one=True)
    else:
        cur = q(f"select {ROW} from indices where period_type=%s order by end_date desc limit 1", (kind,), one=True)
    if not cur:
        return None
    step = timedelta(days=1 if kind == "kun" else 7)
    n = 30 if kind == "kun" else 12
    s, e = cur["start_date"], cur["end_date"]
    hist = q(f"""select {ROW} from indices where period_type=%s and start_date between %s and %s""",
             (kind, s - step * (n - 1), s)) or []
    prev = next((r for r in hist if r["start_date"] == s - step), None)
    chans = q(f"select count(distinct channel) n from posts where {DAY} between %s and %s", (s, e), one=True)["n"]
    try:
        active = q("select count(*) n from channels where active", one=True)["n"]
    except Exception:                                   # the channels table appears with the admin panel
        active = 0
    eai, esi = _f(cur["eai"]), _f(cur["esi"])
    return {
        "kind": kind, "period": cur["period"], "start": s.isoformat(), "end": e.isoformat(),
        "eai": eai, "esi": esi,
        "d_eai": round(eai - _f(prev["eai"]), 1) if prev and eai is not None and prev["eai"] is not None else None,
        "d_esi": round(esi - _f(prev["esi"]), 1) if prev and esi is not None and prev["esi"] is not None else None,
        "nonad": cur["nonad"], "econ": cur["econ"], "channels": chans, "channels_total": max(active, chans),
        "days": cur["days"], "days_expected": cur["days_expected"],
        "series": _series(hist, s, step, n), "topics": _topics(q, s, e),
    }


def contributions(topics, econ):
    """Topics that lifted and pulled down ESI most (net contribution, two of each)."""
    if not econ:
        return [], []
    share = lambda x: round(x.get("wp", x["p"]) - x.get("wg", x["g"]), 4)
    net = sorted(((share(x), x["n"], x["t"]) for x in topics if share(x)), key=lambda v: (-v[0], -v[1]))
    up = [t for v, _, t in net if v > 0][:2]
    down = [t for v, _, t in sorted(net, key=lambda v: (v[0], -v[1])) if v < 0][:2]
    return up, down


def top_posts(q, lo, hi, n=5):
    return q(f"""select channel, message_id, views, primary_topic, raw_text, headline,
                        case when {POS} then 'pos' when {NEG} then 'neg' else 'neu' end tone
                 from posts where {DAY} between %s and %s and {COUNTED}
                 order by views + 2 * forwards desc, views desc limit %s""", (lo, hi, n)) or []


# ----------------------------------------------------------- messages -------
def caption(data, lang, em=None):
    """Text under the daily or weekly card (fits Telegram's 1024-character caption)."""
    daily = data["kind"] == "kun"
    when = period_label(data, lang)
    names = lambda keys: ", ".join(topic_name(lang, k) for k in keys)
    lines = [ic(em, "logo" if daily else "week") + "<b>" + escape(tr(lang, "daily_title" if daily else "weekly_title", d=when)) + "</b>", ""]
    lines.append(f"{ic(em, 'eai')}{escape(tr(lang, 'eai'))}: <b>{num(data['eai'], lang, 1)}%</b>"
                 + delta(data["d_eai"], lang, tr(lang, "pp"), em))
    lines.append(f"{ic(em, 'esi')}{escape(tr(lang, 'esi'))}: <b>{signed(data['esi'], lang)}</b>"
                 + delta(data["d_esi"], lang, em=em, tone=True))
    if daily:
        econ = tr(lang, "econ_day", e=num(data["econ"], lang), n=num(data["nonad"], lang),
                  c=data["channels"], t=data["channels_total"])
    else:
        econ = tr(lang, "econ_week", e=num(data["econ"], lang), n=num(data["nonad"], lang),
                  d=data["days"], t=data["days_expected"])
    lines.append(ic(em, "news") + escape(econ))
    top = [x for x in data["topics"]][:3]
    up, down = contributions(data["topics"], data["econ"])
    if top or up or down:
        lines.append("")
    if top:
        lst = ", ".join(f"{topic_name(lang, x['t'])} ({x['n']})" for x in top)
        lines.append(ic(em, "topics") + escape(tr(lang, "topics_day" if daily else "topics_week", x=lst)))
    if up:
        lines.append(ic(em, "up") + escape(tr(lang, "lifted", x=names(up))))
    if down:
        lines.append(ic(em, "down") + escape(tr(lang, "pulled", x=names(down))))
    return "\n".join(lines)


def topics_text(data, lang, em=None):
    if not data or not data["topics"]:
        return tr(lang, "no_data")
    when = period_label(data, lang)
    out = [ic(em, "topics") + "<b>" + escape(tr(lang, "topics_title", d=when)) + "</b>",
           escape(tr(lang, "topics_sub", n=num(data["econ"], lang))), ""]
    for x in data["topics"]:
        esi = 100 * (x["p"] - x["g"]) / x["n"] if x["n"] else None
        out.append(f"<b>{escape(topic_name(lang, x['t']))}</b> — {num(x['n'], lang)} · ESI {signed(esi, lang)}")
    return "\n".join(out)


def period_label(data, lang):
    if data["kind"] == "kun":
        return day_label(data["start"], lang)
    return range_label(data["start"], data["end"], lang)


def top_text(rows, data, lang, titles, parts, em=None):
    """Each post: the channel (a link to the post), topic and tone first, then the headline in
    bold and up to 100 characters of the text. `parts(raw)` splits a post into (headline, text)."""
    if not rows:
        return tr(lang, "no_posts")
    out = [ic(em, "news") + "<b>" + escape(tr(lang, "top_title", d=period_label(data, lang))) + "</b>"]
    for i, r in enumerate(rows, 1):
        ch = str(r["channel"])
        link = f"https://t.me/{ch.lstrip('@')}/{r['message_id']}"
        name = escape(titles.get(ch, ch.lstrip("@")))
        head, body = parts(r["raw_text"], headline=r.get("headline"))
        mark = ic(em, {"pos": "rise", "neg": "fall"}.get(r["tone"], ""))
        meta = (f'<a href="{escape(link)}">{name}</a> · {escape(topic_name(lang, r["primary_topic"]))} · '
                f'{mark}{escape(tr(lang, "tone")[r["tone"]])}')
        out.append(f"\n{i}. <i>{meta}</i>\n<b>{escape(head)}</b>" + (f"\n{escape(body)}" if body else ""))
    return "\n".join(out)


def welcome_text(lang, em=None, with_pick=True):
    text = (f"{ic(em, 'logo')}<b>UZ Economic Index</b>\n{escape(tr(lang, 'brand_tag'))}.\n"
            f"{escape(tr(lang, 'about'))}")
    return text + (f"\n\n{ic(em, 'globe')}{escape(tr(lang, 'pick'))}" if with_pick else "")


def gate_text(state, lang, em=None):
    if state == "login":
        return (f"{ic(em, 'lock')}<b>{escape(tr(lang, 'login_title'))}</b>\n{escape(tr(lang, 'login_text'))}\n\n"
                f"<i>{escape(tr(lang, 'login_note'))}</i>")
    return (f"{ic(em, 'lock')}<b>{escape(tr(lang, state + '_title'))}</b>\n"
            f"{escape(tr(lang, state + '_text'))}")


def activated_text(acc, lang, em=None):
    role = tr(lang, "roles").get(acc["role"], acc["role"])
    return (f"{ic(em, 'check')}<b>{escape(tr(lang, 'activated'))}</b>\n"
            + tr(lang, "login_role", login=f"<code>{escape(acc['login'])}</code>", role=escape(role)) + "\n"
            + escape(tr(lang, "morning")))


def home_text(lang, em=None):
    return (f"{ic(em, 'logo')}<b>UZ Economic Index</b>\n{escape(tr(lang, 'brand_tag'))}.\n\n"
            f"{ic(em, 'bell')}{escape(tr(lang, 'morning'))}")


def me_text(acc, digest, lang, em=None):
    # short facts share a line: Telegram sizes the message by its longest line, and a narrow
    # message leaves the buttons under it wider than the message
    lines = [f"{ic(em, 'user')}<b>{escape(tr(lang, 'me_title'))}</b>"]
    if acc.get("owner"):
        lines.append(escape(tr(lang, "me_owner")))
    else:
        lines.append(tr(lang, "me_login", x=f"<code>{escape(acc['login'])}</code>") + " · "
                     + escape(tr(lang, "me_role", x=tr(lang, "roles").get(acc["role"], acc["role"]))))
        until = acc.get("expires_at")
        lines.append(escape(tr(lang, "me_until", x=until.strftime("%d.%m.%Y")) if until else tr(lang, "me_forever")))
    lines.append(escape(tr(lang, "lang_title")) + ": " + LANG_NAMES[lang] + " · "
                 + ic(em, "bell") + escape(tr(lang, "digest_on" if digest else "digest_off")))
    return "\n".join(lines)
