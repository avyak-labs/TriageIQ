# Setup Guide

Follow these steps in order. Each one builds on the last — don't skip ahead.
If something doesn't look like what's described, stop and check before continuing.

---

## 1. Create your Neon (Postgres) database

1. Go to https://neon.tech and sign up (free tier is enough).
2. Click **"Create a project"**. Give it any name, e.g. `triageiq`.
3. Once created, go to your project's **Dashboard**.
4. Find the **Connection String** (usually shown right on the dashboard, or
   under "Connection Details"). It looks like:
   ```
   postgresql://username:password@ep-something.neon.tech/dbname?sslmode=require
   ```
5. Copy this whole string somewhere safe — you'll need it in step 4.

## 2. Get a Gemini API key

1. Go to https://aistudio.google.com/apikey
2. Sign in with a Google account.
3. Click **"Create API key"**.
4. Copy the key somewhere safe — you'll need it in step 4.

## 3. Install Python dependencies

Open a terminal **inside the `triageiq` project folder**, then run:

```bash
# Create a virtual environment (keeps this project's packages separate)
python3 -m venv venv

# Activate it
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows

# Install everything the project needs
pip install -r requirements.txt
```

You'll know it worked if the install finishes with no red error text.
**Every time you open a new terminal to work on this project, run the
`activate` command again first.**

## 4. Set up your secrets file

1. In the project folder, find the file `.env.example`.
2. Make a copy of it named exactly `.env` (no `.example`).
3. Open `.env` in a text editor and fill in the two values from steps 1 and 2:
   ```
   DATABASE_URL=postgresql://... (from step 1)
   GEMINI_API_KEY=... (from step 2)
   ```
4. Save the file. **Never share this file or commit it to GitHub** — it's
   already excluded via `.gitignore`, but double-check before pushing.

## 5. Create the database table

```bash
python -m scripts.init_db
```

Expected output: `Database initialized: 'feedback' table is ready.`

If you get a connection error, double-check your `DATABASE_URL` in `.env` —
this is the most common mistake (extra spaces, missing `?sslmode=require`).

## 6. Run the pipeline (generate data + classify + load)

```bash
python -m scripts.run_pipeline
```

This will now be much faster than a naive per-row approach — the
pipeline batches ~15 rows into each Gemini request, so the full
~370-row dataset takes roughly **25-30 API requests total**, finishing
in a couple of minutes rather than 30+.

**Tip: test with a smaller batch first.** Before running the full
pipeline, confirm everything works end-to-end with a quick run:
```bash
python -m scripts.run_pipeline --rows 20 --spike 8
```
This finishes in well under a minute and still includes a spike, so
you can check the dashboard and anomaly detection work before
committing to the full run.

Once you're ready for the real dataset:
```bash
python -m scripts.run_pipeline
```

This will:
- Generate ~370 pieces of mock feedback (including a seeded "spike" of
  payment-failure complaints)
- Send each one to Gemini for classification (this takes a few minutes —
  it's calling the AI once per row)
- Load everything into your Neon database

You'll see progress logs like `-> classified 25/372`. When it finishes,
you'll see `Done. 372 rows loaded into the 'feedback' table.`

**Tip:** you can re-run this command any time — it always clears old data
first, so you never end up with duplicates.

## 7. Launch the dashboard

```bash
streamlit run app.py
```

This should automatically open a browser tab at `http://localhost:8501`.
You should see:
- KPI cards at the top (total feedback, bugs reported, etc.)
- An "Anomaly Alerts" section — this should show **1 detected spike**
  about the seeded payment-failure complaints
- A filterable table of all feedback, ranked by priority
- A "Download as CSV" button at the bottom

## Troubleshooting

| Problem | Likely cause |
|---|---|
| `Missing required environment variables` | `.env` file missing or not filled in correctly |
| `404 ... model not found for API version` | The app should now auto-fallback to a working model and just log a warning — if you still see a hard failure, every fallback candidate is unavailable; check https://ai.google.dev/gemini-api/docs/models and set `GEMINI_MODEL=` in your `.env` to a current name |
| `429 ... exceeded your current quota` | Normal on the free tier if you're going too fast — much rarer now that requests are batched. If it keeps happening, lower `GEMINI_RPM` or `GEMINI_BATCH_SIZE` in `.env` |
| Connection refused / timeout on `init_db` | Wrong `DATABASE_URL`, or Neon project is paused (free tier auto-pauses when idle — just wait a few seconds and retry) |
| Pipeline is very slow | Normal — it's one Gemini API call per row. ~370 rows takes a few minutes |
| Dashboard shows "No feedback data found" | You haven't run `run_pipeline` yet, or it failed partway — check the terminal logs |
| `ModuleNotFoundError` | You forgot to activate the virtual environment (`source venv/bin/activate`) before running commands |

## Running the tests (optional, but good practice)

```bash
python -m pytest tests/ -v
```

This doesn't need your `.env` filled in — the tests use fake data and don't
call the database or Gemini.
