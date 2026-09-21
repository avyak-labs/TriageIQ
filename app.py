"""
TriageIQ dashboard. A single Streamlit app that reads from the
database and renders everything — no separate backend/API layer.
Run with: streamlit run app.py
"""
import html as html_lib
import datetime

import streamlit as st
import pandas as pd
import altair as alt

from core.database import fetch_all_feedback
from core.priority_engine import rank_feedback
from core.anomaly_detector import detect_spikes
from core.metrics import compute_kpis, hourly_volume, sentiment_distribution, source_breakdown
from core.ai_classifier import generate_ticket_title

st.set_page_config(page_title="TriageIQ", page_icon="📊", layout="wide")

CATEGORY_CLASS = {
    "Bug": "cat-bug",
    "Feature Request": "cat-feature",
    "Complaint": "cat-complaint",
    "Praise": "cat-praise",
    "Spam": "cat-spam",
    "Uncategorized": "cat-uncategorized",
}
SENTIMENT_DOT_CLASS = {
    "Negative": "dot-negative",
    "Neutral": "dot-neutral",
    "Positive": "dot-positive",
}
SENTIMENT_COLORS = {"Negative": "#ef4444", "Neutral": "#f59e0b", "Positive": "#22c55e"}

CUSTOM_CSS = """
<style>
.category-pill {
    padding: 2px 10px; border-radius: 12px; font-size: 0.75rem;
    font-weight: 600; display: inline-block; white-space: nowrap;
}
.cat-bug { background: rgba(239,68,68,0.15); color: #f87171; border: 1px solid rgba(239,68,68,0.4); }
.cat-feature { background: rgba(59,130,246,0.15); color: #60a5fa; border: 1px solid rgba(59,130,246,0.4); }
.cat-complaint { background: rgba(245,158,11,0.15); color: #fbbf24; border: 1px solid rgba(245,158,11,0.4); }
.cat-praise { background: rgba(34,197,94,0.15); color: #4ade80; border: 1px solid rgba(34,197,94,0.4); }
.cat-spam, .cat-uncategorized { background: rgba(107,114,128,0.15); color: #9ca3af; border: 1px solid rgba(107,114,128,0.4); }

.sentiment-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
.dot-negative { background: #ef4444; }
.dot-neutral { background: #f59e0b; }
.dot-positive { background: #22c55e; }

.severity-badge {
    padding: 2px 10px; border-radius: 6px; font-weight: 700;
    font-size: 0.7rem; letter-spacing: 0.05em; display: inline-block;
}
.severity-critical { background: rgba(239,68,68,0.2); color: #f87171; }
.severity-high { background: rgba(245,158,11,0.2); color: #fbbf24; }

.ai-tag { color: #6b7280; font-size: 0.75rem; }
.ticket-meta { margin-bottom: 6px; }
.ticket-title { font-size: 1.3rem; font-weight: 700; margin: 4px 0 6px 0; color: #f3f4f6; }
.ticket-impact { color: #f87171; font-size: 0.95rem; margin-bottom: 10px; }

.source-tag {
    background: #1f2937; border: 1px solid #374151; border-radius: 12px;
    padding: 2px 10px; font-size: 0.75rem; margin-right: 6px; color: #9ca3af;
    display: inline-block; margin-bottom: 6px;
}

.quote-box {
    background: #111827; border-radius: 8px; padding: 10px 14px;
    margin-bottom: 8px; font-style: italic; color: #d1d5db; font-size: 0.88rem;
}
.quote-source-tag {
    background: #1f2937; border-radius: 4px; padding: 1px 8px;
    font-size: 0.7rem; margin-right: 8px; font-style: normal; color: #9ca3af;
}

.feedback-table-wrap { overflow-x: auto; }
.feedback-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
.feedback-table th {
    text-align: left; padding: 10px 12px; color: #9ca3af;
    font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.03em;
    border-bottom: 1px solid #2d3340;
}
.feedback-table td { padding: 10px 12px; border-bottom: 1px solid #1f2430; vertical-align: top; }
.feedback-table tr:hover { background: rgba(255,255,255,0.02); }
.score-cell { font-weight: 700; color: #f3f4f6; }
.quote-cell { color: #d1d5db; max-width: 420px; }
.date-cell, .source-cell { color: #9ca3af; white-space: nowrap; }

.app-subtitle { color: #9ca3af; margin-top: -8px; }
.sync-note { color: #6b7280; font-size: 0.85rem; }
</style>
"""


@st.cache_data(ttl=60)
def load_data() -> pd.DataFrame:
    """Cached so the dashboard doesn't re-query Postgres on every
    filter interaction. Refreshes automatically after 60 seconds,
    or immediately if the user clicks 'Refresh data'."""
    return fetch_all_feedback()


@st.cache_data(ttl=3600, show_spinner=False)
def cached_ai_title(ticket_id: str, sample_reviews: tuple, fallback: str) -> str:
    """Caches the AI-generated ticket title per unique ticket, so
    Streamlit re-running the whole script on every interaction (a
    filter click, a button press) doesn't trigger a fresh Gemini call
    each time — only the first time a given spike is seen."""
    return generate_ticket_title(list(sample_reviews), fallback)


def format_delta(pct):
    if pct is None:
        return None
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct}%"


def render_feedback_table(df: pd.DataFrame, max_rows: int = 100) -> str:
    rows_html = []
    for _, row in df.head(max_rows).iterrows():
        cat_class = CATEGORY_CLASS.get(row["category"], "cat-uncategorized")
        sent_class = SENTIMENT_DOT_CLASS.get(row["sentiment"], "dot-neutral")
        quote = html_lib.escape(str(row["clean_text"]))
        source = html_lib.escape(str(row["source"]))
        category = html_lib.escape(str(row["category"]))
        sentiment = html_lib.escape(str(row["sentiment"]))
        created = row["created_at"]
        created_str = created.strftime("%Y-%m-%d %H:%M") if hasattr(created, "strftime") else str(created)

        rows_html.append(f"""
        <tr>
          <td class="score-cell">{row['priority_score']:.2f}</td>
          <td><span class="category-pill {cat_class}">{category}</span></td>
          <td><span class="sentiment-dot {sent_class}"></span>{sentiment}</td>
          <td>{row['urgency_score']}</td>
          <td class="source-cell">{source}</td>
          <td class="quote-cell">{quote}</td>
          <td class="date-cell">{created_str}</td>
        </tr>""")

    return f"""
    <div class="feedback-table-wrap">
    <table class="feedback-table">
      <thead>
        <tr>
          <th>Priority</th><th>Category</th><th>Sentiment</th><th>Urgency</th>
          <th>Source</th><th>Feedback</th><th>Date</th>
        </tr>
      </thead>
      <tbody>{''.join(rows_html)}</tbody>
    </table>
    </div>
    """


def render_volume_chart(chart_df: pd.DataFrame, window_hours: int):
    vol_df = hourly_volume(chart_df, hours=window_hours)
    if vol_df.empty:
        st.info("Not enough data in this window to chart volume.")
        return

    baseline = vol_df["count"].mean()
    vol_df = vol_df.copy()
    vol_df["baseline"] = baseline

    line = alt.Chart(vol_df).mark_line(color="#3b82f6", strokeWidth=2.5).encode(
        x=alt.X("hour:T", title=None),
        y=alt.Y("count:Q", title="# Reports"),
        tooltip=[alt.Tooltip("hour:T", title="Time"), alt.Tooltip("count:Q", title="Reports")],
    )
    baseline_rule = alt.Chart(vol_df).mark_line(strokeDash=[4, 4], color="#6b7280", strokeWidth=1).encode(
        x="hour:T", y="baseline:Q",
    )
    chart = (line + baseline_rule).properties(height=260)
    st.altair_chart(chart, width="stretch")

    peak = vol_df.loc[vol_df["count"].idxmax()]
    if baseline > 0 and peak["count"] > baseline * 1.5:
        pct = round((peak["count"] - baseline) / baseline * 100)
        st.caption(f"🔺 Spike detected around {peak['hour'].strftime('%b %d, %H:%M')} — "
                   f"{pct}% above the window's average")


def render_sentiment_chart(chart_df: pd.DataFrame):
    sent_df = sentiment_distribution(chart_df)
    chart = alt.Chart(sent_df).mark_bar(size=45).encode(
        x=alt.X("sentiment:N", sort=["Negative", "Neutral", "Positive"], title=None),
        y=alt.Y("count:Q", title="# Reports"),
        color=alt.Color(
            "sentiment:N",
            scale=alt.Scale(domain=list(SENTIMENT_COLORS.keys()), range=list(SENTIMENT_COLORS.values())),
            legend=None,
        ),
        tooltip=["sentiment:N", "count:Q"],
    ).properties(height=260)
    st.altair_chart(chart, width="stretch")


def render_source_chart(chart_df: pd.DataFrame):
    src_df = source_breakdown(chart_df)
    if src_df.empty:
        st.info("No data in this window.")
        return
    chart = alt.Chart(src_df).mark_bar(color="#3b82f6", size=22).encode(
        y=alt.Y("source:N", sort="-x", title=None),
        x=alt.X("count:Q", title="# Reports"),
        tooltip=["source:N", "count:Q"],
    ).properties(height=260)
    st.altair_chart(chart, width="stretch")


def render_anomaly_card(ticket: dict):
    severity_class = "critical" if ticket["severity"] == "Critical" else "high"

    with st.container(border=True):
        top_col, action_col = st.columns([5, 2])

        with top_col:
            badge_html = f'<span class="severity-badge severity-{severity_class}">{ticket["severity"].upper()}</span>'
            st.markdown(
                f'<div class="ticket-meta">{ticket["ticket_id"]} &nbsp; {badge_html} '
                f'&nbsp; <span class="ai-tag">AI-Generated Summary</span></div>',
                unsafe_allow_html=True,
            )

            ai_title = cached_ai_title(ticket["ticket_id"], tuple(ticket["sample_reviews"]), ticket["title"])
            st.markdown(f'<div class="ticket-title">{html_lib.escape(ai_title)}</div>', unsafe_allow_html=True)

            pct_text = (
                f"({ticket['pct_above_baseline']}% increase above normal baseline)"
                if ticket["pct_above_baseline"] is not None else ""
            )
            st.markdown(
                f'<div class="ticket-impact">{ticket["affected_count"]} users impacted in the last '
                f'{ticket["window_minutes"]} minutes {pct_text}</div>',
                unsafe_allow_html=True,
            )

            tags_html = " ".join(
                f'<span class="source-tag">{html_lib.escape(src)} · {count}</span>'
                for src, count in ticket["source_counts"].items()
            )
            st.markdown(f'<div>{tags_html}</div>', unsafe_allow_html=True)

            for sample in ticket["sample_reviews_with_source"]:
                st.markdown(
                    f'<div class="quote-box"><span class="quote-source-tag">'
                    f'{html_lib.escape(sample["source"])}</span>'
                    f'"{html_lib.escape(sample["clean_text"])}"</div>',
                    unsafe_allow_html=True,
                )

        with action_col:
            created_key = f"jira_created_{ticket['ticket_id']}"
            if st.session_state.get(created_key):
                st.success(f"✅ {ticket['ticket_id']} created")
            else:
                if st.button("Create Jira Ticket", key=f"btn_{ticket['ticket_id']}", width="stretch"):
                    st.session_state[created_key] = True
                    st.rerun()

            with st.expander("View Details"):
                st.write(f"**Category:** {ticket['category']}")
                st.write(f"**Window:** {ticket['window_start']} → {ticket['window_end']}")
                st.write(f"**Avg urgency:** {ticket['avg_urgency']} / 5")
                st.write(f"**Sources:** {', '.join(ticket['sources'])}")


def main():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    header_col, refresh_col = st.columns([5, 1])
    with header_col:
        st.markdown("## 📊 TriageIQ")
        st.markdown(
            '<div class="app-subtitle">E-Commerce Mobile App (iOS &amp; Android) · '
            'Digital Product Feedback Intelligence</div>',
            unsafe_allow_html=True,
        )
    with refresh_col:
        st.write("")
        if st.button("🔄 Refresh data", width="stretch"):
            st.cache_data.clear()

    df = load_data()

    if df.empty:
        st.warning(
            "No feedback data found. Run the pipeline first:\n\n"
            "`python -m scripts.run_pipeline`"
        )
        return

    st.caption(f"Last synced: {datetime.datetime.now().strftime('%b %d, %Y · %H:%M')}")

    window_label = st.selectbox("Time range", ["Last 24 Hours", "Last 7 Days"], index=0)
    window_hours = 24 if window_label == "Last 24 Hours" else 24 * 7

    df_all = df.copy()
    df_all["created_at"] = pd.to_datetime(df_all["created_at"])
    window_start = df_all["created_at"].max() - pd.Timedelta(hours=window_hours)
    chart_df = df_all[df_all["created_at"] >= window_start]

    # --- KPI cards ---
    kpis = compute_kpis(df_all, hours=window_hours)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Feedback Processed", kpis["total_feedback"]["value"],
              delta=format_delta(kpis["total_feedback"]["delta_pct"]))
    k2.metric("Bugs Reported", kpis["bugs_reported"]["value"],
              delta=format_delta(kpis["bugs_reported"]["delta_pct"]), delta_color="inverse")
    k3.metric("Negative Sentiment Rate", f"{kpis['negative_rate']['value']}%",
              delta=format_delta(kpis["negative_rate"]["delta_pct"]), delta_color="inverse")
    k4.metric("Average Urgency Score", f"{kpis['avg_urgency']['value']} / 5",
              delta=format_delta(kpis["avg_urgency"]["delta_pct"]), delta_color="inverse")

    st.divider()

    # --- Charts ---
    st.subheader("Feedback Intelligence")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"**Feedback Volume · {window_label}**")
        render_volume_chart(chart_df, window_hours)
    with c2:
        st.markdown("**Sentiment Distribution**")
        render_sentiment_chart(chart_df)
    with c3:
        st.markdown("**Source Breakdown**")
        render_source_chart(chart_df)

    st.divider()

    # --- Anomaly alerts (Jira-style cards) ---
    tickets = detect_spikes(df_all)  # always runs on the full dataset, independent of the chart time-range
    st.subheader("🚨 Actionable Anomaly Alerts")
    st.caption(f"{len(tickets)} active anomal{'y' if len(tickets) == 1 else 'ies'} requiring attention")

    if not tickets:
        st.info("No anomalies detected in the current data.")
    else:
        for ticket in tickets:
            render_anomaly_card(ticket)

    st.divider()

    # --- Prioritized feedback table ---
    ranked_df = rank_feedback(df_all)

    st.subheader("Prioritized Feedback Backlog")
    st.caption(f"{len(ranked_df)} items · ranked by AI priority score")

    f1, f2, f3 = st.columns(3)
    with f1:
        category_filter = st.multiselect("Category", sorted(df_all["category"].unique()))
    with f2:
        sentiment_filter = st.multiselect("Sentiment", sorted(df_all["sentiment"].unique()))
    with f3:
        source_filter = st.multiselect("Source", sorted(df_all["source"].unique()))

    filtered = ranked_df.copy()
    if category_filter:
        filtered = filtered[filtered["category"].isin(category_filter)]
    if sentiment_filter:
        filtered = filtered[filtered["sentiment"].isin(sentiment_filter)]
    if source_filter:
        filtered = filtered[filtered["source"].isin(source_filter)]

    st.markdown(render_feedback_table(filtered), unsafe_allow_html=True)
    if len(filtered) > 100:
        st.caption(f"Showing top 100 of {len(filtered)} results — use the CSV export below for the full list.")

    display_cols = [
        "priority_score", "category", "sentiment", "urgency_score",
        "source", "clean_text", "created_at",
    ]
    csv_bytes = filtered[display_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Export to CSV",
        data=csv_bytes,
        file_name="triageiq_prioritized_feedback.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
