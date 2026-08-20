# uz_economic_index

O'zbekiston Telegram yangilik kanallaridan **iqtisodiy "kayfiyat indeksi"** quruvchi Python quvuri (pipeline). Postlarni yig'adi → matnni tozalaydi → LDA mavzuli modeli quradi → iqtisodiy mavzular ulushini engagement bilan tortib **kunlik indeks** hisoblaydi → 3 varaqli Excel hisobot chiqaradi.

## Bosqichlar

| Fayl | Vazifasi |
|------|----------|
| `main.py` | Butun quvurni ketma-ket ishga tushiradi |
| `config.py` | API kalitlari, kanallar, model parametrlari, proxy/sessiya |
| `scraper.py` | Telethon orqali Telegram'dan xabarlarni yig'adi |
| `preprocessor.py` | Matn tozalash + gensim lug'at/korpus |
| `topic_model.py` | LDA modeli + indeks hisoblash |
| `excel_exporter.py` | Excel hisoboti (`output/economic_index_<sana>.xlsx`) |
| `export_session.py` | CI uchun `StringSession` yaratuvchi yordamchi |

## Lokal ishga tushirish (Windows)

```powershell
cd D:\claude\uz_economic_index\uz_economic_index
.\venv\Scripts\python.exe main.py
```

> **Diqqat:** bu mashinaning tarmog'i (O'zbekiston) Telegram MTProto ulanishini DPI orqali reset qiladi — to'g'ridan-to'g'ri ulanish ishlamaydi. Lokal ishga tushirish uchun VPN/proxy kerak:
> ```powershell
> $env:USE_PROXY=1; $env:PROXY_PORT=10808; .\venv\Scripts\python.exe main.py
> ```
> Ishonchli, avtomatik variant — quyidagi GitHub Actions (u O'zbekiston tarmog'idan tashqarida ishlaydi, proxy shart emas).

## GitHub Actions (avtomatik, tavsiya etiladi)

`.github/workflows/scrape.yml` har kuni **18:00 UTC (23:00 Toshkent)** da va qo'lda ("Run workflow") ishlaydi, natijani repo'ga commit qiladi va artifact sifatida yuklaydi.

Kerakli **secret**lar (repo → Settings → Secrets and variables → Actions):

| Secret | Nima |
|--------|------|
| `TG_API_ID` | Telegram API ID |
| `TG_API_HASH` | Telegram API Hash |
| `TG_SESSION_STRING` | Avtorizatsiya qilingan Telethon StringSession |

`TG_SESSION_STRING` ni yaratish (bir marta, o'z mashinangizda):

```powershell
.\venv\Scripts\python.exe export_session.py
```

Bu `session_string.txt` faylini yaratadi — ichidagi satrni `TG_SESSION_STRING` secret'ga joylang, so'ng faylni **o'chiring** (bu parolga teng).

## Muhim eslatma — `TARGET_TOPICS`

`config.py` dagi `TARGET_TOPICS = [0, 2]` — bu **taxmin**. LDA mavzulari nazoratsiz o'rganiladi, shuning uchun birinchi run'dan keyin Excel'dagi **`Topic Glossary`** varag'iga qarang va qaysi mavzular haqiqatan iqtisodiy so'zlardan (inflatsiya, valyuta, byudjet, eksport...) iborat bo'lsa — o'sha indekslarni `TARGET_TOPICS` ga qo'ying.
