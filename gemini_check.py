r"""
Diagnose the Gemini API from your own machine, without sharing the key.

Run:
    # PowerShell
    $env:GEMINI_API_KEY="YOUR_KEY"; .\venv\Scripts\python.exe gemini_check.py

It (1) lists the models your key can use, (2) resolves the configured model,
(3) does ONE real classification call and prints the exact result or error.
This tells us precisely why Gemini "won't run" (wrong model id, API not enabled,
region, quota, schema, network) — paste the output back.
"""
import json
import requests
from config import GEMINI_API_KEY, GEMINI_MODEL

BASE = "https://generativelanguage.googleapis.com/v1beta"


def main():
    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY is not set. Set it and re-run.")
        return

    print(f"Configured GEMINI_MODEL = {GEMINI_MODEL}\n")

    print("== 1) ListModels ==")
    r = requests.get(f"{BASE}/models", params={"key": GEMINI_API_KEY}, timeout=60)
    print("HTTP", r.status_code)
    if r.status_code != 200:
        print("ERROR body:", r.text[:800])
        print("\n-> If 403 SERVICE_DISABLED: enable 'Generative Language API' for the key's")
        print("   Google Cloud project. If 400 about location: the API may be region-limited")
        print("   (GitHub Actions runs in the US, so CI still works even if local fails).")
        return
    models = [m["name"].replace("models/", "")
              for m in r.json().get("models", [])
              if "generateContent" in m.get("supportedGenerationMethods", [])]
    print("Models your key can call with generateContent:")
    for m in models:
        print("   ", m)

    print("\n== 2) Resolve model ==")
    from gemini_classifier import resolve_model, _call_gemini
    model = resolve_model(GEMINI_MODEL)
    print("Using:", model)

    print("\n== 3) One real classification ==")
    sample = ["Markaziy bank dollar kursini e'lon qildi: dollar biroz ko'tarildi.",
              "Bugun Toshkentda havo issiq bo'ladi, yomg'ir kutilmaydi."]
    try:
        out = _call_gemini(sample, model)
        print("SUCCESS. Labels:")
        print(json.dumps(out, ensure_ascii=False, indent=2))
    except Exception as e:
        print("FAILED:", e)


if __name__ == "__main__":
    main()
