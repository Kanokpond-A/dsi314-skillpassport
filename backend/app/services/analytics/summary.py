from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any
import json
import time
from statistics import mean, median

from ..scoring import score_applicant, ScoringConfig

SAMPLES_DIR = Path("shared_data/test_samples")

@dataclass
class _Cache:
    mtime: float = 0.0
    payload: Dict[str, Any] | None = None

_cache = _Cache()

def _folder_mtime(path: Path) -> float:
    if not path.exists():
        return 0.0
    return max((p.stat().st_mtime for p in path.glob("*.json")), default=0.0)

def _load_samples() -> List[Dict[str, Any]]:
    if not SAMPLES_DIR.exists():
        return []
    data = []
    for p in sorted(SAMPLES_DIR.glob("*.json")):
        try:
            data.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            # ข้ามไฟล์ที่อ่านไม่ได้
            continue
    return data

def _band(score: float) -> str:
    # แปลง 0–100 เป็น label แบบง่าย
    if score >= 85: return "Excellent"
    if score >= 70: return "Strong"
    if score >= 50: return "Moderate"
    return "Needs improvement"

def build_summary(refresh: bool = False, limit: int | None = None) -> Dict[str, Any]:
    """
    อ่านไฟล์ parsed_resume_*.json → คำนวณคะแนน → สรุปสถิติในครั้งเดียว
    ใช้ in-memory cache เพื่อลดเวลาคำนวณซ้ำ
    """
    mt = _folder_mtime(SAMPLES_DIR)
    if (not refresh) and _cache.payload is not None and mt <= _cache.mtime:
        payload = _cache.payload
    else:
        cfg = ScoringConfig()
        rows = []
        top_missing: Dict[str, int] = {}
        scores_0_100: List[float] = []
        matched_pct: List[float] = []
        evidence_cnt: List[int] = []
        band_count: Dict[str, int] = {"Excellent":0,"Strong":0,"Moderate":0,"Needs improvement":0}

        for rec in _load_samples():
            name = rec.get("name", "Unknown")
            skills = rec.get("skills", [])
            evidence = rec.get("evidence", [])
            res = score_applicant(skills, evidence, cfg)
            hr = res["hr_view"]
            sc = float(hr["score"])          # 0–100
            scores_0_100.append(sc)
            matched_pct.append(hr["summary"]["matched_percent"])
            evidence_cnt.append(hr["summary"]["evidence_count"])
            band_count[_band(sc)] += 1

            for m in hr["summary"]["missing_skills"]:
                top_missing[m] = top_missing.get(m, 0) + 1

            rows.append({
                "name": name,
                "score": sc,
                "level": hr["level"],
                "matched_percent": hr["summary"]["matched_percent"],
                "missing_skills": hr["summary"]["missing_skills"],
                "evidence_count": hr["summary"]["evidence_count"],
            })

        rows_sorted = sorted(rows, key=lambda r: r["score"], reverse=True)
        if limit:
            rows_sorted = rows_sorted[:max(1, int(limit))]

        payload = {
            "meta": {
                "generated_at": int(time.time()),
                "source_dir": str(SAMPLES_DIR),
                "count": len(rows),
            },
            "metrics": {
                "avg_score": round(mean(scores_0_100), 1) if scores_0_100 else 0.0,
                "median_score": round(median(scores_0_100), 1) if scores_0_100 else 0.0,
                "avg_matched_percent": round(mean(matched_pct), 1) if matched_pct else 0.0,
                "avg_evidence": round(mean(evidence_cnt), 2) if evidence_cnt else 0.0,
                "bands": band_count,
            },
            "top_gaps": sorted(
                [{"skill": k, "count": v} for k, v in top_missing.items()],
                key=lambda x: x["count"],
                reverse=True
            ),
            "candidates": rows_sorted,
        }
        _cache.mtime = mt
        _cache.payload = payload

    return payload
