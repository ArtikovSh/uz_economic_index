"""
Trilingual economic lexicons as PRECISE regex patterns (uz-Latin, uz-Cyrillic, ru).

Why patterns, not bare stems
----------------------------
The earlier version matched bare stems as `\\bstem`, which collided badly:
`цен`→центр/центральный (center), `yevro`→Yevropa (Europe), `elektr`→elektron,
`baho`→baholash (assess), `dollar`→"$" as a unit. A corpus audit showed the single
largest category was ~44% collision garbage and ~7% of "economic" posts were false
positives that also inflated the EAI index. Here every entry is a bounded regex
(negative look-aheads, word boundaries, context requirements) audited against the
real surface forms. See METHODOLOGY.md §7 and the workflow audit.

Structure
---------
ECONOMIC_TERMS : {category: [regex, ...]}  — 10 economic categories.
CAT_RE / ECON_RE : compiled per-category and combined.
Flag detectors (run on normalize_light text, which keeps 'реклама'/'aksiya'):
  AD_RE, DIGEST_RE, FOREIGN_RE, UZ_ENTITY_RE.
STOPWORDS : for the exploratory LDA only.
"""
import re
from collections import Counter

# ============================================================ ECONOMIC ========
# Each list holds bounded regexes. Priority order (tie-break) defined below.
ECONOMIC_TERMS = {
    "prices_inflation": [
        r"\bnarx", r"\bнарх", r"инфляц", r"inflats", r"qimmatchilik", r"қиммат",
        r"подорожан", r"подешеван", r"подорожал", r"подешевел", r"қимматлаш",
        r"\bцен(?=а|ы|е|у|ой|ам|ах|н|ово)",       # цена/цены/ценовой… NOT центр
        r"стоимост", r"\btarif", r"тариф", r"qimmat", r"arzonlash",
    ],
    "currency_fx": [
        r"валют", r"valyuta", r"девальвац", r"devalvatsiya", r"деноминац",
        r"курс\s+(доллар|евро|валют|рубл|сум)",   # exchange RATE, not $-as-unit
        r"\bkurs(i|ida|ining|lari)?\b", r"\bевро\b", r"\byevro\b",
        r"(доллар|dollar)\w*\s+(вырос|снизил|подорожал|подешевел|укрепил|ослаб|tushdi|ko'taril|pasay)",
    ],
    "fiscal": [
        r"бюджет", r"byudjet", r"бюджет", r"\bналог", r"\bsoliq", r"солиқ",
        r"таможн", r"bojxona", r"божхона", r"субсид", r"subsidiya",
        r"\bдефицит", r"defitsit", r"госдолг", r"\bрасход", r"xarajat", r"харажат",
        r"\bштраф", r"\bjarima", r"\bжарима", r"акциз",
    ],
    "trade": [
        r"экспорт", r"eksport", r"импорт", r"\bimport", r"внешнеторгов",
        r"tashqi savdo", r"ташқи савдо", r"торговл", r"\bsavdo", r"\bсавдо",
        r"товарооборот", r"\bтовар(?=ов|ы|а|ные|ного|ам|у)",
    ],
    "macro": [
        r"\bввп\b", r"\byaim\b", r"\bgdp\b", r"макроэконом", r"iqtisodiyot",
        r"иқтисодиёт", r"iqtisodiy o'sish", r"рецесси", r"retsessiya",
        r"промышленн", r"производств", r"ishlab chiqar", r"ишлаб чиқар",
        r"iste'mol", r"истеъмол",
    ],
    "banking_finance": [
        r"\bбанк", r"\bbank", r"кредит", r"kredit", r"кредитн", r"ипотек",
        r"ipoteka", r"депозит", r"depozit", r"инвестиц", r"investits", r"sarmoya",
        r"сармоя", r"облигаци", r"obligatsiya", r"\bбиржа", r"фондов",
        r"ставк[аиуе]", r"процентн", r"\bqarz", r"\bқарз", r"микрозайм",
    ],
    "labour_income": [
        r"зарплат", r"ish haqi", r"иш ҳақи", r"\bmaosh", r"\bмаош", r"\boylik",
        r"\bойлик", r"безработиц", r"ishsiz", r"ишсиз", r"занятост", r"bandlik",
        r"\bпенси", r"pensiya", r"пенсия", r"нафақа", r"nafaqa", r"\bдоход(?!ит|ят)",
        r"daromad", r"даромад",
    ],
    "energy_utility": [
        r"бензин", r"benzin", r"yoqilg'i", r"ёқилғи", r"\bтоплив",
        r"\bгаз(?=а|у|ом|оснабж|опровод|ифи|\b)", r"\bgaz\b", r"\bгаз\b",
        r"электроэнерг", r"\belektr(?!on|osh)", r"электр(?=о|и|ост)", r"коммунал",
        r"kommunal", r"нефт", r"\bneft", r"нефтегаз",
    ],
    "business": [
        r"тадбиркор", r"tadbirkor", r"предпринимател", r"\bбизнес", r"\bbiznes",
        r"kichik biznes", r"малый бизнес", r"\bмсб\b", r"реестр\s+операторов",
        r"мораторий\s+на\s+проверк", r"litsenziya", r"лицензи",
    ],
    "construction_realty": [
        r"qurilish", r"қурилиш", r"строительств", r"недвижимост", r"ko'chmas mulk",
        r"кўчмас мулк", r"\bжиль[её]", r"uy-joy", r"уй-жой", r"новостро",
        r"застройщик",
    ],
}

# Tie-break priority (more specific / narrower first, macro last)
PRIORITY = [
    "currency_fx", "prices_inflation", "banking_finance", "fiscal", "trade",
    "energy_utility", "labour_income", "construction_realty", "business", "macro",
]

# ================================================================ FLAGS ========
# Run on normalize_light() text (boilerplate kept).
AD_RE = re.compile(
    r"\bреклама\b|\breklama\b|\(reklama\)|\bаксия\b|\baksiya\w*|промокод|промо-?акци|"
    r"скидк\w+|chegirma|sotuvda|sotiladi|аренда\b|arzon narx|скидки до|"
    r"salom\s+maktab|байрам\s+акци", re.IGNORECASE)

DIGEST_RE = re.compile(r"дайджест|dayjest|yangiliklar\s+dayjest|янгиликлар\s+дайжест|"
                       r"кун\w*\s+asosiy\s+yangilik|главное\s+за\s+день", re.IGNORECASE)

# Foreign-country / -leader markers (a post is foreign only if NO UZ entity present)
FOREIGN_RE = re.compile(
    r"\bсша\b|\baqsh\b|\bu\.?s\.?a\b|россия\b|россии\b|российск|rossiya|украин|ukraina|"
    r"\bкитай|xitoy|xitoyn|турци|turkiya|\bиран\b|\beron\b|израил|isroil|"
    r"казахстан|qozog'iston|европ|yevropa|евросоюз|\bкорея|япони|германи|"
    r"трамп|\btrump|путин|байден|zelensk|\bгаза\b|сектор\s+газа", re.IGNORECASE)

UZ_ENTITY_RE = re.compile(
    r"узбекистан|o'zbekiston|ozbekiston|ўзбекистон|\bсум\b|\bсўм|so'm\b|"
    r"ташкент|toshkent|тошкент|самарканд|samarqand|бухар|buxoro|андижан|andijon|"
    r"фергана|farg'ona|наманган|namangan|кашкадарь|qashqadaryo|сурхандарь|surxondaryo|"
    r"джизак|jizzax|сырдарь|sirdaryo|навои|navoiy|хорезм|xorazm|каракалпак|qoraqalpog|"
    r"марказий\s+банк|центробанк|\bцб\b|мирзиёев|mirziyoyev|минэконом|макроиқтисод",
    re.IGNORECASE)

# ============================================================= STOPWORDS =======
STOPWORDS = set("""
va ham uchun bilan da ga dan bu o shuningdek yoki hamda esa emas edi ekan
bir bo'ldi bo'lgan bo'lib kerak lekin ammo yana faqat qildi qilish bo'yicha
yangi kuni kun yil oy soat mln mlrd ming yicha zbekistonda zbekiston mumkin
и в на с по для что это как из а но же то за от до об или бы был были быть
также при после уже еще есть нет тот эта эти год года лет день дней сум сумов
млн млрд тыс который которые между более менее очень так этот того чтобы
""".split())
STOPWORDS |= set("""
chto dlya takje pri posle budet budut goda god ego kak bolee chem eto bil bili
mejdu kotoriy kotorie vse uje esche net tot eta eti tom toy svoi nash ves pod
nad bez ili bi je li iz za ob dvuh treh raz kogda tolko tak etot etogo etu ona
uzbekistan uzbekistana uzbekistane ozbekiston ozbekistonda sum suma sumov mln
mlrd tis avgust avgusta rossiya rossii oblasti kanali rasmiy bolgan boldi bor
strani stranah goroda dnya chego komu byla svoih etom togo krome odnako ranee
pochti biznesa tashkente godu chelovek cherez mojno ego dlya
""".split())

# ============================================================ COMPILED =========
CAT_RE = {c: [re.compile(p, re.IGNORECASE | re.UNICODE) for p in pats]
          for c, pats in ECONOMIC_TERMS.items()}
_ALL = [re.compile(p, re.IGNORECASE | re.UNICODE)
        for pats in ECONOMIC_TERMS.values() for p in pats]


def econ_hits(norm_text: str) -> int:
    return sum(len(r.findall(norm_text)) for r in _ALL)


def category_hits(norm_text: str) -> Counter:
    """Per-category hit counts on normalize_text() output."""
    c = Counter()
    for cat, rgxs in CAT_RE.items():
        n = sum(len(r.findall(norm_text)) for r in rgxs)
        if n:
            c[cat] = n
    return c
