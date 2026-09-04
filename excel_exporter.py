"""
Excel report writer. Multi-sheet workbook with an embedded chart:

  1. Daily Index      – EAI/ESI time series (+ line chart)
  2. Messages & Scores – every message with topic + relevance/sentiment/flags,
                         SORTED by economic importance (relevance x attention)
  3. Topic Breakdown   – per primary_topic: count, mean relevance, mean sentiment
  4. Economic Lexicon  – the category patterns that drive classification
  5. Topic Glossary    – exploratory LDA (clearly secondary)
  6. Methodology       – formulas at a glance (full text in METHODOLOGY.md)
"""
import os
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from openpyxl.chart import LineChart, Reference

from config import OUTPUT_DIR
from lexicons import ECONOMIC_TERMS

MSG_COLS = ["channel", "message_id", "date", "primary_topic", "secondary_topics",
            "is_economic", "in_index", "is_ad", "is_foreign", "econ_hits",
            "relevance", "sentiment", "sent_label", "importance",
            "views", "forwards", "engagement", "eng_weight", "raw_text"]


def _add_line_chart(ws, n_rows):
    chart = LineChart()
    chart.title = "Economic Attention (EAI_100) vs Sentiment (ESI_100)"
    chart.y_axis.title = "index (avg day = 100 / 50 = neutral)"
    chart.x_axis.title = "date"
    chart.height, chart.width = 9, 22
    # date A(1); EAI_100 = col H(8); ESI_100 = col K(11)
    for col in (8, 11):
        data = Reference(ws, min_col=col, min_row=1, max_row=n_rows + 1)
        chart.add_data(data, titles_from_data=True)
    ws_cats = Reference(ws, min_col=1, min_row=2, max_row=n_rows + 1)
    chart.set_categories(ws_cats)
    ws.add_chart(chart, "N2")


def _topic_breakdown(scored):
    econ = scored[scored["in_index"] == 1]
    if econ.empty:
        return pd.DataFrame([{"primary_topic": "-", "posts": 0}])
    g = econ.groupby("primary_topic").agg(
        posts=("message_id", "count"),
        mean_relevance=("relevance", "mean"),
        mean_sentiment=("sentiment", "mean"),
        total_engagement=("engagement", "sum"),
    ).reset_index().sort_values("posts", ascending=False)
    g["share_%"] = (100 * g["posts"] / g["posts"].sum()).round(1)
    return g.round(3)


def export_results(scored_df, daily_df, topics, coherence):
    # Fixed filename, overwritten each run, so the repo keeps ONE current report
    # instead of accumulating a timestamped file per run.
    filepath = os.path.join(OUTPUT_DIR, "economic_index_latest.xlsx")

    scored_df = scored_df.copy()
    scored_df["importance"] = (scored_df["relevance"] * scored_df["eng_weight"]).round(4)

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        # 1) Daily index + chart
        daily_df.to_excel(writer, sheet_name="Daily Index", index=False)
        _add_line_chart(writer.sheets["Daily Index"], len(daily_df))

        # 2) Per-message scores — economic posts first, by importance
        cols = [c for c in MSG_COLS if c in scored_df.columns]
        ordered = scored_df.sort_values(
            ["in_index", "importance"], ascending=[False, False])
        ordered[cols].to_excel(writer, sheet_name="Messages & Scores", index=False)

        # 3) Topic breakdown
        _topic_breakdown(scored_df).to_excel(writer, sheet_name="Topic Breakdown", index=False)

        # 4) Economic lexicon (transparency)
        lex_rows = [{"Category": cat, "Pattern (regex)": p}
                    for cat, pats in ECONOMIC_TERMS.items() for p in pats]
        pd.DataFrame(lex_rows).to_excel(writer, sheet_name="Economic Lexicon", index=False)

        # 5) LDA glossary (exploratory only)
        tg = pd.DataFrame(topics) if topics else pd.DataFrame([{"Topic_ID": "-", "Top_Keywords": "n/a"}])
        tg.loc[len(tg)] = ["coherence(u_mass)", str(coherence)]
        tg.loc[len(tg)] = ["NOTE", "LDA is exploratory only — NOT the topic column; see 'primary_topic'"]
        tg.to_excel(writer, sheet_name="Topic Glossary", index=False)

        # 6) Methodology summary
        method = pd.DataFrame({"Methodology (summary — see METHODOLOGY.md)": [
            "primary_topic = argmax of per-category lexicon hits (bounded regex),",
            "   tie-break by fixed priority; 'non_economic' if < 2 econ hits.",
            "ads / news-digests / foreign-macro posts are flagged and EXCLUDED from the indices.",
            "relevance R  = 1 - exp(-econ_hits / TAU)      (0..1, saturating)",
            "sentiment s  = aspect-based: direction x aspect (cost-up=neg, output-up=pos,",
            "   fx-rate-up=neg), + unambiguous polarity, + negation guard   (-1..1)",
            "engagement   = ln(1 + views + 2*forwards),  weight = engagement / channel mean",
            "EAI = sum(w*R)/sum(w) over ALL posts (non-counted -> 0)     Attention (0..1)",
            "ESI = sum(w*s)/sum(w) over counted economic posts           Sentiment (-1..1)",
            "EAI_100 = 100*EAI/mean(EAI);  ESI_100 = 50*(ESI+1);  z = standardised",
            "Grounding: EPU (Baker-Bloom-Davis 2016); FRBSF News Sentiment (Shapiro 2020);",
            "dictionary/aspect sentiment (Loughran-McDonald 2011; Tetlock 2007).",
        ]})
        method.to_excel(writer, sheet_name="Methodology", index=False)

    print(f"Excel report generated: {filepath}")
    return filepath


def export_monthly(series_df, month_df, label):
    """Monthly report: the month-over-month series + the target month's detail."""
    filepath = os.path.join(OUTPUT_DIR, "economic_index_monthly_latest.xlsx")
    month_df = month_df.copy()
    month_df["importance"] = (month_df["relevance"] * month_df["eng_weight"]).round(4)

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        # 1) monthly time series (+ chart if >=2 months)
        series_df.to_excel(writer, sheet_name="Monthly Index", index=False)
        if len(series_df) >= 2:
            ws = writer.sheets["Monthly Index"]
            cols = {c: i + 1 for i, c in enumerate(series_df.columns)}
            chart = LineChart()
            chart.title = f"Monthly EAI_100 & ESI_100 (through {label})"
            chart.height, chart.width = 9, 22
            for name in ("EAI_100", "ESI_100"):
                if name in cols:
                    chart.add_data(Reference(ws, min_col=cols[name], min_row=1,
                                             max_row=len(series_df) + 1), titles_from_data=True)
            chart.set_categories(Reference(ws, min_col=cols["month"], min_row=2,
                                           max_row=len(series_df) + 1))
            ws.add_chart(chart, "N2")

        # 2) topic breakdown for the month
        _topic_breakdown(month_df).to_excel(writer, sheet_name=f"Topics {label}", index=False)

        # 3) the month's messages, most economically important first
        cols = [c for c in MSG_COLS if c in month_df.columns]
        (month_df.sort_values(["in_index", "importance"], ascending=[False, False])[cols]
         .to_excel(writer, sheet_name=f"Messages {label}", index=False))

    print(f"Monthly report generated: {filepath}  (month {label})")
    return filepath
