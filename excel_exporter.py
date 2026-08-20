"""
Excel report writer. Produces a multi-sheet workbook with an embedded chart:

  1. Daily Index      – the EAI/ESI time series (+ a line chart)
  2. Messages & Scores – every message with its relevance / sentiment / weight
  3. Economic Lexicon  – the terms that drive the relevance score (transparency)
  4. Topic Glossary    – exploratory LDA themes + coherence
  5. Methodology       – the formulas in one glance (full text in METHODOLOGY.md)
"""
import os
import pandas as pd
from datetime import datetime, timezone
from openpyxl.chart import LineChart, Reference

from config import OUTPUT_DIR
from lexicons import ECONOMIC_TERMS, POSITIVE_TERMS, NEGATIVE_TERMS

MSG_COLS = ["channel", "message_id", "date", "views", "forwards",
            "econ_hits", "is_economic", "relevance",
            "pos_hits", "neg_hits", "sentiment",
            "engagement", "eng_weight", "raw_text"]


def _add_line_chart(ws, n_rows):
    chart = LineChart()
    chart.title = "Economic Attention (EAI_100) vs Sentiment (ESI_100)"
    chart.y_axis.title = "index (avg day = 100 / 50 = neutral)"
    chart.x_axis.title = "date"
    chart.height, chart.width = 9, 22
    # EAI_100 = col G(7), ESI_100 = col J(10); dates in col A(1)
    for col in (7, 10):
        data = Reference(ws, min_col=col, min_row=1, max_row=n_rows + 1)
        chart.add_data(data, titles_from_data=True)
    cats = Reference(ws, min_col=1, min_row=2, max_row=n_rows + 1)
    chart.set_categories(cats)
    ws.add_chart(chart, "M2")


def export_results(scored_df, daily_df, topics, coherence):
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    filepath = os.path.join(OUTPUT_DIR, f"economic_index_{ts}.xlsx")

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        # 1) Daily index + chart
        daily_df.to_excel(writer, sheet_name="Daily Index", index=False)
        _add_line_chart(writer.sheets["Daily Index"], len(daily_df))

        # 2) Per-message scores
        cols = [c for c in MSG_COLS if c in scored_df.columns]
        scored_df[cols].to_excel(writer, sheet_name="Messages & Scores", index=False)

        # 3) Economic lexicon (transparency)
        lex_rows = [{"Category": cat, "Term (stem)": t}
                    for cat, terms in ECONOMIC_TERMS.items() for t in terms]
        lex_rows += [{"Category": "sentiment_positive", "Term (stem)": t} for t in POSITIVE_TERMS]
        lex_rows += [{"Category": "sentiment_negative", "Term (stem)": t} for t in NEGATIVE_TERMS]
        pd.DataFrame(lex_rows).to_excel(writer, sheet_name="Economic Lexicon", index=False)

        # 4) Topic glossary (diagnostic)
        tg = pd.DataFrame(topics) if topics else pd.DataFrame([{"Topic_ID": "-", "Top_Keywords": "n/a"}])
        tg.loc[len(tg)] = ["coherence(c_v)", str(coherence)]
        tg.to_excel(writer, sheet_name="Topic Glossary", index=False)

        # 5) Methodology summary
        method = pd.DataFrame({"Methodology (summary — see METHODOLOGY.md)": [
            "relevance R  = 1 - exp(-econ_hits / TAU)      (0..1, saturating)",
            "sentiment s  = (pos_hits - neg_hits)/(pos_hits+neg_hits)   (-1..1)",
            "engagement   = ln(1 + views + 2*forwards)     (heavy-tail compression)",
            "eng_weight w = engagement / channel_mean_engagement   (fair channels)",
            "EAI = sum(w*R)/sum(w)            Economic Attention Index (0..1)",
            "ESI = sum(w*s)/sum(w) over economic posts   Sentiment Index (-1..1)",
            "EAI_100 = 100 * EAI / mean(EAI)   (average day = 100)",
            "ESI_100 = 50 * (ESI + 1)          (0..100, 50 = neutral)",
            "z-scores standardise each series across the available days.",
            "Grounding: EPU (Baker-Bloom-Davis 2016); FRBSF News Sentiment (Shapiro",
            "et al 2020); dictionary sentiment (Loughran-McDonald 2011; Tetlock 2007).",
        ]})
        method.to_excel(writer, sheet_name="Methodology", index=False)

    print(f"Excel report generated: {filepath}")
    return filepath
