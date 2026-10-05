"""
Excel report writer. Multi-sheet workbook with an embedded chart:

  1. Daily Index       – EAI/ESI time series (+ line chart)
  2. Messages & Scores – every message with topic + relevance/sentiment/flags,
                         SORTED by economic importance (relevance x attention)
  3. Topic Breakdown   – per primary_topic: count, mean relevance, mean sentiment
  4. Methodology       – formulas at a glance (full text in METHODOLOGY.md)
"""
import os

import pandas as pd
from openpyxl.chart import LineChart, Reference

from config import OUTPUT_DIR

MSG_COLS = ["channel", "message_id", "date", "scraped_at", "primary_topic",
            "is_economic", "in_index", "is_ad", "ad_marker", "is_digest", "is_foreign",
            "relevance", "sentiment", "sent_label", "importance",
            "views", "forwards", "engagement", "eng_weight", "label_model", "raw_text"]

METHOD_LINES = [
    "Collection: one full Tashkent day per run, right after midnight, 2 days back;",
    "   every post is measured once, at >= 24h of age (views/forwards).",
    "Labels: Gemini, once per post (cached) — economic?, primary_topic (10 categories),",
    "   relevance 0..1, sentiment -1..1 (aspect logic; routine/protocol news = 0),",
    "   flags: ad / news digest / foreign-macro. No rule-based fallback.",
    "Ads / digests / foreign-macro posts are EXCLUDED from the indices; a post the",
    "   channel itself marks as advertising ('(реклама)', trailing 'Reklama') always is.",
    "engagement = ln(1 + views + 2*forwards),  weight = engagement / channel mean",
    "EAI = sum(w*R)/sum(w) over ALL posts (non-counted -> 0)     Attention (0..1)",
    "ESI = sum(w*s)/sum(w) over counted economic posts           Sentiment (-1..1)",
    "EAI_100 = 100*EAI/mean(EAI);  ESI_100 = 50*(ESI+1);  z = standardised",
    "A day is published only when all its posts are labelled (unlabeled_messages = 0).",
    "Grounding: EPU (Baker-Bloom-Davis 2016); FRBSF News Sentiment (Shapiro et al. 2022).",
]


def _add_line_chart(ws, df, title, cat_col, anchor="N2"):
    if len(df) < 2:
        return
    cols = {c: i + 1 for i, c in enumerate(df.columns)}
    chart = LineChart()
    chart.title = title
    chart.y_axis.title = "index (avg = 100 / 50 = neutral)"
    chart.height, chart.width = 9, 22
    for name in ("EAI_100", "ESI_100"):
        chart.add_data(Reference(ws, min_col=cols[name], min_row=1, max_row=len(df) + 1),
                       titles_from_data=True)
    chart.set_categories(Reference(ws, min_col=cols[cat_col], min_row=2, max_row=len(df) + 1))
    ws.add_chart(chart, anchor)


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


def _messages(scored):
    df = scored.copy()
    df["importance"] = (df["relevance"].fillna(0) * df["eng_weight"]).round(4)
    cols = [c for c in MSG_COLS if c in df.columns]
    return df.sort_values(["in_index", "importance"], ascending=[False, False])[cols]


def export_results(scored_df, daily_df):
    # Fixed filename, overwritten each run: the repo keeps ONE current report.
    filepath = os.path.join(OUTPUT_DIR, "economic_index_latest.xlsx")
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        daily_df.to_excel(writer, sheet_name="Daily Index", index=False)
        _add_line_chart(writer.sheets["Daily Index"], daily_df,
                        "Economic Attention (EAI_100) vs Sentiment (ESI_100)", "date_only")
        _messages(scored_df).to_excel(writer, sheet_name="Messages & Scores", index=False)
        _topic_breakdown(scored_df).to_excel(writer, sheet_name="Topic Breakdown", index=False)
        pd.DataFrame({"Methodology (summary — see METHODOLOGY.md)": METHOD_LINES}).to_excel(
            writer, sheet_name="Methodology", index=False)
    print(f"Excel report generated: {filepath}")
    return filepath


def export_monthly(series_df, month_df, label):
    """Monthly report: the month-over-month series + the target month's detail."""
    filepath = os.path.join(OUTPUT_DIR, "economic_index_monthly_latest.xlsx")
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        series_df.to_excel(writer, sheet_name="Monthly Index", index=False)
        _add_line_chart(writer.sheets["Monthly Index"], series_df,
                        f"Monthly EAI_100 & ESI_100 (through {label})", "month")
        _topic_breakdown(month_df).to_excel(writer, sheet_name=f"Topics {label}", index=False)
        _messages(month_df).to_excel(writer, sheet_name=f"Messages {label}", index=False)
    print(f"Monthly report generated: {filepath}  (month {label})")
    return filepath
