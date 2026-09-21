"""
Loads configuration from environment variables (.env file).
Keeping this in one place means nothing else in the project
needs to know HOW settings are loaded, only that they exist.
"""
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Which Gemini model to try first. gemini-3.5-flash-lite is current as
# of testing this, but Google has been changing model availability
# often — if this exact name goes stale, the classifier automatically
# tries a short list of fallbacks (see FALLBACK_MODELS in
# core/ai_classifier.py) before giving up, so you shouldn't need to
# edit this on every Google model change.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

# Client-side throttle: max requests per minute we allow ourselves to
# send, kept a little under the model's actual free-tier RPM limit as
# safety margin. This prevents hitting 429 errors in the first place,
# rather than just reacting to them after the fact.
GEMINI_RPM = int(os.getenv("GEMINI_RPM", "12"))

# How many feedback rows to send to Gemini in a single request. Batching
# turns ~370 individual API calls into ~25, which is both far faster and
# much friendlier to the free-tier daily request quota. Larger batches
# use fewer requests but risk the model returning a malformed/truncated
# array for very long prompts — 15 is a reasonable middle ground.
GEMINI_BATCH_SIZE = int(os.getenv("GEMINI_BATCH_SIZE", "15"))

# How many similar complaints in the SPIKE_WINDOW_MINUTES window
# count as an "anomaly" worth auto-generating a ticket for.
SPIKE_THRESHOLD = int(os.getenv("SPIKE_THRESHOLD", "5"))
SPIKE_WINDOW_MINUTES = int(os.getenv("SPIKE_WINDOW_MINUTES", "60"))


def validate_config():
    """Called at startup by scripts that need real credentials.
    Fails loudly and early instead of a confusing error later."""
    missing = []
    if not DATABASE_URL:
        missing.append("DATABASE_URL")
    if not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Copy .env.example to .env and fill these in. See SETUP.md."
        )
