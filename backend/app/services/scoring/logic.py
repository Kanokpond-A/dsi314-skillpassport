# backend/app/services/scoring/logic.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable, Dict, List, Tuple
from ...core.logging import get_logger

log = get_logger("ucb.scoring")

# -----------------------------
# 1) Config
# -----------------------------
@dataclass
class ScoringConfig:
    required_weights: Dict[str, float] = field(default_factory=lambda: {
        "Python": 0.35,
        "SQL": 0.25,
        "FastAPI": 0.20,
        "Docker": 0.20,
    })
    aliases: Dict[str, str] = field(default_factory=lambda: {
        "py": "Python",
        "postgres": "SQL",
        "postgresql": "SQL",
        "fast api": "FastAPI",
        "fast-api": "FastAPI",
    })
    evidence_bonus_each: float = 2.5
    evidence_bonus_cap: float = 10.0
    bands: List[Tuple[float, str]] = field(default_factory=lambda: [
        (85, "Excellent fit"),
        (70, "Strong fit"),
        (50, "Moderate fit"),
        (0,  "Needs improvement"),
    ])

# -----------------------------
# 2) Utilities
# -----------------------------
def _canon_builder(cfg: ScoringConfig):
    """สร้างฟังก์ชัน norm(s) ที่แปลงชื่อสกิลเป็นรูปมาตรฐานของ required_weights"""
    alias_low_map = {k.lower(): v for k, v in cfg.aliases.items()}
    req_low_map = {k.lower(): k for k in cfg.required_weights.keys()}

    def norm(s: str) -> str:
        raw = (s or "").strip()
        low = raw.lower()
        if low in alias_low_map:
            return alias_low_map[low]
        if low in req_low_map:
            return req_low_map[low]
        return raw
    return norm

def _band_label(score_0_100: float, cfg: ScoringConfig) -> str:
    for threshold, label in cfg.bands:
        if score_0_100 >= threshold:
            return label
    return cfg.bands[-1][1]

def _make_notes(matched: List[str], missing: List[str]) -> List[str]:
    notes: List[str] = []
    if missing:
        notes.append(f"Key gaps: {', '.join(missing)}")
    if matched:
        notes.append(f"Strengths: {', '.join(matched)}")
    if not matched:
        notes.append("No required skills matched yet.")
    return notes

# -----------------------------
# 3) Scorer
# -----------------------------
def score_applicant(
    skills: Iterable[str],
    evidence: Iterable[dict] | None = None,
    cfg: ScoringConfig | None = None
) -> dict:
    """
    คืนผลลัพธ์:
      - machine_view: {'fit_score': 0-1, 'gaps': [...]}
      - hr_view:      {'score': 0-100, 'level': str, 'summary': {...}, 'breakdown': [...]}
    """
    cfg = cfg or ScoringConfig()
    evidence = list(evidence or [])
    evidence_count = len(evidence)

    norm = _canon_builder(cfg)
    req_norm = cfg.required_weights                     # ไม่ต้อง copy
    have_set = {norm(s) for s in (skills or []) if s}

    log.info(
        f"Start scoring | have={sorted(have_set)} | required={list(req_norm.keys())} "
        f"| weights={list(req_norm.values())}"
    )

    # คำนวณคะแนนตามน้ำหนัก
    max_raw = sum(req_norm.values()) or 1.0
    raw_score = 0.0
    matched: List[str] = []
    missing: List[str] = []
    contributions: List[dict] = []

    for skill, weight in req_norm.items():
        if skill in have_set:
            raw_score += weight
            matched.append(skill)
            contributions.append({"skill": skill, "weight": weight, "hit": True})
            log.debug(f"+ {skill} (w={weight}) -> raw={raw_score:.2f}")
        else:
            missing.append(skill)
            contributions.append({"skill": skill, "weight": weight, "hit": False})
            log.debug(f"- {skill} (w={weight}) -> raw={raw_score:.2f}")

    base_0_100 = (raw_score / max_raw) * 100.0
    bonus = min(cfg.evidence_bonus_each * evidence_count, cfg.evidence_bonus_cap)
    final_0_100 = max(0.0, min(100.0, base_0_100 + bonus))
    band = _band_label(final_0_100, cfg)

    log.info(
        f"Base={base_0_100:.1f} | bonus={bonus:.1f} (evidence={evidence_count}) "
        f"| final={final_0_100:.1f} → {band}"
    )

    matched_pct = round((len(matched) / len(req_norm)) * 100.0, 1) if req_norm else 0.0
    fit_0_1 = round(final_0_100 / 100.0, 2)

    hr_view = {
        "score": round(final_0_100, 1),
        "level": band,  # ← ใช้ตัวแปรที่คำนวณแล้ว ไม่เรียกซ้ำ
        "summary": {
            "matched_skills": matched,
            "missing_skills": missing,
            "matched_percent": matched_pct,
            "evidence_count": evidence_count,
            "evidence_bonus": bonus,
        },
        "breakdown": contributions,
        "notes": _make_notes(matched, missing),
    }

    machine_view = {
        "fit_score": fit_0_1,
        "gaps": missing,
    }

    return {"machine_view": machine_view, "hr_view": hr_view}
