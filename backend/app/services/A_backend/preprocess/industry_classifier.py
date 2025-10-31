# backend/app/services/A_backend/preprocess/industry_classifier.py
from __future__ import annotations
from pathlib import Path
from collections import Counter
import re, csv
from typing import Iterable, Dict, Tuple

# คีย์เวิร์ดเสริม (กันกรณีไม่มีสกิลตรง)
KEYWORDS = {
    "Tech": [
        r"\b(sql|python|pandas|numpy|docker|kubernetes|airflow|tableau|power\s*bi|github|etl|api|django|flask)\b",
        r"\b(data\s+(engineer|analyst|scientist)|software|developer|ml|ai)\b",
    ],
    "Finance": [
        r"\b(accounting|bookkeep|reconcil|payable|receivable|ifrs|gaap|tax|audit|sap|oracle)\b",
        r"\b(budget|forecast|treasury|payroll|vat)\b",
    ],
    "Hospitality": [
        r"\b(front\s*desk|reception|check[- ]?in|check[- ]?out|concierge|housekeeping|banquet|opera\s*pms|f&b|guest\s*relations?)\b",
        r"\b(hotel|resort)\b",
    ],
    "Marketing": [
        r"\b(seo|sem|google\s*ads|facebook\s*ads|tiktok\s*ads|crm|campaign|brand|content|copywriting|ga4|analytics)\b",
        r"\b(performance\s*marketing|wordpress|shopify)\b",
    ],
    "Healthcare": [
        r"\b(patient\s*care|vital\s*signs?|medical\s*record|wound\s*care|triage|cpr|ekg|emr|ehr|phlebotomy|steriliz)\b",
        r"\b(laboratory|lab|icd-?10|cpt)\b",
    ],
    "Education": [
        r"\b(lesson\s*planning|classroom\s*management|curriculum|assessment|grading|stem|steam|esl|google\s*classroom|lms|moodle)\b",
        r"\b(early\s*childhood|special\s*education|instructional\s*design)\b",
    ],
}

OTHER = "General / Admin / Support"

def _load_alias_map(skills_csv: Path) -> Dict[str, Tuple[str,str]]:
    """
    อ่าน skills_master.csv → คืน dict[alias_lower] = (canonical, industry)
    """
    mp: Dict[str, Tuple[str,str]] = {}
    with open(skills_csv, encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            alias = (row.get("alias") or "").strip().lower()
            canonical = (row.get("canonical") or "").strip()
            industry = (row.get("industry") or "").strip() or OTHER
            if alias:
                mp[alias] = (canonical, industry)
    return mp

def _industry_from_skills(canon_skills: Iterable[str], alias_map: Dict[str, Tuple[str,str]]) -> str | None:
    # นับ industry จาก canonical ที่มีอยู่ในไฟล์ csv
    # สร้าง reverse map: canonical -> industry (ใช้ entry แรกที่เจอ)
    canon2ind: Dict[str,str] = {}
    for a, (c, ind) in alias_map.items():
        canon2ind.setdefault(c, ind)

    cnt = Counter()
    for c in canon_skills or []:
        ind = canon2ind.get(c)
        if ind:
            cnt[ind] += 1
    if not cnt:
        return None
    # เลือกตัวที่มากสุด (tie → ตามลำดับตัวอักษรเพื่อให้คงที่)
    top = sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    return top

def _industry_from_keywords(text: str) -> str | None:
    t = text.lower()
    for ind, patterns in KEYWORDS.items():
        for pat in patterns:
            if re.search(pat, t, flags=re.I):
                return ind
    return None

def classify_industry(
    *,
    text: str,
    canon_skills: Iterable[str],
    skills_csv_path: Path,
) -> str:
    """
    เลือกอุตสาหกรรมจาก (1) canonical skills ที่แมปกับไฟล์ CSV (2) คีย์เวิร์ดเสริม (3) fallback
    """
    alias_map = _load_alias_map(skills_csv_path)
    by_skill = _industry_from_skills(canon_skills, alias_map)
    if by_skill:
        return by_skill

    by_kw = _industry_from_keywords(text or "")
    if by_kw:
        return by_kw

    return OTHER
