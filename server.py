"""
FastAPI Backend for TriageIQ Dashboard.
Exposes REST endpoints that reuse the battle-tested core engine:
- core.database (Neon Postgres retrieval)
- core.metrics (KPI computation, chart rollups)
- core.anomaly_detector (Spike detection & automated ticketing)
- core.priority_engine (Non-linear priority ranking)
- core.ai_classifier (Cached incident titling via Gemini)
"""
import io
import datetime
from typing import Optional, List, Dict, Any
from functools import lru_cache

from fastapi import FastAPI, Query, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd

from core.database import fetch_all_feedback
from core.priority_engine import rank_feedback
from core.anomaly_detector import detect_spikes
from core.metrics import compute_kpis, hourly_volume, sentiment_distribution, source_breakdown
from core.ai_classifier import generate_ticket_title

app = FastAPI(
    title="TriageIQ API",
    description="Backend API for Digital Product Feedback Intelligence",
    version="1.0.0"
)

# Enable CORS for Vite frontend (http://localhost:5173) and any local origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory Jira tickets set (persists during server runtime)
_created_jira_tickets: set[str] = set()

# Cache for AI-generated incident titles: ticket_id -> title
_title_cache: Dict[str, str] = {}


def get_cached_ai_title(ticket_id: str, samples: list, fallback_title: str) -> str:
    """Caches AI title per ticket to avoid redundant Gemini API quota usage."""
    if ticket_id in _title_cache:
        return _title_cache[ticket_id]
    try:
        title = generate_ticket_title(samples, fallback_title)
        _title_cache[ticket_id] = title
        return title
    except Exception:
        return fallback_title


@app.get("/api/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.datetime.now().isoformat()}


@app.get("/api/metadata")
def get_metadata():
    """Returns application metadata, options, and filter choices."""
    df = fetch_all_feedback()
    categories = sorted(df["category"].unique().tolist()) if not df.empty and "category" in df.columns else []
    sentiments = ["Negative", "Neutral", "Positive"]
    sources = sorted(df["source"].unique().tolist()) if not df.empty and "source" in df.columns else []
    
    return {
        "app_name": "TriageIQ",
        "target_app": "E-Commerce Mobile App (iOS & Android)",
        "subtitle": "Aggregated from App Store, Play Store, Twitter & Support Tickets",
        "last_synced": datetime.datetime.now().strftime("%b %d, %Y · %H:%M"),
        "time_windows": [
            {"label": "All Time", "hours": 720},
            {"label": "Last 7 Days", "hours": 168},
            {"label": "Last 24 Hours", "hours": 24},
        ],
        "categories": categories,
        "sentiments": sentiments,
        "sources": sources,
        "total_records": len(df)
    }


@app.get("/api/kpis")
def get_kpis(hours: int = Query(720, description="Time window in hours")):
    """Computes the 4 top KPI cards matching Figma wireframe."""
    df = fetch_all_feedback()
    if df.empty:
        return {
            "total_feedback": {"value": 0, "delta_pct": None, "subtext": "vs yesterday"},
            "bugs_reported": {"value": 0, "delta_pct": None, "subtext": "spike"},
            "negative_rate": {"value": 0.0, "delta_pct": None, "subtext": "vs baseline"},
            "avg_urgency": {"value": 0.0, "delta_pct": None, "subtext": "vs baseline"}
        }

    kpis = compute_kpis(df, hours=hours)
    
    return {
        "total_feedback": {
            "value": kpis["total_feedback"]["value"],
            "delta_pct": kpis["total_feedback"]["delta_pct"],
            "subtext": "vs previous period"
        },
        "bugs_reported": {
            "value": kpis["bugs_reported"]["value"],
            "delta_pct": kpis["bugs_reported"]["delta_pct"],
            "subtext": "spike"
        },
        "negative_rate": {
            "value": kpis["negative_rate"]["value"],
            "delta_pct": kpis["negative_rate"]["delta_pct"],
            "subtext": "vs baseline"
        },
        "avg_urgency": {
            "value": kpis["avg_urgency"]["value"],
            "delta_pct": kpis["avg_urgency"]["delta_pct"],
            "subtext": "/ 5 vs baseline"
        }
    }


@app.get("/api/charts")
def get_charts(hours: int = Query(720, description="Time window in hours")):
    """Returns data for the 3 visual charts matching Figma wireframe."""
    df = fetch_all_feedback()
    if df.empty:
        return {
            "volume_timeline": [],
            "spike_annotation": None,
            "sentiment_distribution": [],
            "source_breakdown": []
        }

    df_copy = df.copy()
    df_copy["created_at"] = pd.to_datetime(df_copy["created_at"])
    window_start = df_copy["created_at"].max() - pd.Timedelta(hours=hours)
    chart_df = df_copy[df_copy["created_at"] >= window_start]

    # 1. Hourly Volume Timeline
    vol_df = hourly_volume(chart_df, hours=hours)
    volume_records = []
    spike_annotation = None

    if not vol_df.empty:
        baseline = float(vol_df["count"].mean())
        for _, r in vol_df.iterrows():
            volume_records.append({
                "time": r["hour"].strftime("%H:%M") if hasattr(r["hour"], "strftime") else str(r["hour"]),
                "iso_time": r["hour"].isoformat() if hasattr(r["hour"], "isoformat") else str(r["hour"]),
                "count": int(r["count"]),
                "baseline": round(baseline, 1)
            })

        peak_idx = vol_df["count"].idxmax()
        peak = vol_df.loc[peak_idx]
        # Require a minimum absolute volume threshold (at least 3 items in that hour)
        # to prevent single isolated reports in sparse periods from falsely flagging a "+500% spike"
        if baseline > 0 and peak["count"] >= 3 and peak["count"] > baseline * 1.5:
            pct = round((peak["count"] - baseline) / baseline * 100)
            peak_time = peak["hour"].strftime("%H:%M") if hasattr(peak["hour"], "strftime") else str(peak["hour"])
            spike_annotation = {
                "peak_time": peak_time,
                "peak_count": int(peak["count"]),
                "pct_above_baseline": pct,
                "label": f"Spike Detected: ~{peak_time} (+{pct}% above norm)"
            }

    # 2. Sentiment Distribution
    sent_df = sentiment_distribution(chart_df)
    total_sent = int(sent_df["count"].sum()) if not sent_df.empty else 0
    sentiment_records = []
    for _, r in sent_df.iterrows():
        count = int(r["count"])
        pct = round((count / total_sent * 100), 1) if total_sent > 0 else 0.0
        sentiment_records.append({
            "sentiment": r["sentiment"],
            "count": count,
            "percentage": pct
        })

    # 3. Source Breakdown
    src_df = source_breakdown(chart_df)
    source_records = []
    for _, r in src_df.iterrows():
        # Clean label (e.g. app_review -> App Store, support_ticket -> Support Ticket)
        raw_src = r["source"]
        friendly_label = {
            "app_review": "App Store",
            "play_store": "Play Store",
            "tweet": "Twitter / X",
            "support_ticket": "Support Ticket"
        }.get(raw_src, raw_src.replace("_", " ").title())
        
        source_records.append({
            "source_key": raw_src,
            "source": friendly_label,
            "count": int(r["count"])
        })

    return {
        "volume_timeline": volume_records,
        "spike_annotation": spike_annotation,
        "sentiment_distribution": sentiment_records,
        "source_breakdown": source_records
    }


@app.get("/api/anomalies")
def get_anomalies():
    """Returns detected spike incident tickets formatted for Figma Jira-style cards."""
    df = fetch_all_feedback()
    if df.empty:
        return {"tickets": [], "active_count": 0}

    tickets = detect_spikes(df)
    enriched_tickets = []

    for t in tickets:
        ticket_id = t["ticket_id"]
        # AI title enrichment
        ai_title = get_cached_ai_title(ticket_id, t.get("sample_reviews", []), t.get("title", ""))
        
        # Source counts formatted
        source_counts_list = []
        for src, cnt in t.get("source_counts", {}).items():
            label = {
                "app_review": "App Store",
                "play_store": "Play Store",
                "tweet": "Twitter",
                "support_ticket": "Support Ticket"
            }.get(src, src.replace("_", " ").title())
            source_counts_list.append({"source": label, "count": cnt})

        enriched_tickets.append({
            "ticket_id": ticket_id,
            "title": ai_title,
            "original_title": t.get("title"),
            "severity": t.get("severity", "Critical"),
            "affected_count": t.get("affected_count", 0),
            "window_minutes": t.get("window_minutes", 60),
            "pct_above_baseline": t.get("pct_above_baseline"),
            "source_counts": source_counts_list,
            "sample_reviews": [
                {
                    "source": {
                        "app_review": "App Store",
                        "play_store": "Play Store",
                        "tweet": "Twitter",
                        "support_ticket": "Support Ticket"
                    }.get(s["source"], s["source"].replace("_", " ").title()),
                    "text": s["clean_text"]
                }
                for s in t.get("sample_reviews_with_source", [])
            ],
            "jira_created": ticket_id in _created_jira_tickets,
            "category": t.get("category"),
            "window_start": t.get("window_start"),
            "window_end": t.get("window_end"),
            "avg_urgency": t.get("avg_urgency")
        })

    return {
        "tickets": enriched_tickets,
        "active_count": len(enriched_tickets)
    }


@app.post("/api/anomalies/{ticket_id}/jira")
def create_jira_ticket(ticket_id: str):
    """Simulates creating a Jira ticket for the detected anomaly."""
    _created_jira_tickets.add(ticket_id)
    return {
        "success": True,
        "ticket_id": ticket_id,
        "jira_key": f"TIQ-JIRA-{ticket_id.replace('TIQ-', '')}",
        "message": f"Successfully created Jira ticket for {ticket_id}"
    }


@app.get("/api/feedback")
def get_feedback(
    category: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    hours: Optional[int] = Query(None, description="Optional time window in hours"),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200)
):
    """Returns prioritized feedback backlog with multi-faceted filtering."""
    df = fetch_all_feedback()
    if df.empty:
        return {"items": [], "total": 0, "page": page, "limit": limit, "total_pages": 0}

    ranked = rank_feedback(df)

    if hours:
        ranked["_created_dt"] = pd.to_datetime(ranked["created_at"])
        window_start = ranked["_created_dt"].max() - pd.Timedelta(hours=hours)
        ranked = ranked[ranked["_created_dt"] >= window_start]

    if category:
        ranked = ranked[ranked["category"] == category]
    if sentiment:
        ranked = ranked[ranked["sentiment"] == sentiment]
    if source:
        ranked = ranked[ranked["source"] == source]
    if search:
        s_lower = search.lower()
        ranked = ranked[ranked["clean_text"].astype(str).str.lower().str.contains(s_lower)]

    total = len(ranked)
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    start = (page - 1) * limit
    end = start + limit
    page_df = ranked.iloc[start:end]

    items = []
    for _, r in page_df.iterrows():
        created = r["created_at"]
        created_str = created.strftime("%Y-%m-%d %H:%M") if hasattr(created, "strftime") else str(created)
        
        friendly_src = {
            "app_review": "App Store",
            "play_store": "Play Store",
            "tweet": "Twitter",
            "support_ticket": "Support Ticket"
        }.get(r["source"], r["source"])

        items.append({
            "id": int(r["id"]) if "id" in r and pd.notnull(r["id"]) else None,
            "priority_score": float(r["priority_score"]),
            "category": str(r["category"]),
            "sentiment": str(r["sentiment"]),
            "urgency_score": int(r["urgency_score"]),
            "source": friendly_src,
            "raw_source": str(r["source"]),
            "clean_text": str(r["clean_text"]),
            "created_at": created_str
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }


@app.get("/api/export-csv")
def export_csv(
    category: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    hours: Optional[int] = Query(None, description="Optional time window in hours")
):
    """Exports prioritized feedback directly as CSV."""
    df = fetch_all_feedback()
    if df.empty:
        raise HTTPException(status_code=404, detail="No feedback data to export")

    ranked = rank_feedback(df)
    if hours:
        ranked["_created_dt"] = pd.to_datetime(ranked["created_at"])
        window_start = ranked["_created_dt"].max() - pd.Timedelta(hours=hours)
        ranked = ranked[ranked["_created_dt"] >= window_start]

    if category:
        ranked = ranked[ranked["category"] == category]
    if sentiment:
        ranked = ranked[ranked["sentiment"] == sentiment]
    if source:
        ranked = ranked[ranked["source"] == source]
    if search:
        s_lower = search.lower()
        ranked = ranked[ranked["clean_text"].astype(str).str.lower().str.contains(s_lower)]

    display_cols = [
        "priority_score", "category", "sentiment", "urgency_score",
        "source", "clean_text", "created_at"
    ]
    buffer = io.StringIO()
    ranked[display_cols].to_csv(buffer, index=False)
    
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=triageiq_prioritized_feedback.csv"}
    )
