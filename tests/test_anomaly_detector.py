import datetime
import pandas as pd
from core.anomaly_detector import detect_spikes


def make_row(category, minutes_offset, urgency=4, source="app_review", text="checkout failed"):
    base = datetime.datetime(2026, 1, 1, 12, 0, 0)
    return {
        "category": category,
        "created_at": base + datetime.timedelta(minutes=minutes_offset),
        "clean_text": text,
        "urgency_score": urgency,
        "source": source,
    }


def test_no_spike_below_threshold():
    rows = [make_row("Bug", i * 5) for i in range(3)]  # only 3 reports
    df = pd.DataFrame(rows)
    tickets = detect_spikes(df, threshold=5, window_minutes=60)
    assert tickets == []


def test_spike_detected_above_threshold():
    rows = [make_row("Bug", i * 2) for i in range(8)]  # 8 reports within ~16 min
    df = pd.DataFrame(rows)
    tickets = detect_spikes(df, threshold=5, window_minutes=60)
    assert len(tickets) == 1
    assert tickets[0]["affected_count"] >= 5
    assert tickets[0]["category"] == "Bug"


def test_spike_outside_window_not_flagged():
    # 6 reports, but spread far apart (well beyond the window)
    rows = [make_row("Bug", i * 120) for i in range(6)]  # every 2 hours
    df = pd.DataFrame(rows)
    tickets = detect_spikes(df, threshold=5, window_minutes=60)
    assert tickets == []


def test_praise_and_spam_never_generate_tickets():
    rows = [make_row("Praise", i * 2) for i in range(10)]
    rows += [make_row("Spam", i * 2) for i in range(10)]
    df = pd.DataFrame(rows)
    tickets = detect_spikes(df, threshold=5, window_minutes=60)
    assert tickets == []


def test_empty_dataframe_returns_empty_list():
    df = pd.DataFrame(columns=["category", "created_at", "clean_text", "urgency_score", "source"])
    assert detect_spikes(df) == []
