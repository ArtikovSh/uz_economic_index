# uz_economic_index

O'zbekiston Telegram yangilik kanallaridan **ikkita iqtisodiy indeks** quruvchi Python
quvuri. To'liq metodologiya: [METHODOLOGY.md](METHODOLOGY.md).

| Indeks | Nimani o'lchaydi | Diapazon |
|--------|------------------|----------|
| **EAI** — Economic Attention Index | Yangiliklar oqimining qancha qismi iqtisodga oid (e'tibor bilan tortilgan) | 0…1 |
| **ESI** — Economic Sentiment Index | Iqtisodiy yangiliklarning ohangi (ijobiy/salbiy) | −1…+1 |

## Jarayon

1. **Yig'ish** — har kuni Toshkent vaqti bilan 00:05 da 2 kun oldingi to'liq kun
   (00:00–23:59) yig'iladi. Shu sababli har bir post ko'rishlari o'lchanayotganda
   kamida 24 soat ochiq turgan bo'ladi. Har post **bir marta** o'lchanadi.
   02:05 dagi zaxira run faqat birinchi run yig'a olmagan kanallarni yig'adi.
   Yig'ilmay qolgan kunlar keyinroq to'ldirilmaydi.
2. **Tasniflash** — har yangi post **Gemini** bilan bir marta belgilanadi: iqtisodiymi,
   mavzu (10 kategoriya), relevantlik, sentiment, reklama/dayjest/xorijiy bayroqlari.
   Natija `data/llm_labels.csv` da keshlanadi. Qoidaga asoslangan zaxira
   klassifikator yo'q: belgilanmay qolgan post keyingi run'da qayta yuboriladi.
3. **Filtrlar** — reklama, dayjest va xorijiy-makro postlar indeksga kirmaydi. Kanal
   o'zi reklama deb belgilagan post (`(реклама)`, oxirida `Reklama`) Gemini javobidan
   qat'i nazar chiqariladi.
4. **Indeks** — kunlik EAI/ESI (`data/daily_index.csv`) va Excel hisobot.
   Postlari to'liq belgilanmagan kun indekssiz qoladi (`unlabeled_messages` > 0)
   va keyingi run'da avtomatik to'ldiriladi.

## Modullar

| Fayl | Vazifasi |
|------|----------|
| `main.py` | Kunlik quvur: yig'ish → Gemini → indeks → Excel |
| `config.py` | Sozlamalar: kanallar, yig'ish oynasi, Gemini, proxy |
| `scraper.py` | Telethon orqali kunni yig'ish; sessiyani oldindan tekshiradi |
| `store.py` | O'suvchi, dublikatsiz arxiv (`data/messages.csv`) |
| `llm_classifier.py` | Gemini klassifikatori: kesh, partiyalar, kvota nazorati |
| `prompts.py` | Gemini prompti va JSON sxema |
| `indicator.py` | Filtrlar va EAI/ESI hisobi |
| `monthly.py`, `main_monthly.py` | Oylik indeks (to'liqlik nazorati bilan) |
| `excel_exporter.py` | Excel hisobotlar (kunlik va oylik) |
| `sync_to_db.py` | Supabase'ga sinxronlash (bot va Mini App uchun) |
| `sheets_sync.py` | Natijalarni Google Sheets'ga yozish (jonli oyna) |
| `check.py` | Oldindan tekshiruv: Telegram sessiyasi va kanallar, Gemini, Sheets, bot ogohlantirishi |
| `export_session.py` | CI uchun Telegram sessiya satrini yaratish |
| `app/` | Telegram bot + Mini App (Vercel) |

## Natijalar

- `data/messages.csv` — xom arxiv (har postning `scraped_at` o'lchov vaqti bilan)
- `data/llm_labels.csv` — Gemini belgilari keshi (versiya va model bilan)
- `data/daily_index.csv` — kunlik EAI/ESI qatori
- `data/monthly_index.csv` — oylik qator (`days_covered` / `days_expected`, `complete`)
- `output/economic_index_latest.xlsx` — kunlik hisobot; oylik hisobot Actions artifact'da

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
- `uz-economic-index` — kunlik (00:05 va 02:05 Toshkent) + qo'lda.
- `uz-economic-index-monthly` — har oyning 3-kunida o'tgan oy uchun. Qo'lda
  ishga tushirganda `target_month` (YYYY-MM) bilan istalgan oyni qayta hisoblash mumkin.
- `check` — post yig'masdan hamma narsani tekshiradi (Telegram, Gemini, Sheets) va natijani botga yuboradi. Kunlik run bilan bir vaqtda ishlamaydi (navbatga turadi).

## Google Sheets oynasi

Hisob-kitob backend'da (GitHub Actions) bajariladi, jadvalga faqat natija yoziladi
(formulalar yo'q). Har run'dan keyin jadval yangilanadi:

| Varaq | Mazmuni |
|-------|---------|
| Kunlik indeks | kunlik EAI/ESI qatori |
| Oylik indeks | oylik qator |
| Xabarlar | har bir belgilangan post (mavzu, bayroqlar, ballar, havola), eng yangisi tepada |
| Info | oxirgi yangilanish vaqti, belgilash holati |

Jadvalga qo'lda yozmang: o'chirilgan yoki o'zgartirilgan qatorlarni keyingi run qayta tiklaydi.
Tahlil uchun alohida varaq yoki nusxa oching.

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
