# Metodologiya — O'zbekiston Iqtisodiy Yangiliklar Indeksi

Bu hujjat indeks **qanday hisoblanishini**, natijalarning **asl ma'nosini**,
**formulalarni**, ularning **ilmiy manbalarini**, **ishonchlilik** darajasini va
**cheklovlarni** to'liq bayon qiladi. v2 (sifat qayta qurilishi) real 1105 ta xabar
korpusida o'tkazilgan **ko'p-agentli audit** natijalariga asoslanadi.

---

## 1. Maqsad, chiqadigan natijalar

Loyiha O'zbekiston Telegram yangiliklaridan uch xil natija beradi:

| Natija | Nima | Diapazon |
|--------|------|----------|
| **primary_topic** (har xabar) | Xabar qaysi iqtisodiy kategoriyaga tegishli (10 tadan biri yoki `non_economic`) | kategoriya |
| **EAI** — Economic **Attention** Index (kunlik) | Yangiliklarning qancha qismi iqtisodga oid (e'tibor bilan tortilgan) | 0…1 |
| **ESI** — Economic **Sentiment** Index (kunlik) | Iqtisodiy yangiliklarning ohangi (ijobiy/salbiy) | −1…+1 |

EAI va ESI ataylab **ajratilgan** (biri hajm/diqqat, biri yo'nalish/ohang).

---

## 2. Ma'lumot manbai va o'suvchi arxiv

- **Kanallar:** umumiy + biznes/iqtisod media (`config.CHANNELS`). Scraper har kanal
  uchun "collected N"/"skipped" log qiladi — noto'g'ri handle xavfsiz o'tkaziladi.
- **O'suvchi master arxiv** `data/messages.csv`: har run yangi postlarni qo'shadi,
  `(kanal, message_id)` bo'yicha dublikatsiz → **haqiqiy, solishtiriladigan vaqt qatori**.
- Til: rus + o'zbek (lotin) + o'zbek (kirill) — leksikonlar **uch tilli**.

---

## 3. Matnni qayta ishlash (`text_utils.py`)

- `normalize_text`: kichik harf, apostrof birlashtirish, **shablon** (footer/link/CTA:
  telegram/obuna/batafsil/реклама…) olib tashlash → leksikon mosligi uchun.
- `normalize_light`: shablon **saqlanadi** → flag aniqlash (reklama/aksiya) uchun.
- `cyr_to_lat`: o'zbek kirill→lotin (faqat LDA tokenlari uchun).

### 3.1. Muhim tuzatish — chegaralangan naqshlar (v2)

v1 da leksikon bare o'zaklarni `\bstem` sifatida qidirardi va **polisemiya** tufayli
xato ishlardi (audit isbotladi): `цен`→**центр/центральный**, `yevro`→**Yevropa**,
`elektr`→**elektron**, `baho`→**baholash**, `dollar`→"$" birlik. Eng katta kategoriya
~44% shovqin edi va ~7% "iqtisodiy" postlar soxta bo'lib, EAI'ni ham shishirardi.

v2 da har atama **chegaralangan regex**: masalan `\bцен(?=а|ы|е|у|ой|ам|ах|н)` (narx,
lekin центр emas), `\belektr(?!on|osh)`, `\bевро\b` (aniq so'z), FX faqat `курс/kurs/
валют` kontekstida. Har o'zgarish real yuza-shakllarga qarab tekshirilgan.

---

## 4. Har xabar bo'yicha o'lchovlar (`indicator.py`, `categorizer.py`, `sentiment.py`)

### 4.1. Iqtisodiy relevantlik R
`econ_hits` = chegaralangan leksikon mosliklarining umumiy soni.
$$R = 1 - e^{-\text{econ\_hits}/\text{TAU}} \quad (\text{TAU}=2,\; 0..1)$$
Post `econ_hits ≥ 2` bo'lsagina **iqtisodiy** (`is_economic`) deb belgilanadi — v1 dagi
1 chegara "tanga tashlash" edi (audit: iqtisodiy postlarning 46% bitta moslikda hal
bo'lardi, aynan shu yerda soxtaliklar). *Manba:* Baker–Bloom–Davis (2016) EPU.

### 4.2. Kategoriya klassifikatori (LDA "topic"lar o'rniga)
Buzuq, beqaror LDA o'rniga **deterministik** klassifikator (`categorizer.py`):
10 kategoriya — `prices_inflation, currency_fx, fiscal, trade, macro, banking_finance,
labour_income, energy_utility, business, construction_realty` (+ `non_economic`).
Qoida: har kategoriya bo'yicha moslik sanaladi → `primary_topic = argmax`, tenglikда
qat'iy **priority** tartibi (aniqroq kategoriya avval, `macro` oxirida). Shaffof: har
yorliqni qaysi so'z keltirganini ko'rsatish mumkin. Bu — saralanadigan/guruhlanadigan
qatlam (`Topic Breakdown` varag'i). *Manba:* mavzuli tasnif — kuzatiladigan taksonomiya.

### 4.3. Filtrlar (indeksdan chiqariladi)
- `is_ad` — reklama/aksiya/chegirma/ipoteka reklamalari (bank mahsulot reklamalari).
- `is_digest` — "yangiliklar dayjesti" (bir postda ko'p voqea — baholab bo'lmaydi).
- `is_foreign` — xorijiy davlat/rahbar bor **va** O'zbekiston obyekti (12 viloyat,
  Markaziy bank, so'm…) **yo'q** → xorijiy makro (masalan "AQSH davlat qarzi"). UZ index
  uchun chiqariladi. Bular `in_index=0` — EAI/ESI'ga kirmaydi.

### 4.4. Sentiment (aspekt-asosli) s
Oddiy pos/neg lug'at ~30% xato qiladi, chunki yo'nalish so'zi (o'sish/рост) ma'nosi
**nimaga** tegishliligiga bog'liq. v2 yo'nalishni eng yaqin **aspekt** bilan bog'laydi
(±45 belgi oynasi):
$$\text{UP}\times\text{cost}=-,\;\;\text{DOWN}\times\text{cost}=+,\;\;\text{UP}\times\text{output}=+,\;\;\text{DOWN}\times\text{output}=-,\;\;\text{FX-rate UP}=-$$
$$s = \frac{\sum \text{signals}}{|\text{signals}|} \in [-1,1]$$
Masalan "*Курс доллара вырос*" → −1 (so'm zaiflashdi = salbiy); "*dollar kursi tushdi*"
→ +1; "*рост себестоимости*" → − (xarajat o'sishi). Qo'shimcha: bir ma'noli qutb
so'zlari (инqiroz/льгот…) + **inkor himoyasi** ("oshirmaslik"/"не повысить").
Audit: iqtisodiy postlarda belgi-xatosi **30% → ~4%**.
Ikki ortiqcha-tuzatish ataylab **cheklangan**: FX faqat *kurs* kontekstida (birlik "$"
emas), va "domestic keyword gate" olib tashlangan (u Xorazm/prezident postlarini
noto'g'ri neytrallagan). *Manba:* Loughran–McDonald (2011), Tetlock (2007).

### 4.5. E'tibor og'irligi w
$$\text{engagement}=\ln(1+\text{views}+2\cdot\text{forwards}),\qquad w=\frac{\text{engagement}}{\text{kanal o'rtachasi}}$$
`ln` — og'ir-dumli ko'rishlarni siqadi; forward×2 — kuchliroq signal; kanalga bo'lish —
katta kanal bosib ketmasin. *Manba:* Antweiler–Frank (2004).

### 4.6. LLM klassifikator — ixtiyoriy, yuqori sifat (`llm_classifier.py`)
LLM til va kontekstni qoidalardan ancha yaxshi tushunadi (aspekt, reklama, geosiyosat).
Har xabarni tasniflaydi: `economic`, `topic` (o'sha 10 kategoriya), `relevance` (0–1),
`sentiment` (−1..1), `is_ad`/`is_digest`/`is_foreign` — majburiy JSON bilan. Prompt
`prompts.py` da (kategoriyalar, aspekt-sentiment mantiqi, O'zbekiston domen fokusi).

**Ikki provayder** (`LLM_PROVIDER`):
- **`github`** (default, tavsiya) — **GitHub Models**: BEPUL, alohida kalit shart emas,
  Actions'dagi `GITHUB_TOKEN` ishlatadi (`permissions: models: read`), **GPT** modellari
  (`openai/gpt-4o-mini`, `openai/gpt-4o`). OpenAI-mos JSON rejimi.
- **`gemini`** — Google Gemini API (`GEMINI_API_KEY` kerak; bepul kvotasi past).

Muhandislik jihatlari: (a) natijalar `data/llm_labels.csv` da **keshlanadi** — faqat
yangi `(kanal, message_id)` chaqiriladi; (b) **partiyalab** (20 tadan); (c) har run
`LLM_MAX_PER_RUN` (default 600) tadan ko'p yangi post chaqirilmaydi — rate-limitни
oshirmaslik uchun katta backfill bir necha run'ga taqsimlanadi; (d) kvota/tarmoq/kalit
xatosida o'sha partiya **qoida-asosli fallback** qiladi (quvur buzilmaydi), faqat
haqiqiy LLM yorliqlari keshlanadi (xatolilar keyingi run'da qayta urinadi).
Diagnostika: `llm_check.py` / `llm-check` workflow aniq xatoni ko'rsatadi.

---

## 5. Kunlik indekslar

`in_index` = `is_economic` **va** reklama/dayjest/xorijiy emas. `relevance_eff` =
in-index bo'lsa `relevance`, aks holda 0.

$$EAI_d=\frac{\sum_{\text{barcha}} w_i\cdot \text{relevance\_eff}_i}{\sum w_i}\qquad
ESI_d=\frac{\sum_{\text{in\_index}} w_i\cdot s_i}{\sum_{\text{in\_index}} w_i}$$

Normallashtirish: `x_z=(x-mean)/std`; `EAI_100=100·EAI/mean(EAI)` (o'rtacha kun=100);
`ESI_100=50·(ESI+1)` (0…100, 50=neytral). *Manba:* FRBSF News Sentiment (Shapiro 2020);
z-ball/diffuziya indekslari — standart iqtisodiy amaliyot.

---

## 6. Natijalarni o'qish

- `Daily Index` (grafik bilan): `economic_messages` (iqtisodiy), `counted_messages`
  (indeksga kirgan = reklama/xorijiysiz), `EAI_100`, `ESI_100`.
  `EAI_100=150` → o'rtachadan 1.5× ko'p iqtisodiy e'tibor. `ESI_100=63` → neytraldan ijobiy.
- `Messages & Scores` — **muhimlik (relevance×e'tibor) bo'yicha saralangan**, topic +
  sentiment + flaglar bilan. Yuqori qatorlar — kun indeksini haqiqatan qo'zg'agan postlar.
- `Topic Breakdown` — har kategoriya: postlar soni, o'rtacha relevantlik/sentiment, ulush.

---

## 7. LDA — ikkilamchi diagnostika

LDA (`Topic Glossary`) faqat "hozir qanday mavzular bor"ни ko'rsatuvchi **eksploratsiya**
(coherence `u_mass`). Indeksni **hisoblamaydi** va `primary_topic` bilan almashtirilmaydi:
qisqa matnlarda beqaror, til/shablon bo'yicha ajraladi, har run qayta o'rgatilgani uchun
kunlar solishtirib bo'lmaydi. Ishlab chiqarish uchun: bir marta o'rgatib `model.save()`.

---

## 8. Formulalar ishonchlimi?

**Uslub jihatidan — ha.** Har biri markaziy banklar/akademik iqtisodchilar ishlatadigan
tan olingan usul (EPU kalit-so'z chastotasi, FRBSF news sentiment, lug'at/aspekt sentiment,
log-e'tibor, z-normallashtirish). Muhimi — **shaffof va tekshiriladigan**: har son
formuladan, har yorliq aniq so'zdan keladi (`Economic Lexicon` varag'i).

**Lekin** aniqlik leksikon sifatiga bog'liq. v2 auditdan o'tdi (soxtaliklar ~7%→past,
sentiment belgi-xatosi 30%→~4%), lekin bu hali **signal-indikator (proksi)**, rasmiy
statistika emas — §11 validatsiyasigacha.

---

## 9. Ilmiy manbalar

1. Baker, Bloom, Davis (2016) *Measuring Economic Policy Uncertainty*, QJE — EAI asosi.
2. Shapiro, Sudhof, Wilson (2020) *Measuring News Sentiment*, FRBSF/J.Econometrics — ESI asosi.
3. Loughran, McDonald (2011) *…Textual Analysis, Dictionaries, and 10-Ks*, J.Finance — lug'at-sentiment.
4. Tetlock (2007) *Giving Content to Investor Sentiment*, J.Finance.
5. Antweiler, Frank (2004) *Is All That Talk Just Noise?*, J.Finance — e'tibor/hajm.
6. Blei, Ng, Jordan (2003) *Latent Dirichlet Allocation*, JMLR — LDA.
7. Röder, Both, Hinneburg (2015) *…Topic Coherence Measures*, WSDM.

---

## 10. Cheklovlar va qolgan xatolik (halol)

**v2 tuzatgan:** stem-kolliziyalari (цен/yevro/elektr/baho), aspekt-sentiment,
1-chegara, reklama/xorijiy shovqin.

**Qolgan (auditda o'lchangan):**
1. **Reklama over-flag:** ba'zi haqiqiy biznes yangiliklari reklama deb belgilanib
   chiqarilishi mumkin (aksincha soxtalikdan afzal — precision).
2. **Inkor/soya-iqtisod:** "narxni oshirmaslik", "soya iqtisod ВВПга nisbatan tushdi"
   kabi noyob holatlar hali xato bo'lishi mumkin (residual ~4%).
3. **Kanal handle'lari** shu mashinada tasdiqlanmadi (proxy) — CI logi haqiqat manbai.
4. **Geosiyosiy "iqtisod"** ("иқтисодий операция") — foreign filtri ko'pini tutadi, hammasini emas.
5. **Sabab-oqibat emas:** indeks yangiliklardagi aks-sadoni o'lchaydi, iqtisodiy voqelikni emas.

---

## 11. Validatsiya rejasi

Indeksni rasmiy ko'rsatkichlarga solishtirish: **ESI ↔ CPI / USD-UZS kursi**,
**EAI ↔ yirik iqtisodiy e'lonlar** (stavka/byudjet qarorlari). Korrelyatsiya + lag-tahlil.

---

## 12. Yaxshilanish yo'l xaritasi

- **P2 (keyingi):** transformer ko'p tilli sentiment (aspekt darajasi), reklama flagini
  aniqlashtirish, muzlatilgan LDA, real ko'rsatkichlarga backtest.
- **P3:** dashboard + Markaziy bank tahlil platformasiga (tashqi-savdo) integratsiya.

*Xulosa:* v2 — shaffof, chegaralangan naqshli, aspekt-sentimentli, auditdan o'tgan.
Har xabar endi to'g'ri kategoriyaga tushadi va indeks domen shovqinidan tozalangan.
