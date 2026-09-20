"""
One-command pipeline: generate mock data -> clean -> classify via
Gemini -> compute priority scores -> load into Postgres.

Clears the table first, so re-running this script is idempotent —
you always end up with exactly one fresh batch, never duplicates.

Usage: python -m scripts.run_pipeline
       python -m scripts.run_pipeline --rows 500 --spike 25
"""
import argparse
import datetime
import logging

from core.config import validate_config
from core.database import clear_feedback_table, insert_feedback_batch
from core.preprocessing import clean_text
from core.ai_classifier import classify_feedback
from core.priority_engine import compute_priority_scores
from data.mock_data_generator import generate_mock_data

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_pipeline")


def run(n_general: int, n_spike: int):
    validate_config()

    logger.info("Step 1/4: Generating mock feedback data...")
    raw_rows = generate_mock_data(n_general=n_general, n_spike=n_spike)
    logger.info(f"  -> {len(raw_rows)} raw rows generated")

    logger.info("Step 2/4: Cleaning + classifying each row via Gemini "
                "(this is the slow step, one API call per row)...")
    processed_rows = []
    for i, row in enumerate(raw_rows, start=1):
        cleaned = clean_text(row["raw_text"])
        result = classify_feedback(cleaned)

        processed_rows.append({
            "source": row["source"],
            "raw_text": row["raw_text"],
            "clean_text": cleaned,
            "created_at": datetime.datetime.fromisoformat(row["created_at"]),
            "category": result["category"],
            "sentiment": result["sentiment"],
            "urgency_score": result["urgency_score"],
        })

        if i % 25 == 0 or i == len(raw_rows):
            logger.info(f"  -> classified {i}/{len(raw_rows)}")

    logger.info("Step 3/4: Computing priority scores...")
    df = pd.DataFrame(processed_rows)
    df = compute_priority_scores(df)

    logger.info("Step 4/4: Loading into database (clearing old rows first)...")
    clear_feedback_table()
    insert_feedback_batch(df.to_dict(orient="records"))

    logger.info(f"Done. {len(df)} rows loaded into the 'feedback' table.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the TriageIQ data pipeline")
    parser.add_argument("--rows", type=int, default=350, help="Number of general feedback rows")
    parser.add_argument("--spike", type=int, default=22, help="Number of rows in the seeded spike")
    args = parser.parse_args()

    run(n_general=args.rows, n_spike=args.spike)
