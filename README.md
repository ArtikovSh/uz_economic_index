# uz_economic_index

O'zbekiston Telegram yangilik kanallaridan **ikkita ilmiy-asosli iqtisodiy indeks**
quruvchi Python quvuri. To'liq metodologiya: [METHODOLOGY.md](METHODOLOGY.md).

| Indeks | Nimani o'lchaydi | Diapazon |
|--------|------------------|----------|
| **EAI** — Economic Attention Index | Yangiliklar oqimining qancha qismi iqtisodga oid (e'tibor bilan tortilgan) | 0…1 |
| **ESI** — Economic Sentiment Index | Iqtisodiy yangiliklarning ohangi (ijobiy/salbiy) | −1…+1 |

Indeks **shaffof, uch tilli leksikon** (o'zbek lotin+kirill, rus) asosida ishlaydi —
LDA faqat yordamchi diagnostikaga tushirilgan. Sabablari METHODOLOGY.md §1, §7 da.

## Modullar

| Fayl | Vazifasi |
|------|----------|
| `main.py` | Quvurni ishga tushiradi (scrape → store → score → index → export) |
| `config.py` | Sozlamalar: API/sessiya, kanallar, indeks parametrlari, proxy |
| `scraper.py` | Telethon orqali yig'ish (StringSession/proxy qo'llab-quvvatlaydi) |
| `store.py` | O'suvchi, dublikatsiz master arxiv (`data/messages.csv`) |
| `text_utils.py` | Normallashtirish, shablon-filtri, kirill→lotin transliteratsiya |
| `lexicons.py` | Uch tilli iqtisodiy leksikon — **chegaralangan regex naqshlar** (10 kategoriya) + reklama/xorijiy detektorlar |
| `categorizer.py` | Qoida-asosli **primary_topic** (10 kategoriya) + reklama/dayjest/xorijiy flag |
| `sentiment.py` | Qoida-asosli **aspekt** sentiment (narx↑=−, ishlab chiqarish↑=+, kurs↑=−) |
| `llm_classifier.py` | **LLM** klassifikatori — OpenAI-mos (Groq bepul GPT) yoki Gemini; keshli, fallback bilan |
| `prompts.py` | LLM uchun tasniflash prompti + JSON sxema |
| `llm_check.py` | LLM provayderini diagnostika qiluvchi skript |
| `indicator.py` | **Yadro:** relevance, sentiment, engagement → EAI/ESI |
| `topic_model.py` | LDA (faqat diagnostik: mavzular + koherentlik) |
| `excel_exporter.py` | 5 varaqli Excel + grafik |
| `export_session.py` | CI uchun StringSession yaratuvchi |

## Natijalar

- `data/messages.csv` — o'suvchi xom arxiv (CI commit qiladi)
- `data/daily_index.csv` — EAI/ESI kunlik vaqt qatori (CI commit qiladi)
- `output/economic_index_<sana>.xlsx` — 6 varaqli hisobot + grafik:
  Daily Index · Messages & Scores (muhimlik bo'yicha saralangan) · Topic Breakdown ·
  Economic Lexicon · Topic Glossary · Methodology

Har xabar `primary_topic` (10 iqtisodiy kategoriya yoki `non_economic`) oladi; reklama,
dayjest va xorijiy-makro postlar indeksdan chiqariladi.

## Lokal ishga tushirish (Windows)

> UZ tarmog'i Telegram MTProto'ni DPI orqali reset qiladi → lokal to'g'ridan-to'g'ri
> ulanish ishlamaydi. Lokalda VPN/proxy kerak; ishonchli yo'l — GitHub Actions.

```powershell
cd D:\claude\uz_economic_index\uz_economic_index
$env:USE_PROXY=1; $env:PROXY_PORT=10808   # agar proxy klientingiz bo'lsa
.\venv\Scripts\python.exe main.py
```

## GitHub Actions (avtomatik, tavsiya etiladi)

`.github/workflows/scrape.yml` har kuni **21:00 va 23:00 Toshkent** + qo'lda ishlaydi.
Har run **2 kun oldingi to'liq kun**ni (Toshkent 00:00–23:59) yig'adi (`SCRAPE_DAYS_BACK`),
natijani `ArtikovSh` nomidan repo'ga commit qiladi + artifact yuklaydi. Aniq kunni
qo'lda backfill qilish: `TARGET_DATE=YYYY-MM-DD`.

Secretlar: `TG_API_ID`, `TG_API_HASH`, `TG_SESSION_STRING` (sessiyani Google Colab
yoki `export_session.py` orqali yarating — METHODOLOGY.md / oldingi ko'rsatmalarga qarang).

**LLM bilan tasniflash (tavsiya etiladi):**
- **Groq (BEPUL, GPT, default):** https://console.groq.com/keys da bepul kalit oling →
  repo'ga **`OPENAI_API_KEY`** secret'ini qo'shing. Provayder avtomatik `openai` bo'ladi,
  endpoint Groq (`OPENAI_BASE_URL` default). Model: `OPENAI_MODEL` o'zgaruvchisi
  (default `llama-3.3-70b-versatile`; GPT uchun `openai/gpt-oss-120b`).
  OpenRouter/OpenAI/lokal — `OPENAI_BASE_URL`'ni almashtiring.
- **Gemini (muqobil):** `LLM_PROVIDER=gemini` + `GEMINI_API_KEY` (https://aistudio.google.com/apikey).
- **GitHub Models — eskirgan** (GitHub yopyapti, HTTP 410); ishlatmang.
- LLM ishlamasa — avtomatik **qoida-asosli** fallback (quvur buzilmaydi). Har yangi
  xabar bir marta belgilanadi va `data/llm_labels.csv` da keshlanadi.
- Diagnostika: Actions → **`llm-check`** → Run workflow (aniq xato/modelni ko'rsatadi).
