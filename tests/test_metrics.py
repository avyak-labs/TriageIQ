import datetime
import pandas as pd
from core.metrics import compute_kpis, hourly_volume, sentiment_distribution, source_breakdown


def make_row(hours_ago, category="Bug", sentiment="Negative", urgency=3, source="app_review"):
    now = datetime.datetime(2026, 1, 10, 12, 0, 0)
    return {
        "category": category,
        "sentiment": sentiment,
        "urgency_score": urgency,
        "source": source,
        "created_at": now - datetime.timedelta(hours=hours_ago),
    }


def test_compute_kpis_empty_dataframe():
    df = pd.DataFrame(columns=["category", "sentiment", "urgency_score", "created_at"])
    kpis = compute_kpis(df)
    assert kpis["total_feedback"]["value"] == 0
    assert kpis["total_feedback"]["delta_pct"] is None


def test_compute_kpis_shows_increase_vs_previous_window():
    # 2 rows in the last 24h, 1 row in the 24h before that -> current window has more
    rows = [make_row(1), make_row(2), make_row(30)]
    df = pd.DataFrame(rows)
    kpis = compute_kpis(df, hours=24)
    assert kpis["total_feedback"]["value"] == 2
    assert kpis["total_feedback"]["delta_pct"] == 100.0  # doubled vs previous window's 1


def test_compute_kpis_no_previous_data_gives_none_delta():
    rows = [make_row(1), make_row(2)]
    df = pd.DataFrame(rows)
    kpis = compute_kpis(df, hours=24)
    assert kpis["total_feedback"]["delta_pct"] is None


def test_bug_and_urgency_kpis_reflect_current_window_only():
    rows = [
        make_row(1, category="Bug", urgency=5),
        make_row(2, category="Praise", urgency=1),
        make_row(40, category="Bug", urgency=5),  # outside current window
    ]
    df = pd.DataFrame(rows)
    kpis = compute_kpis(df, hours=24)
    assert kpis["bugs_reported"]["value"] == 1
    assert kpis["avg_urgency"]["value"] == 3.0  # (5+1)/2


def test_hourly_volume_empty_dataframe():
    df = pd.DataFrame(columns=["created_at"])
    result = hourly_volume(df)
    assert list(result.columns) == ["hour", "count"]
    assert len(result) == 0


def test_hourly_volume_buckets_correctly():
    rows = [make_row(1), make_row(1.1), make_row(2)]
    df = pd.DataFrame(rows)
    result = hourly_volume(df, hours=24)
    assert result["count"].sum() == 3


def test_sentiment_distribution_fixed_order_and_zero_fill():
    rows = [make_row(1, sentiment="Negative"), make_row(2, sentiment="Negative")]
    df = pd.DataFrame(rows)
    result = sentiment_distribution(df)
    assert list(result["sentiment"]) == ["Negative", "Neutral", "Positive"]
    assert result[result["sentiment"] == "Negative"]["count"].iloc[0] == 2
    assert result[result["sentiment"] == "Positive"]["count"].iloc[0] == 0


def test_source_breakdown_sorted_descending():
    rows = [
        make_row(1, source="tweet"), make_row(2, source="tweet"), make_row(3, source="tweet"),
        make_row(4, source="app_review"),
    ]
    df = pd.DataFrame(rows)
    result = source_breakdown(df)
    assert result.iloc[0]["source"] == "tweet"
    assert result.iloc[0]["count"] == 3
