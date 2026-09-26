# TriageIQ: Twitter (X) Live Ingestion Sequence Diagram & Data Flow

> **Document Version:** 1.0.0  
> **Target Audience:** Engineering Leads, System Architects, Full-Stack AI Engineers  
> **Status:** Architecture Reference & Specification  
> **Related Document:** [TWITTER_INGESTION_ARCHITECTURE.md](./TWITTER_INGESTION_ARCHITECTURE.md)

---

## 1. Overview

This document provides a visual and operational specification of how the **TriageIQ** backend communicates with the **Twitter (X) API v2** endpoint (`/2/tweets/search/recent`). It details the step-by-step lifecycle from watermark checkpoint retrieval to AI classification, priority scoring, and idempotent persistence in PostgreSQL.

> [!TIP]
> **Viewing in VS Code:** Press `Ctrl + Shift + V` (or `Ctrl + K, V`) to open the Markdown Preview. VS Code and GitHub natively render the Mermaid diagram below.

---

## 2. End-to-End Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Admin as "Operator / Pipeline Runner"
    participant Runner as "Pipeline Runner<br/>(scripts/run_pipeline.py)"
    participant Store as "Checkpoint Store<br/>(data/twitter_checkpoint.json)"
    participant Collector as "TwitterCollector Adapter<br/>(core/ingestion/twitter_collector.py)"
    participant TwitterAPI as "X (Twitter) API v2<br/>(/2/tweets/search/recent)"
    participant Sanitizer as "Text Sanitizer<br/>(core/preprocessing.py)"
    participant Gemini as "Gemini AI Classifier<br/>(core/ai_classifier.py)"
    participant Engine as "Priority Engine<br/>(core/priority_engine.py)"
    participant DB as "PostgreSQL (Neon)<br/>(core/database.py)"

    Admin->>Runner: Execute: python -m scripts.run_pipeline --source twitter
    Runner->>Store: Read last checkpoint watermark (get_checkpoint)
    Store-->>Runner: Return since_id (e.g. "1839999999999999") or None

    Runner->>Collector: fetch_recent_tweets(query, since_id, max_results=50)
    Note over Collector: 1. Clamp results between 10 and 100<br/>2. Prepare OAuth 2.0 Bearer Token headers<br/>3. Format query: -is:retweet -is:nullcast lang:en

    Collector->>TwitterAPI: GET /2/tweets/search/recent?query=...&since_id=...&tweet_fields=created_at,lang,author_id
    
    alt 200 OK: Tweets Found
        TwitterAPI-->>Collector: 200 OK with JSON (data: [...], meta: {newest_id: "1840000000000000"})
        Note over Collector: Normalize raw tweets into standardized dictionary format: (external_id, raw_text, created_at, source="tweet")
        Collector->>Runner: Return (normalized_rows, newest_id)
        Runner->>Store: Persist save_checkpoint(newest_id)
    else 200 OK: No New Tweets (Empty Window)
        TwitterAPI-->>Collector: 200 OK with meta: {result_count: 0}
        Collector->>Runner: Return ([], since_id)
    else 429 Too Many Requests (Rate Limit Exceeded)
        TwitterAPI-->>Collector: 429 Too Many Requests (retry-after: Xs)
        Note over Collector: Caught by tweepy.errors.TooManyRequests.<br/>Log warning and preserve existing since_id.
        Collector->>Runner: Return ([], since_id)
    end

    opt When New Rows Exist
        Runner->>Sanitizer: clean_text(raw_text) (strip URLs, user handles, bot noise)
        Sanitizer-->>Runner: Cleaned text
        Runner->>Gemini: classify_feedback_batch(micro-batches of 15 rows)
        Gemini-->>Runner: Category, Sentiment, Urgency (1 to 5)
        Runner->>Engine: compute_priority_scores(df) (urgency x category weight x volume damping)
        Engine-->>Runner: Calculated priority scores
        Runner->>DB: upsert_feedback_batch(rows) (ON CONFLICT (external_id) DO NOTHING)
        DB-->>Runner: Commit successful (idempotent insert)
    end
```

---

## 3. Step-by-Step Architectural Lifecycle

### Phase 1: Watermark Retrieval (`since_id`)
1. Before initiating any outbound HTTP connection, `scripts/run_pipeline.py` checks `data/twitter_checkpoint.json`.
2. **First Run:** If no checkpoint exists, `since_id = None`. The query retrieves recent brand mentions from the past 7 days.
3. **Subsequent Runs:** If a watermark exists (e.g. `"1839999999999999"`), Twitter only returns tweets created *after* this ID. This guarantees:
   - Zero duplicate token consumption in Google Gemini.
   - Zero duplicate DB writes.
   - Conservation of limited monthly X API call limits.

### Phase 2: Client Configuration & Guardrails
In `core/ingestion/twitter_collector.py`:
1. **Authentication:** Authenticates with App-Only **OAuth 2.0 Bearer Token** (`TWITTER_BEARER_TOKEN`) using `tweepy.Client(wait_on_rate_limit=True)`.
2. **Boolean Query Filter:**
   ```
   (to:YourApp OR @YourApp OR #YourApp) -is:retweet -is:nullcast lang:en
   ```
   - `-is:retweet`: Discards retweets to avoid processing repetitive echo chambers.
   - `-is:nullcast`: Excludes dark/promotional ads.
   - `lang:en`: Restricts ingestion to English for structured Gemini prompt compatibility.
3. **Parameter Clamping:** Enforces `max(10, min(max_results, 100))` to strictly comply with X API v2 specification limits.

### Phase 3: Response Handling & Branching
The client dispatches `GET /2/tweets/search/recent` and handles three distinct scenarios:
- **Scenario A (Success - Data Returned):**
  - Extracts items from `response.data`.
  - Reads `response.meta["newest_id"]`.
  - Normalizes tweets into TriageIQ's standard schema contract.
  - Returns `(rows, newest_id)` and saves the updated watermark to disk.
- **Scenario B (Empty Window):**
  - `response.meta["result_count"] == 0`.
  - Returns `([], since_id)` without altering the checkpoint.
- **Scenario C (HTTP 429 Rate Limit):**
  - Trapped cleanly by `tweepy.errors.TooManyRequests`.
  - Logs a warning message and gracefully returns `([], since_id)` without terminating or crashing the backend.

### Phase 4: Downstream AI Enrichment & Storage
When new feedback items are retrieved:
1. **Sanitization (`core/preprocessing.py`):** Strips URLs, usernames, formatting anomalies, and bot noise.
2. **Micro-Batched AI Classification (`core/ai_classifier.py`):** Rows are grouped into chunks of **15 items per prompt** to reduce Gemini API calls by **~93%**, classifying each item into `category`, `sentiment`, and `urgency_score` (1–5).
3. **Priority Engine (`core/priority_engine.py`):** Calculates priority score:
   $$\text{priority\_score} = \text{urgency} \times \text{category\_weight} \times \left(1 + \frac{\sqrt{\text{volume}}}{10}\right)$$
4. **Idempotent Storage (`core/database.py`):** Rows are bulk inserted into PostgreSQL via:
   ```sql
   INSERT INTO feedback (...) VALUES (...) ON CONFLICT (external_id) DO NOTHING;
   ```
   Ensuring zero duplicate entries even if the pipeline is triggered repeatedly.
