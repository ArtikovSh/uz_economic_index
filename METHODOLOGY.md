# Metodologiya — O'zbekiston Iqtisodiy Yangiliklar Indeksi (v3)

Bu hujjatda indeks qanday hisoblanishi, formulalar, ularning manbalari va
cheklovlar bayon qilingan. v3 da per-post tasnif to'liq **Gemini** ga o'tkazildi.
Qoidaga asoslangan lug'at klassifikatori va LDA olib tashlandi. Indeks formulalari
(5–6-bo'limlar) o'zgarmagan. Ularni nazariy jihatdan mustahkamlash — keyingi bosqich (10-bo'lim).

---

## 1. Maqsad va natijalar

| Natija | Nima | Diapazon |
|--------|------|----------|
| **primary_topic** (har post) | 10 iqtisodiy kategoriyadan biri yoki `non_economic` | kategoriya |
| **EAI** — Economic **Attention** Index (kunlik) | Yangiliklarning qancha qismi iqtisodga oid (e'tibor bilan tortilgan) | 0…1 |
| **ESI** — Economic **Sentiment** Index (kunlik) | Iqtisodiy yangiliklarning ohangi | −1…+1 |

EAI va ESI ataylab ajratilgan: biri hajm va e'tiborni, ikkinchisi yo'nalish va ohangni o'lchaydi.

---

## 2. Ma'lumotlarni yig'ish

- **Kanallar:** umumiy va biznes/iqtisod media (`config.CHANNELS`).
- **Bir kun — bir run:** run har kuni Toshkent vaqti bilan **00:05** da boshlanadi va
  `SCRAPE_DAYS_BACK = 2` kun oldingi to'liq kalendar kunni (00:00:00–23:59:59) yig'adi.
  Shu sababli o'lchov paytida kunning oxirgi posti **kamida 24 soat**, birinchi posti
  ~48 soat auditoriyada bo'lgan bo'ladi. Run vaqti har kuni bir xil, shuning uchun
  kunlar bir xil sharoitda o'lchanadi.
- **Har post bir marta o'lchanadi:** ko'rishlar va forward'lar birinchi yig'ilgan
  paytdagi qiymatda qoladi. Keyingi qayta yig'ish ularni yangilamaydi.
  O'lchov vaqti `scraped_at` ustunida saqlanadi (post yoshini hisoblash uchun).
- **Zaxira run (02:05):** faqat birinchi run yig'a olmagan kanallarni yig'adi.
- **Bo'shliqlar to'ldirilmaydi:** yig'ilmay qolgan kun keyinroq yig'ilmaydi. Sabab —
  kech yig'ilgan postlarning ko'rishlari boshqalarnikiga qaraganda ko'proq "yetilgan"
  bo'lib qoladi. Oylik qatorda bu `days_covered` / `days_expected` sifatida ko'rinadi.
- **Ishonchlilik:** Telegram sessiyasi yig'ishdan oldin tekshiriladi. Run yiqilsa
  (sessiya, kanal yoki Gemini kaliti muammosi), bot administratorga xabar yuboradi.
- Sanalar UTC'da saqlanadi, kunlik indeks esa **Toshkent kuni** bo'yicha guruhlanadi.

---

## 3. Tasniflash — Gemini (`llm_classifier.py`, `prompts.py`)

Har post bir marta belgilanadi va natija `data/llm_labels.csv` da keshlanadi.

| Maydon | Ma'nosi |
|--------|---------|
| `economic` | post O'zbekiston ichki iqtisodiyotiga oidmi |
| `topic` | `prices_inflation, currency_fx, fiscal, trade, macro, banking_finance, labour_income, energy_utility, business, construction_realty` yoki `non_economic` |
| `relevance` | iqtisod postda qanchalik markaziy (0–1) |
| `sentiment` | O'zbekiston iqtisodiyoti va aholisi uchun ohang (−1…+1) |
| `is_ad`, `is_digest`, `is_foreign` | reklama, dayjest, xorijiy-makro bayroqlari |

**Sentiment qoidalari (aspekt mantiqi):**
- Narx, tarif, inflyatsiya yoki soliq stavkasi **oshsa — salbiy**, kamaysa — ijobiy.
- YaIM, ishlab chiqarish, eksport, investitsiya, ish haqi yoki zaxiralar **oshsa — ijobiy**.
- Dollar/yevro kursi oshsa (so'm zaiflashsa) — **salbiy**, kurs tushsa — ijobiy.
- Inkor hisobga olinadi ("narx oshirilmaydi" salbiy emas).
- **Protokol yangiliklari — 0:** uchrashuv, tashrif, forum, memorandum, reja yoki niyat
  haqidagi postlar, agar ularda aniq o'lchanadigan o'zgarish bo'lmasa, neytral
  baholanadi. Bu qoida v2 dagi ijobiy tomonga siljishni kamaytiradi.

**Muhandislik qoidalari:**
- **Kesh va versiya:** belgi `label_version` (hozir `v3`) va uni bergan `model` bilan
  saqlanadi. Prompt ma'nosi o'zgarsa, versiya oshiriladi va hamma postlar qayta belgilanadi.
- **Qat'iy model:** `GEMINI_MODEL` berilgan bo'lsa, faqat shu model ishlatiladi.
  Aks holda keshdagi belgilarni bergan model saqlanadi. U ishlamay qolsagina boshqa
  model tanlanadi va bu ogohlantirish sifatida qayd etiladi.
- **Zaxira klassifikator yo'q:** Gemini javob bermasa yoki kvota tugasa, post
  belgilanmay qoladi va keyingi run'da qayta yuboriladi. Indeks hech qachon ikki xil
  usulda olingan belgilarni aralashtirmaydi.
- **Kvota:** so'rovlar daqiqalik limitga moslab yuboriladi. Har run'da so'rovlar soni
  cheklangan (`LLM_MAX_REQUESTS`). Eng yangi postlar birinchi belgilanadi.

---

## 4. Filtrlar — indeksga nima kiradi

`in_index` = post belgilangan **va** `economic` **va** reklama, dayjest yoki xorijiy-makro emas.

**Kanal reklama belgisi — deterministik filtr.** Kanal o'zi reklama deb belgilagan post
modelning javobidan qat'i nazar chiqariladi. Belgilar: matnning istalgan joyidagi
`(реклама)`, `на правах рекламы`, `#реклама` yoki postning oxirgi so'zi sifatidagi
`Reklama`/`Реклама` (Daryo va Kun.uz formati). Gap ichida kelgan "реклама" so'zi
(reklama bozori haqidagi yangilik) filtrga tushmaydi.

Sentabr 2026 ma'lumotida bunday belgili postlar 337 ta (8.7%) chiqdi. v2 modeli ulardan
165 tasini reklama deb belgilamagan va **105 tasi indeksga kirib ketgan**.

---

## 5. Kunlik indekslar (`indicator.py`)

**E'tibor vazni:**
$$\text{engagement}=\ln(1+\text{views}+2\cdot\text{forwards}),\qquad w=\frac{\text{engagement}}{\text{kanal o'rtachasi}}$$

**Samarali relevantlik:** `relevance_eff` = post indeksga kirsa `relevance`, aks holda 0.

$$EAI_d=\frac{\sum_{\text{barcha}} w_i\cdot \text{relevance\_eff}_i}{\sum w_i}\qquad
ESI_d=\frac{\sum_{\text{in\_index}} w_i\cdot s_i}{\sum_{\text{in\_index}} w_i}$$

**Normallashtirish:**
- `x_z = (x − mean) / std`;
- `EAI_100 = 100·EAI / mean(EAI)` — o'rtacha kun = 100;
- `ESI_100 = 50·(ESI + 1)` — 0…100, 50 = neytral.

Kunning **hamma posti belgilangandagina** indeks e'lon qilinadi. Aks holda qiymat bo'sh
qoladi (`unlabeled_messages` > 0) va keyingi run'da to'ldiriladi.
*Manbalar:* Baker–Bloom–Davis (2016); Shapiro–Sudhof–Wilson (2022); Antweiler–Frank (2004).

## 6. Oylik indeks (`monthly.py`)

Oylik indeks kunlik qiymatlarning o'rtachasi emas. U o'sha oy (Toshkent vaqti)
postlari bo'yicha **post darajasida** qayta hisoblanadi:

$$EAI_{oy}=\frac{\sum w R}{\sum w},\qquad ESI_{oy}=\frac{\sum w s}{\sum w}$$

`EAI_100` oylar bo'yicha normallashtiriladi (o'rtacha oy = 100). Hisob har oyning
3-kunida o'tgan oy uchun bajariladi. Har qatorda `days_covered`, `days_expected`,
`unlabeled_messages` va `complete` bor. To'liq bo'lmagan oy ogohlantirish bilan yoziladi.

---

## 7. Natijalarni o'qish

- `Daily Index` (grafik bilan) ustunlari:
  - `economic_messages` — iqtisodiy postlar soni;
  - `counted_messages` — indeksga kirgan postlar;
  - `EAI_100`, `ESI_100` — indeks qiymatlari;
  - `unlabeled_messages` — hali belgilanmagan postlar.
- `EAI_100 = 150` — iqtisodiy e'tibor o'rtachadan 1.5 baravar yuqori. `ESI_100 = 63` — neytraldan ijobiy.
- `Messages & Scores` — postlar muhimlik bo'yicha (relevance × e'tibor) saralangan.
  Ustunlar: `ad_marker` (kanal reklama belgisi), `label_model`, `scraped_at`.
- `Topic Breakdown` — har kategoriya bo'yicha postlar soni, o'rtacha relevantlik va sentiment, ulush.

---

## 8. Cheklovlar (halol)

1. **LLM aniqligi hali o'lchanmagan.** Inson belgilagan etalon to'plam (gold set) yo'q;
   aniqlik foizi — ochiq savol.
2. **E'tibor vazni amalda deyarli ishlamaydi.** Logarifm farqlarni juda siqadi.
   Sentabr ma'lumotida vaznsiz indeks vaznli indeksdan o'rtacha atigi 0.3 punkt farq qildi.
3. **Butun tarix bo'yicha normallashtirish.** `EAI_100` va z-ball har run'da qayta
   hisoblanadi, shuning uchun o'tgan kunlar qiymati o'zgarib turadi.
4. **Kanal tarkibi.** Posti ko'p kanal (@uzdaily) indeksga nisbatan ko'proq ta'sir qiladi.
5. **Hafta kuni effekti.** Yakshanba kunlari EAI odatda past bo'ladi.
6. **Sabab-oqibat emas.** Indeks yangiliklardagi aks-sadoni o'lchaydi, iqtisodiy voqelikni emas.

2–5-bandlar keyingi bosqichda hal qilinadi (10-bo'lim).

---

## 9. Ilmiy manbalar

1. Baker, Bloom, Davis (2016) *Measuring Economic Policy Uncertainty*, QJE — EAI asosi.
2. Shapiro, Sudhof, Wilson (2022) *Measuring News Sentiment*, J. of Econometrics — ESI asosi.
3. Tetlock (2007) *Giving Content to Investor Sentiment*, J. of Finance.
4. Antweiler, Frank (2004) *Is All That Talk Just Noise?*, J. of Finance — e'tibor/hajm.
5. Barbaglia, Consoli, Manzan (2023) *Forecasting with Economic News*, JBES — aspektli sentiment.

---

## 10. Keyingi bosqich — hisoblash texnikasini nazariy mustahkamlash

- **Vazn:** postning ko'rishlarini o'sha kanalning o'sha kundagi medianasiga nisbati
  sifatida o'lchash (chekka qiymatlar cheklanadi) va post yoshiga tuzatish kiritish
  (`scraped_at` asosida).
- **Kanallarni birlashtirish:** avval har kanal uchun alohida indeks, keyin
  standartlashtirib birlashtirish (EPU usuli).
- **Qat'iy bazaviy davr:** e'lon qilingan qiymatlar keyin o'zgarmasligi uchun.
- **Me'yordan og'ish:** ESI uchun balans ko'rsatkichi va uzoq muddatli o'rtachaga
  nisbatan normallashtirish; hafta kuni effektini tuzatish.
- **Validatsiya:** etalon to'plam; rasmiy ko'rsatkichlar (CPI, MB inflyatsion kutilmalar so'rovi) bilan solishtirish.
