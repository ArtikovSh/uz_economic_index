-- =====================================================================
-- Supabase / PostgreSQL schema for the UZ Economic Index bot + mini app.
-- Run once in the Supabase SQL editor (or psql). Safe to re-run.
--
-- Access model: the backend (bot webhook + mini-app API) connects with the
-- Supabase SERVICE ROLE key and enforces per-user roles in code. RLS is enabled
-- with NO public policies, so the anon/public key cannot read anything — data is
-- reachable only through the backend. Users sign in with a login + password that an
-- admin creates (accounts table); roles analyst / economist / admin.
-- =====================================================================

-- ---------- raw scraped messages -------------------------------------
create table if not exists messages (
    channel      text        not null,
    message_id   bigint      not null,
    date_utc     timestamptz not null,
    views        integer     default 0,
    forwards     integer     default 0,
    raw_text     text,
    primary key (channel, message_id)
);
create index if not exists idx_messages_date on messages (date_utc);

-- ---------- per-message classification (GPT/rules) -------------------
create table if not exists labels (
    channel        text    not null,
    message_id     bigint  not null,
    is_economic    boolean default false,
    primary_topic  text    default 'non_economic',
    relevance      real    default 0,
    sentiment      real    default 0,
    is_ad          boolean default false,
    is_digest      boolean default false,
    is_foreign     boolean default false,
    label_version  text,
    primary key (channel, message_id),
    foreign key (channel, message_id) references messages (channel, message_id) on delete cascade
);
create index if not exists idx_labels_topic on labels (primary_topic);

-- convenience view: message joined with its label
create or replace view posts as
    select m.*, l.is_economic, l.primary_topic, l.relevance, l.sentiment,
           l.is_ad, l.is_digest, l.is_foreign, l.label_version
    from messages m left join labels l
      on m.channel = l.channel and m.message_id = l.message_id;

-- ---------- index table (written by sync_to_db.py; one row per closed period) ----
create table if not exists indices (
    period_type    text    not null,          -- kun | hafta | oy | chorak | yil
    period         text    not null,          -- 2026-10-04 | 2026-W40 | 2026-10 | 2026-Q4 | 2026
    start_date     date    not null,
    end_date       date    not null,
    days           integer,
    days_expected  integer,
    posts          integer,
    nonad          integer,
    econ           integer,
    pos            integer,
    neu            integer,
    neg            integer,
    eai            real,                      -- % of non-ad posts that are economic
    esi            real,                      -- 100 * (pos - neg) / econ
    note           text,
    primary key (period_type, period)
);

-- ---------- legacy daily/monthly tables (pre-v4; no longer written) --------
-- ---------- daily index time series ----------------------------------
create table if not exists daily_index (
    date_only          date primary key,
    total_messages     integer,
    economic_messages  integer,
    counted_messages   integer,
    econ_share         real,
    eai                real,
    eai_z              real,
    eai_100            real,
    esi                real,
    esi_z              real,
    esi_100            real,
    avg_engagement     real
);

-- ---------- monthly index time series --------------------------------
create table if not exists monthly_index (
    month              text primary key,          -- 'YYYY-MM'
    days_covered       integer,
    total_messages     integer,
    economic_messages  integer,
    counted_messages   integer,
    econ_share         real,
    eai                real,
    eai_100            real,
    esi                real,
    esi_100            real,
    avg_engagement     real,
    top_topics         text
);

-- ---------- access: logins an admin creates (app/api/_auth.py) -------
-- The backend also creates these on its first request (same DDL).
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

-- ---------- channels the pipeline collects (app/api/_channels.py) ----
-- An admin adds or pauses them in the Mini App; the backend seeds the first five.
create table if not exists channels (
    handle      text primary key,          -- '@daryo': always '@' and lower case
    title       text,
    active      boolean not null default true,
    added_at    timestamptz not null default now(),
    added_by    bigint,
    changed_at  timestamptz
);

-- ---------- the bot's own state (app/api/_bot.py) --------------------
-- Language and morning-summary choice per Telegram user, /setup results, card uploads.
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
    key        text primary key,         -- 'emoji' (custom emoji ids), 'avatar_sha'
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

-- ---------- legacy (pre-login, no longer used) ------------------------
create table if not exists app_users (
    telegram_id  bigint primary key,
    username     text,
    full_name    text,
    role         text        not null default 'public'
                 check (role in ('admin','cb_analyst','economist','public')),
    status       text        not null default 'pending'
                 check (status in ('pending','active','blocked')),
    lang         text        default 'uz',
    created_at   timestamptz default now(),
    approved_by  bigint,
    approved_at  timestamptz
);

-- ---------- subscriptions (digests / alerts) -------------------------
create table if not exists subscriptions (
    id           bigserial primary key,
    telegram_id  bigint not null references app_users (telegram_id) on delete cascade,
    kind         text   not null,            -- 'daily' | 'weekly' | 'monthly' | 'topic' | 'alert'
    params       jsonb  default '{}'::jsonb, -- e.g. {"topic":"currency_fx"} or {"metric":"esi","op":"<","value":-0.3}
    active       boolean default true,
    created_at   timestamptz default now()
);
create index if not exists idx_subs_user on subscriptions (telegram_id);

-- ---------- lock down: enable RLS, add NO public policies ------------
-- (service_role bypasses RLS; anon/public gets nothing -> backend-only access)
alter table messages       enable row level security;
alter table labels         enable row level security;
alter table daily_index    enable row level security;
alter table monthly_index  enable row level security;
alter table indices        enable row level security;
alter table app_users      enable row level security;
alter table subscriptions  enable row level security;
alter table accounts        enable row level security;
alter table access_requests enable row level security;
alter table auth_failures   enable row level security;
alter table channels        enable row level security;
alter table bot_users       enable row level security;
alter table bot_settings    enable row level security;
alter table bot_cards       enable row level security;
