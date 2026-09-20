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
├── app.py                      Streamlit dashboard (the only frontend)
├── core/                       All logic — plain Python, no framework
│   ├── config.py                 Loads .env
│   ├── database.py                DB connection + read/write helpers
│   ├── models.py                   Table schema (single 'feedback' table)
│   ├── preprocessing.py            Text cleaning
│   ├── ai_classifier.py            Gemini classification
│   ├── priority_engine.py          Priority scoring/ranking
│   └── anomaly_detector.py         Spike detection → ticket generation
├── data/
│   ├── mock_data_generator.py    Generates synthetic feedback + a seeded spike
│   └── sample_feedback.csv       A pre-generated sample (for reference)
├── scripts/
│   ├── init_db.py                Creates the DB table
│   └── run_pipeline.py           One command: generate → classify → load
└── tests/                       Unit tests for priority_engine & anomaly_detector
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
- **Never crashes on bad AI output.** `ai_classifier.py` retries once, then
  falls back to a safe default rather than stopping the whole batch.
