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

- **Kanallar:** umumiy va biznes/iqtisod media. Ro'yxatni admin Mini App'da boshqaradi
  (`channels` jadvali); qo'shilgan yoki to'xtatilgan kanal keyingi kunlik yig'imdan
  kuchga kiradi, yakunlangan kunlar o'zgarmaydi. Baza ishlamasa `config.CHANNELS`
  zaxira ro'yxati ishlatiladi.
- **Bir kun — bir run:** run har kuni Toshkent vaqti bilan **00:05** da boshlanadi va
  **2 kun oldingi** to'liq kunni yig'adi. Masalan, 6-oktabr 00:05 dagi run 4-oktabr
  postlarini (00:00:00–23:59:59) yig'adi. Shu sababli kunning oxirgi posti yig'ish
  paytida kamida 24 soatlik bo'ladi.
- **Har post bir marta o'lchanadi:** ko'rishlar, forward'lar va o'lchov vaqti
  (`scraped_at`) yig'ilganda saqlanadi va keyin yangilanmaydi. Ular indeks hisobida
  ishlatilmaydi, lekin kelajakdagi tahlil uchun yig'ib boriladi.
- **Zaxira run (02:05)** faqat birinchi run yig'a olmagan kanallarni yig'adi.
- **Yig'ilmagan kunlar avtomatik to'ldirilmaydi.** Ular davr qatorlarida `kunlar`
  ustunida ko'rinadi, masalan 26/30. Davr hali yopilmagan bo'lsa, bunday kunni
  `backfill.py` bilan qo'lda yig'ish mumkin (workflow'da `backfill_days`). Indeks postlar
  sonidan hisoblanadi, shuning uchun kech yig'ish uni o'zgartirmaydi; faqat saqlangan
  ko'rishlar soni kattaroq bo'ladi. 2026-09-28..2026-10-03 shu yo'l bilan yig'ilgan.
- Telegram sessiyasi yig'ishdan oldin tekshiriladi. Biror muammo bo'lsa, bot
  administratorga xabar yuboradi.

---

## 3. Tasniflash — OpenAI yoki Gemini (`llm_classifier.py`, `prompts.py`)

Har bir post bir marta belgilanadi (belgi versiyasi `v5`). 2–21-sentabr postlari `v4` bilan
belgilangan: ularda `central_bank` mavzusi yo'q, bunday postlar bank, inflyatsiya yoki kurs
mavzusida. Indeks to'liq ishga tushganda butun tarix bitta versiya bilan qayta quriladi.
Postlarni bitta model belgilaydi:
- `OPENAI_API_KEY` da OpenAI kaliti (`sk-...`) bo'lsa — OpenAI (`gpt-6-luna`, u ishlamasa
  `gpt-5-mini`). Javob qat'iy JSON sxema bo'yicha olinadi, OpenAI postlarni saqlamaydi
  (`store: false`).
- aks holda, yoki `LLM_PROVIDER=gemini` bo'lsa — Gemini.

Ikkalasi ham bir xil prompt va sxemani oladi. Prompt modelni indeks
belgilarni ishlatadigan tartibda yuritadi: reklama → dayjest → iqtisodiy → xorijiy →
mavzu → relevance → sentiment.

| Maydon | Ma'nosi |
|--------|---------|
| `is_ad` | mahsulot yoki brend reklamasi, advertorial ("biz", "мы"), kanal "Reklama" deb belgilagan post |
| `is_digest` | bitta postda bir-biriga bog'liq bo'lmagan bir nechta yangilik |
| `economic` | postning asosiy mavzusi iqtisodiy (qaysi mamlakat haqida bo'lishidan qat'i nazar) |
| `is_foreign` | voqea O'zbekistondan tashqarida va unda O'zbekiston tomoni yo'q |
| `topic` | 11 kategoriyadan biri yoki `non_economic` (pastda) |
| `sentiment` | O'zbekiston iqtisodiyoti, aholisi va biznesi uchun yaxshi yoki yomon yangilikmi (−1…+1) |
| `relevance` | iqtisod postda qanchalik markaziy (indeksda ishlatilmaydi, saqlanadi) |

Indeksdagi iqtisodiy post = reklama emas **va** `economic` **va** dayjest emas **va**
xorijiy emas.

**Mavzular:** narx va inflatsiya, valyuta kursi, byudjet va soliq, tashqi savdo,
makroiqtisodiyot, **Markaziy bank**, bank va moliya, mehnat va daromad, energetika,
biznes, qurilish. O'zbekiston Markaziy bankining qarori, bayonoti, prognozi yoki
qoidasi haqidagi post — inflyatsiya, kurs yoki banklar haqida bo'lsa ham — `central_bank`.
Kunlik rasmiy kurs xabari va Markaziy bank ma'lumotiga shunchaki tayangan yangilik o'z
mavzusida qoladi (`currency_fx`, `banking_finance`, ...). Mavzu indeks formulasiga
kirmaydi; u mavzular kesimi uchun ishlatiladi (`v5` belgilaridan boshlab).

**Ohang:** sentiment > +0.15 bo'lsa ijobiy, < −0.15 bo'lsa salbiy, qolgani neytral.

Sentiment qoidalari (indeksda faqat yo'nalish ishlatiladi):
- Ishora faqat **aniq iqtisodiy o'zgarishga** beriladi. Bu sodir bo'lgan voqea, o'lchangan
  natija yoki qabul qilingan chora bo'lishi mumkin. Aniq raqam bilan rasman taklif
  qilingan chora ham hisoblanadi ("yo'lkirani 2 500 so'mga oshirish taklif qilindi").
- Narx, tarif, inflyatsiya, soliq, boj, yig'im yoki jarima oshsa — salbiy, tushsa — ijobiy.
- YaIM, ishlab chiqarish, eksport, investitsiya, turistlar, ish o'rinlari, maosh yoki pensiya
  oshsa — ijobiy, kamaysa — salbiy.
- So'm mustahkamlansa (dollar kursi tushsa) — ijobiy, zaiflashsa — salbiy. Bu qoida
  Markaziy bankning kunlik kurs postlariga ham tegishli.
- Asosiy stavka pasaysa — ijobiy, oshsa — salbiy, o'zgarmasa — 0.
- Imtiyoz, subsidiya yoki soddalashtirish — ijobiy. Tanqislik, elektr o'chishi, taqiq,
  ishdan bo'shatish yoki bankrotlik — salbiy.
- Zavod, yo'l yoki xizmat haqiqatda ishga tushsa, moliyalash haqiqatda ajratilsa — ijobiy.
- Quyidagilar **0** oladi: uchrashuv, muzokara, tashrif, forum, ko'rgazma, memorandum va
  "X mlrd dollarlik kelishuvlar" (bular niyat), reja, strategiya, maqsad, prognoz,
  tayinlov, yubiley, mukofot va yo'nalishi aniq bo'lmagan statistika.
- Aralash yangilikda sarlavha va asosiy fakt hal qiladi. Inkor hisobga olinadi.

**Belgi boshqa postga tushmaydi:** model har bir javobni post raqami (`id`) bilan qaytaradi.
Raqamlar so'ralganiga mos kelmasa, javob rad etiladi va partiya ikkiga bo'linib qayta
yuboriladi. Har bir post modelga kanal nomi bilan birga yuboriladi.

**Reklama filtri:** kanal o'zi reklama deb belgilagan post (`(реклама)`,
`на правах рекламы`, `#реклама` yoki oxirgi so'z sifatidagi `Reklama`/`Реклама`)
model javobidan qat'i nazar reklama hisoblanadi.

**Zaxira klassifikator yo'q:**
- Model javob bermasa yoki kvota tugasa, post kutib turadi va keyingi run'da qayta
  yuboriladi.
- Vaqtinchalik xatolarda (HTTP 429, 5xx, timeout) tizim pauza qilib qayta urinadi.
- Ketma-ket uch partiya o'tmasa, run'ning belgilash bosqichi to'xtaydi.
- Run birorta ham postni belgilay olmasa va sabab kunlik kvota bo'lmasa, bot ogohlantiradi.
- Model bitta postni ikki xil run'da ham belgilay olmasa, u iqtisodiy emas deb saqlanadi
  (`label_model` oxirida `:unlabelled` belgisi qo'yiladi). Shunday qilib bitta post keyingi
  kunlarni to'xtatib qo'ymaydi.

Har bir belgi uni bergan modelni (`label_model`) va versiyasini (`label_version`) saqlaydi.

**Kvota va narx:**
- Gemini'ning eng yangi Flash modelida bepul limit kuniga taxminan 20 so'rov. Shuning
  uchun bitta so'rovda 50 ta post yuboriladi, bu kuniga ~1 000 post.
- OpenAI pullik, lekin kunlik limiti yo'q. `gpt-6-luna` narxi 1M token uchun $0.10
  (kirish) va $0.50 (chiqish). Kuniga ~150 post uchun xarajat oyiga taxminan bir dollar.
- Kunlik oqim ~150 post, ya'ni 3–4 so'rov.
- OpenAI'ga bir vaqtda 4 tagacha so'rov yuboriladi, bitta run'da 240 tagacha (6 000 post),
  shuning uchun to'liq qayta belgilash bitta tunda tugaydi.

**Nazorat to'plami:**
- `gold_set.py` da 26 ta haqiqiy post va ularning kutilgan natijasi saqlanadi: reklama,
  boshqa, iqtisodiy-ijobiy, neytral yoki salbiy.
- `check` workflow ularni ishlatilayotgan modelga yuboradi va nechtasi to'g'ri ekanini
  botga yozadi. 85% va undan ko'p to'g'ri bo'lsa, natija ✅.
- `eval` workflow kattaroq namunani (26 + 174 post) belgilaydi va natijani `eval/`
  papkasiga yozadi, shunda belgilarni qo'lda ko'rib chiqish mumkin. OpenAI'da `low` va
  `medium` reasoning rejimlari solishtiriladi.

---

## 4. Saqlash — ikki jadval, faqat qo'shish

| Fayl | Jadval | Mazmuni |
|------|--------|---------|
| `data/messages.csv` | **Xabarlar** | har bir post: matn, sana, ko'rishlar, forward'lar, model belgilari va indeks bayroqlari (`nonad`, `econ`, `tone`) |
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
