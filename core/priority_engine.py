"""
Turns raw urgency scores into a ranked priority list, factoring in
how often similar issues are showing up (volume matters as much as
severity — one angry review is noise, twenty is a fire).

Pure pandas logic, no DB or API calls, so it's easy to unit test.
"""
import pandas as pd

# Category weight: bugs/complaints matter more for triage than praise/spam
CATEGORY_WEIGHT = {
    "Bug": 1.5,
    "Complaint": 1.2,
    "Feature Request": 0.8,
    "Praise": 0.2,
    "Spam": 0.0,
    "Uncategorized": 0.5,
}


def compute_priority_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Adds a 'priority_score' column to a feedback DataFrame.

    priority_score = urgency_score * category_weight * log-scaled volume
    of similar-category feedback, so a category with many reports ranks
    higher than an isolated one-off at the same urgency level.

    Expects columns: category, urgency_score
    """
    if df.empty:
        df = df.copy()
        df["priority_score"] = pd.Series(dtype=float)
        return df

    df = df.copy()
    category_counts = df["category"].value_counts()

    def score_row(row):
        weight = CATEGORY_WEIGHT.get(row["category"], 0.5)
        volume = category_counts.get(row["category"], 1)
        # +1 avoids log(0); scales volume's influence without letting
        # it completely dominate an individual item's urgency
        volume_factor = 1 + (volume ** 0.5) / 10
        return round(row["urgency_score"] * weight * volume_factor, 2)

    df["priority_score"] = df.apply(score_row, axis=1)
    return df


def rank_feedback(df: pd.DataFrame) -> pd.DataFrame:
    """Returns the DataFrame sorted highest priority first."""
    scored = compute_priority_scores(df)
    return scored.sort_values("priority_score", ascending=False).reset_index(drop=True)
