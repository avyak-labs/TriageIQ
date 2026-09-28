# Setup Guide

Follow these steps in order. Each one builds on the last — don't skip ahead.
If something doesn't look like what's described, stop and check before continuing.

---

## Prerequisites
- **Python 3.11+** installed
- **Node.js (v18+) & npm** installed (required for the React + Vite frontend)

---

## 1. Create your Neon (Postgres) database

1. Go to https://neon.tech and sign up (free tier is enough).
2. Click **"Create a project"**. Give it any name, e.g. `triageiq`.
3. Once created, go to your project's **Dashboard**.
4. Find the **Connection String** (usually shown right on the dashboard, or under "Connection Details"). It looks like:
   ```
   postgresql://username:password@ep-something.neon.tech/dbname?sslmode=require
   ```
5. Copy this whole string somewhere safe — you'll need it in step 5.

## 2. Get a Gemini API key

1. Go to https://aistudio.google.com/apikey
2. Sign in with a Google account.
3. Click **"Create API key"**.
4. Copy the key somewhere safe — you'll need it in step 5.

## 3. Install Python dependencies

Open a terminal **inside the `triageiq` project folder**, then run:

```bash
# Create a virtual environment (keeps this project's packages separate)
python3 -m venv venv

# Activate it
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows

# Install everything the backend and pipelines need
pip install -r requirements.txt
```

You'll know it worked if the install finishes with no red error text.
**Every time you open a new terminal to work on this project, run the `activate` command again first.**

## 4. Install Frontend dependencies

Open a terminal and navigate to the `frontend/` directory to install the React packages:

```bash
cd frontend
npm install
cd ..
```

This installs React 19, Vite, Tailwind CSS, Lucide icons, and Recharts.

## 5. Set up your secrets file

1. In the project root folder, find the file `.env.example`.
2. Make a copy of it named exactly `.env` (no `.example`).
3. Open `.env` in a text editor and fill in the two values from steps 1 and 2:
   ```bash
   DATABASE_URL=postgresql://... (from step 1)
   GEMINI_API_KEY=... (from step 2)
   ```
4. Save the file. **Never share this file or commit it to GitHub** — it's already excluded via `.gitignore`, but double-check before pushing.

## 6. Create the database table

```bash
python -m scripts.init_db
```

Expected output: `Database initialized: 'feedback' table is ready.`

If you get a connection error, double-check your `DATABASE_URL` in `.env` — this is the most common mistake (extra spaces, missing `?sslmode=require`).

## 7. Run the pipeline (mock data OR live Reddit data)

### Option 1: Live Reddit Ingestion (Zero Credentials Needed)
TriageIQ connects directly to live subreddits (e.g. `r/swiggy`, `r/GooglePixel`) via official Atom/RSS feeds:
```bash
python -m scripts.run_pipeline --source reddit --subreddits "swiggy,GooglePixel" --rows 25
```
To append newly ingested Reddit posts without clearing existing data in the table, pass `--append`:
```bash
python -m scripts.run_pipeline --source reddit --subreddits "swiggy" --append
```

### Option 2: Synthetic Mock Data Ingestion (Default)
```bash
python -m scripts.run_pipeline --source mock --rows 350 --spike 22
```

The pipeline batches ~15 rows into each Gemini request, so a full ~370-row dataset takes roughly **25-30 API requests total**, finishing in a couple of minutes rather than 30+.

**Tip: test with a smaller batch first.** Before running the full pipeline, confirm everything works end-to-end with a quick run:
```bash
python -m scripts.run_pipeline --rows 20 --spike 8
```
This finishes in well under a minute and still includes a spike, so you can check the dashboard and anomaly detection work before committing to the full run.

You'll see progress logs like `-> classified 25/372`. When it finishes, you'll see `Done. 372 rows loaded into the 'feedback' table.`

**Tip:** you can re-run this command any time — by default it clears old data first, so you never end up with duplicates (unless `--append` is specified).

---

## 8. Launch the Application

### Option A: Modern React + FastAPI Dashboard (Recommended)

Run the unified runner from the project root:

```bash
python run_app.py
```

This automatically launches both services:
- **Frontend Dashboard (React + Tailwind + Recharts)**: http://localhost:5173
- **Backend REST API (FastAPI)**: http://127.0.0.1:8001
- **API Interactive Swagger Docs**: http://127.0.0.1:8001/docs

#### Running Services Separately (Optional):
If you prefer running them in separate terminal windows:
```bash
# Terminal 1 - Backend API:
python -m uvicorn server:app --host 127.0.0.1 --port 8001 --reload

# Terminal 2 - Frontend:
cd frontend
npm run dev
```

### Option B: Legacy Streamlit Prototype

If you want to view the standalone Streamlit prototype:

```bash
streamlit run app.py
```

This opens `http://localhost:8501`.

---

## Troubleshooting

| Problem | Likely cause | Solution |
|---|---|---|
| `Missing required environment variables` | `.env` file missing or not filled in correctly | Ensure `.env` exists in the root folder with `DATABASE_URL` and `GEMINI_API_KEY`. |
| `npm: command not found` | Node.js is not installed | Install Node.js LTS (v18+) from https://nodejs.org. |
| `404 ... model not found for API version` | Fallback candidate unavailable | The app auto-fallbacks models; verify https://ai.google.dev/gemini-api/docs/models and set `GEMINI_MODEL=` in `.env` if needed. |
| `429 ... exceeded your current quota` | Normal on free tier with frequent calls | Rate limiter will automatically pause. You can lower `GEMINI_RPM` or `GEMINI_BATCH_SIZE` in `.env`. |
| Connection refused / timeout on `init_db` | Wrong `DATABASE_URL` or paused Neon branch | Check `DATABASE_URL` format. Neon free tier pauses when idle — wait 5 seconds and retry. |
| Dashboard shows "No feedback data found" | `run_pipeline` hasn't been run yet | Run `python -m scripts.run_pipeline` to generate and seed data. |
| `ModuleNotFoundError` | Virtual environment not active | Activate virtual environment (`venv\Scripts\activate` on Windows or `source venv/bin/activate` on Mac/Linux). |
| Vite proxy error `ECONNREFUSED 127.0.0.1:8001` | Backend FastAPI server is not running | Ensure `server.py` is running on port 8001 (or use `python run_app.py`). |

---

## Running the Unit Tests

```bash
python -m pytest tests/ -v
```

This runs all 25 business logic and collector unit tests (Priority Engine, Anomaly Detector, Metrics, and Reddit Collector). The tests use synthetic fixtures and mock HTTP stubs and do not require external DB or Gemini connections.
