import asyncio

from scraper import run_scraper
from store import merge_master, save_daily
from indicator import score_messages, build_daily_index
from topic_model import run_topic_model
from excel_exporter import export_results
from config import (MESSAGES_PER_CHANNEL, LLM_PROVIDER, USE_LLM, OPENAI_API_KEY,
                    OPENAI_MODEL, GEMINI_API_KEY)


def _llm_status():
    if not USE_LLM:
        return "classifier: RULE-BASED (no LLM provider — set OPENAI_API_KEY for GPT)"
    if LLM_PROVIDER == "openai":
        key = "set" if OPENAI_API_KEY else "MISSING"
        return f"classifier: LLM openai model={OPENAI_MODEL} (OPENAI_API_KEY={key})"
    if LLM_PROVIDER == "gemini":
        return f"classifier: LLM gemini (GEMINI_API_KEY={'set' if GEMINI_API_KEY else 'MISSING'})"
    return f"classifier: LLM {LLM_PROVIDER}"


def main():
    print(f">>> {_llm_status()}")
    print("--- STEP 1: Scrape Telegram ---")
    df_raw = asyncio.run(run_scraper(limit_per_channel=MESSAGES_PER_CHANNEL))

    print("--- STEP 2: Merge into master store ---")
    master = merge_master(df_raw)

    print("--- STEP 3: Score messages (relevance / sentiment / engagement) ---")
    scored = score_messages(master)

    print("--- STEP 4: Build daily EAI / ESI index ---")
    daily = build_daily_index(scored)
    save_daily(daily)

    print("--- STEP 5: Exploratory topic model ---")
    topics, coherence = run_topic_model(scored)

    print("--- STEP 6: Export Excel report ---")
    export_results(scored, daily, topics, coherence)

    print("Pipeline finished. Latest day:")
    print(daily.tail(1).to_string(index=False))


if __name__ == "__main__":
    main()
