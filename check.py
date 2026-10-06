"""
Pre-flight check of every external dependency, without collecting any posts.

  * Telegram: the session is authorized and every channel handle resolves
  * LLM:      the provider the pipeline uses (OpenAI or Gemini) works, and its model
              labels the control set in gold_set.py (26 real posts with known answers)
              well enough. Bounded to a few minutes. (eval.yml labels a larger sample.)
  * Sheets:   runs the real sync (fills the sheet), if its secrets are set
  * Alerts:   sends this summary through the bot, if its secrets are set

Run from Actions -> check -> Run workflow (or locally with the same env vars).
Exits non-zero if anything that is configured does not work.
"""
import asyncio
import os
import sys
import time

import requests

from config import CHANNELS, GEMINI_API_KEY, OPENAI_API_KEY, LLM_PROVIDER, is_openai_key

GOLD_PASS = 0.85        # share of the control set the model must get right
LLM_CHECK_SECONDS = 240  # the LLM check gives up after this


def check_telegram():
    from scraper import SessionError, open_client

    async def run():
        client = await open_client()
        try:
            me = await client.get_me()
            bad = []
            for ch in CHANNELS:
                try:
                    await client.get_entity(ch)
                except Exception as e:
                    bad.append(f"{ch} ({type(e).__name__})")
            who = me.username or me.first_name
            if bad:
                return False, f"sessiya ishlayapti ({who}), lekin kanal topilmadi: {', '.join(bad)}"
            return True, f"sessiya ishlayapti ({who}), {len(CHANNELS)} ta kanal topildi"
        finally:
            await client.disconnect()

    try:
        return asyncio.run(run())
    except SessionError as e:
        return False, str(e)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def say(line):
    print(line, flush=True)                 # progress shows in the log even if a step hangs


def check_llm(provider):
    """One request: label the control set with the model the pipeline would use.
    Bounded to LLM_CHECK_SECONDS, so a slow API cannot hang the whole check."""
    configured = is_openai_key(OPENAI_API_KEY) if provider == "openai" else bool(GEMINI_API_KEY)
    if not configured:
        key = "OPENAI_API_KEY" if provider == "openai" else "GEMINI_API_KEY"
        return False, f"sozlanmagan ({key} yo'q yoki noto'g'ri)"
    from gold_set import GOLD, outcome
    from llm_classifier import candidate_models, classify_batch
    from store import load_ledger, load_pending
    used = (load_pending()["label_model"].dropna().tolist()
            or load_ledger()["label_model"].dropna().tolist())
    errors = []
    try:
        models = candidate_models(used[-1] if used else None, provider)[:2]
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    deadline = time.time() + LLM_CHECK_SECONDS
    for model in models:
        t0 = time.time()
        say(f"  {model}: {len(GOLD)} ta nazorat posti yuborildi...")
        try:
            labels = classify_batch(model, [g[3] for g in GOLD], [g[0] for g in GOLD], deadline)
        except Exception as e:
            say(f"  {model}: {type(e).__name__} ({time.time() - t0:.0f} s)")
            errors.append(f"{model}: {type(e).__name__}: {e}")
            if time.time() >= deadline:
                break
            continue
        wrong = [f"#{i + 1} {why}: kutilgan {want}, javob {outcome(lab)}"
                 for i, ((_, want, why, _), lab) in enumerate(zip(GOLD, labels))
                 if outcome(lab) != want]
        right = len(GOLD) - len(wrong)
        msg = (f"{model} ishlayapti ({time.time() - t0:.0f} s); "
               f"nazorat to'plami: {right}/{len(GOLD)} to'g'ri")
        if wrong:
            msg += "\n   " + "\n   ".join(wrong)
        return right >= GOLD_PASS * len(GOLD), msg[:1500]
    return False, ("; ".join(errors) or "mos model topilmadi")[:600]


def check_sheets():
    import sheets_sync
    if not sheets_sync.SA_JSON or not sheets_sync.SHEET_ID:
        return None, "sozlanmagan (GOOGLE_SERVICE_ACCOUNT_JSON / GSHEET_ID yo'q)"
    try:
        code = sheets_sync.main()
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    return code == 0, "jadval yangilandi" if code == 0 else "xato — Actions log'iga qarang"


def notify(text):
    """Send text via the bot; None if not configured, else whether it was delivered."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.getenv("BOT_ADMIN_ID", "").strip()
    if not token or not chat:
        return None
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": text}, timeout=20)
        return r.ok
    except requests.RequestException:
        return False


def main() -> int:
    name = {"openai": "OpenAI", "gemini": "Gemini"}[LLM_PROVIDER]
    results = []
    for title, fn in [("Telegram", check_telegram), (name, lambda: check_llm(LLM_PROVIDER)),
                      ("Google Sheets", check_sheets)]:
        say(f"{title}...")
        results.append((title, *fn()))
        say(f"  -> {results[-1][1]}")
    icon = {True: "✅", False: "❌", None: "⚪"}
    text = "uz-economic-index tekshiruvi\n" + "\n".join(
        f"{icon[ok]} {name}: {msg}" for name, ok, msg in results)
    print(text)
    sent = notify(text)
    print("Bot xabari:", {True: "yuborildi", None: "sozlanmagan (TELEGRAM_BOT_TOKEN / BOT_ADMIN_ID)",
                          False: "YUBORILMADI — token yoki ID noto'g'ri, yoki botga /start bosilmagan"}[sent])
    failed = any(ok is False for _, ok, _ in results) or sent is False
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
