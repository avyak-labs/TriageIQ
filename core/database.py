"""
All direct database access lives here. Everything else in the project
(app.py, scripts/) calls these functions instead of touching SQLAlchemy
sessions directly — makes it obvious where DB logic lives, and easy to
swap the database later if you ever need to.
"""
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config import DATABASE_URL
from core.models import Base, FeedbackItem

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        if not DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is not set. Copy .env.example to .env and fill it in."
            )
        _engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    return _engine


def get_session():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal()


def init_db():
    """Creates the feedback table if it doesn't already exist."""
    Base.metadata.create_all(get_engine())


def clear_feedback_table():
    """Wipes all rows. Called at the start of run_pipeline.py so
    re-running the pipeline is idempotent (no duplicate rows)."""
    session = get_session()
    try:
        session.query(FeedbackItem).delete()
        session.commit()
    finally:
        session.close()


def insert_feedback_batch(rows: list[dict]):
    """rows: list of dicts matching FeedbackItem columns
    (source, raw_text, clean_text, created_at, category, sentiment,
    urgency_score, priority_score)."""
    session = get_session()
    try:
        objects = [FeedbackItem(**row) for row in rows]
        session.add_all(objects)
        session.commit()
    finally:
        session.close()


def fetch_all_feedback() -> pd.DataFrame:
    """Returns the whole feedback table as a DataFrame. Used by the
    dashboard and by the priority/anomaly logic."""
    session = get_session()
    try:
        rows = session.query(FeedbackItem).all()
        data = [r.as_dict() for r in rows]
        return pd.DataFrame(data)
    finally:
        session.close()
