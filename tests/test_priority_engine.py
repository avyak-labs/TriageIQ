import pandas as pd
from core.priority_engine import compute_priority_scores, rank_feedback


def make_df(rows):
    return pd.DataFrame(rows)


def test_empty_dataframe_returns_empty_with_column():
    df = make_df([])
    df = pd.DataFrame(columns=["category", "urgency_score"])
    result = compute_priority_scores(df)
    assert "priority_score" in result.columns
    assert len(result) == 0


def test_bug_scores_higher_than_praise_at_same_urgency():
    df = make_df([
        {"category": "Bug", "urgency_score": 3},
        {"category": "Praise", "urgency_score": 3},
    ])
    result = compute_priority_scores(df)
    bug_score = result[result["category"] == "Bug"]["priority_score"].iloc[0]
    praise_score = result[result["category"] == "Praise"]["priority_score"].iloc[0]
    assert bug_score > praise_score


def test_higher_urgency_scores_higher_within_same_category():
    df = make_df([
        {"category": "Bug", "urgency_score": 1},
        {"category": "Bug", "urgency_score": 5},
    ])
    result = compute_priority_scores(df)
    scores = result.sort_values("urgency_score")["priority_score"].tolist()
    assert scores[0] < scores[1]


def test_rank_feedback_sorts_descending():
    df = make_df([
        {"category": "Bug", "urgency_score": 1},
        {"category": "Bug", "urgency_score": 5},
        {"category": "Praise", "urgency_score": 3},
    ])
    ranked = rank_feedback(df)
    scores = ranked["priority_score"].tolist()
    assert scores == sorted(scores, reverse=True)


def test_spam_scores_lowest():
    df = make_df([
        {"category": "Spam", "urgency_score": 5},
        {"category": "Bug", "urgency_score": 1},
    ])
    result = compute_priority_scores(df)
    spam_score = result[result["category"] == "Spam"]["priority_score"].iloc[0]
    bug_score = result[result["category"] == "Bug"]["priority_score"].iloc[0]
    assert spam_score < bug_score
