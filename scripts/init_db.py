"""
Creates the 'feedback' table in your Postgres (Neon) database.
Run this once after setting up your .env file, and again any time
you change the schema in core/models.py.

Usage: python -m scripts.init_db
"""
from core.config import validate_config
from core.database import init_db

if __name__ == "__main__":
    validate_config()
    init_db()
    print("Database initialized: 'feedback' table is ready.")
