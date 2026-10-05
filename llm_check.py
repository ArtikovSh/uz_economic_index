r"""
Diagnose Gemini access without sharing any secret.

Run locally:   $env:GEMINI_API_KEY="..."; .\venv\Scripts\python.exe llm_check.py
or via the `llm-check` workflow (Actions tab -> Run workflow).

Lists the models the key can call, then makes ONE real classification call per
candidate until one works, and prints the labels or the exact error.
"""
import json

from config import GEMINI_API_KEY, GEMINI_MODEL
from llm_classifier import candidate_models, classify_batch, list_models

SAMPLE = ["Markaziy bank dollar kursini e'lon qildi: dollar biroz ko'tarildi.",
          "Bugun Toshkentda havo issiq bo'ladi, yomg'ir kutilmaydi."]

if __name__ == "__main__":
    print(f"GEMINI_API_KEY: {'set' if GEMINI_API_KEY else 'MISSING'} | "
          f"GEMINI_MODEL: {GEMINI_MODEL or '(auto)'}")
    if GEMINI_API_KEY:
        try:
            print("Models with generateContent:", list_models())
        except Exception as e:
            print("Model list FAILED:", e)
        for model in candidate_models()[:4]:
            try:
                out = classify_batch(model, SAMPLE)
                print(f"SUCCESS with {model}:", json.dumps(out, ensure_ascii=False))
                break
            except Exception as e:
                print(f"FAILED with {model}: {type(e).__name__}: {e}")
