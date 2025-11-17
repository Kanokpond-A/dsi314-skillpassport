# backend/app/scoring/logic_020.py

from typing import Dict, Any
import math

"""
calculate_fit_score(candidate: dict) -> float

Logic version 0.22 (adjusted weights):
ใช้สำหรับ HR dashboard และการกรองก่อนสัมภาษณ์

- skills match               (25%)
- years of experience        (10%)
- availability urgency       (15%)
- expected salary fit        (10%)
- education level match      (10%)
- language proficiency       (10%)
- certifications/portfolio   (20%)

รวม: 100%
"""

def _clamp_score(x: float) -> float:
    return max(0.0, min(100.0, x))


def _score_skills(candidate: Dict[str, Any]) -> float:
    skills = set([s.lower().strip() for s in candidate.get("skills", []) if isinstance(s, str)])
    req = set([s.lower().strip() for s in candidate.get("required_skills", []) if isinstance(s, str)])
    if not req:
        return 50.0
    if not skills:
        return 0.0
    match_count = sum(1 for s in req if s in skills)
    return (match_count / len(req)) * 100.0


def _score_experience(candidate: Dict[str, Any]) -> float:
    yrs = candidate.get("experience_years", 0) or 0
    try:
        yrs = float(yrs)
    except (TypeError, ValueError):
        yrs = 0.0
    if yrs <= 0:
        base = 10.0
    elif yrs >= 3.0:
        base = 100.0
    else:
        ratio = yrs / 3.0
        base = 10.0 + ratio * (100.0 - 10.0)
    return _clamp_score(base)


def _score_availability(candidate: Dict[str, Any]) -> float:
    avail_raw = str(candidate.get("availability", "")).lower()
    if any(k in avail_raw for k in ["immediate", "now", "available now", "asap", "พร้อมทันที", "start now"]):
        return 100.0

    import re
    days_est = None
    if "month" in avail_raw:
        m = re.search(r"(\d+)", avail_raw)
        month_n = int(m.group(1)) if m else 1
        days_est = month_n * 30
    elif "day" in avail_raw or "notice" in avail_raw:
        m = re.search(r"(\d+)", avail_raw)
        if m:
            days_est = int(m.group(1))

    if days_est is not None:
        if days_est <= 0:
            return 100.0
        elif days_est <= 30:
            return 80.0
        else:
            return 50.0
    return 60.0


def _score_salary(candidate: Dict[str, Any]) -> float:
    def _to_float(v):
        if v is None:
            return None
        try:
            if isinstance(v, str):
                v = v.replace(",", "").strip()
            return float(v)
        except (TypeError, ValueError):
            return None

    sal = _to_float(candidate.get("expected_salary"))
    bud = _to_float(candidate.get("budget_max"))

    if sal is None or bud is None or bud <= 0:
        return 60.0
    if sal <= bud:
        return 100.0
    if sal <= bud * 1.2:
        return 70.0
    return 30.0


def _score_education(candidate: Dict[str, Any]) -> float:
    level = str(candidate.get("education_level", "")).lower()
    required = str(candidate.get("required_education", "")).lower()
    levels = ["none", "highschool", "vocational", "diploma", "bachelor", "master", "phd"]
    level_rank = {lvl: i for i, lvl in enumerate(levels)}
    user_rank = level_rank.get(level, 0)
    req_rank = level_rank.get(required, 3)  # default: bachelor
    if user_rank < req_rank:
        return 20.0
    elif user_rank == req_rank:
        return 80.0
    else:
        return 100.0


def _score_language(candidate: Dict[str, Any]) -> float:
    langs = candidate.get("languages", [])
    score = 0.0
    for lang in langs:
        
        # ▼▼▼ [ เพิ่มโค้ดป้องกันการแครช ] ▼▼▼
        name = ""
        level = ""
        if isinstance(lang, dict):
            name = lang.get("name", "").lower()
            level = str(lang.get("level", "")).lower()
        elif isinstance(lang, str):
            name = lang.lower()
            level = "intermediate" # หรือค่า default ที่คุณต้องการ
        # ▲▲▲ [ สิ้นสุดโค้ดแก้ไข ] ▲▲▲

        if name in ["english", "อังกฤษ"]:
            if "native" in level or "professional" in level:
                score += 100.0
            elif "intermediate" in level:
                score += 70.0
            elif "basic" in level:
                score += 40.0
    return min(score, 100.0)


def _score_certification(candidate: Dict[str, Any]) -> float:
    certs = candidate.get("certifications", [])
    portfolio = candidate.get("portfolio", None)
    if not certs and not portfolio:
        return 30.0
    score = 50.0
    if certs:
        score += min(len(certs) * 10, 30)
    if portfolio:
        score += 20
    return min(score, 100.0)


def calculate_fit_score(candidate: Dict[str, Any]) -> float:
    s_skills = _score_skills(candidate) * 0.25
    s_exp = _score_experience(candidate) * 0.10
    s_avail = _score_availability(candidate) * 0.15
    s_salary = _score_salary(candidate) * 0.10
    s_edu = _score_education(candidate) * 0.10
    s_lang = _score_language(candidate) * 0.10
    s_cert = _score_certification(candidate) * 0.20

    total = s_skills + s_exp + s_avail + s_salary + s_edu + s_lang + s_cert
    return round(_clamp_score(total), 2)

