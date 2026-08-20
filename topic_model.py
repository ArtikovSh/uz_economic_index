import numpy as np
import pandas as pd
from gensim.models.ldamodel import LdaModel
from config import NUM_TOPICS, PASSES, TARGET_TOPICS

def fit_lda_and_score(df, dictionary, corpus):
    lda_model = LdaModel(
        corpus=corpus,
        id2word=dictionary,
        num_topics=NUM_TOPICS,
        random_state=42,
        passes=PASSES,
        alpha='auto'
    )
    
    # Calculate topic distributions
    topic_distributions = []
    for bow in corpus:
        doc_topics = dict(lda_model.get_document_topics(bow, minimum_probability=0.0))
        topic_distributions.append(doc_topics)
    
    topic_df = pd.DataFrame(topic_distributions).fillna(0.0)
    topic_df.columns = [f'topic_{i}_weight' for i in range(NUM_TOPICS)]
    
    # Combine with original DataFrame
    df = pd.concat([df, topic_df], axis=1)
    
    # Calculate target topic weights and engagement-weighted scores
    target_cols = [f'topic_{i}_weight' for i in TARGET_TOPICS]
    df['target_topic_weight'] = df[target_cols].sum(axis=1)
    df['engagement_score'] = np.log1p(df['views'] + (df['forwards'] * 2))
    df['weighted_index_score'] = df['target_topic_weight'] * df['engagement_score']
    
    # Aggregate to Daily Index
    df['date_only'] = pd.to_datetime(df['date']).dt.date
    daily_index = df.groupby('date_only').agg(
        total_messages=('message_id', 'count'),
        avg_target_topic_share=('target_topic_weight', 'mean'),
        composite_daily_index=('weighted_index_score', 'mean')
    ).reset_index()
    
    return lda_model, df, daily_index