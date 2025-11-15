# jd_parser.py  —  Cleaned & Safe version
# ------------------------------------------------------------
# รวม 3 โหมดการรับ JD (inline / text / template) → คืนรูปแบบมาตรฐานเดียว
# พร้อม normalization เบื้องต้น + กัน error และ fallback อัตโนมัติ
# ------------------------------------------------------------

from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Dict, List

import yaml

# ---- Path to config (ปรับเส้นทางให้ตรงโปรเจกต์ของคุณ) --------------------
# สมมติไฟล์นี้อยู่ใน backend/app/services/scoring/jd_parser.py
# jd_templates.yml อยู่ที่   backend/app/config/jd_templates.yml
ROOT = Path(__file__).resolve().parents[2]   # .../backend
JD_PATH = ROOT / "app" / "config" / "jd_templates.yml"

# ---- Patterns / Normalization ----------------------------------------------
# รายการสกิลยอดฮิต (เขียนแบบ regex) — เริ่มจากแกนหลักก่อน ขยายได้ใน YAML ภายหลัง
SKILL_PATTERNS = re.compile(
    r"\b("
    r"python|sql|excel|r|tableau|power\s*bi|looker|bi|"
    r"etl|airflow|dbt|aws|gcp|azure|spark|pyspark|"
    r"ml|machine\s*learning|statistics|"
    r"fastapi|django|flask|docker|kubernetes"
    r")\b",
    re.IGNORECASE
)

def _normalize_skill(token: str) -> str:
    """ทำให้รูปแบบสกิลสม่ำเสมอ เช่น 'PowerBI' -> 'power bi'"""
    t = token.strip().lower()
    if t.replace(" ", "") == "powerbi":
        return "power bi"
    return t

# ---- Parsers for each input mode -------------------------------------------
def parse_from_inline(text: str) -> Dict:
    """
    รับ JD แบบ JSON string สั้น ๆ
    eg. {"name":"data_analyst","required_skills":["python","sql"]}
    """
    try:
        data = json.loads(text or "{}")
    except Exception as e:
        raise ValueError(f"Invalid --jd-inline JSON: {e}")

    skills: List[str] = []
    if isinstance(data, dict):
        raw = data.get("required_skills") or data.get("skills") or []
        if isinstance(raw, list):
            skills = [_normalize_skill(x) for x in raw if isinstance(x, str)]

    return {
        "required_skills": sorted(set(skills)),
        "name": (data.get("name") if isinstance(data, dict) else None) or "inline",
        "source": "inline",
    }

def parse_from_text(text: str) -> Dict:
    """
    รับ JD เป็นข้อความยาว → ใช้ regex จับสกิลที่รู้จัก
    """
    skills = set()
    for m in SKILL_PATTERNS.finditer(text or ""):
        token = m.group(0)
        skills.add(_normalize_skill(token))

    return {
        "required_skills": sorted(skills),
        "name": "from_text",
        "source": "text",
    }

def parse_from_template(key: str) -> Dict:
    """
    รับ key ของเทมเพลต → โหลดจาก jd_templates.yml
    ถ้าไฟล์/คีย์ไม่เจอ จะ fallback เป็น generic
    """
    # ถ้าไฟล์เทมเพลตยังไม่มี ให้ fallback
    if not JD_PATH.exists():
        return {
            "required_skills": ["communication", "teamwork"],
            "name": "generic",
            "source": "fallback",
        }

    try:
        with JD_PATH.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        # กัน yaml พัง
        return {
            "required_skills": ["communication", "teamwork"],
            "name": f"generic (yaml error: {e})",
            "source": "fallback",
        }

    k = (key or "").strip().lower()
    jd = data.get(k) or data.get("generic") or {
        "required_skills": ["communication", "teamwork"]
    }

    # normalize skills เผื่อใน YAML พิมพ์คละรูปแบบ
    req = jd.get("required_skills") or jd.get("skills") or []
    if isinstance(req, list):
      req_norm = sorted({_normalize_skill(x) for x in req if isinstance(x, str)})
    else:
      req_norm = ["communication", "teamwork"]

    return {
        "required_skills": req_norm,
        "name": (jd.get("name") or (k if k in data else "generic")),
        "source": "template",
    }

# ---- Orchestrator -----------------------------------------------------------
def parse_jd(args) -> Dict:
    """
    รวม 3 โหมดให้เหลือ dict มาตรฐานเดียว:
    { required_skills: [...], name: str, source: "inline|text|template|fallback" }
    ลำดับความสำคัญ: inline > text > template > fallback
    """
    if getattr(args, "jd_inline", None):
        return parse_from_inline(args.jd_inline)

    if getattr(args, "jd_text", None):
        return parse_from_text(args.jd_text)

    if getattr(args, "jd_template", None):
        return parse_from_template(args.jd_template)

    # สุดท้ายจริง ๆ (ไม่ส่งอะไรมาก็ยังรันต่อได้)
    return {
        "required_skills": ["communication", "teamwork"],
        "name": "generic",
        "source": "fallback",
    }
