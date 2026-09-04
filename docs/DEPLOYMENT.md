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

## 2-qism — Vercel (bot + Mini App)  ← keyingi bosqich (kod tayyorlanmoqda)

Kod tayyor bo'lgach:
1. **Telegram bot yarating:** Telegram'da **@BotFather** → `/newbot` → tokenni saqlang.
2. **O'z Telegram ID'ingizni oling:** @userinfobot ga yozing → raqamli `id`.
3. **Vercel loyihasi:** https://vercel.com → GitHub repo'ni import qiling.
4. **Vercel env o'zgaruvchilari:** `TELEGRAM_BOT_TOKEN`, `BOT_ADMIN_ID` (sizning ID),
   `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`.
5. **Webhook o'rnating:** `https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<vercel-app>.vercel.app/api/bot`
6. Botga `/start` yozing → admin sifatida tan olinasiz → boshqa foydalanuvchilarni
   `/approve <id> <rol>` bilan tasdiqlaysiz.

*(2-qism qadamlari kod tayyor bo'lganda to'ldiriladi.)*

---

## Rollar (admin tasdig'i bilan)
- `admin` — hammasi + foydalanuvchilarni tasdiqlash (siz).
- `cb_analyst` / `economist` — to'liq statistika + eksport.
- `public` — faqat sarlavha indeks + top postlar.
- Yangi foydalanuvchi `pending` bo'lib qo'shiladi; admin `/approve <id> <rol>` bilan faollashtiradi.
