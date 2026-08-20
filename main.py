import asyncio
from scraper import run_scraper
from preprocessor import process_corpus
from topic_model import fit_lda_and_score
from excel_exporter import export_results

def main():
    print("--- STEP 1: Scraping Telegram Data ---")
    df_raw = asyncio.run(run_scraper(limit_per_channel=300))
    
    print("--- STEP 2: Preprocessing Text ---")
    dictionary, corpus, df_processed = process_corpus(df_raw)
    
    print("--- STEP 3: Fitting LDA & Computing Index ---")
    lda_model, df_scored, daily_index = fit_lda_and_score(df_processed, dictionary, corpus)
    
    print("--- STEP 4: Exporting Excel Output ---")
    export_results(df_scored, daily_index, lda_model)
    print("Pipeline Execution Finished!")

if __name__ == '__main__':
    main()