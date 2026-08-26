r"""
Diagnose the active LLM provider without sharing any secret.

Run locally:
    # GitHub Models (needs a PAT with `models: read`)
    $env:GITHUB_TOKEN="ghp_..."; .\venv\Scripts\python.exe llm_check.py
    # Gemini
    $env:GEMINI_API_KEY="..."; .\venv\Scripts\python.exe llm_check.py
Or run the `llm-check` workflow from the Actions tab (uses the built-in token).

It does ONE real classification call and prints the labels or the exact error.
"""
import json
import requests
from config import (LLM_PROVIDER, GITHUB_TOKEN, GITHUB_MODEL, GEMINI_API_KEY,
                    GEMINI_MODEL)


def check_github():
    print(f"Provider: github  model: {GITHUB_MODEL}")
    if not GITHUB_TOKEN:
        print("GITHUB_TOKEN not set (in Actions add `permissions: models: read`).")
        return
    try:
        r = requests.get("https://models.github.ai/catalog/models",
                         headers={"Authorization": f"Bearer {GITHUB_TOKEN}"}, timeout=60)
        if r.status_code == 200:
            ids = [m.get("id") for m in r.json()][:25]
            print("Sample catalog model ids:", ids)
        else:
            print(f"catalog HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print("catalog fetch skipped:", e)
    from llm_classifier import _call_github
    try:
        out = _call_github(["Markaziy bank dollar kursini oshirdi.",
                            "Bugun havo issiq bo'ladi."])
        print("SUCCESS:", json.dumps(out, ensure_ascii=False))
    except Exception as e:
        print("FAILED:", e)


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
    try:
        out = _call_gemini(["Dollar kursi tushdi.", "Bugun havo issiq."])
        print("SUCCESS:", json.dumps(out, ensure_ascii=False))
    except Exception as e:
        print("FAILED:", e)


if __name__ == "__main__":
    print("Active LLM_PROVIDER:", LLM_PROVIDER, "\n")
    if LLM_PROVIDER == "gemini":
        check_gemini()
    else:
        check_github()
