"""
Sends cleaned feedback text to Gemini and gets back structured tags:
category, sentiment, and urgency_score.

Handles the messy reality of LLM output: markdown code fences around
JSON, occasional malformed responses, and API errors. On any failure,
falls back to a safe default rather than crashing the whole batch —
one bad row should never stop the pipeline.
"""
import json
import re
import time
import logging

import google.generativeai as genai

from core.config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_RPM, GEMINI_BATCH_SIZE

logger = logging.getLogger("ai_classifier")

VALID_CATEGORIES = {"Bug", "Feature Request", "Complaint", "Spam", "Praise"}
VALID_SENTIMENTS = {"Positive", "Neutral", "Negative"}

FALLBACK_RESULT = {
    "category": "Uncategorized",
    "sentiment": "Neutral",
    "urgency_score": 1,
}

_PROMPT_TEMPLATE = """You are classifying a single piece of user feedback for a digital product.

Feedback text: "{text}"

Respond with ONLY a JSON object (no markdown, no explanation) with exactly these fields:
{{
  "category": one of "Bug", "Feature Request", "Complaint", "Spam", "Praise",
  "sentiment": one of "Positive", "Neutral", "Negative",
  "urgency_score": integer from 1 (trivial) to 5 (critical, e.g. payment/checkout failure)
}}
"""

_model = None
_active_model_name = None
_resolution_attempted = False
_resolution_error = None

# Models to try, in order, if the configured GEMINI_MODEL isn't available
# for this API key. Google has been changing model availability frequently,
# so this makes the pipeline self-healing across most of those changes
# without needing a code or .env edit every time.
FALLBACK_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-flash-latest",
    "gemini-2.5-flash",
]

# --- Client-side rate limiting ---
# Proactively spaces out requests to stay under the free-tier RPM limit,
# instead of firing as fast as possible and reacting to 429s after the
# fact. This is what actually prevents most rate-limit errors.
_last_call_at = [0.0]


def _throttle():
    min_interval = 60.0 / GEMINI_RPM
    elapsed = time.time() - _last_call_at[0]
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _last_call_at[0] = time.time()


_RETRY_DELAY_RE = re.compile(r"retry in (\d+\.?\d*)s", re.IGNORECASE)


def _extract_retry_delay(error_str: str, default: float = 20.0) -> float:
    """Gemini's 429 errors include a suggested wait time in the message
    itself (e.g. 'Please retry in 41.02s'). Use that instead of guessing,
    so we wait exactly as long as needed and no longer."""
    match = _RETRY_DELAY_RE.search(error_str)
    if match:
        return min(float(match.group(1)) + 1, 65.0)  # +1s buffer, cap the wait
    return default


def _is_model_unavailable_error(err_str: str) -> bool:
    """Matches the family of 404 errors Google returns when a model name
    is deprecated, shut down, or no longer available to this account —
    as opposed to a transient network/rate-limit error, which should be
    retried on the SAME model rather than triggering a model switch."""
    err_lower = err_str.lower()
    return "404" in err_str and (
        "no longer available" in err_lower
        or "not found" in err_lower
        or "not supported for generatecontent" in err_lower
    )


def _resolve_model():
    """Finds a Gemini model that actually works for this API key by
    trying the configured model first, then known-current fallbacks.
    Runs once per process; the result is cached in _model. If every
    candidate fails, the error is also cached so we fail fast instead
    of re-probing all candidates on every single row."""
    global _model, _active_model_name

    genai.configure(api_key=GEMINI_API_KEY, transport="rest")
    # transport="rest" avoids the default gRPC transport's internal
    # retry-on-connection-error behavior, which can ignore our per-call
    # timeout and hang far longer than expected on a flaky network.
    # REST fails predictably within the timeout instead.

    candidates = [GEMINI_MODEL] + [m for m in FALLBACK_MODELS if m != GEMINI_MODEL]

    last_error = None
    for name in candidates:
        try:
            _throttle()
            candidate = genai.GenerativeModel(name)
            candidate.generate_content(  # minimal live check this model actually works
                "Reply with just the word OK.",
                request_options={"timeout": 15},
            )
            _model = candidate
            _active_model_name = name
            if name != GEMINI_MODEL:
                logger.warning(
                    f"Configured model '{GEMINI_MODEL}' isn't available for this "
                    f"API key — using '{name}' instead. Consider updating "
                    f"GEMINI_MODEL in your .env to '{name}' to skip this check next time."
                )
            else:
                logger.info(f"Using Gemini model: {name}")
            return
        except Exception as e:
            err_str = str(e)
            last_error = e
            if _is_model_unavailable_error(err_str):
                logger.warning(f"Model '{name}' unavailable for this API key, trying next candidate...")
                continue
            # Some other error (rate limit, network hiccup) during the
            # check — don't discard a possibly-fine model over a flaky probe.
            _model = candidate
            _active_model_name = name
            logger.warning(f"Could not fully verify model '{name}' ({e}); proceeding with it anyway.")
            return

    raise RuntimeError(
        f"None of these Gemini models are available for your API key: {candidates}. "
        f"Check https://ai.google.dev/gemini-api/docs/models for current model names "
        f"and set GEMINI_MODEL in your .env. Last error: {last_error}"
    )


def _get_model():
    global _resolution_attempted, _resolution_error
    if _model is not None:
        return _model
    if _resolution_attempted:
        raise _resolution_error
    _resolution_attempted = True
    try:
        _resolve_model()
    except Exception as e:
        _resolution_error = e
        raise
    return _model


def _extract_json(raw_response: str) -> dict:
    """Gemini sometimes wraps JSON in ```json ... ``` fences, or adds
    stray text around it. Strip that before parsing."""
    text = raw_response.strip()
    text = re.sub(r"^```(json)?", "", text.strip())
    text = re.sub(r"```$", "", text.strip())
    text = text.strip()

    # If there's still leading/trailing junk, grab the outermost { ... }
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)

    return json.loads(text)


def _validate(result: dict) -> dict:
    category = result.get("category")
    sentiment = result.get("sentiment")
    urgency = result.get("urgency_score")

    if category not in VALID_CATEGORIES:
        category = "Uncategorized"
    if sentiment not in VALID_SENTIMENTS:
        sentiment = "Neutral"
    try:
        urgency = int(urgency)
        urgency = min(max(urgency, 1), 5)
    except (TypeError, ValueError):
        urgency = 1

    return {"category": category, "sentiment": sentiment, "urgency_score": urgency}


def classify_feedback(clean_text: str, retries: int = 2) -> dict:
    """Returns {category, sentiment, urgency_score}. Never raises —
    falls back to a safe default only after genuinely exhausting
    retries, so one bad row doesn't kill a whole batch run."""
    if not clean_text.strip():
        return dict(FALLBACK_RESULT)

    prompt = _PROMPT_TEMPLATE.format(text=clean_text[:2000])  # guard against huge inputs
    attempts = retries + 1

    for attempt in range(attempts):
        try:
            _throttle()
            model = _get_model()
            response = model.generate_content(
                prompt,
                request_options={"timeout": 20},  # never hang forever on a network hiccup
            )
            parsed = _extract_json(response.text)
            return _validate(parsed)
        except Exception as e:
            err_str = str(e)
            is_rate_limit = "429" in err_str or "quota" in err_str.lower() or "TooManyRequests" in type(e).__name__

            logger.warning(f"Classification attempt {attempt + 1}/{attempts} failed: {e}")
            if attempt < attempts - 1:
                if is_rate_limit:
                    wait = _extract_retry_delay(err_str)
                    logger.info(f"  Rate limited — waiting {wait:.0f}s before retry (this is expected on the free tier)")
                    time.sleep(wait)
                else:
                    time.sleep(1.5)  # brief backoff before retry on other errors
            continue

    logger.error(f"Classification failed after {attempts} attempts, using fallback. Text: {clean_text[:80]!r}")
    return dict(FALLBACK_RESULT)


# --- Batch classification ---
# Sends multiple rows in a single prompt instead of one call per row.
# This is the main lever for speed and free-tier quota efficiency:
# ~370 rows at batch size 15 is ~25 requests instead of ~370.

_BATCH_PROMPT_TEMPLATE = """You are classifying multiple pieces of user feedback for a digital product.

Feedback items:
{items}

Respond with ONLY a JSON array (no markdown, no explanation) with exactly {count} objects, in the SAME ORDER as the input, one object per feedback item. Each object must have exactly these fields:
{{
  "category": one of "Bug", "Feature Request", "Complaint", "Spam", "Praise",
  "sentiment": one of "Positive", "Neutral", "Negative",
  "urgency_score": integer from 1 (trivial) to 5 (critical, e.g. payment/checkout failure)
}}
"""


def _extract_json_array(raw_response: str) -> list:
    """Same idea as _extract_json, but for a JSON array response instead
    of a single object — strips markdown fences and grabs the outermost
    [ ... ] block in case the model added stray text around it."""
    text = raw_response.strip()
    text = re.sub(r"^```(json)?", "", text.strip())
    text = re.sub(r"```$", "", text.strip())
    text = text.strip()

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        text = match.group(0)

    return json.loads(text)


def classify_feedback_batch(clean_texts: list[str], retries: int = 2) -> list[dict]:
    """Classifies multiple rows in ONE Gemini request. Returns a list of
    {category, sentiment, urgency_score} dicts, same length and order as
    clean_texts. Never raises — any failure falls back to safe defaults
    for the whole batch, same guarantee as classify_feedback().

    Empty strings are handled locally (no point spending a request slot
    on them) and merged back into the right position afterward.
    """
    if not clean_texts:
        return []

    non_empty_indices = [i for i, t in enumerate(clean_texts) if t.strip()]
    if not non_empty_indices:
        return [dict(FALLBACK_RESULT) for _ in clean_texts]

    texts_to_send = [clean_texts[i][:1000] for i in non_empty_indices]  # guard against huge inputs
    items_text = "\n".join(f'{i + 1}. "{t}"' for i, t in enumerate(texts_to_send))
    prompt = _BATCH_PROMPT_TEMPLATE.format(items=items_text, count=len(texts_to_send))
    attempts = retries + 1

    for attempt in range(attempts):
        try:
            _throttle()
            model = _get_model()
            response = model.generate_content(
                prompt,
                request_options={"timeout": 60},  # batches take longer than single-row calls
            )
            parsed_list = _extract_json_array(response.text)
            results = [_validate(item) for item in parsed_list]

            if len(results) != len(texts_to_send):
                logger.warning(
                    f"Batch returned {len(results)} results for {len(texts_to_send)} inputs "
                    f"— padding/truncating to match."
                )
                if len(results) < len(texts_to_send):
                    results += [dict(FALLBACK_RESULT) for _ in range(len(texts_to_send) - len(results))]
                else:
                    results = results[:len(texts_to_send)]

            # merge results back into their original positions, with
            # fallback already in place for the empty-text slots
            full_results = [dict(FALLBACK_RESULT) for _ in clean_texts]
            for idx, result in zip(non_empty_indices, results):
                full_results[idx] = result
            return full_results

        except Exception as e:
            err_str = str(e)
            is_rate_limit = "429" in err_str or "quota" in err_str.lower() or "TooManyRequests" in type(e).__name__

            logger.warning(f"Batch classification attempt {attempt + 1}/{attempts} failed: {e}")
            if attempt < attempts - 1:
                if is_rate_limit:
                    wait = _extract_retry_delay(err_str)
                    logger.info(f"  Rate limited — waiting {wait:.0f}s before retry")
                    time.sleep(wait)
                else:
                    time.sleep(1.5)
            continue

    logger.error(f"Batch classification failed after {attempts} attempts, using fallback for {len(clean_texts)} items")
    return [dict(FALLBACK_RESULT) for _ in clean_texts]


def chunk_list(items: list, chunk_size: int) -> list[list]:
    """Splits a list into consecutive chunks of at most chunk_size —
    used by scripts/run_pipeline.py to build batches."""
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


# --- Ticket title generation ---
# Separate from row classification: called once per DETECTED SPIKE (rare),
# never per row, so it's cheap even on the free tier. Deliberately kept
# out of core/anomaly_detector.py so that module stays a pure, API-free,
# easily-testable function — this is the one "impure" AI enrichment step,
# and it lives here alongside the other Gemini calls instead of leaking
# into the detection logic itself.

_TITLE_PROMPT_TEMPLATE = """You are a product manager writing a short, specific bug-ticket title for a cluster of similar user complaints.

Sample complaints:
{samples}

Respond with ONLY the title text (no quotes, no explanation) — 3 to 8 words, specific enough to identify the actual issue. Good: "PhonePe / UPI Checkout Failures on iOS". Bad (too generic): "Payment Issue"."""


def generate_ticket_title(sample_reviews: list[str], fallback: str) -> str:
    """Generates a short, specific title for a detected anomaly cluster.
    This is a nice-to-have for the dashboard — on any failure, it falls
    back to the generic title anomaly_detector.py already produced,
    rather than blocking ticket generation."""
    if not sample_reviews:
        return fallback

    try:
        _throttle()
        model = _get_model()
        samples_text = "\n".join(f"- {s}" for s in sample_reviews[:5])
        prompt = _TITLE_PROMPT_TEMPLATE.format(samples=samples_text)
        response = model.generate_content(prompt, request_options={"timeout": 20})
        title = response.text.strip().strip('"').strip()
        if title and len(title) < 100:
            return title
        return fallback
    except Exception as e:
        logger.warning(f"Ticket title generation failed, using generic fallback: {e}")
        return fallback
