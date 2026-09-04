# Telegram Bot + Mini App — Reja va Chuqur Tahlil

O'zbekiston Iqtisodiy Yangiliklar Indeksi (EAI/ESI) uchun **Telegram bot** va
**Telegram Mini App** ishlab chiqish rejasi. Auditoriya: iqtisodchilar va Markaziy
bank (MB) xodimlari.

> Bu — reja hujjati (dizayn/arxitektura), kod emas. Amalga oshirish bosqichlari §12 da.

---

## 1. Maqsad va hal qilinadigan muammo

**Hozirgi og'riq:** iqtisodchilar va MB xodimlari iqtisodga oid yangiliklarni topish
uchun **o'nlab Telegram kanallarini qo'lda kuzatishga** majbur. Bu:
- ko'p vaqt oladi, izchil emas (kim nimani ko'radi — tasodifiy);
- miqdoriy emas ("kayfiyat yaxshimi/yomonmi?" — his-tuyg'u bilan baholanadi);
- tarixiy solishtirish yo'q (o'tgan oyga nisbatan qanday?).

**Yechim:** mavjud quvur (scraper → GPT tasnif → EAI/ESI indeks) allaqachon
iqtisodiy yangiliklarni **saralab, tasniflab, miqdorlashtirib** beryapti. Bot va Mini
App shu natijani foydalanuvchiga **qulay yetkazadi**, shunda ular:
1. **kanal kovlamaydilar** — tayyor, saralangan iqtisodiy lenta va indeks oladi;
2. o'z xulosalari uchun **tayyor statistika** oladi (mavzu, vaqt, kayfiyat kesimida);
3. muhim o'zgarishlardan **avtomatik xabardor** bo'ladi (alert/digest);
4. ma'lumotni **eksport** qilib, o'z hisobotlarida ishlatadi.

**Shimoliy yulduz (North Star):** *"MB analitigi ertalab botni ochib, 30 soniyada
kechagi iqtisodiy manzarani (indeks + top yangiliklar + o'zgarishlar) tushunib oladi —
hech qanday kanal ochmasdan."*

---

## 2. Foydalanuvchilar va ularning ehtiyojlari (personalar)

| Persona | Kim | Asosiy ehtiyoj | Kalit funksiya |
|---------|-----|----------------|----------------|
| **MB pul-kredit analitigi** | Monetar siyosat bo'limi | FX kayfiyati, inflatsiya diqqati, rasmiy CPI/kurs bilan solishtirish, eksport | FX/inflatsiya paneli, indikator overlay, Excel eksport |
| **MB tadqiqotchi/iqtisodchi** | Tahlil departamenti | Mavzu trendlari, uzun vaqt qatori, metodologiya shaffofligi, API | Trend grafiklar, metodologiya, data yuklab olish |
| **Rahbariyat/qaror qabul qiluvchi** | Boshqaruv | Tez kunlik/haftalik dayjest, sarlavha indeks, "bugun nima o'zgardi" | Kunlik digest, headline gauge |
| **Tashqi iqtisodchi/jurnalist** *(ixtiyoriy, public)* | Universitet, media | Saralangan iqtisodiy lenta, top postlar | Public lenta, headline indeks |

**Umumiy ehtiyoj:** iqtisodiy yangiliklarga **filtrlangan, miqdoriy, so'rov qilinadigan**
oyna + o'zlari uchun **xulosa chiqarish** uchun toza ma'lumot.

---

## 3. Mahsulot ko'rinishi: ikki sirt (surface)

### A) Telegram Bot — suhbat + push (tez kirish, ogohlantirish)
Sarlavha raqamlar, kunlik dayjest va alertlar uchun. "Kanal kovlash"ni to'g'ridan-to'g'ri
almashtiradi: har kuni ertalab tayyor xulosa keladi.

### B) Telegram Mini App — boy vizual (chuqur tahlil)
Dashboard, drill-down, grafiklar, post-explorer, eksport. Telegram ichida ochiladigan
web-app (WebApp SDK). Chuqur tahlil va o'z xulosalarini chiqarish uchun.

Ikkalasi **bitta backend/API va bitta ma'lumotlar bazasi**dan oziqlanadi.

---

## 4. Arxitektura (eng muhim o'zgarish)

Hozir quvur natijani **git'dagi CSV/xlsx**ga yozadi. Bot/app uchun bu yaramaydi — real
vaqt so'rovlari, alertlar, ko'p foydalanuvchi kerak. Shuning uchun **serving qatlami**
qo'shiladi: ma'lumotlar bazasi + API.

```
   ┌─────────────────────────────────────────────────────────┐
   │  MAVJUD QUVUR (scraper → GPT tasnif → EAI/ESI)           │
   │  GitHub Actions (kunlik/oylik) yoki VPS cron            │
   └───────────────────────┬─────────────────────────────────┘
                           │ yozadi (git-CSV o'rniga)
                           ▼
                 ┌───────────────────┐
                 │   PostgreSQL DB   │  messages, labels, daily_index,
                 │                   │  monthly_index, users, subscriptions
                 └─────────┬─────────┘
                           │ o'qiydi
                           ▼
                 ┌───────────────────┐
                 │  Backend API      │  FastAPI (REST/JSON)
                 │  + auth + cache   │  /index, /topics, /posts, /search,
                 └────┬──────────┬───┘  /subscribe, /export
                      │          │
          ┌───────────▼──┐   ┌───▼───────────────┐
          │ Telegram Bot │   │  Mini App (WebApp) │
          │ (aiogram)    │   │  React + charts    │
          │ digest/alert │   │  dashboard/explorer│
          └──────────────┘   └────────────────────┘
```

**Asosiy arxitektura qarorlari:**
1. **git-CSV → PostgreSQL.** Quvur natijani DB'ga yozadi (yoki CSV + sync job). Bu — eng
   katta o'zgarish; qolgan hamma narsa shunga tayanadi.
2. **Backend = Python FastAPI** — mavjud Python kodini (`indicator.py`, `monthly.py`,
   leksikon, metodologiya) **to'g'ridan-to'g'ri qayta ishlatish** mumkin. Katta yutuq.
3. **Doim ishlaydigan server** kerak (bot online turishi, alert yuborishi uchun) —
   kichik VPS yoki Railway/Render/Fly.io. Scraper esa GitHub Actions'da qolib, DB'ga
   yozishi mumkin (yoki serverga cron sifatida ko'chiriladi).

---

## 5. Telegram Bot — funksiyalar va komandalar

**On-demand (so'rov bo'yicha):**
| Komanda | Nima qiladi |
|---------|-------------|
| `/start` | Kirish, ro'yxatdan o'tish, til tanlash (uz/ru/en) |
| `/today` | Kechagi (T−2) iqtisodiy manzara: EAI/ESI, o'zgarish, top 3–5 yangilik |
| `/week` `/month` | Haftalik/oylik xulosa + trend |
| `/index` | Sarlavha indekslar (EAI_100, ESI_100) + oldingi davrga nisbatan o'zgarish |
| `/fx` | Valyuta kayfiyati (dollar/so'm), so'nggi kurs yangiliklari |
| `/inflation` | Narx/inflatsiya diqqati va kayfiyati |
| `/topic <nom>` | Tanlangan kategoriya (bank, fiskal, savdo, energetika…) kesimi |
| `/top` | Kunning eng muhim iqtisodiy postlari (relevance × e'tibor) |
| `/search <so'z>` | Kalit so'z bo'yicha tasniflangan postlarni izlash |
| `/chart` | Grafik rasm (indeks trendi) — server tomonda chiziladi |
| `/export` | Excel/CSV faylini yuboradi (indeks yoki postlar) |
| `/app` | Mini App'ni ochish tugmasi |
| `/methodology` | Qanday hisoblanadi (qisqa + to'liq havola) |

**Push (avtomatik):**
- **Kunlik dayjest** — har ertalab (masalan 09:00) obunachilarga: kechagi indeks,
  top yangiliklar, kayfiyat. ← "kanal kovlash"ni almashtiruvchi asosiy funksiya.
- **Haftalik/oylik hisobot** — dushanba / oyning 3-kuni.
- **Alert (ostona)** — foydalanuvchi belgilagan shart bo'yicha: masalan "FX kayfiyati
  −0.3 dan pastga tushsa" yoki "inflatsiya diqqati keskin oshsa".
- **Mavzu obunasi** — faqat tanlangan kategoriyalar bo'yicha xabar.

**Ixtiyoriy (kuchli):** tabiiy til savol-javob (LLM) — "o'tgan hafta kayfiyat qanday
edi?" → bot DB'dagi ma'lumotdan javob beradi.

---

## 6. Telegram Mini App — ekranlar

1. **Dashboard (bosh ekran)**
   - Headline gauge: EAI_100, ESI_100 (0–100, 50=neytral), o'zgarish strelkasi;
   - Trend grafik: kunlik/oylik EAI & ESI (davr tanlagich: 7k/30k/3oy/1yil);
   - Mavzu donut: kategoriyalar ulushi; sentiment svetofor (ijobiy/neytral/salbiy).
2. **Mavzu drill-down** — kategoriyaga bosilганda: shu mavzu vaqt qatori, kayfiyati,
   top postlari (o'qish + kanalga havola).
3. **Post-explorer (saralangan lenta)** — barcha tasniflangan postlar; filtr: mavzu,
   kayfiyat, kanal, sana, faqat-iqtisodiy. ← "kanal kovlash"ni boy shaklda almashtiradi.
4. **Solishtirish (Compare)** — indeksni rasmiy ko'rsatkich bilan ustma-ust: CPI,
   USD/UZS kursi, stavka qarorlari (agar ma'lumot ulanса).
5. **Eksport** — Excel/CSV yoki grafik PNG yuklab olish.
6. **Metodologiya** — formulalar (METHODOLOGY.md dan), shaffoflik (MB ishonchi uchun muhim).
7. **Sozlamalar** — til, obunalar, alert ostonalari, rol.

---

## 7. Chiqariladigan statistika (kerakli statistikalar)

- **Sarlavha:** EAI, ESI (kunlik/haftalik/oylik) + oldingi davrga o'zgarish, z-ball.
- **Mavzu kesimi (10 kategoriya):** diqqat ulushi, o'rtacha kayfiyat, trend, top postlar
  (inflatsiya, valyuta, fiskal, bank, savdo, energetika, mehnat, biznes, qurilish, makro).
- **Kayfiyat taqsimoti:** ijobiy/neytral/salbiy postlar soni va ulushi.
- **Hajm:** iqtisodiy vs umumiy xabarlar, kanal bo'yicha kesim.
- **Movers (o'zgaruvchilar):** kayfiyat/diqqat bo'yicha eng katta o'zgarishlar.
- **Yetakchi indikator ko'rinishi:** indeksni rasmiy CPI/kurs bilan korrelyatsiya (§11
  validatsiya) — MB uchun eng qimmatli.
- **Eksport:** tasniflangan xom postlar + indeks qatorlari (Excel/CSV/API).

---

## 8. Ma'lumotlar modeli va API

**DB jadvallari (PostgreSQL):**
- `messages` — channel, message_id, date_utc, views, forwards, raw_text.
- `labels` — message_id, is_economic, primary_topic, relevance, sentiment, is_ad,
  is_digest, is_foreign, label_version (mavjud `llm_labels` bilan bir xil).
- `daily_index`, `monthly_index` — hisoblangan qatorlar.
- `users` — telegram_id, rol, til, ro'yxatdan o'tgan sana.
- `subscriptions` — user_id, tur (digest/alert/topic), parametrlar (ostona, mavzu, vaqt).
- *(ixtiyoriy)* `official_indicators` — CPI, USD/UZS (validatsiya/overlay uchun).

**API endpointlar (FastAPI, JSON):**
- `GET /index/daily?from=&to=` · `GET /index/monthly`
- `GET /topics?period=` — mavzu breakdown · `GET /topics/{topic}/series`
- `GET /posts?topic=&sentiment=&channel=&from=&to=&q=` — saralangan lenta
- `GET /top?date=` — kunning top postlari
- `GET /summary/today` — dayjest matni (bot uchun tayyor)
- `POST /subscribe` / `DELETE /subscribe` — obuna boshqaruvi
- `GET /export?type=&format=` — Excel/CSV
- Barchasi **auth** ostida (quyida).

---

## 9. Kirish nazorati va xavfsizlik (MB konteksti — muhim)

- **Auth (Mini App):** Telegram `initData` hash'ini bot-token bilan **server tomonda
  tekshirish** (WebApp standart usuli) — foydalanuvchi haqiqiyligi.
- **Rollar:** `admin`, `cb_analyst`, `economist`, `public_viewer`.
  - `public_viewer` — faqat sarlavha indeks + top postlar;
  - `cb_analyst`/`economist` — to'liq drill-down + eksport + xom postlar + overlay.
- **Allowlist:** MB xodimlari uchun tasdiqlangan Telegram ID'lar ro'yxati; yangi
  foydalanuvchi admin tasdig'idan o'tadi (yoki MB email/domen orqali).
- **Ma'lumot maxfiyligi:** indeks **ochiq yangiliklardan** olingan (maxfiy emas), lekin
  MB'ning undan **foydalanishi** sezgir bo'lishi mumkin → ehtiyot uchun kirishni cheklash.
- **⚠️ Muhim disclaimer:** bu — **proksi/tajriba indeksi**, MB'ning **rasmiy statistikasi
  EMAS**. Har ekranda va eksportda aniq belgilanishi shart (noto'g'ri ishlatilmasligi uchun).

---

## 10. Texnologiya steki (tavsiya)

| Qatlam | Tavsiya | Sabab |
|--------|---------|-------|
| Backend | **Python + FastAPI** | Mavjud Python kodini qayta ishlatish; tez, async |
| DB | **PostgreSQL** (yoki avval SQLite) | Ishonchli, so'rov/agregatsiya |
| Bot | **aiogram 3** (async) | Zamonaviy, FastAPI bilan mos |
| Mini App | **React + TypeScript + Telegram WebApp SDK** + **Recharts/ECharts** + Tailwind | Boy grafik, tez ishlab chiqish |
| Grafik (bot rasm) | **matplotlib** (server) | Botga PNG yuborish |
| Deploy | VPS (Docker Compose) yoki **Railway/Render/Fly.io** | Doim online bot |
| Scheduler | GitHub Actions (scraping) yoki server cron | Mavjud quvurni saqlash |

Muqobil: Mini App uchun **Svelte** (yengilroq); DB uchun boshida **SQLite** (keyin Postgres).

---

## 11. Bosqichlar / Yo'l xaritasi

| Bosqich | Ish | Taxminiy vaqt* |
|---------|-----|----------------|
| **0. Serving poydevori** | DB sxema; quvurni DB'ga yozadigan qilish; FastAPI o'qish endpointlari (mavjud kodni qayta ishlatib) | 1–2 hafta |
| **1. MVP Bot** | `/today` `/index` `/topic` `/top`; kunlik dayjest push; allowlist auth | 1–2 hafta |
| **2. MVP Mini App** | Dashboard (gauge + trend + donut); post-explorer; eksport | 2–3 hafta |
| **3. Alert & obunalar** | Mavzu obunasi, ostona-alert, rejalashtirilgan dayjest | ~1 hafta |
| **4. Ilg'or** | NL savol-javob (LLM); rasmiy CPI/kurs overlay; rollar; admin panel; validatsiya dashboard; ko'p til | Davomiy |

\* Yakka dasturchi uchun taxminiy. MVP (bot + oddiy app): **~4–6 hafta**; to'liq: **~2–3 oy**.

**MVP ta'rifi (birinchi ishlaydigan mahsulot):** bot `/today` + `/index` + kunlik
dayjest + oddiy dashboard (gauge + trend). Shu bilan "kanal kovlash"ni allaqachon
almashtiradi.

---

## 12. Deploy va infratuzilma

- **Bir server (Docker Compose):** Postgres + FastAPI + bot (bitta konteynerlar to'plami).
  Mini App static build — nginx yoki bir xil serverdan HTTPS bilan.
- **HTTPS majburiy** (Mini App + webhook uchun) — domen + TLS (Caddy/Let's Encrypt).
- **Scraper:** GitHub Actions'da qoldirib, DB'ga yozadigan qilish (kalitlar secret) —
  yoki serverga cron. Kesh (`llm_labels`) DB'ga ko'chadi.
- **Backup:** Postgres kunlik backup (indeks va postlar qimmatli tarix).
- **Monitoring:** oddiy healthcheck + xato loglari (bot online turishini kuzatish).

---

## 13. Xatarlar va cheklovlar

| Xatar | Yumshatish |
|-------|------------|
| **Indeks — proksi, rasmiy emas** | Har joyda aniq disclaimer; validatsiya (§11) bilan ishonch |
| git-CSV → DB ko'chirish murakkabligi | Bosqichma-bosqich; avval CSV→DB sync, keyin to'liq |
| Bot doim online turishi | Ishonchli hosting + healthcheck + auto-restart |
| MB uchun xavfsizlik/kirish | Allowlist + rol + initData tekshirish |
| LLM narx/limit (NL savol-javob) | Keshlash; faqat ilg'or bosqichda; limit nazorati |
| Telegram kanallarini scraping (ToS) | Faqat ochiq kanallar; hozirgi amaliyot; huquqiy e'tibor |
| Ko'p til (uz lotin/kirill, rus) | Interfeys i18n; kontent allaqachon uch tilli |

---

## 14. Muvaffaqiyat mezonlari (KPI)

- Faol foydalanuvchilar (MB analitiklari) soni; kunlik dayjest ochilish darajasi.
- "Kanal kovlashga sarflangan vaqt" kamayishi (so'rov/intervyu bilan).
- Eksport/API foydalanish soni.
- Indeksning rasmiy CPI/kurs bilan korrelyatsiyasi (metodologik ishonch).
- Alert/obuna faollashuvi.

---

## 15. Ochiq qarorlar (siz hal qilishingiz kerak)

1. **Auditoriya doirasi:** faqat MB-ichki (allowlist) mi, yoki public + MB tabaqali mi?
2. **Hosting:** VPS (o'zingizniki) mi, yoki Railway/Render mi?
3. **Scraper joyi:** GitHub Actions'da qoladimi (DB'ga yozib), yoki serverga ko'chadimi?
4. **MVP ko'lami:** avval faqat **bot**mi, yoki bot+minimal **app** birga mi?
5. **Rasmiy indikatorlar (CPI/kurs)** manbasi bormi (overlay/validatsiya uchun)?
6. **NL savol-javob (LLM)** birinchi versiyada kerakmi, yoki keyinroqmi?

---

## 16. Tavsiya etilgan boshlanish (mening tavsiyam)

1. **Bosqich 0 + 1'dan boshlang:** DB + FastAPI o'qish endpointlari + `/today`/`/index`
   bot + kunlik dayjest. Bu 3–4 haftada "kanal kovlash"ni almashtiruvchi ishlaydigan
   qiymat beradi.
2. **Auditoriya:** avval **MB-ichki allowlist** (xavfsiz, aniq foydalanuvchi), keyin public.
3. **Hosting:** kichik VPS + Docker Compose (bot online, to'liq nazorat).
4. **Mini App**ni Bosqich 2'da qo'shing (dashboard + explorer).
5. Har joyda **"rasmiy statistika emas"** disclaimer'ini saqlang.

> Keyingi qadam: agar ma'qullasangiz, **Bosqich 0** (DB sxema + FastAPI skeleti +
> mavjud kodni serving'ga ulash) ni amalda boshlab beraman.
