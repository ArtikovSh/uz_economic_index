"""Account preferences and unweighted news counts for the leadership view."""
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
                       from posts, unnest({TOPICS_OF}) topic
                       where {COUNTED} and {DAY} in {FINAL_DAYS} and channel=any(%s)
                       group by 1, 2 order by 1, 2""", (chosen,)) or []
    except psycopg.errors.UndefinedTable:
        days, all_channels, counts, tones = [], [], [], []
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
            "channels": [{"id": c, "name": names.get(c, c.lstrip("@"))} for c in order],
            # Daily distinct counts cannot be summed to obtain weekly/monthly distinct channels.
            "channel_days": channel_days}
