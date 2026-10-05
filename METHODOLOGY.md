# Metodologiya — O'zbekiston Iqtisodiy Yangiliklar Indeksi (v4)

Bu hujjat indeks qanday hisoblanishini, ma'lumot qanday saqlanishini va cheklovlarni
bayon qiladi. v4 da indeks **oddiy sanoq** bilan hisoblanadi: vazn yo'q,
normallashtirish yo'q. Ma'lumot ikki jadvalda saqlanadi va ularga yangi qatorlar
faqat qo'shiladi.

---

## 1. Ikki indeks

Har qanday davr (kun, hafta, oy, chorak, yil) uchun **barcha kanallar birga**:

| Belgi | Ma'nosi |
|-------|---------|
| `reklama emas` | reklama bo'lmagan xabarlar soni |
| `iqtisodiy` | reklama emas **va** O'zbekiston iqtisodiyotiga oid xabarlar (dayjest va xorijiy-makro emas) |
| `ijobiy`, `salbiy` | iqtisodiy xabarlar ichida ohangi ijobiy yoki salbiy bo'lganlari |

$$EAI = 100\cdot\frac{\text{iqtisodiy}}{\text{reklama emas}}\qquad
ESI = 100\cdot\frac{\text{ijobiy}-\text{salbiy}}{\text{iqtisodiy}}$$

- **EAI** (Economic Attention Index) — reklama bo'lmagan yangiliklarning necha foizi
  O'zbekiston iqtisodiyotiga oid. Shkala 0–100%.
- **ESI** (Economic Sentiment Index) — balans: ijobiy xabarlar salbiylardan necha foiz
  punkt ko'p. Shkala −100…+100, 0 = neytral. Biznes va iste'molchi so'rovnomalaridagi
  balans ko'rsatkichi ham shunday hisoblanadi (Yevrokomissiya; Pesaran va Weale, 2006).

**Misol:** kunda 140 ta reklama bo'lmagan xabar, ulardan 73 tasi iqtisodiy (40 ijobiy,
21 neytral, 12 salbiy). EAI = 73/140 = **52.1%**, ESI = 100·(40−12)/73 = **+38**.

Hafta, oy, chorak va yil indekslari shu formulalar bilan butun davrdagi xabarlar
soni bo'yicha hisoblanadi, kunlik qiymatlarning o'rtachasi emas.

---

## 2. Xabarlarni yig'ish

- **Kanallar:** umumiy va biznes/iqtisod media (`config.CHANNELS`).
- **Bir kun — bir run:** run har kuni Toshkent vaqti bilan **00:05** da boshlanadi va
  **2 kun oldingi** to'liq kunni yig'adi. Masalan, 6-oktabr 00:05 dagi run 4-oktabr
  postlarini (00:00:00–23:59:59) yig'adi. Shu sababli kunning oxirgi posti yig'ish
  paytida kamida 24 soatlik bo'ladi.
- **Har post bir marta o'lchanadi:** ko'rishlar, forward'lar va o'lchov vaqti
  (`scraped_at`) yig'ilganda saqlanadi va keyin yangilanmaydi. Ular indeks hisobida
  ishlatilmaydi, lekin kelajakdagi tahlil uchun yig'ib boriladi.
- **Zaxira run (02:05)** faqat birinchi run yig'a olmagan kanallarni yig'adi.
- **Yig'ilmagan kunlar keyin to'ldirilmaydi.** Ular davr qatorlarida `kunlar`
  ustunida ko'rinadi, masalan 26/30.
- Telegram sessiyasi yig'ishdan oldin tekshiriladi. Biror muammo bo'lsa, bot
  administratorga xabar yuboradi.

---

## 3. Tasniflash — Gemini (`llm_classifier.py`, `prompts.py`)

Har bir post bir marta belgilanadi:

| Maydon | Ma'nosi |
|--------|---------|
| `economic` | post O'zbekiston ichki iqtisodiyotiga oidmi |
| `topic` | 10 kategoriyadan biri yoki `non_economic` |
| `sentiment` | O'zbekiston iqtisodiyoti va aholisi uchun ohang (−1…+1) |
| `is_ad`, `is_digest`, `is_foreign` | reklama, dayjest, xorijiy-makro bayroqlari |
| `relevance` | iqtisod postda qanchalik markaziy (indeksda ishlatilmaydi, saqlanadi) |

**Ohang:** sentiment > +0.15 bo'lsa ijobiy, < −0.15 bo'lsa salbiy, qolgani neytral.

Sentiment qoidalari:
- narx, tarif yoki soliq oshsa — salbiy; YaIM, eksport yoki daromad oshsa — ijobiy;
- dollar kursi oshsa (so'm zaiflashsa) — salbiy;
- inkor hisobga olinadi;
- protokol yangiliklari (uchrashuv, memorandum, tashrif, reja) aniq o'zgarishsiz bo'lsa — 0.

**Reklama filtri:** kanal o'zi reklama deb belgilagan post (`(реклама)`,
`на правах рекламы`, `#реклама` yoki oxirgi so'z sifatidagi `Reklama`/`Реклама`)
model javobidan qat'i nazar reklama hisoblanadi.

**Zaxira klassifikator yo'q:** Gemini javob bermasa yoki kvota tugasa, post kutib turadi
va keyingi run'da qayta yuboriladi. Har bir belgi uni bergan modelni (`label_model`) va
versiyasini (`label_version`) saqlaydi.

---

## 4. Saqlash — ikki jadval, faqat qo'shish

| Fayl | Jadval | Mazmuni |
|------|--------|---------|
| `data/messages.csv` | **Xabarlar** | har bir post: matn, sana, ko'rishlar, forward'lar, Gemini belgilari va indeks bayroqlari (`nonad`, `econ`, `tone`) |
| `data/indices.csv` | **Indekslar** | har bir yopilgan davr uchun bitta qator: `period_type` (kun / hafta / oy / chorak / yil), sanoqlar, EAI, ESI, izoh |
| `data/pending.csv` | — | yig'ilgan, lekin kuni hali yakunlanmagan postlar (odatda bo'sh) |

**Qatorlar qachon qo'shiladi:**
- **Kun yakunlanadi**, qachonki uning barcha postlari belgilangan bo'lsa **va** barcha
  kanallar yig'ilgan bo'lsa (yoki quvur keyingi kunga o'tgan bo'lsa — unda kun
  "yig'ilmagan kanal" izohi bilan yopiladi).
- Yakunlangan kunning postlari "Xabarlar"ga, kun qatori esa "Indekslar"ga qo'shiladi.
- Kunlar faqat sana tartibida yakunlanadi: oldingi kun ochiq turgan bo'lsa, keyingisi kutadi.
- **Hafta, oy, chorak va yil qatori** davrning oxirgi kuni yakunlanganda qo'shiladi
  (yoki davrga boshqa ma'lumot kelmasligi aniq bo'lganda).

**Qo'shilgan qator hech qachon o'zgartirilmaydi.** E'lon qilingan qiymatlar qayta
ko'rib chiqilmaydi. Prompt kelajakda o'zgartirilsa, yangi qoida faqat yangi postlarga
qo'llanadi; butun tarixni qayta hisoblash alohida qaror bilan qilinadi.

Jadvallar Google Sheets'ga ("Indekslar", "Xabarlar", "Info"), Excel hisobotga va
Supabase'ga (bot va Mini App uchun) ko'chiriladi.

---

## 5. Natijalarni o'qish

- **EAI = 52.1%** — reklama bo'lmagan xabarlarning yarmidan ko'pi iqtisodiy.
- **ESI = +38** — iqtisodiy xabarlar orasida ijobiylari salbiylaridan 38 foiz punkt ko'p.
  **ESI = −10** — salbiylari ko'proq.
- **Kunlik qiymat** kuniga ~140 ta reklama bo'lmagan va ~60 ta iqtisodiy xabarga tayanadi.
  Shuning uchun uning tasodifiy tebranishi katta: 90% ishonch oralig'i EAI uchun taxminan
  ±7, ESI uchun ±15 punkt. Haftalik qatorda bu ±3 va ±6 punktga tushadi. Trendni haftalik
  va oylik qatorlardan kuzatish ishonchliroq.
- `kunlar` / `kunlar (jami)` — davrning necha kuni yig'ilgani. `izoh` — yig'ilmagan
  kanal yoki ma'lumotsiz kunlar.

---

## 6. Cheklovlar

1. **Kanal tarkibi:** indeks barcha kanallar bo'yicha birga hisoblanadi. Shuning uchun
   ko'p post yozadigan kanal (masalan, @uzdaily — postlarning ~37%) natijaga ko'proq
   ta'sir qiladi. Kanallar soni yoki faolligi o'zgarsa, indeks ham o'zgaradi.
2. **LLM aniqligi** hali inson belgilagan etalon to'plamda o'lchanmagan.
3. **Kunlik shovqin:** kichik tanlanma tufayli kundan-kunga o'zgarishlarni ehtiyotkorlik
   bilan talqin qilish kerak.
4. **Sabab-oqibat emas:** indeks yangiliklardagi aks-sadoni o'lchaydi, iqtisodiy voqelikni emas.

---

## 7. Manbalar

1. Baker, Bloom, Davis (2016). *Measuring Economic Policy Uncertainty*. QJE — maqolalar ulushi (EAI g'oyasi).
2. European Commission. *The Joint Harmonised EU Programme of Business and Consumer Surveys: User Guide* — balans ko'rsatkichi.
3. Pesaran, Weale (2006). *Survey Expectations*. Handbook of Economic Forecasting — balans statistikasi.
4. Shapiro, Sudhof, Wilson (2022). *Measuring News Sentiment*. J. of Econometrics.
