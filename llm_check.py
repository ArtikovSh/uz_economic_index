r"""
Diagnose the active LLM provider without sharing any secret.

Run locally (or via the `llm-check` workflow from the Actions tab):
    # OpenAI-compatible (Groq is free)
    $env:OPENAI_API_KEY="gsk_..."; .\venv\Scripts\python.exe llm_check.py
    # Gemini
    $env:GEMINI_API_KEY="..."; .\venv\Scripts\python.exe llm_check.py

It does ONE real classification call and prints the labels or the exact error.
"""
import json
import requests
from config import (LLM_PROVIDER, OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL,
                    GITHUB_TOKEN, GITHUB_MODEL, GEMINI_API_KEY, GEMINI_MODEL)

SAMPLE = ["Markaziy bank dollar kursini e'lon qildi: dollar biroz ko'tarildi.",
          "Bugun Toshkentda havo issiq bo'ladi, yomg'ir kutilmaydi."]


def _report(fn):
    try:
        out = fn()
        print("SUCCESS:", json.dumps(out, ensure_ascii=False))
    except Exception as e:
        print("FAILED:", e)


def check_openai(base_url, api_key, model, label):
    print(f"Provider: {label}  base: {base_url}  model: {model}")
    if not api_key:
        print("API key not set.")
        return
    from llm_classifier import _call_openai
    _report(lambda: _call_openai(SAMPLE, base_url, api_key, model, label))


def check_gemini():
    print(f"Provider: gemini  model: {GEMINI_MODEL}")
    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY not set.")
        return
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                     params={"key": GEMINI_API_KEY}, timeout=60)
    print("ListModels HTTP", r.status_code)
    if r.status_code != 200:
        print(r.text[:600])
        return
    models = [m["name"].replace("models/", "") for m in r.json().get("models", [])
              if "generateContent" in m.get("supportedGenerationMethods", [])]
    print("Models:", models)
    from llm_classifier import _call_gemini
    _report(lambda: _call_gemini(SAMPLE))


if __name__ == "__main__":
    print("Active LLM_PROVIDER:", LLM_PROVIDER, "\n")
    if LLM_PROVIDER == "gemini":
        check_gemini()
    elif LLM_PROVIDER == "github":
        check_openai("https://models.github.ai/inference", GITHUB_TOKEN, GITHUB_MODEL, "github")
    else:
        check_openai(OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL, "openai")
