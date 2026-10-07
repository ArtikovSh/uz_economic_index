"""
/setup (bot owner only): configures the bot's own profile through the Bot API and reports back.

* name, description (the empty-chat screen) and short description (the profile) in uz / ru / en,
  uz being the default for other languages;
* the command menu in the three languages, plus /setup in the owner's chat;
* the menu button that opens the Mini App;
* the profile photo, from app/public/bot/avatar.png (uploaded again only when the file changes);
* two custom emoji sets made from app/public/bot/emoji/*.png: coloured tiles for message text and
  plain glyphs (repainted to the text colour) for buttons. Custom emoji work in a bot's private
  chats only if its owner has Telegram Premium, so the bot first sends the owner a test message and
  uses them only when Telegram kept the custom emoji.

`call(method, params=None, files=None)` returns the API result or raises TgError; `fetch(url)`
returns the bytes of one of the Mini App's own static files.
"""
import hashlib
import json

from _bot import GLYPHS, LANGS, T, TILES, COMMANDS

NAME = "UZ Economic Index"
# (key, set name prefix, icons, needs_repainting). Telegram keeps a set's pictures, so new
# pictures go into a set with a new prefix; the old set is deleted.
SETS = (("t", "uzei_t2", TILES, False), ("g", "uzei_g", GLYPHS, True))
OLD_SETS = ("uzei_t",)

REPORT = {
    "uz": {"title": "Bot sozlamalari", "ok": "tayyor", "same": "o‘zgarmagan", "fail": "xato: {x}",
           "skip": "o‘tkazib yuborildi: {x}", "profile": "Nom va tavsif", "commands": "Buyruqlar menyusi",
           "menu": "Dashboard tugmasi", "photo": "Avatar", "icons": "Premium ikonkalar",
           "icons_ok": "ishlaydi ({n} ta)", "icons_off": "bot ulardan foydalana olmaydi (egasida Premium bormi?)",
           "digest": "Ertalabki xulosa", "no_cron": "Vercel'da CRON_SECRET o‘rnatilmagan",
           "no_url": "WEBAPP_URL o‘rnatilmagan", "picture": "Tavsif rasmi faqat @BotFather orqali: /setdescriptionpic"},
    "ru": {"title": "Настройка бота", "ok": "готово", "same": "без изменений", "fail": "ошибка: {x}",
           "skip": "пропущено: {x}", "profile": "Имя и описание", "commands": "Меню команд",
           "menu": "Кнопка дашборда", "photo": "Аватар", "icons": "Premium-иконки",
           "icons_ok": "работают ({n})", "icons_off": "бот не может их использовать (есть ли у владельца Premium?)",
           "digest": "Утренние итоги", "no_cron": "в Vercel не задан CRON_SECRET",
           "no_url": "не задан WEBAPP_URL", "picture": "Картинка описания — только через @BotFather: /setdescriptionpic"},
    "en": {"title": "Bot setup", "ok": "done", "same": "unchanged", "fail": "error: {x}",
           "skip": "skipped: {x}", "profile": "Name and description", "commands": "Command menu",
           "menu": "Dashboard button", "photo": "Profile photo", "icons": "Premium icons",
           "icons_ok": "working ({n})", "icons_off": "the bot cannot use them (does the owner have Premium?)",
           "digest": "Morning summary", "no_cron": "CRON_SECRET is not set in Vercel",
           "no_url": "WEBAPP_URL is not set", "picture": "The description picture is set only in @BotFather: /setdescriptionpic"},
}


class TgError(Exception):
    pass


def _setting(q, key):
    row = q("select value from bot_settings where key=%s", (key,), one=True)
    return row["value"] if row else None


def _save(q, key, value):
    q("""insert into bot_settings (key, value) values (%s, %s::jsonb)
         on conflict (key) do update set value = excluded.value, changed_at = now()""", (key, json.dumps(value)))


def profile(call):
    call("setMyName", {"name": NAME})
    for lang in LANGS:
        code = "" if lang == "uz" else lang
        call("setMyDescription", {"description": T[lang]["description"], "language_code": code})
        call("setMyShortDescription", {"short_description": T[lang]["short"], "language_code": code})


def commands(call, owner_id, owner_lang):
    for lang in LANGS:
        cmds = [{"command": c, "description": T[lang]["cmd"][c]} for c in COMMANDS]
        call("setMyCommands", {"commands": cmds, "language_code": "" if lang == "uz" else lang})
    if owner_id:
        own = [{"command": c, "description": T[owner_lang]["cmd"][c]} for c in COMMANDS + ("setup",)]
        call("setMyCommands", {"commands": own, "scope": {"type": "chat", "chat_id": int(owner_id)}})


def menu_button(call, url):
    call("setChatMenuButton", {"menu_button": {"type": "web_app", "text": "Dashboard", "web_app": {"url": url}}})


def photo(call, q, fetch, base):
    png = fetch(base + "/bot/avatar.png")
    digest = hashlib.sha256(png).hexdigest()
    if _setting(q, "avatar_sha") == digest:
        return False
    call("setMyProfilePhoto", {"photo": {"type": "static", "photo": "attach://avatar"}},
         files={"avatar": ("avatar.png", png, "image/png")})
    _save(q, "avatar_sha", digest)
    return True


def emoji_sets(call, q, owner_id, base):
    """Create the two sets if missing, add icons that are new since; returns {key: {icon: id}}."""
    bot = call("getMe")["username"]
    out = {}
    for key, prefix, icons, repaint in SETS:
        name = f"{prefix}_by_{bot}"
        sticker = lambda icon: {"sticker": f"{base}/bot/emoji/{key}-{icon}.png?set={prefix}", "format": "static",
                                "emoji_list": [icons[icon]]}
        try:
            have = call("getStickerSet", {"name": name})["stickers"]
        except TgError:
            call("createNewStickerSet", {"user_id": int(owner_id), "name": name, "title": NAME,
                                         "stickers": [sticker(i) for i in icons], "sticker_type": "custom_emoji",
                                         "needs_repainting": repaint})
            have = call("getStickerSet", {"name": name})["stickers"]
        names = list(icons)
        for icon in names[len(have):]:                  # the set keeps the order icons were added in
            call("addStickerToSet", {"user_id": int(owner_id), "name": name, "sticker": sticker(icon)})
        if len(have) < len(names):
            have = call("getStickerSet", {"name": name})["stickers"]
        out[key] = {icon: s["custom_emoji_id"] for icon, s in zip(names, have)}
    for prefix in OLD_SETS:
        try:
            call("deleteStickerSet", {"name": f"{prefix}_by_{bot}"})
        except TgError:                                  # already gone
            pass
    return out


def emoji_work(call, owner_id, em):
    """Telegram turns a custom emoji into its plain fallback when the bot may not use it."""
    eid = em["t"]["logo"]
    msg = call("sendMessage", {"chat_id": int(owner_id), "parse_mode": "HTML",
                               "text": f'<tg-emoji emoji-id="{eid}">{TILES["logo"]}</tg-emoji> UZ Economic Index',
                               "disable_notification": True})
    try:
        call("deleteMessage", {"chat_id": int(owner_id), "message_id": msg["message_id"]})
    except TgError:
        pass
    return any(e.get("type") == "custom_emoji" for e in msg.get("entities") or [])


def run(call, q, fetch, owner_id, owner_lang, base, cron_ready):
    """All steps; one failing does not stop the others. Returns the owner's report (HTML)."""
    r = REPORT.get(owner_lang, REPORT["uz"])
    lines = []

    def step(label, fn):
        try:
            res = fn()
            lines.append(f"{r[label]} — {res if isinstance(res, str) else r['ok']}")
        except TgError as e:
            lines.append(f"{r[label]} — " + r["fail"].format(x=str(e)[:160]))
        except Exception as e:                           # network or a missing static file
            lines.append(f"{r[label]} — " + r["fail"].format(x=type(e).__name__))

    step("profile", lambda: profile(call))
    step("commands", lambda: commands(call, owner_id, owner_lang))
    if base:
        step("menu", lambda: menu_button(call, base))
        step("photo", lambda: r["ok"] if photo(call, q, fetch, base) else r["same"])

        def icons():
            em = emoji_sets(call, q, owner_id, base)
            em["ok"] = emoji_work(call, owner_id, em)
            _save(q, "emoji", em)
            return r["icons_ok"].format(n=len(em["t"]) + len(em["g"])) if em["ok"] else r["icons_off"]
        step("icons", icons)
    else:
        for label in ("menu", "photo", "icons"):
            lines.append(f"{r[label]} — " + r["skip"].format(x=r["no_url"]))
    lines.append(f"{r['digest']} — " + (r["ok"] if cron_ready else r["no_cron"]))
    return f"<b>{r['title']}</b>\n" + "\n".join(lines) + f"\n\n<i>{r['picture']}</i>"
