"""
Basic cleanup of raw feedback text before it goes to the AI classifier.
Deliberately simple (no NLP libraries) so it's easy to read and extend.
"""
import re

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # symbols & pictographs, supplemental
    "\U00002600-\U000027BF"  # misc symbols & dingbats
    "\U0001F1E6-\U0001F1FF"  # flags
    "]+",
    flags=re.UNICODE,
)
_MULTI_SPACE_RE = re.compile(r"\s+")


def clean_text(raw_text: str) -> str:
    """Strips HTML, URLs, emojis, and collapses whitespace.
    Keeps punctuation and casing — the AI classifier benefits from
    tone cues like exclamation marks and capitalization."""
    if not raw_text:
        return ""

    text = _HTML_TAG_RE.sub(" ", raw_text)
    text = _URL_RE.sub(" ", text)
    text = _EMOJI_RE.sub(" ", text)
    text = _MULTI_SPACE_RE.sub(" ", text).strip()
    return text
