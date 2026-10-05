"""
Generate a Telethon StringSession for headless / GitHub Actions use.

Run this ONCE on your own machine, with your my.telegram.org API pair:

    $env:TG_API_ID="1234567"; $env:TG_API_HASH="abcdef..."
    .\\venv\\Scripts\\python.exe export_session.py --fresh

  * --fresh  performs a NEW interactive login (phone number + the code Telegram
    sends you). Use it when the CI session was revoked: an old local
    session_lda_index.session file holds the same dead key.
  * without --fresh, an existing authorized local session file is converted
    offline (no Telegram connection needed).
A login needs a working Telegram connection: on networks that block Telegram set
USE_PROXY=1 (and PROXY_PORT) for a local VPN/proxy client.

The string is written to session_string.txt (git-ignored). Put its contents into
the GitHub Actions secret TG_SESSION_STRING, then DELETE the file. Treat it like a
password: anyone who has it can act as your Telegram account. Use it ONLY in CI —
using the same session from two places at once makes Telegram revoke it — and do
not terminate the "Telethon" session in Telegram -> Settings -> Devices.
"""
import os
import sys

from telethon.sync import TelegramClient
from telethon.sessions import SQLiteSession, StringSession

from config import API_ID, API_HASH, PROXY

OUT_FILE = "session_string.txt"
LOCAL_SESSION = "session_lda_index"


def from_existing_file():
    """Convert an already-authorized .session file to a StringSession, offline."""
    if not os.path.exists(LOCAL_SESSION + ".session"):
        return None
    s = SQLiteSession(LOCAL_SESSION)
    if s.auth_key is None:
        return None
    return StringSession.save(s)


def from_interactive_login():
    """Fresh login -> StringSession (needs a working Telegram connection)."""
    with TelegramClient(StringSession(), int(API_ID), API_HASH, proxy=PROXY) as client:
        return client.session.save()


def main():
    if not API_ID.isdigit() or not API_HASH:
        sys.exit("Set TG_API_ID and TG_API_HASH (from my.telegram.org) first.")
    string = None if "--fresh" in sys.argv else from_existing_file()
    if string:
        print("Converted the existing local session file (offline). If CI says the "
              "session is revoked, run again with --fresh.")
    else:
        print("Starting interactive login...")
        string = from_interactive_login()
        print("Login successful.")

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(string)

    print(f"\nStringSession written to: {OUT_FILE}  (length {len(string)})")
    print("Next steps:")
    print("  1. Open the file, copy the whole string.")
    print("  2. GitHub repo -> Settings -> Secrets and variables -> Actions ->")
    print("     TG_SESSION_STRING -> Update -> paste -> save.")
    print(f"  3. Delete {OUT_FILE} afterwards (it is a credential).")


if __name__ == "__main__":
    main()
