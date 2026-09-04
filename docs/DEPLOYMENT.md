# Deploy — Supabase + Vercel (bepul)

Bot va Mini App uchun infratuzilma. Hammasi **bepul**, kredit karta shart emas.
Stek: **Supabase** (Postgres + auth) + **Vercel** (bot webhook + Mini App) +
mavjud **GitHub Actions** quvuri (Supabase'ga yozadi).

```
GitHub Actions (quvur)  --sync-->  Supabase Postgres  <--o'qiydi--  Vercel (bot + app)
```

Bosqichma-bosqich. **1-qism (Supabase) hozir bajariladi**; bot/app kodi tayyor bo'lgach 2-qism.

---

## 1-qism — Supabase (ma'lumotlar bazasi)  ← HOZIR

1. **Loyiha yarating:** https://supabase.com → *New project* (bepul reja).
   Region: yaqinroq (Frankfurt/EU). *Database password*ni saqlang.
2. **Sxemani ishga tushiring:** Supabase → *SQL Editor* → *New query* → `db/schema.sql`
   ичидагини butunlay ko'chirib qo'ying → **Run**. (Jadvallar + RLS yaratiladi.)
3. **Ulanish satrini oling:** Supabase → *Project Settings* → *Database* →
   **Connection string** → **Connection pooler** (Transaction mode, port **6543**) →
   URI'ni nusxalang. Ko'rinishi:
   ```
   postgresql://postgres.<ref>:<PAROL>@aws-0-<region>.pooler.supabase.com:6543/postgres
   ```
   (`<PAROL>` o'rniga 1-qadamdagi parolni qo'ying.)
4. **GitHub secret qo'shing:** repo → *Settings → Secrets and variables → Actions* →
   *New repository secret* → nomi **`SUPABASE_DB_URL`** → qiymati yuqoridagi URI.
5. **Sinang:** *Actions → uz-economic-index → Run workflow*. Log'da
   `Sync to Supabase ... synced N rows` chiqadi. Supabase → *Table Editor* da
   `daily_index`, `messages`, `labels` to'lganini ko'rasiz.

> `SUPABASE_DB_URL` qo'yilmasa — sync bosqichi **no-op** (hech narsa buzilmaydi).
> Sxema xavfsiz: RLS yoqilgan, anon kalit hech narsa o'qiy olmaydi — faqat backend
> (service_role) kiradi.

**Sizga kerak bo'ladigan boshqa Supabase qiymatlari (bot/app uchun, 2-qismда):**
- *Project URL* (Settings → API → Project URL)
- *service_role* kalit (Settings → API → service_role — **maxfiy**, faqat backend)

---

## 2-qism — Vercel (bot)  ← bot kodi TAYYOR (`app/api/bot.py`)

1. **Bot yarating:** Telegram'da **@BotFather** → `/newbot` → nomi bering → **tokenni** saqlang.
2. **O'z Telegram ID'ingizni oling:** **@userinfobot** ga yozing → raqamli `id` (bu sizni
   admin qiladi).
3. **Vercel loyihasi:** https://vercel.com (GitHub bilan kiring) → *Add New → Project* →
   `uz_economic_index` repo'ni import qiling. **MUHIM:** *Root Directory* ni **`app`** qilib
   belgilang (Edit → app). Framework: **Other**.
4. **Env Variables** (Vercel loyiha sozlamalarida) qo'shing:
   | Nomi | Qiymati |
   |------|---------|
   | `TELEGRAM_BOT_TOKEN` | BotFather tokeni |
   | `BOT_ADMIN_ID` | sizning Telegram ID'ingiz |
   | `SUPABASE_DB_URL` | 1-qismdagi pooler URI (parol bilan) |
   | `WEBHOOK_SECRET` | ixtiyoriy — istalgan tasodifiy satr |
5. **Deploy** bosing → app manzilini oling: `https://<app>.vercel.app`.
   Tekshirish: brauzerda `https://<app>.vercel.app/api/bot` → "bot is running" chiqadi.
6. **Webhook o'rnating** (brauzerda bir marta oching, `<TOKEN>` va `<app>` ni almashtiring;
   `WEBHOOK_SECRET` qo'ygan bo'lsangiz `&secret_token=...` qo'shing):
   ```
   https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<app>.vercel.app/api/bot&secret_token=<WEBHOOK_SECRET>
   ```
   `{"ok":true,...}` chiqishi kerak.
7. **Botga `/start`** yozing → admin sifatida tan olinasiz. Endi:
   - boshqalar `/start` yozsa — sizga bildirishnoma keladi;
   - `/approve <id> economist` (yoki `cb_analyst` / `public`) bilan tasdiqlaysiz;
   - `/pending`, `/users`, `/block <id>` — boshqaruv.

**Bot buyruqlari:** `/today` `/index` `/top` `/topics` `/topic <nom>` `/me` `/help`.
Statistikalar 1-qismdagi Supabase ma'lumotidan olinadi (avval workflow sync qilgan bo'lsin).

## 3-qism — Mini App (keyingi bosqich)
React dashboard, Vercel'da statik. Kod keyingi bosqichda tayyorlanadi.

---

## Rollar (admin tasdig'i bilan)
- `admin` — hammasi + foydalanuvchilarni tasdiqlash (siz).
- `cb_analyst` / `economist` — to'liq statistika + eksport.
- `public` — faqat sarlavha indeks + top postlar.
- Yangi foydalanuvchi `pending` bo'lib qo'shiladi; admin `/approve <id> <rol>` bilan faollashtiradi.
