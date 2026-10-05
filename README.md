# uz_economic_index

O'zbekiston Telegram yangilik kanallaridan **ikkita iqtisodiy indeks** quruvchi Python
quvuri. To'liq metodologiya: [METHODOLOGY.md](METHODOLOGY.md).

| Indeks | Formula | Shkala |
|--------|---------|--------|
| **EAI** — Economic Attention Index | 100 · iqtisodiy / reklama emas | 0–100% |
| **ESI** — Economic Sentiment Index | 100 · (ijobiy − salbiy) / iqtisodiy | −100…+100, 0 = neytral |

Ikkalasi ham barcha kanallar bo'yicha birga, oddiy sanoq bilan hisoblanadi. Kun, hafta,
oy, chorak va yil uchun formula bir xil.

## Jarayon

1. **Yig'ish** — har kuni Toshkent vaqti bilan 00:05 da 2 kun oldingi to'liq kun
   yig'iladi (6-oktabr 00:05 → 4-oktabr postlari). Har post **bir marta** o'lchanadi.
   02:05 dagi zaxira run faqat birinchi run yig'a olmagan kanallarni yig'adi.
   Yig'ilmay qolgan kunlar keyinroq to'ldirilmaydi. Ko'rishlar va forward'lar indeksda
   ishlatilmaydi, lekin yig'ib boriladi.
2. **Tasniflash** — har post **Gemini** bilan bir marta belgilanadi: iqtisodiymi, mavzu,
   sentiment, reklama/dayjest/xorijiy bayroqlari. Zaxira klassifikator yo'q: belgilanmay
   qolgan post keyingi run'da qayta yuboriladi.
3. **Filtrlar** — kanal o'zi reklama deb belgilagan post (`(реклама)`, oxirida `Reklama`)
   Gemini javobidan qat'i nazar reklama hisoblanadi.
4. **Ikki jadval** — kun yakunlangach (barcha postlari belgilangach) uning postlari
   **Xabarlar** jadvaliga, kun qatori **Indekslar** jadvaliga qo'shiladi. Hafta, oy,
   chorak va yil qatori davrning oxirgi kuni yakunlanganda qo'shiladi. Qo'shilgan qator
   keyin hech qachon o'zgartirilmaydi.

## Modullar

| Fayl | Vazifasi |
|------|----------|
| `main.py` | Kunlik quvur: yig'ish → Gemini → kunni yakunlash → indekslar → Excel |
| `config.py` | Sozlamalar: kanallar, yig'ish oynasi, Gemini, proxy |
| `scraper.py` | Telethon orqali kunni yig'ish; sessiyani oldindan tekshiradi |
| `store.py` | Ikki jadval va kutish fayli (faqat qo'shish) |
| `llm_classifier.py` | Gemini klassifikatori: partiyalar, kvota nazorati |
| `prompts.py` | Gemini prompti va JSON sxema |
| `indicator.py` | Reklama filtri, kunni yakunlash, EAI/ESI sanog'i |
| `excel_exporter.py` | Excel hisobot ("Indekslar", "Xabarlar", "Metodika") |
| `sync_to_db.py` | Supabase'ga sinxronlash (bot va Mini App uchun) |
| `sheets_sync.py` | Jadvallarni Google Sheets'ga qo'shish |
| `check.py` | Oldindan tekshiruv: Telegram sessiyasi va kanallar, Gemini, Sheets, bot ogohlantirishi |
| `export_session.py` | CI uchun Telegram sessiya satrini yaratish |
| `app/` | Telegram bot + Mini App (Vercel) |

## Natijalar

- `data/messages.csv` — **Xabarlar**: har bir yakunlangan post, Gemini belgilari va indeks
  bayroqlari (`nonad`, `econ`, `tone`) bilan, sana tartibida
- `data/indices.csv` — **Indekslar**: har bir yopilgan kun, hafta, oy, chorak va yil
  (sanoqlar, EAI, ESI, izoh)
- `data/pending.csv` — kuni hali yakunlanmagan postlar (odatda bo'sh)
- `output/economic_index_latest.xlsx` — Excel hisobot (Actions artifact sifatida ham)

## GitHub sozlamalari

**Secrets** (Settings → Secrets and variables → Actions):

| Nomi | Nima uchun |
|------|-----------|
| `TG_API_ID`, `TG_API_HASH` | my.telegram.org dagi API juftligi |
| `TG_SESSION_STRING` | Telegram sessiyasi (pastga qarang) |
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey |
| `TELEGRAM_BOT_TOKEN`, `BOT_ADMIN_ID` | run yiqilsa botdan ogohlantirish (ixtiyoriy) |
| `SUPABASE_DB_URL` | bot/Mini App bazasi (ixtiyoriy) |
| `GOOGLE_SERVICE_ACCOUNT_JSON`, `GSHEET_ID` | Google Sheets oynasi (ixtiyoriy, pastga qarang) |

**Variables** (ixtiyoriy): `GEMINI_MODEL` — modelni qat'iy belgilash. Bo'sh bo'lsa
avtomatik tanlanadi va keyin o'sha model saqlanib qoladi. Qaysi modelda bepul
kvota borligini https://aistudio.google.com/rate-limit da ko'ring.

**Workflow'lar:**
- `uz-economic-index` — kunlik (00:05 va 02:05 Toshkent) + qo'lda. Barcha davrlar
  (kun, hafta, oy, chorak, yil) shu run'da yopiladi.
- `check` — post yig'masdan hamma narsani tekshiradi (Telegram, Gemini, Sheets) va natijani botga yuboradi. Kunlik run bilan bir vaqtda ishlamaydi (navbatga turadi).

## Google Sheets oynasi

Hisob-kitob backend'da (GitHub Actions) bajariladi, jadvalga faqat natija yoziladi
(formulalar yo'q). Har run'dan keyin yangi qatorlar pastdan qo'shiladi:

| Varaq | Mazmuni |
|-------|---------|
| Indekslar | har bir yopilgan kun / hafta / oy / chorak / yil |
| Xabarlar | har bir yakunlangan post (mavzu, bayroqlar, ohang, havola), sana tartibida |
| Info | oxirgi yangilanish vaqti, qatorlar soni, kutayotgan postlar |

Jadvalga qo'lda yozmang. Tahlil uchun alohida varaq yoki nusxa oching.

**Bir martalik sozlash (~20 daqiqa):**
1. Google Sheets'da yangi jadval yarating. Uning manzilidagi ID'ni nusxalang:
   `docs.google.com/spreadsheets/d/`**`<ID>`**`/edit`.
2. https://console.cloud.google.com → yangi loyiha (masalan, `uz-economic-index`).
3. *APIs & Services → Library* → **Google Sheets API** → *Enable*.
4. *IAM & Admin → Service Accounts → Create service account* → nom (masalan,
   `sheets-writer`) → *Create and continue* → *Done*. Rol berish shart emas.
5. Yaratilgan akkauntni oching → *Keys → Add key → Create new key → JSON*.
   Kompyuteringizga JSON fayl yuklanadi.
6. Jadvalga qayting → *Share* → JSON ichidagi `client_email` manzilini kiriting
   (`...@...iam.gserviceaccount.com`) → **Editor** → *Notify* belgisini olib tashlang → *Share*.
7. GitHub → *Settings → Secrets and variables → Actions*:
   - `GOOGLE_SERVICE_ACCOUNT_JSON` = JSON faylning **butun** matni;
   - `GSHEET_ID` = 1-qadamdagi ID.

   Shundan keyin JSON faylni kompyuterdan o'chiring.
8. *Actions → uz-economic-index → Run workflow* — jadval darhol to'ladi.

Xizmat akkaunti faqat o'ziga ulashilgan shu bitta jadvalni ko'radi. Google
hisobingizdagi boshqa fayllarga kira olmaydi.

## Telegram sessiyasini yangilash

Run "Telegram session is not authorized" deb yiqilsa, yangi sessiya kerak:

```powershell
$env:TG_API_ID="..."; $env:TG_API_HASH="..."
$env:USE_PROXY=1; $env:PROXY_PORT=10808     # Telegram bloklangan tarmoqda
.\venv\Scripts\python.exe export_session.py --fresh
```

Hosil bo'lgan `session_string.txt` ichidagini `TG_SESSION_STRING` secret'iga qo'ying va
faylni o'chiring. Bu sessiyani **faqat CI'da** ishlating va Telegram → Sozlamalar →
Qurilmalar ro'yxatidagi "Telethon" seansini o'chirmang.
