"""
Pre-flight check of every external dependency, without collecting any posts.

  * Telegram: the session is authorized and every channel handle resolves
  * Gemini:   the key works, and the model labels the control set in gold_set.py
              (26 real posts with known answers) well enough
  * Sheets:   runs the real sync (fills the sheet), if its secrets are set
  * Alerts:   sends this summary through the bot, if its secrets are set

Run from Actions -> check -> Run workflow (or locally with the same env vars).
Exits non-zero if anything that is configured does not work.
"""
import asyncio
import os
import sys

import requests

from config import CHANNELS, GEMINI_API_KEY, TONE_THRESHOLD

GOLD_PASS = 0.85        # share of the control set the model must get right


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


def outcome(label):
    """What a label does to the index: reklama / boshqa / iqt+ / iqt0 / iqt-."""
    if label["is_ad"]:
        return "reklama"
    if not label["is_economic"] or label["is_digest"] or label["is_foreign"]:
        return "boshqa"
    s = label["sentiment"]
    return "iqt+" if s > TONE_THRESHOLD else "iqt-" if s < -TONE_THRESHOLD else "iqt0"


def check_gemini():
    """One request: label the control set with the model the pipeline would use."""
    if not GEMINI_API_KEY:
        return False, "GEMINI_API_KEY yo'q"
    from gold_set import GOLD
    from llm_classifier import candidate_models, classify_batch
    from store import load_ledger, load_pending
    used = (load_pending()["label_model"].dropna().tolist()
            or load_ledger()["label_model"].dropna().tolist())
    errors = []
    try:
        models = candidate_models(used[-1] if used else None)[:4]
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    for model in models:
        try:
            labels = classify_batch(model, [g[3] for g in GOLD], [g[0] for g in GOLD])
        except Exception as e:
            errors.append(f"{model}: {type(e).__name__}: {e}")
            continue
        wrong = [f"#{i + 1} {why}: kutilgan {want}, javob {outcome(lab)}"
                 for i, ((_, want, why, _), lab) in enumerate(zip(GOLD, labels))
                 if outcome(lab) != want]
        right = len(GOLD) - len(wrong)
        msg = f"{model} ishlayapti; nazorat to'plami: {right}/{len(GOLD)} to'g'ri"
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
