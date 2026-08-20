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
| `lexicons.py` | Uch tilli iqtisodiy + sentiment + stop-so'z leksikonlari |
| `indicator.py` | **Yadro:** relevance, sentiment, engagement → EAI/ESI |
| `topic_model.py` | LDA (faqat diagnostik: mavzular + koherentlik) |
| `excel_exporter.py` | 5 varaqli Excel + grafik |
| `export_session.py` | CI uchun StringSession yaratuvchi |

## Natijalar

- `data/messages.csv` — o'suvchi xom arxiv (CI commit qiladi)
- `data/daily_index.csv` — EAI/ESI kunlik vaqt qatori (CI commit qiladi)
- `output/economic_index_<sana>.xlsx` — 5 varaqli hisobot + grafik:
  Daily Index · Messages & Scores · Economic Lexicon · Topic Glossary · Methodology

## Lokal ishga tushirish (Windows)

> UZ tarmog'i Telegram MTProto'ni DPI orqali reset qiladi → lokal to'g'ridan-to'g'ri
> ulanish ishlamaydi. Lokalda VPN/proxy kerak; ishonchli yo'l — GitHub Actions.

```powershell
cd D:\claude\uz_economic_index\uz_economic_index
$env:USE_PROXY=1; $env:PROXY_PORT=10808   # agar proxy klientingiz bo'lsa
.\venv\Scripts\python.exe main.py
```

## GitHub Actions (avtomatik, tavsiya etiladi)

`.github/workflows/scrape.yml` har kuni 23:00 Toshkent + qo'lda ishlaydi, natijani
`ArtikovSh` nomidan repo'ga commit qiladi + artifact yuklaydi.

Secretlar: `TG_API_ID`, `TG_API_HASH`, `TG_SESSION_STRING` (sessiyani Google Colab
yoki `export_session.py` orqali yarating — METHODOLOGY.md / oldingi ko'rsatmalarga qarang).
