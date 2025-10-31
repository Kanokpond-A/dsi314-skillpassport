# backend/app/api/v2/routes.py
from dotenv import load_dotenv
load_dotenv() 

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from ...services.scoring.logic_020 import calculate_fit_score
from ...core.logging import get_logger 
from pathlib import Path

import json, os, re

router = APIRouter(prefix="/api/v2", tags=["v2"])
logger = get_logger("ucb.v2")

#   PARSED_DATA_PATH=/.../shared_data/latest_parsed
#   IMPORT_LOG_PATH=/.../shared_data/import_log.json
PARSED_DATA_PATH = Path(os.getenv("PARSED_DATA_PATH", "shared_data/latest_parsed")).resolve()
IMPORT_LOG_PATH  = Path(os.getenv("IMPORT_LOG_PATH", "shared_data/import_log.json")).resolve()

def get_parsed_path() -> Path:
    if not PARSED_DATA_PATH:
        raise RuntimeError("❌ Environment variable PARSED_DATA_PATH not found.")
    return Path(PARSED_DATA_PATH).resolve()

def get_import_log_path() -> Path:
    if not IMPORT_LOG_PATH:
        raise RuntimeError("❌ Environment variable IMPORT_LOG_PATH not found.")
    return Path(IMPORT_LOG_PATH).resolve()


def _safe_float(val):
    try:
        s = str(val)
        s = re.sub(r"[^\d\.\-]", "", s)  # ตัด ฿ , , ช่องว่าง ฯลฯ
        return float(s) if s else 0.0
    except:
        return 0.0

def _is_available_now(text: str) -> bool:
    t = (text or "").lower()
    keys = ["immediate", "พร้อม", "ทันที"]
    return any(k in t for k in keys)

def _load_candidates_from_path(path_str: str):
    """รองรับทั้ง 'โฟลเดอร์ที่มีหลายไฟล์ .json (ไฟล์ละ 1 คน)' และ 'ไฟล์เดียวเป็นลิสต์'"""
    p = Path(path_str).resolve()
    records = []
    if p.is_dir():
        for fp in sorted(p.glob("*.json")):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    obj = json.load(f)  # dict ของผู้สมัคร 1 คน
                    if isinstance(obj, dict):
                        records.append(obj)
                    elif isinstance(obj, list):
                        records.extend(obj)
            except Exception as e:
                logger.warning(f"Skip bad file {fp.name}: {e}")
    elif p.is_file():
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                records = data
            elif isinstance(data, dict):
                records = [data]
    else:
        raise FileNotFoundError(f"PARSED_DATA_PATH not found: {p}")
    return records

@router.get("/candidates")
def get_candidates(
    min_experience: float = Query(0.0, description="Minimum experience in years"),
    max_salary: float = Query(1_000_000.0, description="Maximum expected salary"),
    available_now: bool = Query(False, description="Filter candidates who can start immediately")
):
    try:
        data = _load_candidates_from_path(get_parsed_path())
    except Exception as e:
        logger.error(f"Failed to load resume data: {e}")
        return JSONResponse(status_code=500, content={"error": "Failed to read resume data"})

    enriched = []
    for c in data:
        try:
            c["fit_score"] = float(calculate_fit_score(c))
        except Exception as e:
            logger.warning(f"Score error on candidate {c.get('display_name', '?')}: {e}")
            c["fit_score"] = 0.0
        enriched.append(c)

    filtered = []
    for c in enriched:
        exp = _safe_float(c.get("experience_years", 0))
        sal = _safe_float(c.get("expected_salary", 9e9))
        avail_ok = _is_available_now(c.get("availability", ""))
        if exp >= min_experience and sal <= max_salary:
            if available_now and not avail_ok:
                continue
            filtered.append(c)

    # เรียงคะแนนมาก -> น้อย
    filtered.sort(key=lambda x: x.get("fit_score", 0.0), reverse=True)

    summary = {
        "total_candidates": len(enriched),
        "fit_over_80": sum(1 for c in enriched if _safe_float(c.get("fit_score", 0)) >= 80),
        "available_now": sum(1 for c in enriched if _is_available_now(c.get("availability", ""))),
        "within_budget": sum(1 for c in enriched if _safe_float(c.get("expected_salary")) <= max_salary),
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
            "skills": c.get("skills", []),
            "languages": c.get("languages", []),
            "certifications": c.get("certifications", []),
            "portfolio": c.get("portfolio", []),
            "evidence_snippets": c.get("evidence_snippets", [])
        })

    return {"summary": summary, "candidates": output}

@router.get("/import-summary")
def get_import_summary():
    try:
        p = get_import_log_path()
        with open(p, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load import log: {e}")
        return JSONResponse(status_code=500, content={"error": "Failed to read import log"})
    
    rows = []
    if isinstance(logs, list):
        rows = logs
    elif isinstance(logs, dict) and isinstance(logs.get("sources"), list):
        rows = logs["sources"]

    source_counts = {}
    for row in rows:
        source = (row.get("source") or "unknown").strip()
        source_counts[source] = source_counts.get(source, 0) + (row.get("count", 1))

    return {
        "total_imported": sum(source_counts.values()),
        "sources": [{"source": k, "count": v} for k, v in source_counts.items()],
    }

