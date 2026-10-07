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
   ichidagini butunlay ko'chirib qo'ying → **Run**. (Jadvallar + RLS yaratiladi; kirish
   jadvallarini backend birinchi so'rovda o'zi ham yaratadi.)
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
   `indices`, `messages`, `labels` to'lganini ko'rasiz (`indices` jadvalini sinxronlash o'zi yaratadi).

> `SUPABASE_DB_URL` qo'yilmasa — sync bosqichi **no-op** (hech narsa buzilmaydi).
> Sxema xavfsiz: RLS yoqilgan, anon kalit hech narsa o'qiy olmaydi — faqat backend
> (service_role) kiradi.

**Sizga kerak bo'ladigan boshqa Supabase qiymatlari (bot/app uchun, 2-qismda):**
- *Project URL* (Settings → API → Project URL)
- *service_role* kalit (Settings → API → service_role — **maxfiy**, faqat backend)

---

## 2-qism — Vercel (bot)  ← bot kodi TAYYOR (`app/api/index.py`)

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
   | `WEBAPP_URL` | deploy'dan keyingi manzil, masalan `https://<app>.vercel.app` (Mini App tugmasi uchun) |
5. **Deploy** bosing → app manzilini oling: `https://<app>.vercel.app`.
   Tekshirish: brauzerda `https://<app>.vercel.app/api/index` → "bot is running" chiqadi.
6. **Webhook o'rnating** (brauzerda bir marta oching, `<TOKEN>` va `<app>` ni almashtiring;
   `WEBHOOK_SECRET` qo'ygan bo'lsangiz `&secret_token=...` qo'shing):
   ```
   https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<app>.vercel.app/api/index&secret_token=<WEBHOOK_SECRET>
   ```
   `{"ok":true,...}` chiqishi kerak.
7. **Botga `/start`** yozing → bot egasi (admin) sifatida tan olinasiz. Boshqa foydalanuvchilar
   faqat siz bergan login va parol bilan kiradi (pastdagi *Kirish va foydalanuvchilar* bo'limi).

**Bot buyruqlari:** `/today` `/index` `/top` `/topics` `/topic <nom>` `/app` `/me` `/logout` `/help`.
Statistikalar 1-qismdagi Supabase ma'lumotidan olinadi (avval workflow sync qilgan bo'lsin).

## 3-qism — Mini App (TAYYOR: `app/public/` — `index.html`, `css/`, `js/` + `app/api/index.py`)

Mini App bir xil Vercel deploy'da keladi — **build shart emas** (statik HTML/CSS/JS + Chart.js).
Vercel uni ildizda beradi: `https://<app>.vercel.app/`.

1. **Bot'ga `WEBAPP_URL` qo'shing** (2-qism env jadvaliga): `https://<app>.vercel.app`
   (deploy manzili). Endi bot `/app` va `/today` da "Dashboard" tugmasini ko'rsatadi.
2. **Menu tugmasi (ixtiyoriy, chiroyliroq):** @BotFather → `/setmenubutton` → botni tanlang →
   *URL* → `https://<app>.vercel.app` → nomi "Dashboard". Endi bot chatida doim "Open App"
   tugmasi turadi.
3. **Xavfsizlik:** Mini App har so'rovda Telegram `initData` yuboradi; backend uni bot-token
   bilan **HMAC** tekshiradi (soxta yoki 24 soatdan eski bo'lsa rad etiladi), so'ng login
   holatini aniqlaydi. Ma'lumot faqat kirgan foydalanuvchiga beriladi. Baza faqat backend
   orqali (RLS).

**Mini App nima ko'rsatadi** (o'zbek, rus, ingliz tillarida):
- kirish ekrani, administratorga murojaat, admin paneli;
- **Asosiy:** kun / hafta / oy / chorak / yil uchun EAI va ESI, oldingi davr bilan farq,
  dinamika grafigi, ohang taqsimoti, qamrov, asosiy mavzular;
- **Mavzular:** har mavzu bo'yicha ohang va ESI, mavzularning ESI'ga hissasi;
- **Xabarlar:** iqtisodiy postlar — sana yoki oraliq, mavzu, ohang, kanal bo'yicha filtr va saralash;
- **Metodika.**

Davr raqamlari `indices` jadvalidagi kunlik qatorlardan `indicator.py` dagi kabi yig'iladi —
Indekslar jadvali bilan bir xil chiqadi; hali yopilmagan davr "Yakunlanmagan" deb belgilanadi.

## Qanday tekshirish (hammasi ulangach)
1. `SUPABASE_DB_URL` secret → workflow'ni ishga tushiring → DB to'ladi.
2. Botga `/start` → admin → `/today` ishlayapti.
3. `/app` yoki Menu tugmasi → Mini App ochiladi, dashboard ko'rinadi.
4. Mini App → *Foydalanuvchilar* → login yarating va uni boshqa Telegram hisobidan sinab ko'ring.

---

## Kirish va foydalanuvchilar
Bot va Mini App faqat admin bergan login va parol bilan ishlaydi. `BOT_ADMIN_ID` (bot egasi)
doim kiradi va hisobdan chiqmaydi.

- **Login yaratish:** Mini App → yuqoridagi *Foydalanuvchilar* tugmasi (yoki bot xabaridagi
  *Admin panelini ochish*) → *Yangi kirish ma'lumoti* → rol va muddat → *Login va parol
  yaratish*. Parol **bir marta** ko'rsatiladi; bazada faqat uning xeshi (scrypt) saqlanadi.
- **Birinchi kirishda** login foydalanuvchining Telegram hisobiga bog'lanadi va boshqa Telegram
  hisobidan ishlamaydi. Foydalanuvchi hisobdan chiqsa (Mini App → *Hisob* → *Hisobdan chiqish*
  yoki botda `/logout`), bog'lanish bekor bo'ladi.
- **Kirish so'rovlari:** logini yo'q foydalanuvchi kirish ekranidagi *Administratorga* havolasi
  orqali so'rov yuboradi, sizga bot xabar beradi. So'rovdan yaratilgan login va parol
  foydalanuvchiga bot orqali boradi va faqat uning Telegram hisobida ishlaydi. *Parolni
  tiklash* so'rovida foydalanuvchining mavjud logini uchun yangi parol yuboriladi. So'rovni
  xabarsiz yopish yoki rad etish (foydalanuvchiga xabar boradi) mumkin.
- **Boshqaruv:** har bir login uchun parolni tiklash, muddatni uzaytirish, bloklash.
- **Kanallar:** admin paneli → *Kanallar*. Ochiq kanal `@nom` yoki `t.me/nom` ko'rinishida
  qo'shiladi (bot Telegram'dan tekshiradi) yoki to'xtatiladi. O'zgarish keyingi kunlik
  yig'imdan kuchga kiradi; yakunlangan kunlar o'zgarmaydi. Kamida bitta kanal faol qoladi.
- **Himoya:** bitta Telegram hisobidan 5 ta xato urinish — 15 daqiqa blok; bitta loginga
  10 ta xato — 30 daqiqa blok. Parollar log'ga yozilmaydi.

| Rol | Imkoniyat |
|-----|-----------|
| `analyst` (Analitik) | to'liq dashboard va bot |
| `economist` (Iqtisodchi) | to'liq dashboard va bot |
| `admin` (Admin) | yuqoridagilar + foydalanuvchilarni boshqarish |

Muddat: 30 kun, 90 kun yoki muddatsiz; muddati tugagan yoki bloklangan login kira olmaydi.
Jadvallar (`accounts`, `access_requests`, `auth_failures`) birinchi so'rovda avtomatik
yaratiladi. Eski `app_users` jadvali endi ishlatilmaydi — oldingi foydalanuvchilarga yangi
login berish kerak.
