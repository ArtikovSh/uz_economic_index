"""Account preferences and unweighted news counts for the leadership view."""
from datetime import date, timedelta
from math import floor

import psycopg

import _bot as bot
import _channels as channels

SCHEMA = """
create table if not exists leader_prefs (
    account_id bigint primary key references accounts(id) on delete cascade,
    channels text[] not null default '{}',
    topics text[] not null default '{central_bank}',
    onboarded boolean not null default false,
    updated_at timestamptz not null default now()
);
alter table leader_prefs enable row level security;
"""

TOPIC_ORDER = ("central_bank", "currency_fx", "prices_inflation", "banking_finance", "fiscal", "macro",
               "trade", "business", "labour_income", "energy_utility", "transport", "construction_realty")


def active(q):
    return [r["handle"] for r in channels.listing(q) if r["active"]]


def valid_list(value, allowed, empty=True):
    return (isinstance(value, list) and (empty or bool(value))
            and all(isinstance(v, str) and v in allowed for v in value))


def prefs(q, account_id, telegram_id):
    row = q("select channels, topics, onboarded from leader_prefs where account_id=%s",
            (account_id,), one=True)
    row = row or {"channels": [], "topics": ["central_bank"], "onboarded": False}
    # Paused or deleted channels must not strand an existing account with an empty feed.
    available = set(active(q))
    row["channels"] = [c for c in row["channels"] if c in available]
    return {**row, "digest": (bot.user_row(q, telegram_id) or {}).get("digest", True)}


def set_prefs(q, account_id, telegram_id, body, topics):
    if ("channels" in body and not valid_list(body["channels"], active(q), empty=False)
            or "topics" in body and not valid_list(body["topics"], topics)
            or "onboarded" in body and not isinstance(body["onboarded"], bool)):
        return {"ok": False, "error": "bad_input"}
    # Update only supplied fields, including when two settings requests overlap.
    fields = [k for k in ("channels", "topics", "onboarded") if k in body]
    values = [list(dict.fromkeys(body[k])) if isinstance(body[k], list) else body[k] for k in fields]
    cols = ", ".join(["account_id"] + fields)
    placeholders = ", ".join(["%s"] * (len(fields) + 1))
    update = ", ".join([f"{k}=excluded.{k}" for k in fields] + ["updated_at=now()"])
    q(f"insert into leader_prefs ({cols}) values ({placeholders}) "
      f"on conflict (account_id) do update set {update}", [account_id] + values)
    return {"ok": True, "prefs": prefs(q, account_id, telegram_id)}


def leader_stats(q, selected, sql):
    """`sql`: index.py's SQL pieces (COUNTED, DAY, FINAL_DAYS, NEG, POS, TOPICS_OF), so the counts use
    the posts endpoint's final days, economic posts and tones. Passed in rather than imported:
    Vercel may load index.py under another module name, and importing it again would run it twice."""
    COUNTED, DAY, FINAL_DAYS = sql["COUNTED"], sql["DAY"], sql["FINAL_DAYS"]
    NEG, POS, TOPICS_OF = sql["NEG"], sql["POS"], sql["TOPICS_OF"]
    available = active(q)
    if not valid_list(selected, available):
        return {"ok": False, "error": "bad_input"}
    chosen = selected or available
    names = channels.titles(q)
    try:
        days = q("select start_date d from indices where period_type='kun' order by start_date") or []
        all_channels = q(f"""select {DAY} d, channel, count(*) n from posts where {DAY} in {FINAL_DAYS}
                              group by 1, 2 order by 1, 2""") or []
        counts = q(f"""select {DAY} d, channel, count(*) n from posts
                         where {DAY} in {FINAL_DAYS} and channel=any(%s)
                         group by 1, 2 order by 1, 2""", (chosen,)) or []
        tones = q(f"""select {DAY} d, topic,
                            count(*) filter (where {POS}) p,
                            count(*) filter (where not ({POS}) and not ({NEG})) u,
                            count(*) filter (where {NEG}) g
                       from posts cross join lateral
                            (select distinct t as topic from unnest({TOPICS_OF}) t) selected_topics
                       where {COUNTED} and {DAY} in {FINAL_DAYS} and channel=any(%s)
                       group by 1, 2 order by 1, 2""", (chosen,)) or []
        groups = q(f"""select d, ts,
                             count(*) filter (where {POS}) p,
                             count(*) filter (where not ({POS}) and not ({NEG})) u,
                             count(*) filter (where {NEG}) g
                      from (select {DAY} d, sentiment,
                                   array(select distinct t from unnest({TOPICS_OF}) t order by t) ts
                            from posts where {COUNTED} and {DAY} in {FINAL_DAYS}
                              and channel=any(%s)) counted
                      group by 1, 2 order by 1, 2""", (chosen,)) or []
    except psycopg.errors.UndefinedTable:
        days, all_channels, counts, tones, groups = [], [], [], [], []
    totals = {}
    for r in all_channels:
        totals[r["channel"]] = totals.get(r["channel"], 0) + r["n"]
    for c in available:
        totals.setdefault(c, 0)
    order = [c for c in sorted(totals, key=lambda c: -totals[c]) if c in available]
    day_index = {r["d"]: i for i, r in enumerate(days)}
    rows = [[str(r["d"]), 0, 0] for r in days]
    channel_days = []
    for r in counts:
        i = day_index[r["d"]]
        rows[i][1] += r["n"]
        rows[i][2] += 1
        channel_days.append([i, r["channel"]])
    return {"ok": True, "days": rows,
            "topics": [[day_index[r["d"]], r["topic"], r["p"], r["u"], r["g"]] for r in tones],
            "groups": [[day_index[r["d"]], r["ts"], r["p"], r["u"], r["g"]] for r in groups],
            "channels": [{"id": c, "name": names.get(c, c.lstrip("@"))} for c in order],
            # Daily distinct counts cannot be summed to obtain weekly/monthly distinct channels.
            "channel_days": channel_days}


def _shares(counts):
    total = sum(counts)
    if not total:
        return [0, 0, 0]
    raw = [100 * n / total for n in counts]
    out = [floor(n) for n in raw]
    order = sorted(range(3), key=lambda i: (-(raw[i] - out[i]), i))
    for i in order[:100 - sum(out)]:
        out[i] += 1
    return out


def _period(data, lo, hi, selected):
    days = {i for i, row in enumerate(data["days"]) if lo.isoformat() <= row[0] <= hi.isoformat()}
    posts = sum(data["days"][i][1] for i in days)
    tones = [0, 0, 0]
    for day, topics, *counts in data["groups"]:
        if day in days and any(t in selected for t in topics):
            tones = [a + b for a, b in zip(tones, counts)]
    econ = sum(tones)
    mood = floor(100 * (tones[0] - tones[2]) / econ + .5) if econ else None
    by_topic = {topic: [0, 0, 0] for topic in selected}
    for day, topic, *counts in data["topics"]:
        if day in days and topic in by_topic:
            by_topic[topic] = [a + b for a, b in zip(by_topic[topic], counts)]
    ranked = sorted(([key, *counts] for key, counts in by_topic.items() if sum(counts)),
                    key=lambda row: -sum(row[1:]))
    return {"posts": posts, "econ": econ, "tones": tones, "shares": _shares(tones),
            "mood": mood, "topics": ranked}


def leader_summary(q, selection, kind, start, sql):
    """One leader's closed day/week, using the same grouped counts as the Mini App."""
    start = date.fromisoformat(str(start))
    end = start + timedelta(days=6 if kind == "hafta" else 0)
    prev_start = start - timedelta(days=7 if kind == "hafta" else 1)
    prev_end = prev_start + timedelta(days=6 if kind == "hafta" else 0)
    data = leader_stats(q, selection["channels"], sql)
    if not data["ok"]:
        return data
    chosen_channels = selection["channels"] or active(q)
    chosen_topics = selection["topics"] or list(TOPIC_ORDER)
    current = _period(data, start, end, chosen_topics)
    prior = _period(data, prev_start, prev_end, chosen_topics)
    return {**current, "kind": kind, "start": start.isoformat(), "end": end.isoformat(),
            "previous_start": prev_start.isoformat(), "previous_end": prev_end.isoformat(),
            "previous_mood": prior["mood"],
            "change": current["mood"] - prior["mood"] if current["mood"] is not None and prior["mood"] is not None else None,
            "channels": sorted(chosen_channels), "selected_topics": sorted(chosen_topics),
            "topic_count": len(chosen_topics)}
