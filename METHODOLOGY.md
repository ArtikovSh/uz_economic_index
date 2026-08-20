# Metodologiya — O'zbekiston Iqtisodiy Yangiliklar Indeksi

Ushbu hujjat indeks **qanday hisoblanishini**, har bir natijaning **asl ma'nosini**,
ishlatilgan **formulalarni**, ularning **ilmiy manbalarini**, **ishonchlilik** darajasini
va **cheklovlarni** to'liq bayon qiladi.

---

## 1. Maqsad va asosiy g'oya

Loyiha O'zbekistonning yirik yangilik kanallaridagi Telegram postlaridan
**ikki mustaqil iqtisodiy indeks** quradi:

| Indeks | Nomi | Nimani o'lchaydi | Diapazon |
|--------|------|------------------|----------|
| **EAI** | Economic **Attention** Index (iqtisodiy e'tibor) | Yangiliklar oqimining qancha qismi iqtisodga oid (e'tibor bilan tortilgan) | 0 … 1 |
| **ESI** | Economic **Sentiment** Index (iqtisodiy kayfiyat) | Iqtisodiy yangiliklarning ohangi ijobiymi yoki salbiymi | −1 … +1 |

Bu ikkisi **ataylab ajratilgan**, chunki ular har xil narsani o'lchaydi: EAI —
*qancha gapirilyapti* (hajm/diqqat), ESI — *qanday gapirilyapti* (yo'nalish/ohang).
Ularni bitta songa qo'shib yuborish ma'noni yo'qotadi.

> **Muhim tuzatish (eski versiyaga nisbatan):** avvalgi versiya indeksni to'g'ridan-to'g'ri
> LDA mavzularidan qurgan edi. Bu ishonchsiz: (a) LDA mavzulari nazoratsiz, har run'da
> qayta o'rgatilganda "Topic 0" boshqa narsani anglatardi — kunlar solishtirib bo'lmasdi;
> (b) mavzular til va shablon (obuna/havola/footer) bo'yicha ajralib, iqtisodni emas,
> boilerplate hajmini o'lchardi. Yangi versiya **shaffof leksikon** asosida ishlaydi
> (§4–5), LDA esa faqat yordamchi diagnostikaga tushirildi (§7).

---

## 2. Ma'lumot manbai

- **Kanallar:** `@gazetauz`, `@kunuzofficial`, `@daryo`, `@spotuz` (kengaytiriladi).
- **Har post uchun:** matn, sana-vaqt, ko'rishlar (views), ulashishlar (forwards).
- **O'suvchi arxiv (`data/messages.csv`):** har run yangi postlarni qo'shadi va
  `(kanal, message_id)` bo'yicha dublikatlarni olib tashlaydi. Shu tufayli indeks
  bir martalik suratга emas, **haqiqiy, solishtiriladigan vaqt qatoriga** aylanadi
  va eski kunlar asta-sekin to'ldiriladi.
- Til aralashmasi: rus + o'zbek (lotin) + o'zbek (kirill) — real korpusda aksariyat
  postlar rus tilida, shu sababli barcha leksikonlar **uch tilli**.

---

## 3. Matnni qayta ishlash (`text_utils.py`)

1. **Normallashtirish:** kichik harf, apostrof variantlarini birlashtirish
   (`ʻ ' ' → '`), URL/mention/emoji va **shablonlarni** olib tashlash
   (telegram/instagram/youtube footer'lari, "obuna bo'ling", "batafsil", "havola",
   "реклама", "подробнее" …). Bu qadam eng ko'p uchraydigan, ma'nosiz so'zlarni
   yo'q qiladi — aks holda ular signalni bosib ketadi.
2. **Leksikon mosligi** normallashtirilgan matnda, **asl yozuvda** (lotin va kirill)
   bajariladi — shuning uchun leksikonlar har uch tilda beriladi.
3. **Transliteratsiya (faqat LDA uchun):** o'zbek kirill → lotin, токенлар
   birlashishi uchun (`нарх`≡`narx`).

Morfologiya (o'zbek — agglutinativ til) uchun leksikon **o'zaklarni prefiks**
sifatida qidiradi: `narx` → `narxlar`, `narxi`, `narxlarning`ни ham topadi
(`\bstem`). Bu to'liq lemmatizatsiya emas, lekin arzon va samarali o'rnini bosadi.

---

## 4. Uchta o'lchov (har post uchun) — `indicator.py`

### 4.1. Iqtisodiy relevantlik (Relevance) R

Har postda **iqtisodiy leksikon** (`lexicons.py`) so'zlari sanaladi — `econ_hits`.
Leksikon 8 toifadan iborat: narx/inflatsiya, valyuta, byudjet/soliq, tashqi savdo,
makro, bank/moliya, mehnat/daromad, energiya/kommunal.

Relevantlik **to'yinuvchi (saturating)** funksiya bilan [0,1] ga keltiriladi:

```
R = 1 − exp( −econ_hits / TAU )          (TAU = 2)
```

- 1 ta so'z → 0.39, 2 → 0.63, 4 → 0.86, ko'p → 1 ga yaqin.
- **Nega bunday?** Chiziqli sanoq uzun postlarni sun'iy ravishda ustun qo'yadi.
  Konkav (to'yinuvchi) shakl: "postda iqtisod bor-yo'qligi" birinchi bir-ikki so'zda
  hal bo'ladi, keyingi takrorlar kam qo'shadi. Bu **diminishing returns** tamoyili.
- Post `econ_hits ≥ 1` bo'lsa **iqtisodiy** deb belgilanadi (`is_economic`).

**Manba:** kalit-so'z chastotasi orqali iqtisodiy diqqatni o'lchash — Baker, Bloom &
Davis (2016) **Economic Policy Uncertainty** indeksining asosiy usuli (gazeta
maqolalarida iqtisod+siyosat+noaniqlik so'zlarini sanash).

### 4.2. Sentiment (kayfiyat/ohang) s

Har postda **ijobiy** va **salbiy** iqtisodiy so'zlar sanaladi (`pos_hits`, `neg_hits`)
va qutblanish (polarity) hisoblanadi:

```
s = (pos_hits − neg_hits) / (pos_hits + neg_hits)        s ∈ [−1, +1]
```

Agar iqtisodiy ohang so'zlari topilmasa `s = 0` (neytral). Yo'nalish iqtisodiy
farovonlik nuqtai nazaridan: `arzonlashdi, o'sish, barqaror, stavka pasaydi,
подешевел` → ijobiy; `qimmatlashdi, inqiroz, defitsit, ishsizlik, подорожал` → salbiy.

- Real misol (tekshirilgan): "*stavka … opustilas' do 21,6%*" (kredit stavkasi pasaydi)
  → s = +1; "*povysili tarify na gaz*" (tarif oshdi) → salbiyroq. Yo'nalish to'g'ri.

**Manba:** lug'atga (dictionary) asoslangan sentiment — Loughran & McDonald (2011,
moliyaviy lug'at) va Tetlock (2007, "media pessimism") ishlarining klassik usuli;
ijtimoiy matnlarda Antweiler & Frank (2004).

### 4.3. E'tibor og'irligi (Engagement weight) w

```
engagement = ln( 1 + views + 2 × forwards )
w = engagement / (o'sha kanalning o'rtacha engagement'i)
```

- **Nega logarifm?** Ko'rishlar taqsimoti "og'ir dumli" (log-normal): ba'zi postlar
  100 000+, ko'pchiligi ~1 000. `ln` bu farqni siqadi, aks holda bitta viral post
  butun kunni egallardi. Log-transform ijtimoiy metrikalarda standart.
- **Nega forward × 2?** Ulashish — ko'rishdan **kuchliroq** e'tibor signali (odam
  faol harakat qiladi). 2 koeffitsiyenti — asosli, lekin sozlanadigan parametr.
- **Nega kanalga normallashtirish?** Kanallar auditoriyasi har xil. Bo'linish har
  kanalning o'rtachasini 1.0 ga keltiradi — katta kanal indeksni bosib ketmaydi.

**Manba:** viral/e'tibor metrikalarini log bilan siqish — Antweiler & Frank (2004)
va umuman internet-analitikadagi amaliyot.

---

## 5. Ikki kunlik indeks (agregatsiya)

Kun *d* dagi postlar to'plami uchun (`w` — e'tibor og'irligi, `R` — relevantlik,
`s` — sentiment):

### 5.1. Economic Attention Index

```
EAI_d = Σ (w_i · R_i) / Σ (w_i)            (barcha postlar bo'yicha)
```

**Ma'nosi:** o'sha kuni yangiliklar oqimining (e'tibor bilan tortilgan) qancha ulushi
iqtisodga oid edi. 0 — hech iqtisod yo'q; 1 — deyarli hammasi iqtisod. Bu — *diqqat/hajm*
o'lchovi.

### 5.2. Economic Sentiment Index

```
ESI_d = Σ (w_i · s_i) / Σ (w_i)            (faqat iqtisodiy postlar bo'yicha)
```

**Ma'nosi:** o'sha kuni iqtisodiy yangiliklarning e'tibor bilan tortilgan o'rtacha
ohangi. +1 — juda ijobiy (arzonlashuv, o'sish, barqarorlik); −1 — juda salbiy
(qimmatlashuv, inqiroz). Bu — *yo'nalish/kayfiyat* o'lchovi.

**Manba:** e'tibor bilan tortilgan kunlik sentiment agregatsiyasi — Shapiro, Sudhof &
Wilson (2020), **FRBSF Daily News Sentiment Index** metodologiyasi.

### 5.3. Normallashtirish (solishtirish uchun)

Xom EAI/ESI qiymatlariga qo'shimcha ustunlar beriladi:

```
z-ball:   x_z = (x_d − mean(x)) / std(x)         (o'rtachadan necha standart chetlanish)
EAI_100 = 100 × EAI_d / mean(EAI)                (o'rtacha kun = 100)
ESI_100 = 50 × (ESI_d + 1)                       ([−1,1] → [0,100], 50 = neytral)
```

- **z-ball** — indikatorlarni standartlashtirishning klassik usuli (masalan
  iste'molchilar ishonchi indekslari, PMi-ga o'xshash diffuziya indekslari).
- **base-100** — dashboard uchun qulay: "bugun o'rtacha kundan necha foiz baland/past".

> Ko'proq tarix to'planganda bazaviy davrni (masalan birinchi oy = 100) belgilash
> tavsiya etiladi — hozir baza sifatida **mavjud davr o'rtachasi** ishlatiladi.

---

## 6. Natijalarni qanday o'qish kerak (Daily Index varag'i)

| Ustun | Ma'nosi |
|-------|---------|
| `total_messages` | O'sha kungi postlar soni |
| `economic_messages` | Ulardan iqtisodiy deb topilganlari |
| `econ_share` | Iqtisodiy postlar oddiy ulushi (tortilmagan) |
| `EAI` / `EAI_100` / `EAI_z` | Iqtisodiy **e'tibor** (xom / o'rtacha=100 / z-ball) |
| `ESI` / `ESI_100` / `ESI_z` | Iqtisodiy **kayfiyat** (xom / neytral=50 / z-ball) |
| `avg_engagement` | O'sha kun o'rtacha e'tibor darajasi |

Misol o'qish: `EAI_100 = 150` → o'sha kun iqtisodga o'rtachadan **1.5 barobar** ko'proq
e'tibor qaratilgan. `ESI_100 = 65` → iqtisodiy yangiliklar **neytraldan ijobiyroq**
(masalan dollar tushdi, stavka pasaydi).

---

## 7. LDA mavzuli modeli — nega ikkilamchi

LDA (Blei, Ng & Jordan, 2003) faqat **"hozir yangiliklarda qanday mavzular bor"**ni
ko'rsatuvchi **diagnostika** sifatida qoldirildi (Topic Glossary varag'i + `u_mass`
koherentlik balli). U indeksni **hisoblamaydi**, chunki:

- qisqa yangilik matnlarida LDA beqaror;
- har run qayta o'rgatilsa mavzular ma'nosi siljiydi → vaqt bo'yicha solishtirib bo'lmaydi;
- til/shablon bo'yicha ajralib ketishga moyil.

**Ishlab chiqarish uchun yaxshilanish:** modelni bir marta katta tarixda o'rgatib,
diskка saqlab (`model.save()`), keyingi run'larda faqat **baholash** (`lda[bow]`) —
shunda mavzular ham barqaror bo'ladi.

---

## 8. Formulalar ishonchlimi? (Reliability)

**Ha, uslub jihatidan** — har bir formula tan olingan ilmiy adabiyotdagi
metodologiyaga asoslangan (§9). Bular markaziy banklar va akademik iqtisodchilar
matnli iqtisodiy indikatorlar qurishda ishlatadigan standart usullar:

- Kalit-so'z chastotasi orqali **diqqat/noaniqlik** o'lchash (EPU) — keng validatsiyalangan.
- **Lug'atga asoslangan sentiment** — shaffof, takrorlanuvchan, tekshiriladigan
  (qaysi so'z nega hisobga olinganini aniq ko'rsatish mumkin — `Economic Lexicon` varag'i).
- **Log-e'tibor** va **z-normallashtirish** — statistik jihatdan to'g'ri, standart.

**Lekin "ishonchli formula" ≠ "mutlaq haqiqat".** Aniqlik **leksikon sifatiga** va
**ma'lumot qamroviga** bog'liq. Shu sababli §10 (cheklovlar) va §11 (validatsiya) muhim:
indeks **real iqtisodiy ko'rsatkichlarga** (rasmiy inflatsiya, USD/UZS kursi) solishtirib
tekshirilmaguncha, u **signal-indikator** (proksi) hisoblanadi, rasmiy statistika emas.

---

## 9. Ilmiy manbalar (formulalar qayerdan)

1. **Baker, S., Bloom, N., Davis, S. (2016).** *Measuring Economic Policy Uncertainty.*
   Quarterly Journal of Economics. — kalit-so'z chastotasi orqali iqtisodiy diqqat (EAI asosi).
2. **Shapiro, A., Sudhof, M., Wilson, D. (2020/2022).** *Measuring News Sentiment.*
   Journal of Econometrics / FRBSF Daily News Sentiment Index. — e'tibor bilan tortilgan
   kunlik sentiment (ESI asosi).
3. **Loughran, T., McDonald, B. (2011).** *When is a Liability not a Liability? Textual
   Analysis, Dictionaries, and 10-Ks.* Journal of Finance. — moliyaviy lug'at-sentiment.
4. **Tetlock, P. (2007).** *Giving Content to Investor Sentiment.* Journal of Finance. —
   media ohangi va iqtisodiy o'zgaruvchilar aloqasi.
5. **Antweiler, W., Frank, M. (2004).** *Is All That Talk Just Noise?* Journal of Finance. —
   ijtimoiy matn sentiment + hajm/e'tibor.
6. **Blei, D., Ng, A., Jordan, M. (2003).** *Latent Dirichlet Allocation.* JMLR. — LDA.
7. **Röder, M., Both, A., Hinneburg, A. (2015).** *Exploring the Space of Topic Coherence
   Measures.* WSDM. — koherentlik balli.

---

## 10. Cheklovlar va xatolik manbalari (halol ro'yxat)

1. **Aspekt noaniqligi:** "o'sish/рост" — iqtisod o'sishi (ijobiy) yoki narx o'sishi
   (salbiy) bo'lishi mumkin. So'z darajasidagi sentiment buni to'liq ajrata olmaydi;
   leksikon aniq iboralar (`qimmatlash`, `подорожал`, `arzonlash`, `подешевел`) bilan
   yumshatilgan, lekin xato qoladi.
2. **Reklama postlari:** bank/moliya reklamalari iqtisodiy so'zlar saqlaydi va relevantlikni
   sun'iy oshiradi. Shablon-filtri "реклама/reklama"ni belgilaydi, lekin barchasini emas.
3. **Geosiyosiy "iqtisod":** "iqtisodiy operatsiya/sanksiya" (tashqi siyosat) `iqtisod`
   so'zi orqali noto'g'ri belgilanishi mumkin.
4. **Leksikon qamrovi:** qo'lda tuzilgan ro'yxat — yangi atamalarни (masalan yangi soliq
   turi) qamramasligi mumkin. Ro'yxat oson kengaytiriladi.
5. **Ko'rish yetilishi (view maturation):** yangi postlar hali ko'rish to'plamagan →
   e'tibor og'irligi past baholanadi. (Yaxshilanish: 24 soatdan yosh postlarni chiqarish
   yoki yoshga normallashtirish.)
6. **Kanal tanlovi:** faqat 4 umumiy kanal — iqtisodiy kanallar (@cbu_uz, @stat_uz)
   qo'shilsa signal kuchayadi.
7. **Sabab-oqibat emas:** indeks yangiliklardagi *aks-sadoni* o'lchaydi, iqtisodiy
   *voqelikni* emas. U kutish/kayfiyat proksisi.

---

## 11. Validatsiya rejasi (keyingi qadam)

Indeksni **rasmiy ko'rsatkichlar** bilan solishtirish:

- **ESI ↔ oylik inflatsiya (CPI)** va **USD/UZS kursi o'zgarishi** (Markaziy bank ma'lumoti);
- **EAI ↔ yirik iqtisodiy e'lonlar** kunlari (byudjet, stavka qarori) — diqqat cho'qqilari.
- Korrelyatsiya va lag-tahlil (indeks voqeadan oldin/keyin harakatlanadimi).
  Mos kelsa — indeks haqiqiy prognostik qiymatga ega degani.

---

## 12. Yaxshilanish yo'l xaritasi

- **P1:** raqam/foizni saqlash ("inflatsiya 12%"), lemmatizatsiya, bigramlar (Phrases),
  ko'rish-yetilishi tuzatmasi, iqtisodiy kanallar qo'shish.
- **P2:** transformer asosidagi ko'p tilli sentiment (aspekt darajasida), muzlatilgan LDA,
  Streamlit/Plotly dashboard, real ko'rsatkichlarga backtest.
- **P3:** kunlik indeksni Markaziy bank tahlil platformasiga (tashqi-savdo) integratsiya.

---

*Xulosa:* quvur endi **shaffof, barqaror va ilmiy asosli**. Har bir son —
tekshiriladigan formuladan (§4–5), har bir formula — tan olingan manbadan (§9).
Keyingi bosqich — leksikonni boyitish va real ko'rsatkichlarga validatsiya (§11).
