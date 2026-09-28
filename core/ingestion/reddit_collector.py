"""
Dual-Mode Reddit Data Collector for TriageIQ.

Operates in two modes:
1. Zero-Auth Live RSS/Atom Mode (Primary / Default):
   Fetches public subreddit feeds (https://www.reddit.com/r/{subreddit}/new/.rss)
   with zero credentials or registration required. Fully immune to Reddit's
   new Responsible Builder Policy restrictions.
2. PRAW OAuth Mode (Authenticated / Secondary):
   Used automatically if REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET are configured.
3. High-Fidelity Seed Fallback:
   If Reddit rate-limits (HTTP 429) or when running offline/in CI, seamlessly
   serves realistic domain feedback from data/reddit_mock_posts.json.
"""

import json
import logging
import os
import re
import html
import time
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

from core.config import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
    REDDIT_SUBREDDITS,
)

logger = logging.getLogger("reddit_collector")

DEFAULT_CHECKPOINT_FILE = "data/reddit_checkpoint.json"
DEFAULT_SEED_FILE = "data/reddit_mock_posts.json"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def get_reddit_checkpoint(filepath: str = DEFAULT_CHECKPOINT_FILE) -> Optional[float]:
    """Reads the last ingested UTC epoch timestamp from checkpoint file."""
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("since_utc")
        except Exception as e:
            logger.warning(f"Could not read Reddit checkpoint: {e}")
            return None
    return None


def save_reddit_checkpoint(since_utc: Optional[float], filepath: str = DEFAULT_CHECKPOINT_FILE):
    """Persists newest ingested UTC epoch timestamp."""
    if since_utc:
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump({"since_utc": float(since_utc)}, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist Reddit checkpoint: {e}")


class RedditCollector:
    """Ingests, cleans, and standardizes Reddit posts into TriageIQ feedback rows."""

    def __init__(
        self,
        client_id: str = REDDIT_CLIENT_ID,
        client_secret: str = REDDIT_CLIENT_SECRET,
        user_agent: str = REDDIT_USER_AGENT,
    ):
        self.client_id = client_id.strip() if client_id else ""
        self.client_secret = client_secret.strip() if client_secret else ""
        self.user_agent = user_agent.strip() if user_agent else "TriageIQ/1.0"
        self.has_oauth = bool(self.client_id and self.client_secret)
        self.praw_client = None

        if self.has_oauth:
            try:
                import praw
                self.praw_client = praw.Reddit(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    user_agent=self.user_agent,
                    check_for_async=False,
                )
                self.praw_client.read_only = True
                logger.info("RedditCollector initialized in PRAW OAuth mode.")
            except ImportError:
                logger.warning("PRAW not installed. Falling back to Zero-Auth RSS mode.")
                self.has_oauth = False
            except Exception as e:
                logger.warning(f"Failed to initialize PRAW: {e}. Falling back to Zero-Auth RSS mode.")
                self.has_oauth = False
        else:
            logger.info("RedditCollector initialized in Zero-Auth RSS/Atom mode (No credentials required).")

    def fetch_recent_posts(
        self,
        subreddits: str | List[str] = REDDIT_SUBREDDITS,
        since_utc: Optional[float] = None,
        limit: int = 25,
    ) -> Tuple[List[Dict], Optional[float]]:
        """Fetches recent posts across target subreddits newer than since_utc.

        Returns:
            Tuple[List[Dict], Optional[float]]: (normalized_rows, newest_timestamp)
        """
        # Parse subreddits input
        if isinstance(subreddits, str):
            sub_list = [s.strip() for s in subreddits.replace("+", ",").split(",") if s.strip()]
        else:
            sub_list = [s.strip() for s in subreddits if s.strip()]

        if not sub_list:
            sub_list = ["swiggy"]

        # Strategy 1: Attempt PRAW OAuth if credentials provided
        if self.has_oauth and self.praw_client:
            try:
                return self._fetch_via_praw(sub_list, since_utc, limit)
            except Exception as e:
                logger.warning(f"PRAW fetch failed ({e}). Falling back to Zero-Auth RSS feed...")

        # Strategy 2: Zero-Auth Live RSS / Atom Feeds
        rows, max_utc = self._fetch_via_rss(sub_list, since_utc, limit)
        if rows:
            return rows, max_utc

        # Strategy 3: Seed Fallback (Offline / Rate-limit safety)
        logger.info("Serving high-fidelity seed fallback dataset for Reddit ingestion.")
        return self._load_seed_fallback(since_utc, limit)

    def _fetch_via_praw(
        self,
        subreddits: List[str],
        since_utc: Optional[float],
        limit: int,
    ) -> Tuple[List[Dict], Optional[float]]:
        """Fetches submissions using official PRAW OAuth client."""
        sub_query = "+".join(subreddits)
        subreddit = self.praw_client.subreddit(sub_query)
        rows: List[Dict] = []
        max_utc = since_utc or 0.0

        for post in subreddit.new(limit=max(5, min(limit, 100))):
            if post.stickied:
                continue
            if since_utc and post.created_utc <= since_utc:
                continue

            if post.created_utc > max_utc:
                max_utc = post.created_utc

            full_text = post.title.strip()
            if post.selftext:
                full_text += f" - {post.selftext.strip()}"

            created_dt = datetime.fromtimestamp(post.created_utc, timezone.utc)
            rows.append({
                "source": "reddit",
                "external_id": f"reddit_{post.id}",
                "raw_text": full_text,
                "created_at": created_dt.isoformat(),
            })

        new_checkpoint = max_utc if max_utc > 0 else since_utc
        return rows, new_checkpoint

    def _fetch_via_rss(
        self,
        subreddits: List[str],
        since_utc: Optional[float],
        limit: int,
    ) -> Tuple[List[Dict], Optional[float]]:
        """Fetches submissions via public Reddit Atom RSS feeds without authentication."""
        rows: List[Dict] = []
        max_utc = since_utc or 0.0
        per_sub_limit = max(5, min(limit // max(1, len(subreddits)), 25))

        for idx, sub in enumerate(subreddits):
            if idx > 0:
                time.sleep(1.0)  # Polite pacing between multiple subreddit requests

            url = f"https://www.reddit.com/r/{sub}/new/.rss?limit={per_sub_limit}"
            req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})

            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    xml_data = resp.read()
                    sub_rows, sub_max_utc = self._parse_atom_xml(xml_data, since_utc)
                    rows.extend(sub_rows)
                    if sub_max_utc and sub_max_utc > max_utc:
                        max_utc = sub_max_utc
            except urllib.error.HTTPError as he:
                logger.warning(f"Reddit RSS HTTP {he.code} for r/{sub}: {he.reason}")
            except Exception as e:
                logger.warning(f"Could not fetch Reddit RSS for r/{sub}: {e}")

        new_checkpoint = max_utc if max_utc > 0 else since_utc
        return rows, new_checkpoint

    def _parse_atom_xml(
        self,
        xml_bytes: bytes,
        since_utc: Optional[float] = None,
    ) -> Tuple[List[Dict], Optional[float]]:
        """Parses Reddit Atom XML into standardized TriageIQ rows."""
        root = ET.fromstring(xml_bytes)
        rows: List[Dict] = []
        max_utc = since_utc or 0.0

        for entry in root.findall("atom:entry", ATOM_NS):
            id_node = entry.find("atom:id", ATOM_NS)
            title_node = entry.find("atom:title", ATOM_NS)
            updated_node = entry.find("atom:updated", ATOM_NS)
            content_node = entry.find("atom:content", ATOM_NS)

            if id_node is None or title_node is None or updated_node is None:
                continue

            raw_id = id_node.text or ""
            post_id = raw_id.split("/")[-1].replace("t3_", "")
            title = (title_node.text or "").strip()

            # Parse ISO UTC timestamp
            updated_str = updated_node.text or ""
            try:
                dt = datetime.fromisoformat(updated_str)
                post_utc = dt.timestamp()
            except Exception:
                post_utc = time.time()
                dt = datetime.fromtimestamp(post_utc, timezone.utc)

            # Skip older posts if watermark is set
            if since_utc and post_utc <= since_utc:
                continue

            if post_utc > max_utc:
                max_utc = post_utc

            # Extract body text from content HTML if present
            raw_html = content_node.text if content_node is not None else ""
            body = self._extract_clean_body_from_html(raw_html)

            full_text = f"{title} - {body}" if body else title

            rows.append({
                "source": "reddit",
                "external_id": f"reddit_{post_id}",
                "raw_text": full_text,
                "created_at": dt.isoformat(),
            })

        return rows, (max_utc if max_utc > 0 else since_utc)

    @staticmethod
    def _extract_clean_body_from_html(raw_html: str) -> str:
        """Extracts clean selftext from Reddit's atom:content HTML block."""
        if not raw_html:
            return ""

        # Reddit encapsulates selftext markdown between <!-- SC_OFF --> and <!-- SC_ON -->
        sc_match = re.search(r"<!-- SC_OFF -->(.*?)<!-- SC_ON -->", raw_html, re.DOTALL)
        body_html = sc_match.group(1) if sc_match else ""

        if not body_html:
            return ""

        # Remove HTML tags and decode entities
        text = re.sub(r"<[^>]+>", " ", body_html)
        text = html.unescape(text)
        # Clean boilerplate links like '[link] [comments]' or 'submitted by'
        text = re.sub(r"\[link\]|\[comments\]", "", text, flags=re.IGNORECASE)
        text = re.sub(r"submitted by.*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _load_seed_fallback(
        self,
        since_utc: Optional[float] = None,
        limit: int = 25,
    ) -> Tuple[List[Dict], Optional[float]]:
        """Loads curated high-signal Reddit posts from data/reddit_mock_posts.json."""
        seed_path = DEFAULT_SEED_FILE
        if not os.path.exists(seed_path):
            return [], since_utc

        try:
            with open(seed_path, "r", encoding="utf-8") as f:
                seed_data = json.load(f)

            rows: List[Dict] = []
            max_utc = since_utc or 0.0

            for item in seed_data[:limit]:
                dt_str = item.get("created_at", "")
                try:
                    dt = datetime.fromisoformat(dt_str)
                    post_utc = dt.timestamp()
                except Exception:
                    post_utc = time.time()

                if since_utc and post_utc <= since_utc:
                    continue

                if post_utc > max_utc:
                    max_utc = post_utc

                rows.append({
                    "source": "reddit",
                    "external_id": item.get("external_id", f"reddit_{int(post_utc)}"),
                    "raw_text": item.get("raw_text", ""),
                    "created_at": item.get("created_at", datetime.now(timezone.utc).isoformat()),
                })

            return rows, (max_utc if max_utc > 0 else since_utc)
        except Exception as e:
            logger.error(f"Error reading seed fallback: {e}")
            return [], since_utc
