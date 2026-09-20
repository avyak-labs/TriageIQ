"""
Single table for the whole project: one row per piece of feedback,
enriched with whatever the AI classifier extracted from it.

Kept deliberately flat (no joins, no foreign keys) so it's easy
to read, query, and export straight to a dataframe.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import declarative_base
import datetime

Base = declarative_base()


class FeedbackItem(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Raw input
    source = Column(String(50), nullable=False)        # app_review | tweet | support_ticket
    raw_text = Column(Text, nullable=False)
    clean_text = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    # AI-derived fields (from core/ai_classifier.py)
    category = Column(String(50), nullable=False, default="Uncategorized")   # Bug | Feature Request | Complaint | Spam | Praise
    sentiment = Column(String(20), nullable=False, default="Neutral")        # Positive | Neutral | Negative
    urgency_score = Column(Integer, nullable=False, default=1)               # 1 (low) - 5 (critical)

    # Computed at query time by core/priority_engine.py, but we keep a
    # cached column too so the dashboard doesn't need to recompute on load.
    priority_score = Column(Float, nullable=False, default=0.0)

    def as_dict(self):
        return {
            "id": self.id,
            "source": self.source,
            "raw_text": self.raw_text,
            "clean_text": self.clean_text,
            "created_at": self.created_at,
            "category": self.category,
            "sentiment": self.sentiment,
            "urgency_score": self.urgency_score,
            "priority_score": self.priority_score,
        }
