"""Shared, value-only Uzbek tables for the Excel and Sheets reports."""
import pandas as pd

from post_text import post_parts

MONTHS = ("Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust",
          "Sentabr", "Oktabr", "Noyabr", "Dekabr")
WEEKDAYS = ("dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba", "yakshanba")
TOPICS = {
    "prices_inflation": "Narx va inflatsiya", "currency_fx": "Valyuta kursi",
    "fiscal": "Byudjet va soliq", "trade": "Tashqi savdo", "macro": "Makroiqtisodiyot",
    "central_bank": "Markaziy bank", "banking_finance": "Bank va moliya",
    "labour_income": "Mehnat va daromad", "energy_utility": "Energetika",
    "business": "Biznes", "construction_realty": "Qurilish", "non_economic": "Iqtisodiy emas",
}
COUNTS = ["Jami xabarlar", "Reklama emas", "Iqtisodiy", "Ijobiy", "Neytral", "Salbiy"]
DAILY_COLUMNS = ["Sana", "Hafta kuni", *COUNTS, "EAI, %", "ESI", "Kanallar", "Izoh"]
PERIOD_COLUMNS = ["Davr", "Boshlanish", "Tugash", "Kunlar", "Kunlar (jami)", *COUNTS,
                  "EAI, %", "ESI", "EAI farqi", "ESI farqi", "Izoh"]
TOPIC_COLUMNS = ["Sana", "Mavzu", "Xabarlar", "Ijobiy", "Neytral", "Salbiy", "Mavzu ESI", "ESI'ga hissa"]
POST_COLUMNS = ["Sana", "Vaqt", "Kanal", "Sarlavha", "Matn boshi", "Mavzu", "Ohang",
                "Indeksda", "Sabab", "Ko'rishlar", "Forwardlar", "Havola"]


def _number(value, integer=False):
    if pd.isna(value):
        return None
    return int(value) if integer else round(float(value), 1)


def _table(rows, columns):
    # Object dtype preserves Python ints and actual None, including all-empty columns.
    frame = pd.DataFrame(rows, columns=columns, dtype=object)
    return frame.where(frame.notna(), None)


def _totals(row):
    return [_number(row[c], integer=True) for c in ("posts", "nonad", "econ", "pos", "neu", "neg")]


def _period_label(kind, start, end):
    if kind == "hafta":
        left = start.strftime("%d.%m" if start.year == end.year else "%d.%m.%Y")
        return f"{start.isocalendar().week}-hafta ({left}–{end:%d.%m.%Y})"
    if kind == "oy":
        return f"{MONTHS[start.month - 1]} {start.year}"
    if kind == "chorak":
        return f"{start.year}, {('I', 'II', 'III', 'IV')[(start.month - 1) // 3]} chorak"
    return str(start.year)


def _previous(kind, start):
    if kind == "hafta":
        return start - pd.Timedelta(days=7)
    return start - pd.DateOffset(months={"oy": 1, "chorak": 3, "yil": 12}[kind])


def _delta(current, previous):
    if pd.isna(current) or pd.isna(previous):
        return None
    return round(float(current) - float(previous), 1)


def ordered_posts(ledger):
    """Keep the shared post rows and Excel's extra columns in identical order."""
    return ledger.sort_values(["date_local", "channel", "message_id"], kind="stable").reset_index(drop=True)


def _posts(ledger):
    rows = []
    for post in ordered_posts(ledger).to_dict("records"):
        counted = post["econ"] == 1
        reason = None
        if not counted:
            reason = next((label for flag, label in (("is_ad", "reklama"), ("is_digest", "dayjest"),
                                                    ("is_foreign", "xorijiy"))
                           if pd.notna(post[flag]) and post[flag]), "iqtisodiy emas")
        head, body = post_parts(None if pd.isna(post["raw_text"]) else post["raw_text"], body_limit=200,
                                headline=None if pd.isna(post.get("headline")) else post.get("headline"))
        local = pd.Timestamp(post["date_local"])
        link = f"https://t.me/{post['channel'].lstrip('@')}/{int(post['message_id'])}"
        rows.append([local.strftime("%Y-%m-%d"), local.strftime("%H:%M"), post["channel"], head, body,
                     ", ".join(TOPICS.get(t, t) for t in _topic_keys(post)),
                     {1: "ijobiy", 0: "neytral", -1: "salbiy"}.get(post["tone"]),
                     "ha" if counted else "yo'q", reason, _number(post["views"], True),
                     _number(post["forwards"], True), link])
    return _table(rows, POST_COLUMNS)


def _topic_keys(post):
    """Every topic of a post (labels v6), else its one topic."""
    raw = post.get("topics")
    keys = [t for t in str(raw).split(",") if t] if isinstance(raw, str) and raw else []
    return keys or [post["primary_topic"]]


def _topics(ledger, days):
    posts = ledger.loc[ledger["econ"] == 1].copy()
    posts["_day"] = posts["date_local"].str[:10]
    posts = posts.loc[posts["_day"].isin(days)]
    totals = posts.groupby("_day").size()
    # a post counts in each of its topics; its share of ESI is split equally between them
    posts["_topic"] = [_topic_keys(p) for p in posts.to_dict("records")]
    posts["_weight"] = [1.0 / len(keys) for keys in posts["_topic"]]
    posts = posts.explode("_topic")
    rows = []
    for (day, topic), group in posts.groupby(["_day", "_topic"], sort=True):
        n = len(group)
        pos, neu, neg = (int((group["tone"] == tone).sum()) for tone in (1, 0, -1))
        share = (group["_weight"] * group["tone"].fillna(0)).sum()
        # Keep contributions additive; exporters display one decimal without rounding the values.
        rows.append([day, TOPICS.get(topic), n, pos, neu, neg, round(100 * (pos - neg) / n, 1),
                     100 * float(share) / int(totals[day])])
    return _table(rows, TOPIC_COLUMNS).sort_values(["Sana", "Xabarlar"], ascending=[True, False],
                                                  kind="stable").reset_index(drop=True)


def build_tables(indices, ledger):
    """Build seven ordered tables without changing either input or doing I/O."""
    channels = ledger.groupby(ledger["date_local"].str[:10])["channel"].nunique()
    daily = indices.loc[indices["period_type"] == "kun"].sort_values("start")
    rows = []
    for row in daily.to_dict("records"):
        start = pd.Timestamp(row["start"])
        day = start.strftime("%Y-%m-%d")
        rows.append([day, WEEKDAYS[start.weekday()], *_totals(row), _number(row["EAI"]),
                     _number(row["ESI"]), int(channels.get(day, 0)), row["note"]])
    tables = {"Kunlik": _table(rows, DAILY_COLUMNS)}
    for kind, title in (("hafta", "Haftalik"), ("oy", "Oylik"), ("chorak", "Choraklik"), ("yil", "Yillik")):
        periods = indices.loc[indices["period_type"] == kind].sort_values("start").to_dict("records")
        lookup = {pd.Timestamp(row["start"]): row for row in periods}
        rows = []
        for row in periods:
            start, end = pd.Timestamp(row["start"]), pd.Timestamp(row["end"])
            previous = lookup.get(_previous(kind, start), {})
            rows.append([_period_label(kind, start, end), start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"),
                         _number(row["days"], True), _number(row["days_expected"], True), *_totals(row),
                         _number(row["EAI"]), _number(row["ESI"]), _delta(row["EAI"], previous.get("EAI")),
                         _delta(row["ESI"], previous.get("ESI")), row["note"]])
        tables[title] = _table(rows, PERIOD_COLUMNS)
    tables["Mavzular"] = _topics(ledger, set(tables["Kunlik"]["Sana"]))
    tables["Xabarlar"] = _posts(ledger)
    return tables
