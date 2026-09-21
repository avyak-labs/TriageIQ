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

from core.config import validate_config, GEMINI_BATCH_SIZE
from core.database import clear_feedback_table, insert_feedback_batch
from core.preprocessing import clean_text
from core.ai_classifier import classify_feedback_batch, chunk_list
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

    logger.info(f"Step 2/4: Cleaning + classifying via Gemini in batches of "
                f"{GEMINI_BATCH_SIZE} (much faster than one call per row)...")
    cleaned_rows = [
        {**row, "clean_text": clean_text(row["raw_text"])}
        for row in raw_rows
    ]
    batches = chunk_list(cleaned_rows, GEMINI_BATCH_SIZE)

    processed_rows = []
    classified_count = 0
    for batch_num, batch in enumerate(batches, start=1):
        texts = [row["clean_text"] for row in batch]
        results = classify_feedback_batch(texts)

        for row, result in zip(batch, results):
            processed_rows.append({
                "source": row["source"],
                "raw_text": row["raw_text"],
                "clean_text": row["clean_text"],
                "created_at": datetime.datetime.fromisoformat(row["created_at"]),
                "category": result["category"],
                "sentiment": result["sentiment"],
                "urgency_score": result["urgency_score"],
            })

        classified_count += len(batch)
        logger.info(f"  -> classified {classified_count}/{len(raw_rows)} "
                    f"(batch {batch_num}/{len(batches)})")

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
