"""
Excel report (one workbook, overwritten each run):

  1. Indekslar  – every closed day / week / month / quarter / year
  2. Xabarlar   – the posts table (every final post with its labels and flags)
  3. Metodika   – the formulas at a glance (full text in METHODOLOGY.md)
"""
import os

import pandas as pd

from config import OUTPUT_DIR

INDEX_HEADERS = {
    "period_type": "davr turi", "period": "davr", "start": "boshlanish", "end": "tugash",
    "days": "kunlar", "days_expected": "kunlar (jami)", "posts": "jami xabarlar",
    "nonad": "reklama emas", "econ": "iqtisodiy", "pos": "ijobiy", "neu": "neytral",
    "neg": "salbiy", "EAI": "EAI, %", "ESI": "ESI (balans)", "note": "izoh",
}
POST_HEADERS = {
    "date_local": "sana (Toshkent)", "channel": "kanal", "message_id": "post id",
    "primary_topic": "mavzu", "is_economic": "iqtisodiy (LLM)", "is_ad": "reklama",
    "ad_marker": "kanal reklama belgisi", "is_digest": "dayjest", "is_foreign": "xorijiy",
    "econ": "indeksda", "tone": "ohang", "sentiment": "sentiment", "relevance": "relevance",
    "views": "ko'rishlar", "forwards": "forwardlar", "scraped_at": "o'lchangan (UTC)",
    "label_model": "model", "raw_text": "matn",
}
METHOD_LINES = [
    "Indekslar barcha kanallar bo'yicha birga, oddiy sanoq bilan hisoblanadi:",
    "  EAI = 100 * iqtisodiy / reklama emas   (reklama bo'lmagan xabarlarning necha foizi iqtisodiy)",
    "  ESI = 100 * (ijobiy - salbiy) / iqtisodiy   (balans, -100 ... +100; 0 = neytral)",
    "iqtisodiy = reklama emas + O'zbekiston iqtisodiyotiga oid (dayjest va xorijiy-makro emas).",
    "Kanal o'zi reklama deb belgilagan xabar ('(реклама)', oxirida 'Reklama') har doim reklama.",
    "Ohang: sentiment > +0.15 ijobiy, < -0.15 salbiy, qolgani neytral (Gemini belgisi).",
    "Kun yakunlangach (barcha postlar belgilangan) xabarlar va kun qatori jadvalga qo'shiladi;",
    "  hafta / oy / chorak / yil qatori davrning oxirgi kuni yakunlanganda qo'shiladi.",
    "Qo'shilgan qator keyin hech qachon o'zgartirilmaydi.",
    "Yig'ish: har kecha 00:05 da 2 kun oldingi to'liq kun; har post bir marta o'lchanadi.",
]


def export_results(indices, ledger, pending_count=0):
    filepath = os.path.join(OUTPUT_DIR, "economic_index_latest.xlsx")
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        indices.rename(columns=INDEX_HEADERS).to_excel(writer, sheet_name="Indekslar", index=False)
        cols = [c for c in POST_HEADERS if c in ledger.columns]
        ledger[cols].rename(columns=POST_HEADERS).to_excel(writer, sheet_name="Xabarlar", index=False)
        lines = METHOD_LINES + ["", f"Kun yakunlanishini kutayotgan xabarlar: {pending_count}"]
        pd.DataFrame({"Metodika (to'liq matn: METHODOLOGY.md)": lines}).to_excel(
            writer, sheet_name="Metodika", index=False)
        for ws in writer.sheets.values():
            ws.freeze_panes = "A2"
    print(f"Excel report generated: {filepath}")
    return filepath
