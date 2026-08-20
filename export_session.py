"""
Generate a Telethon StringSession for headless / GitHub Actions use.

Run this ONCE on your own machine:

    .\\venv\\Scripts\\python.exe export_session.py

What it does:
  1. If an authorized local session file (session_lda_index.session) already
     exists, it converts it to a StringSession *offline* — no Telegram
     connection needed. This is the easy path (works even when the network
     blocks Telegram, because no handshake happens).
  2. Otherwise it performs a one-time interactive login (asks for your phone
     number + the code Telegram sends you) and then prints the StringSession.
     This step DOES need a working Telegram connection, so run it on a network
     where Telegram works, or set USE_PROXY=1 with a local VPN/proxy client.

The resulting string is written to  session_string.txt  (git-ignored).
Copy its contents into a GitHub Actions secret named  TG_SESSION_STRING,
then DELETE session_string.txt. Treat the string like a password — anyone who
has it can act as your Telegram account.
"""
import os
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
    with TelegramClient(StringSession(), API_ID, API_HASH, proxy=PROXY) as client:
        return client.session.save()


def main():
    string = from_existing_file()
    if string:
        print("Converted the existing authorized session file (offline).")
    else:
        print("No authorized session file found -> starting interactive login...")
        string = from_interactive_login()
        print("Login successful.")

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(string)

    print(f"\nStringSession written to: {OUT_FILE}  (length {len(string)})")
    print("Next steps:")
    print("  1. Open the file, copy the whole string.")
    print("  2. GitHub repo -> Settings -> Secrets and variables -> Actions ->")
    print("     New repository secret -> name: TG_SESSION_STRING -> paste -> save.")
    print(f"  3. Delete {OUT_FILE} afterwards (it is a credential).")


if __name__ == "__main__":
    main()
