# TriageIQ: System Architecture & Engineering Blueprint

> **Project Name:** TriageIQ  
> **System Focus:** Digital Product Feedback Intelligence & Anomaly Triaging  
> **Target Audience:** Engineering Leads, System Architects, Full-Stack AI Engineers  
> **Document Status:** Authoritative Architecture Reference  

---

## 1. High-Level System Architecture Diagram

```mermaid
flowchart TB
    %% ==========================================
    %% INGESTION & DATA SOURCES
    %% ==========================================
    subgraph SOURCELAYER ["1. Multi-Channel Ingestion Tier"]
        direction LR
        REDDIT["Live Reddit Collector<br/><code>core/ingestion/reddit_collector.py</code><br/>(Zero-Auth Atom/RSS + PRAW)"]
        MOCK["Mock Generator<br/><code>data/mock_data_generator.py</code><br/>(Seeded Temporal Spike)"]
        S1["App Store Reviews"]
        S2["Google Play Reviews"]
        S3["Twitter / X Posts"]
        S4["Zendesk Support Tickets"]
        REDDIT -->|Normalized JSON| PIPE
        MOCK -->|Simulated Raw JSON| PIPE
        S1 & S2 & S3 & S4 -.->|Future Adapters| PIPE
    end

    %% ==========================================
    %% PIPELINE & AI ENGINE
    %% ==========================================
    subgraph PIPELAYER ["2. Offline Processing & AI Enrichment (Batch Engine)"]
        PIPE["Ingestion Pipeline<br/><code>scripts/run_pipeline.py</code>"]
        CLEAN["Text Preprocessing<br/><code>core/preprocessing.py</code><br/>(Regex URL/Mention Stripping)"]
        BATCH["Micro-Batcher<br/>(15 items/chunk)"]
        GEMINI["Google Gemini API<br/><code>core/ai_classifier.py</code><br/>• Category (Bug/Complaint/Spam)<br/>• Sentiment (Pos/Neu/Neg)<br/>• Urgency Score (1 to 5)"]
        PRIO["Priority Engine<br/><code>core/priority_engine.py</code><br/>Non-linear Volume-Damped Formula"]

        PIPE --> CLEAN --> BATCH --> GEMINI --> PRIO
    end

    %% ==========================================
    %% DATABASE STORAGE
    %% ==========================================
    subgraph DBLAYER ["3. Storage & Persistence Tier"]
        DB[("Serverless PostgreSQL (Neon)<br/><code>core/database.py</code><br/>Flat 'feedback' table")]
        PRIO -->|Bulk Insert / Upsert| DB
    end

    %% ==========================================
    %% ANALYTICS & BACKEND API
    %% ==========================================
    subgraph APILAYER ["4. Analytics & REST API Tier (FastAPI :8001)"]
        direction TB
        SERVER["FastAPI Application Server<br/><code>server.py</code> (Uvicorn ASGI)"]
        
        subgraph ANALYTICS ["Core Analytical Engines"]
            ANOM["Anomaly Detector<br/><code>core/anomaly_detector.py</code><br/>(60-min Sliding Window)"]
            METRICS["Metrics Calculator<br/><code>core/metrics.py</code><br/>(Period-over-Period Deltas)"]
            TITLE["Incident Title Generator<br/>(Gemini with In-Memory Cache)"]
        end

        DB <-->|Read Dataframe| ANALYTICS
        ANALYTICS --> SERVER

        ENDPOINTS["REST API Endpoints:<br/>• GET /api/metadata<br/>• GET /api/kpis<br/>• GET /api/charts<br/>• GET /api/anomalies<br/>• GET /api/feedback<br/>• POST /api/anomalies/:id/jira<br/>• GET /api/export-csv"]
        SERVER --- ENDPOINTS
    end

    %% ==========================================
    %% FRONTEND PRESENTATION
    %% ==========================================
    subgraph UILAYER ["5. Presentation Tier (React 19 + Vite :5173)"]
        direction TB
        VITE["Vite 8 Dev Server / Bundler"]
        
        subgraph REACTAPP ["React 19 SPA (frontend/src/)"]
            NAV["Navbar & Time Window Selector"]
            KPIS["KpiCards Component<br/>(Total, Bugs, Negative Rate, Urgency)"]
            CHARTS["AnalyticsCharts Component<br/>(Recharts Hourly Spike & Sentiment)"]
            ALERTS["AnomalyAlerts Component<br/>(Jira-Style Critical Incident Cards)"]
            TABLE["FeedbackTable Component<br/>(Backlog Search, Badges & CSV Export)"]
        end

        ENDPOINTS -->|Axios / Fetch JSON| REACTAPP
        VITE --- REACTAPP
    end

    %% ==========================================
    %% UNIFIED ORCHESTRATOR
    %% ==========================================
    RUNNER["Unified Supervisor Script (run_app.py)<br/>Launches FastAPI (:8001) + Vite (:5173) with unified SIGINT handling"]
    RUNNER -.-> SERVER
    RUNNER -.-> VITE
```

---

## 2. End-to-End Data Flow Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Product Ops / PM
    participant UI as React 19 Frontend (:5173)
    participant API as FastAPI Backend (:8001)
    participant Engine as Core Analytics & Priority
    participant DB as Neon PostgreSQL
    participant Gemini as Google Gemini API

    Note over UI, DB: Data Exploration & Incident Detection
    Admin->>UI: Opens Dashboard (Selects "Last 24 Hours")
    UI->>API: GET /api/kpis, GET /api/charts, GET /api/anomalies
    API->>DB: fetch_all_feedback() -> pd.DataFrame
    DB-->>API: Feedback Rows
    
    API->>Engine: detect_spikes() & compute_kpis()
    Engine->>Engine: Sliding window count >= 5 in 60 mins?
    alt Spike Detected (Anomaly Found)
        Engine->>Gemini: generate_ticket_title(sample_reviews)
        Gemini-->>Engine: "Critical Payment Gateway Timeout on Checkout"
    end
    Engine-->>API: Anomaly Tickets + Chart Data + Delta KPIs
    API-->>UI: Structured JSON Response
    UI-->>Admin: Displays KPI Cards, Recharts Graphs, and TIQ-001 Incident Alert

    Note over UI, API: Automated Action / Ticketing
    Admin->>UI: Clicks "Create Jira Ticket" on TIQ-001
    UI->>API: POST /api/anomalies/TIQ-001/jira
    API-->>UI: 200 OK {"jira_key": "TIQ-JIRA-001", "success": true}
    UI-->>Admin: Badge updates to "Jira Created: TIQ-JIRA-001"
```

---

## 3. Layer-by-Layer Architectural Breakdown

### 3.1. Ingestion & Preprocessing Tier
- **Live Reddit Collector (`core/ingestion/reddit_collector.py`):** Ingests real-time community bug reports and complaints from public subreddits (`r/swiggy`, `r/GooglePixel`). Operates in a dual mode:
  1. *Zero-Auth Atom/RSS Mode (Default):* Directly fetches official Reddit feeds (`/r/{sub}/new/.rss`) without needing developer keys, bypassing Reddit's Responsible Builder Policy restrictions.
  2. *PRAW OAuth Mode:* Automatically switches to authenticated sessions if `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` are configured.
  3. *Seed Fallback:* Serves curated domain complaints from `data/reddit_mock_posts.json` if network rate-limits (HTTP 429) occur.
- **Mock Data Engine (`data/mock_data_generator.py`):** Simulates multi-channel customer reviews (App Store, Google Play, Twitter/X, and Zendesk tickets) with seeded temporal clusters (e.g., sudden UPI checkout failure spikes).
- **Sanitization (`core/preprocessing.py`):** Strips URLs, usernames, formatting anomalies, and extra whitespace to minimize token waste before classification.

### 3.2. AI Intelligence Tier (`core/ai_classifier.py`)
- **LLM Foundation:** Google Gemini (`gemini-3.5-flash-lite` with automatic fallback to `gemini-2.5-flash`, `gemini-2.5-flash-lite`, and `gemini-flash-latest`).
- **Batched Ingestion:** Groups rows into chunks of **15 items per request**, slashing total LLM API calls by **~93%** (from ~370 to ~25).
- **Rate-Budget Throttling:** Client-side RPM limiter (`GEMINI_RPM=12`) prevents HTTP 429 quota exhaustion.
- **Output Schema:** Deterministic JSON parsing for `category`, `sentiment`, and `urgency_score` (1–5).

### 3.3. Mathematical Scoring & Anomaly Detection
- **Non-Linear Priority Engine (`core/priority_engine.py`):**
  $$\text{priority\_score} = \text{urgency\_score} \times \text{category\_weight} \times \left(1 + \frac{\sqrt{\text{volume}}}{10}\right)$$
  - Weights Bugs ($1.5$) and Complaints ($1.2$) over Praise ($0.3$) and Spam ($0.0$).
  - Sub-linear volume amplification ($\sqrt{\text{volume}}$) ensures systemic issues bubble up without letting isolated spam dominate.
- **Temporal Spike Detector (`core/anomaly_detector.py`):**
  - Evaluates rolling temporal windows (e.g., $\ge 5$ complaints in 60 minutes).
  - Compares against baseline volume to compute `% spike above norm` and auto-generate incident tickets (`TIQ-001`).

### 3.4. Storage & Persistence Tier (`core/database.py`, `core/models.py`)
- **Database:** Serverless PostgreSQL on **Neon**.
- **Schema:** Single flat `feedback` table for zero-join latency and instant conversion into Pandas dataframes for mathematical processing.
- **Engine Configuration:** SQLAlchemy with `pool_pre_ping=True` to eliminate stale serverless connection drops.

### 3.5. Analytics & REST API Tier (`server.py`)
- **Web Server:** **FastAPI + Uvicorn** listening on port `8001`.
- **API Surface:**
  - `GET /api/metadata`: Dynamic filters, categories, and time windows.
  - `GET /api/kpis`: 4 KPI metrics with period-over-period percentage deltas.
  - `GET /api/charts`: Hourly timeline + spike annotation, sentiment distribution, and source breakdowns.
  - `GET /api/anomalies`: Active incident tickets with AI-generated titles & sample reviews.
  - `POST /api/anomalies/{ticket_id}/jira`: Simulated 1-click Jira ticket dispatch (`TIQ-JIRA-XXX`).
  - `GET /api/feedback`: Paginated, multi-faceted filtered backlog.
  - `GET /api/export-csv`: CSV export with active filters.

### 3.6. Presentation Tier (`frontend/`)
- **Framework:** **React 19 + TypeScript + Vite 8**.
- **Styling:** **Tailwind CSS** with dark-mode theme, custom status pills, and badges.
- **Data Visualization:** **Recharts** for interactive hourly timelines with peak spike annotations and sentiment distribution.
- **Supervisor Runner (`run_app.py`):** A unified Python process supervisor that concurrently starts the FastAPI backend on port 8001 and the Vite development server on port 5173 with clean termination handling.
