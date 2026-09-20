"""
TriageIQ dashboard. A single Streamlit app that reads from the
database and renders everything — no separate backend/API layer.
Run with: streamlit run app.py
"""
import streamlit as st
import pandas as pd

from core.database import fetch_all_feedback
from core.priority_engine import rank_feedback
from core.anomaly_detector import detect_spikes

st.set_page_config(page_title="TriageIQ", page_icon="📊", layout="wide")


@st.cache_data(ttl=60)
def load_data() -> pd.DataFrame:
    """Cached so the dashboard doesn't re-query Postgres on every
    filter interaction. Refreshes automatically after 60 seconds,
    or immediately if the user clicks 'Refresh data'."""
    return fetch_all_feedback()


def main():
    st.title("📊 TriageIQ")
    st.caption("From raw reviews to clean analysis")

    col_refresh, _ = st.columns([1, 5])
    with col_refresh:
        if st.button("🔄 Refresh data"):
            st.cache_data.clear()

    df = load_data()

    if df.empty:
        st.warning(
            "No feedback data found. Run the pipeline first:\n\n"
            "`python -m scripts.run_pipeline`"
        )
        return

    ranked_df = rank_feedback(df)

    # --- KPI cards ---
    st.subheader("Overview")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total feedback", len(df))
    k2.metric("Bugs reported", int((df["category"] == "Bug").sum()))
    k3.metric("Negative sentiment", int((df["sentiment"] == "Negative").sum()))
    k4.metric("Avg. urgency", round(df["urgency_score"].mean(), 1))

    st.divider()

    # --- Spike alerts / auto-generated tickets ---
    st.subheader("🚨 Anomaly Alerts")
    tickets = detect_spikes(df)
    if not tickets:
        st.info("No anomalies detected in the current data.")
    else:
        for ticket in tickets:
            with st.container(border=True):
                st.markdown(f"**{ticket['title']}**")
                c1, c2, c3 = st.columns(3)
                c1.write(f"Severity: **{ticket['severity']}**")
                c2.write(f"Affected users: **{ticket['affected_count']}**")
                c3.write(f"Avg urgency: **{ticket['avg_urgency']}**")
                st.caption(
                    f"Window: {ticket['window_start']} → {ticket['window_end']} "
                    f"| Sources: {', '.join(ticket['sources'])}"
                )
                st.markdown("**Sample reports:**")
                for sample in ticket["sample_reviews"]:
                    st.markdown(f"- _{sample}_")

    st.divider()

    # --- Filters ---
    st.subheader("Prioritized Feedback Roadmap")
    f1, f2, f3 = st.columns(3)
    with f1:
        category_filter = st.multiselect(
            "Category", sorted(df["category"].unique()), default=None
        )
    with f2:
        sentiment_filter = st.multiselect(
            "Sentiment", sorted(df["sentiment"].unique()), default=None
        )
    with f3:
        source_filter = st.multiselect(
            "Source", sorted(df["source"].unique()), default=None
        )

    filtered = ranked_df.copy()
    if category_filter:
        filtered = filtered[filtered["category"].isin(category_filter)]
    if sentiment_filter:
        filtered = filtered[filtered["sentiment"].isin(sentiment_filter)]
    if source_filter:
        filtered = filtered[filtered["source"].isin(source_filter)]

    display_cols = [
        "priority_score", "category", "sentiment", "urgency_score",
        "source", "clean_text", "created_at",
    ]
    st.dataframe(
        filtered[display_cols],
        use_container_width=True,
        hide_index=True,
    )

    # --- CSV export ---
    csv_bytes = filtered[display_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download prioritized list as CSV",
        data=csv_bytes,
        file_name="triageiq_prioritized_feedback.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
