"""
Computes dashboard KPIs with baseline comparisons (e.g. "+12% vs prior
period"), plus time-windowed aggregates used for the dashboard's charts.

Pure pandas functions, no DB/API calls - same testable pattern as
priority_engine.py and anomaly_detector.py.
"""
import pandas as pd


def _split_by_window(df: pd.DataFrame, hours: int = 24):
    """Splits feedback into 'current' (the most recent `hours` hours of
    data) and 'previous' (the equal-length window before that), so KPIs
    can show a real before/after comparison rather than a fake number."""
    if df.empty:
        return df, df

    df = df.copy()
    df["created_at"] = pd.to_datetime(df["created_at"])
    now = df["created_at"].max()
    current_start = now - pd.Timedelta(hours=hours)
    previous_start = current_start - pd.Timedelta(hours=hours)

    current = df[df["created_at"] >= current_start]
    previous = df[(df["created_at"] >= previous_start) & (df["created_at"] < current_start)]
    return current, previous


def _pct_change(current_val: float, previous_val: float):
    """Returns None (not 0) when there's no meaningful baseline to compare
    against, so the UI can show 'new' instead of a misleading '+inf%'."""
    if previous_val == 0:
        return None
    return round((current_val - previous_val) / previous_val * 100, 1)


def compute_kpis(df: pd.DataFrame, hours: int = 24) -> dict:
    """Returns KPI values plus their % change vs the prior equal-length
    window. Each KPI is a dict: {"value": ..., "delta_pct": ... or None}."""
    current, previous = _split_by_window(df, hours)

    def bug_count(d):
        return int((d["category"] == "Bug").sum()) if len(d) else 0

    def negative_rate(d):
        return round((d["sentiment"] == "Negative").mean() * 100, 1) if len(d) else 0.0

    def avg_urgency(d):
        return round(d["urgency_score"].mean(), 1) if len(d) else 0.0

    return {
        "total_feedback": {
            "value": len(current),
            "delta_pct": _pct_change(len(current), len(previous)),
        },
        "bugs_reported": {
            "value": bug_count(current),
            "delta_pct": _pct_change(bug_count(current), bug_count(previous)),
        },
        "negative_rate": {
            "value": negative_rate(current),
            "delta_pct": _pct_change(negative_rate(current), negative_rate(previous)),
        },
        "avg_urgency": {
            "value": avg_urgency(current),
            "delta_pct": _pct_change(avg_urgency(current), avg_urgency(previous)),
        },
    }


def hourly_volume(df: pd.DataFrame, hours: int = 24) -> pd.DataFrame:
    """One row per hour bucket in the last `hours` hours: columns
    [hour, count]. Feeds the feedback-volume-over-time chart."""
    if df.empty:
        return pd.DataFrame(columns=["hour", "count"])

    df = df.copy()
    df["created_at"] = pd.to_datetime(df["created_at"])
    now = df["created_at"].max()
    window_start = now - pd.Timedelta(hours=hours)
    windowed = df[df["created_at"] >= window_start].set_index("created_at")

    if windowed.empty:
        return pd.DataFrame(columns=["hour", "count"])

    hourly = windowed.resample("1h").size().reset_index(name="count")
    hourly = hourly.rename(columns={"created_at": "hour"})
    return hourly


def sentiment_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Counts per sentiment, in a fixed Negative/Neutral/Positive order
    so the bar chart's colors line up consistently across runs."""
    order = ["Negative", "Neutral", "Positive"]
    if df.empty:
        return pd.DataFrame({"sentiment": order, "count": [0, 0, 0]})
    counts = df["sentiment"].value_counts().reindex(order, fill_value=0)
    return pd.DataFrame({"sentiment": order, "count": counts.values})


def source_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """Counts per source, sorted descending. Feeds the source
    breakdown chart (Twitter/App Store/etc. equivalents)."""
    if df.empty:
        return pd.DataFrame(columns=["source", "count"])
    counts = df["source"].value_counts().reset_index()
    counts.columns = ["source", "count"]
    return counts.sort_values("count", ascending=False)
