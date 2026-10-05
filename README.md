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
| `llm_check.py` | Gemini diagnostikasi |
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

**Variables** (ixtiyoriy): `GEMINI_MODEL` — modelni qat'iy belgilash. Bo'sh bo'lsa
avtomatik tanlanadi va keyin o'sha model saqlanib qoladi. Qaysi modelda bepul
kvota borligini https://aistudio.google.com/rate-limit da ko'ring.

**Workflow'lar:**
- `uz-economic-index` — kunlik (00:05 va 02:05 Toshkent) + qo'lda.
- `uz-economic-index-monthly` — har oyning 3-kunida o'tgan oy uchun. Qo'lda
  ishga tushirganda `target_month` (YYYY-MM) bilan istalgan oyni qayta hisoblash mumkin.
- `llm-check` — Gemini kaliti va modellarini tekshirish.

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
