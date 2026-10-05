"""
Pre-flight check of every external dependency, without collecting any posts.

  * Telegram: the session is authorized and every channel handle resolves
  * Gemini:   the key works and a model returns a valid classification
  * Sheets:   runs the real sync (fills the sheet), if its secrets are set
  * Alerts:   sends this summary through the bot, if its secrets are set

Run from Actions -> check -> Run workflow (or locally with the same env vars).
Exits non-zero if anything that is configured does not work.
"""
import asyncio
import os
import sys

import requests

from config import CHANNELS, GEMINI_API_KEY

SAMPLE = ["Markaziy bank dollar kursini e'lon qildi: dollar biroz ko'tarildi.",
          "Bugun Toshkentda havo issiq bo'ladi, yomg'ir kutilmaydi."]


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


def check_gemini():
    if not GEMINI_API_KEY:
        return False, "GEMINI_API_KEY yo'q"
    from llm_classifier import candidate_models, classify_batch
    errors = []
    try:
        models = candidate_models()[:4]
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    for model in models:
        try:
            out = classify_batch(model, SAMPLE)
            return True, (f"{model} ishlayapti (namuna: {out[0]['primary_topic']}, "
                          f"sentiment {out[0]['sentiment']:+.2f})")
        except Exception as e:
            errors.append(f"{model}: {type(e).__name__}: {e}")
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
    results = [("Telegram", *check_telegram()),
               ("Gemini", *check_gemini()),
               ("Google Sheets", *check_sheets())]
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
