# TriageIQ

**Digital Product Feedback Intelligence** — Ideathon 2K26, Challenge 4

From raw reviews to clean analysis: TriageIQ aggregates multi-channel feedback
(app reviews, tweets, support tickets), uses AI to filter noise and classify
each item by category/sentiment/urgency, detects sudden spikes in similar
complaints, and surfaces a prioritized, actionable roadmap on a dashboard.

## How it works

```
Mock feedback data
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
  Streamlit dashboard      app.py                  (KPIs, filters, spike alerts, CSV export)
        ▲
        │
   detect_spikes()        core/anomaly_detector.py (flags complaint clusters → auto-tickets)
```

## Project structure

```
triageiq/
├── .streamlit/config.toml      Dark theme
├── app.py                      Streamlit dashboard (the only frontend)
├── core/                       All logic — plain Python, no framework
│   ├── config.py                 Loads .env
│   ├── database.py                DB connection + read/write helpers
│   ├── models.py                   Table schema (single 'feedback' table)
│   ├── preprocessing.py            Text cleaning
│   ├── ai_classifier.py            Gemini classification (batched) + ticket titles
│   ├── priority_engine.py          Priority scoring/ranking
│   ├── anomaly_detector.py         Spike detection → ticket generation
│   └── metrics.py                  Dashboard KPIs, baselines, chart aggregates
├── data/
│   ├── mock_data_generator.py    Generates synthetic feedback + a seeded spike
│   └── sample_feedback.csv       A pre-generated sample (for reference)
├── scripts/
│   ├── init_db.py                Creates the DB table
│   └── run_pipeline.py           One command: generate → batch-classify → load
└── tests/                       Unit tests for the pure core/ logic
```

## Quick start

See **SETUP.md** for the full step-by-step walkthrough (Neon DB, Gemini key, etc).

Once set up:

```bash
python -m scripts.init_db          # create the table (once)
python -m scripts.run_pipeline     # generate mock data, classify, load into DB
streamlit run app.py               # launch the dashboard
```

## Running tests

```bash
python -m pytest tests/ -v
```

Tests cover `priority_engine.py` and `anomaly_detector.py` with synthetic data —
no database or API key required to run them.

## Design decisions

- **One app, not client/server.** Streamlit calls `core/` functions directly.
  No API layer, no running two processes — easier to read top to bottom.
- **One table.** Kept flat on purpose; no joins to reason about.
- **Idempotent pipeline.** `run_pipeline.py` clears the table before reinserting,
  so re-running it never creates duplicates.
- **Batched AI calls.** ~15 rows go into a single Gemini request instead of
  one call per row — a full run is ~25 requests instead of ~370, which is
  both far faster and much friendlier to the free-tier daily quota.
- **Never crashes on bad AI output.** `ai_classifier.py` retries once, then
  falls back to a safe default rather than stopping the whole batch.
- **Self-healing model selection.** If the configured Gemini model becomes
  unavailable, the classifier automatically tries a short list of current
  fallbacks rather than hard-failing — Google has changed model
  availability several times during this project's development.
- **AI calls stay out of the pure logic.** `priority_engine.py` and
  `anomaly_detector.py` never touch the network or the database — they're
  plain functions over DataFrames, which is what makes them easy to unit
  test. The one AI-enrichment step in the dashboard (generating a specific
  title for a detected spike) lives in `ai_classifier.py` and is called
  from `app.py`, not from inside the detection logic itself.
