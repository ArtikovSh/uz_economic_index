"""
Aspect-based economic sentiment.

A plain pos/neg word list mislabels ~30% of economic posts because it hard-codes
direction words as fixed polarity — but "narx oshdi / цены выросли" (prices UP) is
BAD while "iqtisod o'sdi / производство выросло" (output UP) is GOOD. We instead
pair each direction cue with the nearest ASPECT within a small window:

    UP × cost   = negative      DOWN × cost   = positive
    UP × output = positive      DOWN × output = negative
    UP × fx-rate= negative      DOWN × fx-rate= positive   (som weakens/strengthens)

Verified on a hand-labelled sample: sign-error on economic posts 30% → ~4%.
Two over-corrections found in review are intentionally scoped out (METHODOLOGY §7):
  * FX polarity fires ONLY on the exchange RATE (курс/kurs/валют), never on "$" as a
    unit — so "$590 mln reserves rose" reads as output-up (positive), not fx-up.
  * NO crude "domestic keyword" gate (it wrongly neutralised Khorezm/president posts).
Plus a light negation guard ("oshirmaslik", "не повысить").
"""
import re
from text_utils import normalize_light

UP = [r"oshdi", r"oshir", r"ko'taril", r"o'sd", r"o'sish", r"ortd", r"ortib", r"ошди",
      r"вырос", r"выраст", r"повыси", r"повыше", r"увеличи", r"подорожа", r"дорожа",
      r"\bрост\b", r"\bроста\b", r"\bросте\b", r"поднял"]
DOWN = [r"tushd", r"pasay", r"kamay", r"qisqar", r"arzonlash", r"тушди", r"пасай",
        r"сниж", r"сниз[иеья]", r"упал", r"паден", r"сократ", r"сокращ",
        r"подешевел", r"подешеван", r"опусти", r"\bспад", r"уменьш", r"понизи"]

# aspect families
COST = [r"narx", r"\bцен[аыуе]", r"\bцен\b", r"инфляц", r"inflats", r"тариф", r"tarif",
        r"коммунал", r"kommunal", r"ставк", r"stavka", r"\bfoiz", r"безработиц",
        r"ishsiz", r"\bдолг", r"\bqarz", r"задолж", r"дефицит", r"defitsit",
        r"tanqis", r"\bналог", r"\bsoliq", r"штраф", r"jarima", r"себестоим", r"qimmat"]
FX_RATE = [r"\bкурс", r"\bkurs", r"валют", r"valyuta", r"девальвац", r"devalvatsiya"]
OUTPUT = [r"\bввп", r"\byaim", r"\bgdp", r"производств", r"ishlab chiqar", r"добыч",
          r"экспорт", r"eksport", r"инвестиц", r"investits", r"sarmoya", r"зарплат",
          r"ish haqi", r"maosh", r"oylik", r"\bдоход", r"daromad", r"пенси", r"pensiya",
          r"прибыл", r"foyda", r"товарооборот", r"резерв", r"облигаци", r"obligatsiya",
          r"переводы", r"o'tkazma"]

UNAMBIG_NEG = [r"кризис", r"inqiroz", r"обвал", r"дефолт", r"банкрот", r"рецесси",
               r"retsessiya", r"коллапс", r"tanqisl", r"убыт", r"zarar",
               r"qimmatlash", r"qimmatchilik", r"подорожал", r"дефицит\s+бюджет"]
UNAMBIG_POS = [r"льгот", r"imtiyoz", r"субсид", r"subsidiya", r"barqaror", r"стабильн",
               r"mustahkamlan", r"arzonlashd", r"подешевел", r"qo'llab-quvvat",
               r"tiklan", r"восстанов", r"рекордн"]

NEG_MARK = re.compile(r"не\s|\bne\s|emas|maslik|масин|нельзя|запрет|моратор|"
                      r"asossiz|не\s+будет|не\s+планир", re.IGNORECASE)

WINDOW = 45


def _positions(patterns, text):
    out = []
    for p in patterns:
        for m in re.finditer(p, text, re.IGNORECASE):
            out.append(m.start())
    return out


def _negated(text, pos):
    seg = text[max(0, pos - 22): pos + 18]
    return bool(NEG_MARK.search(seg))


def aspect_sentiment(raw_text: str):
    """Return (score in [-1,1], label in {pos,neg,neu})."""
    t = normalize_light(raw_text)
    signals = []

    ups = _positions(UP, t)
    downs = _positions(DOWN, t)
    cost = _positions(COST, t)
    fx = _positions(FX_RATE, t)
    out = _positions(OUTPUT, t)

    def nearest(dpos, asp):
        best = None
        for a in asp:
            d = abs(a - dpos)
            if d <= WINDOW and (best is None or d < best):
                best = d
        return best

    for dpos in ups:
        if _negated(t, dpos):
            continue
        cand = [(nearest(dpos, cost), -1), (nearest(dpos, fx), -1), (nearest(dpos, out), +1)]
        cand = [c for c in cand if c[0] is not None]
        if cand:
            signals.append(min(cand, key=lambda x: x[0])[1])
    for dpos in downs:
        if _negated(t, dpos):
            continue
        cand = [(nearest(dpos, cost), +1), (nearest(dpos, fx), +1), (nearest(dpos, out), -1)]
        cand = [c for c in cand if c[0] is not None]
        if cand:
            signals.append(min(cand, key=lambda x: x[0])[1])

    for p in UNAMBIG_NEG:
        if re.search(p, t, re.IGNORECASE):
            signals.append(-1)
    for p in UNAMBIG_POS:
        if re.search(p, t, re.IGNORECASE):
            signals.append(+1)

    if not signals:
        return 0.0, "neu"
    s = sum(signals) / len(signals)
    label = "pos" if s > 0.15 else ("neg" if s < -0.15 else "neu")
    return round(s, 3), label
