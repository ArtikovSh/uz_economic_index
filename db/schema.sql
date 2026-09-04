-- =====================================================================
-- Supabase / PostgreSQL schema for the UZ Economic Index bot + mini app.
-- Run once in the Supabase SQL editor (or psql). Safe to re-run.
--
-- Access model: the backend (bot webhook + mini-app API) connects with the
-- Supabase SERVICE ROLE key and enforces per-user roles in code. RLS is enabled
-- with NO public policies, so the anon/public key cannot read anything — data is
-- reachable only through the backend. Roles: admin / cb_analyst / economist /
-- public, assigned by an admin.
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

-- ---------- bot users & roles ----------------------------------------
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
alter table app_users      enable row level security;
alter table subscriptions  enable row level security;
