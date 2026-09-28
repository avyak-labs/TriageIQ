"""
Unit tests for the RedditCollector ingestion module.
Tests Atom XML parsing, watermark checkpointing, HTML cleaning,
and seed fallback mechanisms without requiring external network or live Reddit calls.
"""

import os
import json
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from core.ingestion.reddit_collector import (
    RedditCollector,
    get_reddit_checkpoint,
    save_reddit_checkpoint,
)

SAMPLE_ATOM_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>new posts in swiggy</title>
  <entry>
    <id>t3_test01</id>
    <title>UPI payment failed on checkout</title>
    <updated>2026-09-28T12:00:00+00:00</updated>
    <content type="html">&lt;!-- SC_OFF --&gt;&lt;div class="md"&gt;&lt;p&gt;Money debited via GPay but order was cancelled.&lt;/p&gt;&lt;/div&gt;&lt;!-- SC_ON --&gt; &#32; submitted by &#32; &lt;a href="https://reddit.com/u/user1"&gt; /u/user1 &lt;/a&gt; &lt;span&gt;&lt;a href="https://reddit.com/link1"&gt;[link]&lt;/a&gt;&lt;/span&gt;</content>
  </entry>
  <entry>
    <id>t3_test02</id>
    <title>Delivery address issue</title>
    <updated>2026-09-28T11:00:00+00:00</updated>
    <content type="html">&lt;!-- SC_OFF --&gt;&lt;div class="md"&gt;&lt;p&gt;Saved address disappeared.&lt;/p&gt;&lt;/div&gt;&lt;!-- SC_ON --&gt;</content>
  </entry>
</feed>
"""


def test_parse_atom_xml():
    collector = RedditCollector(client_id="", client_secret="")
    rows, max_utc = collector._parse_atom_xml(SAMPLE_ATOM_XML, since_utc=None)

    assert len(rows) == 2
    assert rows[0]["source"] == "reddit"
    assert rows[0]["external_id"] == "reddit_test01"
    assert "UPI payment failed on checkout" in rows[0]["raw_text"]
    assert "Money debited via GPay" in rows[0]["raw_text"]
    assert "[link]" not in rows[0]["raw_text"]
    assert max_utc is not None
    assert max_utc > 0


def test_parse_atom_xml_with_since_utc_watermark():
    collector = RedditCollector(client_id="", client_secret="")
    # Checkpoint set between test02 (11:00) and test01 (12:00)
    since_utc = 1790593200.0  # Around 11:30 UTC
    rows, _ = collector._parse_atom_xml(SAMPLE_ATOM_XML, since_utc=since_utc)

    # Only test01 (12:00) should be included, test02 (11:00) should be skipped
    assert len(rows) == 1
    assert rows[0]["external_id"] == "reddit_test01"


def test_extract_clean_body_from_html():
    raw_html = (
        '<!-- SC_OFF --><div class="md"><p>App crashed during checkout &amp; payment!</p></div>'
        '<!-- SC_ON --> submitted by /u/someone <span>[link]</span> <span>[comments]</span>'
    )
    cleaned = RedditCollector._extract_clean_body_from_html(raw_html)
    assert cleaned == "App crashed during checkout & payment!"


def test_checkpoint_save_and_get():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        temp_path = tf.name

    try:
        assert get_reddit_checkpoint(temp_path) is None

        save_reddit_checkpoint(1727500000.5, temp_path)
        loaded = get_reddit_checkpoint(temp_path)
        assert loaded == 1727500000.5
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_seed_fallback_when_offline():
    collector = RedditCollector(client_id="", client_secret="")
    rows, max_utc = collector._load_seed_fallback(limit=5)

    assert len(rows) > 0
    assert rows[0]["source"] == "reddit"
    assert "raw_text" in rows[0]
    assert "external_id" in rows[0]
