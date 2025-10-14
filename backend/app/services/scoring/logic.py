# backend/app/services/scoring/logic.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable, Dict, List, Tuple
from ...core.logging import get_logger

log = get_logger("ucb.scoring")

# -----------------------------
# 1) การตั้งค่า (แก้ได้ง่าย)
# -----------------------------

@dataclass
class ScoringConfig:
    # สกิลที่ "อยากได้" พร้อมน้ำหนัก (รวมแล้วได้มากกว่า 1 ก็ได้ เดี๋ยวเราแปลงเป็น 0–100 ให้อัตโนมัติ)
    required_weights: Dict[str, float] = field(default_factory=lambda: {
        "Python": 0.35,
        "SQL": 0.25,
        "FastAPI": 0.20,
        "Docker": 0.20,
    })
    # ชื่อเรียกพ้อง/คำสะกดอื่น -> ชื่อมาตรฐาน
    aliases: Dict[str, str] = field(default_factory=lambda: {
        "py": "Python",
        "postgres": "SQL",
        "postgresql": "SQL",
        "fast api": "FastAPI",
        "fast-api": "FastAPI",
    })
    # โบนัสเมื่อพบหลักฐาน (เช่น มีลิงก์ GitHub/ผลงาน หรือ parser เจอในเอกสาร)
    evidence_bonus_each: float = 2.5      # +2.5 คะแนนต่อหลักฐาน
    evidence_bonus_cap: float = 10.0      # รวมโบนัสสูงสุด 10 คะแนน
    # ระดับผลลัพธ์สำหรับ HR
    bands: List[Tuple[float, str]] = field(default_factory=lambda: [
        (85, "Excellent fit"),
        (70, "Strong fit"),
        (50, "Moderate fit"),
        (0,  "Needs improvement"),
    ])

# -----------------------------
# 2) Utilities
# -----------------------------

def _normalize(s: str, cfg: ScoringConfig) -> str:
    """ทำความสะอาดชื่อสกิล แล้ว map เป็นชื่อมาตรฐาน"""
    s0 = (s or "").strip().lower()
    s0 = cfg.aliases.get(s0, s0)
    return s0.title()

def _band_label(score_0_100: float, cfg: ScoringConfig) -> str:
    for threshold, label in cfg.bands:
        if score_0_100 >= threshold:
            return label
    return cfg.bands[-1][1]

# -----------------------------
# 3) ตัวคำนวณหลัก
# -----------------------------

def score_applicant(
    skills: Iterable[str],
    evidence: Iterable[dict] | None = None,
    cfg: ScoringConfig | None = None
) -> dict:
    """
    คืนผลลัพธ์ 2 มุมมอง:
      - machine_view: ใช้ต่อในระบบ (0–1 + gaps)
      - hr_view: สำหรับ HR อ่านเข้าใจง่าย (0–100 + level + breakdown)
    """
    cfg = cfg or ScoringConfig()
    evidence = list(evidence or [])

    # --- เตรียมชุดสกิลของผู้สมัครแบบ normalize ---
    have = {_normalize(s, cfg) for s in (skills or []) if s}

    # --- เตรียมชุดสกิลที่ต้องการแบบ normalize ---
    req_norm = { _normalize(k, cfg): w for k, w in cfg.required_weights.items() }

    # add log
    log.info(f"Start scoring | have={sorted(have)} | required={list(req_norm.keys())} "
             f"| weights={list(req_norm.values())}")

    # --- คำนวณคะแนนตามน้ำหนัก ---
    max_raw = sum(req_norm.values()) or 1.0
    raw_score = 0.0
    # matched: List[str] = []
    # missing: List[str] = []
    # contributions: List[dict] = []   # ใช้อธิบายว่าแต่ละสกิลให้กี่คะแนน
    matched, missing, contributions = [], [], []

    for skill, weight in req_norm.items():
        if skill in have:
            raw_score += weight
            matched.append(skill)
            contributions.append({"skill": skill, "weight": weight, "hit": True})
            log.debug(f"  + {skill:<10} hit  (w={weight}) -> raw={raw_score:.2f}")
        else:
            missing.append(skill)
            contributions.append({"skill": skill, "weight": weight, "hit": False})
            log.debug(f"  - {skill:<10} miss (w={weight}) -> raw={raw_score:.2f}")

    # --- scale เป็น 0–100 ---
    base_score_0_100 = (raw_score / max_raw) * 100.0

    # --- เพิ่มโบนัสจากหลักฐาน ---
    bonus = min(cfg.evidence_bonus_each * len(evidence), cfg.evidence_bonus_cap)
    final_score_0_100 = max(0.0, min(100.0, base_score_0_100 + bonus))

    band = _band_label(final_score_0_100, cfg)

    log.info(f"Base={base_score_0_100:.1f} | bonus={bonus:.1f} (evidence={len(evidence)}) "
             f"| final={final_score_0_100:.1f} → {band}")

    # --- คำนวณสัดส่วนแมตช์ ---
    matched_percent = round((len(matched) / len(req_norm)) * 100, 1) if req_norm else 0.0

    # --- แปลงเป็น 0–1 สำหรับระบบ (machine view) ---
    machine_score_0_1 = round(final_score_0_100 / 100.0, 2)

    # --- สร้างผลลัพธ์แบบ HR-friendly ---
    hr_view = {
        "score": round(final_score_0_100, 1),               # 0–100
        "level": _band_label(final_score_0_100, cfg),       # ข้อความระดับ
        "summary": {
            "matched_skills": matched,
            "missing_skills": missing,
            "matched_percent": matched_percent,             # % แมตช์ตามจำนวนสกิล
            "evidence_count": len(evidence),
            "evidence_bonus": bonus
        },
        "breakdown": contributions,                          # รายการสกิล + น้ำหนัก + ตรง/ไม่ตรง
        "notes": _make_notes(matched, missing)
    }

    # --- มุมมองที่ระบบเดิมใช้งาน (เข้ากับ schema เดิม) ---
    machine_view = {
        "fit_score": machine_score_0_1,   # 0–1 (เช่น 0.87)
        "gaps": missing
    }

    return {
        "machine_view": machine_view,
        "hr_view": hr_view
    }

def _make_notes(matched: List[str], missing: List[str]) -> List[str]:
    notes = []
    if missing:
        notes.append(f"Key gaps: {', '.join(missing)}")
    if matched:
        notes.append(f"Strengths: {', '.join(matched)}")
    if not matched:
        notes.append("No required skills matched yet.")
    return notes
