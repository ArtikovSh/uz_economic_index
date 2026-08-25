"""
Per-message classification: assign each post a primary economic topic (one of the
10 categories, or 'non_economic') plus ad / digest / foreign flags.

This replaces the unstable LDA "topics" as the sortable/groupable per-message label.
Fully transparent: the category with the most (cleaned) lexicon hits wins, ties
broken by a fixed PRIORITY, and you can print exactly which stems drove each label.
"""
from lexicons import category_hits, PRIORITY, AD_RE, DIGEST_RE, FOREIGN_RE, UZ_ENTITY_RE
from text_utils import normalize_text, normalize_light

# a post needs at least this many economic hits to get a topic (precision > recall)
MIN_HITS_FOR_TOPIC = 2


def classify(raw_text: str) -> dict:
    norm = normalize_text(raw_text)      # boilerplate stripped, for lexicon match
    light = normalize_light(raw_text)    # boilerplate kept, for flag detection

    scores = category_hits(norm)
    total = sum(scores.values())

    is_ad = bool(AD_RE.search(light))
    is_digest = bool(DIGEST_RE.search(light))
    is_foreign = bool(FOREIGN_RE.search(light)) and not bool(UZ_ENTITY_RE.search(light))

    if total < MIN_HITS_FOR_TOPIC or not scores:
        primary = "non_economic"
    else:
        top = max(scores.values())
        cands = [c for c, v in scores.items() if v == top]
        primary = sorted(cands, key=lambda c: PRIORITY.index(c))[0]

    # secondary = other categories that also fired (for context)
    secondary = [c for c, _ in scores.most_common() if c != primary and c in scores]

    return {
        "primary_topic": primary,
        "secondary_topics": ";".join(secondary),
        "category_scores": dict(scores),
        "econ_hits": total,
        "is_ad": int(is_ad),
        "is_digest": int(is_digest),
        "is_foreign": int(is_foreign),
    }
