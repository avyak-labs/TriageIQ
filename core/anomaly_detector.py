"""
Watches for a sudden cluster of similar complaints in a short time
window (e.g. 20 people reporting "checkout failed" within an hour)
and generates a pre-formatted ticket for it — the project's
"killer feature".

Pure pandas logic, no DB or API calls, so it's easy to unit test.
"""
import pandas as pd

from core.config import SPIKE_THRESHOLD, SPIKE_WINDOW_MINUTES


def detect_spikes(
    df: pd.DataFrame,
    threshold: int = SPIKE_THRESHOLD,
    window_minutes: int = SPIKE_WINDOW_MINUTES,
) -> list[dict]:
    """Groups feedback by category within rolling time windows and
    flags groups that exceed `threshold` count.

    Expects columns: category, created_at, clean_text, urgency_score, source
    Returns a list of ticket dicts, one per detected spike.
    """
    if df.empty:
        return []

    df = df.copy()
    df["created_at"] = pd.to_datetime(df["created_at"])
    df = df.sort_values("created_at")

    # Baseline rate per category, used to express a spike as "X% above
    # normal" rather than just a raw count. Computed once over the whole
    # dataset's time span, not per-window, so it reflects the category's
    # typical pace rather than being skewed by the spike itself.
    total_span_minutes = (df["created_at"].max() - df["created_at"].min()).total_seconds() / 60
    category_totals = df["category"].value_counts()

    tickets = []
    ticket_counter = 0
    # Only bugs/complaints are worth auto-ticketing — praise/spam spikes aren't incidents
    relevant = df[df["category"].isin(["Bug", "Complaint"])]

    for category, group in relevant.groupby("category"):
        group = group.sort_values("created_at")
        window = pd.Timedelta(minutes=window_minutes)

        baseline_count_per_window = (
            (category_totals.get(category, 0) / total_span_minutes) * window_minutes
            if total_span_minutes > 0 else 0
        )

        # Sliding window: for each row, count how many category-matching
        # rows fall within `window_minutes` after it.
        times = group["created_at"].tolist()
        n = len(times)
        i = 0
        while i < n:
            window_end = times[i] + window
            j = i
            while j < n and times[j] <= window_end:
                j += 1
            count = j - i

            if count >= threshold:
                window_rows = group.iloc[i:j]
                ticket_counter += 1
                tickets.append(_build_ticket(
                    category, window_rows, ticket_counter, baseline_count_per_window, window_minutes
                ))
                i = j  # skip past this window to avoid overlapping duplicate tickets
            else:
                i += 1

    return tickets


def _build_ticket(
    category: str,
    rows: pd.DataFrame,
    ticket_number: int,
    baseline_count_per_window: float,
    window_minutes: int,
) -> dict:
    avg_urgency = round(rows["urgency_score"].mean(), 1)
    severity = "Critical" if avg_urgency >= 4 else "High"
    affected_count = len(rows)

    if baseline_count_per_window > 0:
        pct_above_baseline = round(
            (affected_count - baseline_count_per_window) / baseline_count_per_window * 100
        )
    else:
        pct_above_baseline = None  # no meaningful baseline to compare against

    source_counts = rows["source"].value_counts().to_dict()

    return {
        "ticket_id": f"TIQ-{ticket_number:03d}",
        "title": f"{severity} Priority: Spike in '{category}' reports",
        "category": category,
        "severity": severity,
        "affected_count": affected_count,
        "avg_urgency": avg_urgency,
        "window_start": rows["created_at"].min(),
        "window_end": rows["created_at"].max(),
        "window_minutes": window_minutes,
        "pct_above_baseline": pct_above_baseline,
        "sample_reviews": rows["clean_text"].head(3).tolist(),
        "sample_reviews_with_source": rows[["source", "clean_text"]].head(3).to_dict("records"),
        "sources": sorted(rows["source"].unique().tolist()),
        "source_counts": source_counts,
    }
