import os
import pandas as pd
from datetime import datetime
from config import OUTPUT_DIR

def export_results(df, daily_index, lda_model):
    filename = f"economic_index_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        # Sheet 1: Daily Index Time Series
        daily_index.to_excel(writer, sheet_name='Daily Index', index=False)
        
        # Sheet 2: Raw Data & Topic Probabilities
        export_df = df.drop(columns=['tokens'])
        export_df.to_excel(writer, sheet_name='Scraped Data & Topics', index=False)
        
        # Sheet 3: Topic Glossary
        topic_words = []
        for i in range(lda_model.num_topics):
            terms = lda_model.show_topic(i, topn=10)
            words = ", ".join([term for term, _ in terms])
            topic_words.append({'Topic_ID': f'Topic {i}', 'Top_Keywords': words})
            
        pd.DataFrame(topic_words).to_excel(writer, sheet_name='Topic Glossary', index=False)
        
    print(f"Excel report generated: {filepath}")
