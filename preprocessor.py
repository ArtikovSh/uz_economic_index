import re
import gensim
from gensim.utils import simple_preprocess
from config import STOPWORDS

def clean_text(text):
    text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)
    text = re.sub(r'@\w+', '', text)
    text = re.sub(r'\d+', '', text)
    tokens = simple_preprocess(text, deacc=True)
    return [w for w in tokens if w not in STOPWORDS and len(w) > 2]

def process_corpus(df):
    df['tokens'] = df['raw_text'].apply(clean_text)
    dictionary = gensim.corpora.Dictionary(df['tokens'])
    dictionary.filter_extremes(no_below=3, no_above=0.5)
    corpus = [dictionary.doc2bow(text) for text in df['tokens']]
    return dictionary, corpus, df