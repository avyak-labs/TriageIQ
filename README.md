# TriageIQ

**Digital Product Feedback Intelligence** — Ideathon 2K26, Challenge 4

From raw reviews to clean analysis: TriageIQ aggregates multi-channel feedback
(app reviews, tweets, support tickets), uses AI to filter noise and classify
each item by category/sentiment/urgency, detects sudden spikes in similar
complaints, and surfaces a prioritized, actionable roadmap on a dashboard.

## How it works

```
Feedback Sources:
  • Mock synthetic generator (data/mock_data_generator.py)
  • Live Reddit subreddits (core/ingestion/reddit_collector.py - Zero-Auth RSS / PRAW)
        │
        ▼
  clean_text()            core/preprocessing.py   (strips HTML, URLs, emojis, noise)
        │
        ▼
 classify_feedback()      core/ai_classifier.py   (Gemini → category, sentiment, urgency)
        │
        ▼
compute_priority_scores() core/priority_engine.py (ranks by urgency × volume)
        │
        ▼
     Postgres (Neon)      core/database.py
        │
        ▼
  FastAPI (:8001) / Streamlit dashboard (KPIs, filters, spike alerts, CSV export)
        ▲
        │
   detect_spikes()        core/anomaly_detector.py (flags complaint clusters → auto-tickets)
```

## Project structure

```
triageiq/
├── .streamlit/config.toml      Dark theme
├── app.py                      Streamlit dashboard prototype
├── server.py                   FastAPI backend (:8001)
├── frontend/                   React 19 + Vite dashboard (:5173)
├── core/                       All logic — plain Python, modular
│   ├── config.py                 Loads .env
│   ├── database.py                DB connection + read/write helpers
│   ├── models.py                   Table schema (single 'feedback' table)
│   ├── preprocessing.py            Text cleaning
│   ├── ai_classifier.py            Gemini classification (batched) + ticket titles
│   ├── priority_engine.py          Priority scoring/ranking
│   ├── anomaly_detector.py         Spike detection → ticket generation
│   ├── metrics.py                  Dashboard KPIs, baselines, chart aggregates
│   └── ingestion/                  Live platform data adapters
│       └── reddit_collector.py       Dual-mode Reddit collector (Zero-Auth RSS + PRAW)
├── data/
│   ├── mock_data_generator.py    Generates synthetic feedback + a seeded spike
│   ├── reddit_mock_posts.json    Curated high-signal fallback posts for r/swiggy, etc.
│   └── sample_feedback.csv       A pre-generated sample (for reference)
├── scripts/
│   ├── init_db.py                Creates the DB table
│   └── run_pipeline.py           One command: ingest (mock or reddit) → batch-classify → load
└── tests/                       25/25 Unit tests for core logic & collectors
```

## Quick start

See **SETUP.md** for the full step-by-step walkthrough (Neon DB, Gemini key, etc).

Once set up:

```bash
python -m scripts.init_db                                              # create the table (once)
python -m scripts.run_pipeline                                         # generate mock data, classify, load
python -m scripts.run_pipeline --source reddit --subreddits swiggy      # or ingest live Reddit posts!
python run_app.py                                                      # launch React UI (:5173) + FastAPI (:8001)
```

## Running tests

```bash
python -m pytest tests/ -v
```

All 25 unit tests pass locally without external network or DB dependencies:
- `test_anomaly_detector.py` (7 tests)
- `test_metrics.py` (8 tests)
- `test_priority_engine.py` (5 tests)
- `test_reddit_collector.py` (5 tests)

## Design decisions

- **Dual-Mode Resilient Ingestion.** Reddit's new Responsible Builder Policy blocks self-serve API keys for student/hobby projects. TriageIQ circumvents this by consuming public Atom/RSS feeds directly with **zero credentials needed**, falling back to PRAW if keys exist, and serving curated seed data if rate-limited.
- **One app or decoupled API.** Run unified via `run_app.py` (FastAPI + React 19) or standalone via Streamlit (`app.py`).
- **One table.** Kept flat on purpose; no joins to reason about.
- **Idempotent pipeline.** `run_pipeline.py` clears the table before reinserting (or accepts `--append` to keep accumulating).
- **Batched AI calls.** ~15 rows go into a single Gemini request instead of one call per row — a full run is ~25 requests instead of ~370, which is both far faster and much friendlier to the free-tier daily quota.
- **Never crashes on bad AI output.** `ai_classifier.py` retries once, then falls back to a safe default rather than stopping the whole batch.
- **Self-healing model selection.** If the configured Gemini model becomes unavailable, the classifier automatically tries a short list of current fallbacks rather than hard-failing.
- **AI calls stay out of the pure logic.** `priority_engine.py` and `anomaly_detector.py` never touch the network or the database — they're plain functions over DataFrames, which makes them fast and testable.
