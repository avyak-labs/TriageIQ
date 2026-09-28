"""
One-command pipeline: ingest feedback (mock synthetic generator or live Reddit)
-> clean -> classify via Gemini -> compute priority scores -> load into Postgres.

Usage:
    # 1. Run offline synthetic generator (default)
    python -m scripts.run_pipeline --source mock --rows 350 --spike 22

    # 2. Run live Reddit ingestion
    python -m scripts.run_pipeline --source reddit --subreddits swiggy,GooglePixel --rows 25

    # 3. Append to database instead of wiping
    python -m scripts.run_pipeline --source reddit --append
"""
import argparse
import datetime
import logging

from core.config import validate_config, GEMINI_BATCH_SIZE, REDDIT_SUBREDDITS, REDDIT_MAX_POSTS
from core.database import clear_feedback_table, insert_feedback_batch
from core.preprocessing import clean_text
from core.ai_classifier import classify_feedback_batch, chunk_list
from core.priority_engine import compute_priority_scores
from core.ingestion.reddit_collector import RedditCollector, get_reddit_checkpoint, save_reddit_checkpoint
from data.mock_data_generator import generate_mock_data

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_pipeline")


def run(
    source: str = "mock",
    n_general: int = 350,
    n_spike: int = 22,
    subreddits: str = REDDIT_SUBREDDITS,
    append: bool = False,
):
    validate_config()

    logger.info(f"Step 1/4: Ingesting raw feedback from source: '{source}'...")
    if source == "reddit":
        collector = RedditCollector()
        checkpoint = get_reddit_checkpoint()
        raw_rows, new_checkpoint = collector.fetch_recent_posts(
            subreddits=subreddits,
            since_utc=checkpoint,
            limit=n_general,
        )
        if new_checkpoint:
            save_reddit_checkpoint(new_checkpoint)
        logger.info(f"  -> Ingested {len(raw_rows)} raw rows from Reddit (r/{subreddits})")
    else:
        raw_rows = generate_mock_data(n_general=n_general, n_spike=n_spike)
        logger.info(f"  -> {len(raw_rows)} raw rows generated from mock generator")

    if not raw_rows:
        logger.warning("No rows ingested (possibly no new posts since last watermark). Exiting pipeline.")
        return

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

    logger.info("Step 4/4: Loading into database...")
    if not append:
        logger.info("  -> Clearing old rows first for clean idempotency...")
        clear_feedback_table()
    else:
        logger.info("  -> Appending rows to existing table...")

    insert_feedback_batch(df.to_dict(orient="records"))
    logger.info(f"Done. {len(df)} rows loaded into the 'feedback' table.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the TriageIQ data pipeline")
    parser.add_argument(
        "--source",
        choices=["mock", "reddit"],
        default="mock",
        help="Data ingestion source: 'mock' (default synthetic) or 'reddit' (live subreddits)"
    )
    parser.add_argument("--rows", type=int, default=350, help="Number of rows to fetch/generate")
    parser.add_argument("--spike", type=int, default=22, help="Number of rows in the seeded spike (mock source only)")
    parser.add_argument(
        "--subreddits",
        type=str,
        default=REDDIT_SUBREDDITS,
        help="Subreddits to monitor when using --source reddit (comma-separated, e.g. 'swiggy,GooglePixel')"
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append rows to the database instead of clearing previous rows"
    )
    args = parser.parse_args()

    limit_rows = args.rows
    if args.source == "reddit" and args.rows == 350:
        limit_rows = REDDIT_MAX_POSTS

    run(
        source=args.source,
        n_general=limit_rows,
        n_spike=args.spike,
        subreddits=args.subreddits,
        append=args.append,
    )
