"""One readable workbook, regenerated from the shared report tables each run."""
import os

import pandas as pd
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from config import OUTPUT_DIR
from report_tables import build_tables, ordered_posts


def export_results(indices, ledger, pending_count=0):
    tables = build_tables(indices, ledger)
    posts = ordered_posts(ledger)
    tables["Xabarlar"]["To'liq matn"] = posts["raw_text"].astype(object).where(posts["raw_text"].notna(), None)
    tables["Xabarlar"]["Model"] = posts["label_model"].astype(object).where(posts["label_model"].notna(), None)
    filepath = os.path.join(OUTPUT_DIR, "economic_index_latest.xlsx")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    widths = {"Davr": 35, "Sana": 13, "Boshlanish": 13, "Tugash": 13, "Vaqt": 9, "Hafta kuni": 15,
              "Kanal": 22, "Sarlavha": 60, "Matn boshi": 75, "To'liq matn": 90,
              "Mavzu": 24, "Sabab": 21, "Havola": 48, "Izoh": 45, "Model": 28}
    wrapped = {"Sarlavha", "Matn boshi", "To'liq matn", "Izoh"}
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        for title, frame in tables.items():
            frame.to_excel(writer, sheet_name=title, index=False)
            ws = writer.sheets[title]
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for cell in ws[1]:
                cell.font = Font(bold=True)
            for i, column in enumerate(frame.columns, 1):
                letter = get_column_letter(i)
                ws.column_dimensions[letter].width = widths.get(column, max(13, len(column) + 2))
                numeric = "EAI" in column or "ESI" in column
                for cells in ws.iter_rows(min_row=2, min_col=i, max_col=i, max_row=ws.max_row):
                    cell = cells[0]
                    # Telegram text is content, even when it starts with an equals sign.
                    if isinstance(cell.value, str):
                        # XML normalizes line endings; avoid doubled CRLF on Windows.
                        cell.value = cell.value.replace("\r\n", "\n").replace("\r", "\n")
                        cell.data_type = "s"
                    cell.alignment = Alignment(vertical="top", wrap_text=column in wrapped)
                    if numeric:
                        cell.number_format = "0.0"
                if "ESI" in column and len(frame):
                    for operator, color in (("greaterThan", "0E7490"), ("lessThan", "C2410C")):
                        ws.conditional_formatting.add(f"{letter}2:{letter}{len(frame) + 1}",
                            CellIsRule(operator=operator, formula=["0"], font=Font(color=color)))
    print(f"Excel report generated: {filepath}")
    return filepath
