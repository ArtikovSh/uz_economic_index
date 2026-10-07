"""Generate the bot avatar and Premium emoji PNGs from SVG.

Install the one-time build dependency with ``pip install resvg-py``.
Run ``python tools/bot_assets.py`` from the repository root.
"""

from pathlib import Path

from resvg_py import svg_to_bytes


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "app" / "public" / "bot"

# Keep the shared icon geometry identical to app/public/js/lib.js PATHS.
PATHS = {
    "target": '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="0.8"/>',
    "pulse": '<path d="M3 12h4l2.5-6 5 12 2.5-6H21"/>',
    "news": '<path d="M4 5h12v14H6a2 2 0 0 1-2-2V5Z"/><path d="M16 9h4v8a2 2 0 0 1-2 2h-2"/><path d="M7 9h6M7 13h6M7 16h4"/>',
    "layers": '<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 13 9 5 9-5"/>',
    "trendUp": '<path d="M3 17 9.5 10.5l4 4L21 7"/><path d="M15 7h6v6"/>',
    "trendDown": '<path d="M3 7l6.5 6.5 4-4L21 17"/><path d="M15 17h6v-6"/>',
    "calendar": '<rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>',
    "lock": '<rect x="4.5" y="10.5" width="15" height="10" rx="2"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3Z"/>',
    "check": '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    "back": '<path d="m15 5-7 7 7 7"/>',
    "up": '<path d="M7 17 17 7M9 7h8v8"/>',
    "down": '<path d="M7 7l10 10M17 9v8H9"/>',
    "grid": (
        '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/>'
        '<rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/>'
        '<rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/>'
        '<rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/>'
    ),
    "bell": '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
    "login": '<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><path d="m10 17 5-5-5-5"/><path d="M15 12H3"/>',
    "logo": '<path d="M4 17 10 11l4 3 6-7"/>',
}

TILES = {
    "logo": ("#0F1B2D", "logo"),
    "eai": ("#2449C2", "target"),
    "esi": ("#0E7490", "pulse"),
    "news": ("#5B6B7F", "news"),
    "topics": ("#4338CA", "layers"),
    "up": ("#0E7490", "trendUp"),
    "down": ("#EA580C", "trendDown"),
    "week": ("#2449C2", "calendar"),
    "user": ("#0F1B2D", "user"),
    "bell": ("#0F1B2D", "bell"),
    "lock": ("#0F1B2D", "lock"),
    "globe": ("#0F1B2D", "globe"),
    "check": ("#0E7490", "check"),
}

GLYPHS = {
    "dashboard": "grid", "topics": "layers", "news": "news", "week": "calendar",
    "eai": "target", "esi": "pulse", "user": "user", "globe": "globe", "bell": "bell",
    "login": "login", "back": "back", "up": "up", "down": "down",
}


def _svg(size, content):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 {size} {size}">{content}</svg>'
    )


def _avatar():
    return _svg(640, (
        '<rect width="640" height="640" fill="#EEF2F7"/>'
        '<svg x="107.5" y="107.5" width="425" height="425" viewBox="0 0 36 36">'
        '<rect width="36" height="36" rx="10" fill="#0F1B2D"/>'
        '<path d="M8 23l6-6 5 4 9-10" fill="none" stroke="#FFFFFF" '
        'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>'
        '<circle cx="28" cy="11" r="2.6" fill="#6F97FF"/>'
        '</svg>'
    ))


def _emoji(icon, background=None):
    size, stroke = (64, 2.6) if background else (80, 2.2)
    inset = (100 - size) / 2
    tile = f'<rect width="100" height="100" rx="26" fill="{background}"/>' if background else ""
    return _svg(100, (
        f'{tile}<svg x="{inset}" y="{inset}" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="{stroke}" '
        f'stroke-linecap="round" stroke-linejoin="round">{PATHS[icon]}</svg>'
    ))


def main():
    emoji_dir = DESTINATION / "emoji"
    emoji_dir.mkdir(parents=True, exist_ok=True)
    images = [(DESTINATION / "avatar.png", _avatar())]
    images.extend((emoji_dir / f"t-{name}.png", _emoji(icon, color))
                  for name, (color, icon) in TILES.items())
    images.extend((emoji_dir / f"g-{name}.png", _emoji(icon))
                  for name, icon in GLYPHS.items())
    for path, svg in images:
        path.write_bytes(svg_to_bytes(svg_string=svg, skip_system_fonts=True))
    for path, _ in images:
        print(path.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
