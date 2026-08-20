"""
Secondary LDA topic model — EXPLORATORY / DIAGNOSTIC ONLY.

It is NOT used to compute the index (the lexicon-based EAI/ESI in indicator.py
is the headline signal, because LDA topics are unstable on short news posts and
not comparable across retrainings). LDA here only surfaces "what themes are in
the news right now" as human-readable context, plus a coherence score so you
can judge topic quality. See METHODOLOGY.md.
"""
from gensim import corpora
from gensim.models.ldamodel import LdaModel
from gensim.models.coherencemodel import CoherenceModel

from text_utils import to_latin_tokens
from lexicons import STOPWORDS
from config import NUM_TOPICS, PASSES, LDA_NO_BELOW, LDA_NO_ABOVE


def run_topic_model(df):
    texts = [to_latin_tokens(t, STOPWORDS) for t in df["raw_text"].fillna("")]
    dictionary = corpora.Dictionary(texts)
    dictionary.filter_extremes(no_below=LDA_NO_BELOW, no_above=LDA_NO_ABOVE)
    corpus = [dictionary.doc2bow(t) for t in texts]

    if len(dictionary) < NUM_TOPICS or sum(1 for c in corpus if c) < NUM_TOPICS:
        print("Topic model: not enough data, skipped.")
        return [], None

    lda = LdaModel(corpus=corpus, id2word=dictionary, num_topics=NUM_TOPICS,
                   random_state=42, passes=PASSES, alpha="auto")

    topics = [
        {"Topic_ID": f"Topic {i}",
         "Top_Keywords": ", ".join(w for w, _ in lda.show_topic(i, topn=10))}
        for i in range(lda.num_topics)
    ]

    coherence = None
    try:
        # u_mass is corpus-based and fast (c_v's sliding window is too slow for CI)
        cm = CoherenceModel(model=lda, corpus=corpus, dictionary=dictionary, coherence="u_mass")
        coherence = round(cm.get_coherence(), 4)
    except Exception as e:
        print(f"Coherence skipped: {e}")

    print(f"Topic model: {NUM_TOPICS} topics, coherence(u_mass)={coherence}")
    return topics, coherence
