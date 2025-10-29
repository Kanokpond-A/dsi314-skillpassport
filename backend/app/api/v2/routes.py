# backend/app/api/v2/routes.py

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from ...services.scoring.logic_020 import calculate_fit_score

from ...core.logging import get_logger 

import json
import os

router = APIRouter(prefix="/api/v2", tags=["v2"])
logger = get_logger("ucb.v2")

PARSED_DATA_PATH = os.getenv("PARSED_DATA_PATH", "parsed_resume.schema.json")
IMPORT_LOG_PATH = os.getenv("IMPORT_LOG_PATH", "import_log.json")

@router.get("/candidates")
def get_candidates(
    min_experience: float = Query(0.0, description="Minimum experience in years"),
    max_salary: float = Query(1_000_000.0, description="Maximum expected salary"),
    available_now: bool = Query(False, description="Filter candidates who can start immediately")
):
    try:
        with open(PARSED_DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load resume data: {e}")
        return JSONResponse(status_code=500, content={"error": "Failed to read resume data"})

    enriched = []
    for c in data:
        try:
            score = calculate_fit_score(c)
            c["fit_score"] = score
        except Exception as e:
            logger.warning(f"Score error on candidate {c.get('display_name', '?')}: {e}")
            c["fit_score"] = 0.0
        enriched.append(c)

    filtered = []
    for c in enriched:
        exp = _safe_float(c.get("experience_years", 0))
        sal = _safe_float(c.get("expected_salary", 999999))
        avail_text = str(c.get("availability", "")).lower()
        is_available = any(k in avail_text for k in ["ทันที", "immediate", "พร้อม"])

        if exp >= min_experience and sal <= max_salary:
            if available_now and not is_available:
                continue
            filtered.append(c)

    filtered.sort(key=lambda c: c["fit_score"], reverse=True)

    summary = {
        "total_candidates": len(enriched),
        "fit_over_80": sum(1 for c in enriched if c["fit_score"] >= 80),
        "available_now": sum(1 for c in enriched if "immediate" in str(c.get("availability", "")).lower()),
        "within_budget": sum(
            1 for c in enriched
            if _safe_float(c.get("expected_salary")) <= _safe_float(c.get("budget_max"))
        )
    }

    output = []
    for c in filtered:
        output.append({
            "display_name": c.get("display_name"),
            "job_title": c.get("job_title") or c.get("position"),
            "fit_score": c.get("fit_score"),
            "experience_years": c.get("experience_years"),
            "availability": c.get("availability"),
            "expected_salary": c.get("expected_salary"),
            "evidence_snippets": c.get("evidence_snippets", []),
            "skills": c.get("skills", []),
            "languages": c.get("languages", []),
            "certifications": c.get("certifications", []),
            "portfolio": c.get("portfolio", [])
        })

    return {"summary": summary, "candidates": output}

@router.get("/import-summary")
def get_import_summary():
    try:
        with open(IMPORT_LOG_PATH, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load import log: {e}")
        return JSONResponse(status_code=500, content={"error": "Failed to read import log"})

    source_counts = {}
    for row in logs:
        source = row.get("source", "unknown")
        source_counts[source] = source_counts.get(source, 0) + 1

    return {
        "total_imported": len(logs),
        "sources": [{"source": k, "count": v} for k, v in source_counts.items()]
    }

def _safe_float(val):
    try:
        return float(str(val).replace(",", "").strip())
    except:
        return 0.0
