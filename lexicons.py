"""
Trilingual economic + sentiment lexicons (Uzbek-Latin, Uzbek-Cyrillic, Russian).

Design
------
The corpus mixes three scripts/languages, so every concept is listed in all of
them. Entries are word STEMS matched at a word boundary as a prefix
(`\\bstem`), which is a cheap stand-in for lemmatisation in an agglutinative
language: the stem "narx" also catches "narxlar", "narxlarning", "narxi".

Three families:
  * ECONOMIC   – concrete domestic-economy concepts (prices, FX, fiscal, trade,
                 macro, banking, labour, energy). Used for the RELEVANCE score.
  * POSITIVE   – wording that is good for the economy / households.
  * NEGATIVE   – wording that is bad for the economy / households.

The lexicons are deliberately transparent and easy to extend – add a stem to a
list and it takes effect immediately. See METHODOLOGY.md for the rationale and
known limitations (ads, geopolitical "economic", aspect ambiguity of "growth").
"""
import re

# ---------------------------------------------------------------- ECONOMIC ----
ECONOMIC_TERMS = {
    "prices_inflation": [
        "narx", "baho", "inflatsiya", "qimmatchilik", "arzon", "qimmat", "tarif",
        "цен", "инфляц", "подорожан", "подешеван", "тариф", "стоимост", "дорожа",
    ],
    "currency_fx": [
        # NB: bare "so'm"/"сум" deliberately excluded — it appears in almost any
        # price/fine post and floods relevance with noise. FX relevance comes
        # from unambiguous terms instead.
        "valyuta", "kurs", "dollar", "yevro", "devalvatsiya",
        "валют", "курс", "доллар", "евро", "девальвац",
    ],
    "fiscal": [
        "byudjet", "soliq", "bojxona", "subsidiya", "xarajat", "defitsit",
        "бюджет", "налог", "таможн", "субсиди", "расход", "дефицит", "госдолг",
    ],
    "trade": [
        "eksport", "import", "savdo", "tovar", "tashqi savdo",
        "экспорт", "импорт", "торговл", "товарооборот", "внешнеторгов",
    ],
    "macro": [
        "iqtisod", "yaim", "yalpi ichki", "ishlab chiqar", "iste'mol", "retsessiya",
        "inqiroz", "o'sish sur", "sanoat", "qishloq xo'jal",
        "экономик", "ввп", "производств", "потреблени", "рецесси", "промышленн",
        "макроэконом",
    ],
    "banking_finance": [
        "bank", "kredit", "ipoteka", "depozit", "qarz", "investitsiya", "sarmoya",
        "aksiya", "birja", "foiz stavka", "stavka",
        "банк", "кредит", "ипотек", "депозит", "инвестиц", "акци", "биржа", "ставк",
    ],
    "labour_income": [
        "ish o'rni", "ish haqi", "maosh", "oylik", "ishsiz", "bandlik", "pensiya",
        "nafaqa", "daromad",
        "зарплат", "безработиц", "занятост", "пенси", "пособи", "доход", "оклад",
    ],
    "energy_utility": [
        "benzin", "yoqilg'i", "gaz", "elektr", "kommunal",
        "бензин", "топлив", "электроэнерг", "коммунальн", "газоснабж",
    ],
}

# ----------------------------------------------------------------- SENTIMENT ---
POSITIVE_TERMS = [
    # uz
    "o'sdi", "o'sish", "ko'paydi", "arzonlash", "arzonlashdi", "yaxshilan",
    "rivojlan", "barqaror", "mustahkamlan", "rekord", "foyda", "tiklan",
    "jonlan", "imtiyoz", "qo'llab-quvvat", "o'sti", "oshirildi maosh",
    # ru
    "рост", "вырос", "увеличил", "подешевел", "улучш", "развит", "стабильн",
    "укреплен", "рекорд", "прибыл", "восстанов", "приток", "льгот", "рекордн",
]
NEGATIVE_TERMS = [
    # uz
    "qimmatlash", "qimmatlashdi", "qimmatchilik", "pasaydi", "tushib ketdi",
    "inqiroz", "tanqislik", "defitsit", "ishsizlik", "devalvatsiya", "jarima",
    "zarar", "kamaydi", "taqchil", "qarz oshdi", "narx oshdi", "baholar oshdi",
    # ru
    "подорожал", "подорожан", "дорожает", "кризис", "дефицит", "безработиц",
    "обвал", "паден", "девальваци", "убыток", "дефолт", "спад", "сокращени",
    "подорожа", "штраф",
]

# ------------------------------------------------------------------ STOPWORDS --
# Expanded trilingual stopword + boilerplate set for the LDA topic model.
STOPWORDS = set("""
va ham uchun bilan da ga dan bu o shuningdek yoki hamda esa emas edi ekan
bir bo'ldi bo'lgan bo'lib kerak lekin ammo yana faqat qildi qilish bo'yicha
yangi kuni kun yil oy soat mln mlrd ming yicha zbekistonda zbekiston mumkin
и в на с по для что это как из а но же то за от до об или бы был были быть
также при после уже еще есть нет тот эта эти год года лет день дней сум сумов
млн млрд тыс который которые между более менее очень так этот того чтобы
""".split())

# Transliterated Russian function words + frequent place/boilerplate leaks that
# survive into the (latinised) LDA tokens. Diagnostic-quality only.
STOPWORDS |= set("""
chto dlya takje pri posle budet budut goda god ego kak bolee chem eto bil bili
mejdu kotoriy kotorie vse uje esche net tot eta eti tom toy svoi nash ves pod
nad bez ili bi je li iz za ob dvuh treh raz kogda tolko tak etot etogo etu ona
uzbekistan uzbekistana uzbekistane ozbekiston ozbekistonda sum suma sumov mln
mlrd tis avgust avgusta rossiya rossii oblasti kanali rasmiy bolgan boldi bor
strani stranah goroda dnya chego komu byla svoih
""".split())

# ---------------------------------------------------------------- compiled -----
def _compile(terms):
    # word-boundary prefix match; escape stems, allow trailing word chars
    parts = [r"\b" + re.escape(t.strip()) for t in terms if t.strip()]
    return re.compile("|".join(parts), re.IGNORECASE | re.UNICODE)

_ALL_ECON = [t for terms in ECONOMIC_TERMS.values() for t in terms]
ECON_RE = _compile(_ALL_ECON)
POS_RE = _compile(POSITIVE_TERMS)
NEG_RE = _compile(NEGATIVE_TERMS)


def econ_hits(norm_text: str) -> int:
    return len(ECON_RE.findall(norm_text))


def pos_hits(norm_text: str) -> int:
    return len(POS_RE.findall(norm_text))


def neg_hits(norm_text: str) -> int:
    return len(NEG_RE.findall(norm_text))
