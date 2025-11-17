# backend/app/services/A_backend/preprocess/skills_normalizer.py
# Minimal, structure_builder-compatible skill normalizer

import csv
import re
from pathlib import Path
from typing import Dict, List, Tuple

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data" / "skills_master.csv"

# -----------------------------
# Fallback aliases (ใช้เมื่อ CSV หาย/ไม่มีคอลัมน์)
# -----------------------------
DEFAULT_ALIASES: Dict[str, str] = {
    "py": "Python",
    "python": "Python",
    "sql": "SQL",
    "ms excel": "Excel",
    "excel": "Excel",
    "บริการลูกค้า": "Customer Service",
    "customer service": "Customer Service",
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ga": "Google Analytics",
    "ga4": "Google Analytics 4",
    "ppt": "PowerPoint"
}

_TOKEN_SPLIT_RE = re.compile(r"[,\u2022•·/|;]+")
_WS_RE = re.compile(r"\s+")


def _clean_token(t: str) -> str:
    """ทำความสะอาด token ก่อน map ให้สั้น กระชับ"""
    t = (t or "").strip()
    if not t:
        return ""
    # ตัดรายละเอียดวงเล็บ
    t = re.sub(r"\([^)]*\)", "", t)
    t = re.sub(r"\[[^]]*\]", "", t)
    t = re.sub(r"\{[^}]*\}", "", t)
    # ช่องว่าง และอักขระหัวท้าย
    t = _WS_RE.sub(" ", t).strip(" .;,-–—•·|/_")
    return t


def _split_tokens(s: str) -> List[str]:
    if not s:
        return []
    parts = [p for p in _TOKEN_SPLIT_RE.split(s) if p and p.strip()]
    out: List[str] = []
    for p in parts:
        if " & " in p:
            out.extend([x.strip() for x in p.split("&") if x.strip()])
        else:
            out.append(p)
    return [_clean_token(x) for x in out if _clean_token(x)]


def load_skill_map(csv_path: Path = DATA) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    คืน (alias->canonical, canonical->category)
    - ใช้คอลัมน์ 'alias', 'canonical'; หมวดหมู่ใช้ 'category' หรือ 'industry'
    - alias ใน CSV แยกด้วย ',' หรือ '/'
    - มี fallback DEFAULT_ALIASES เสมอ
    """
    alias2canon: Dict[str, str] = {}
    canon2cat: Dict[str, str] = {}

    try:
        with open(csv_path, encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            cols = {c.lower(): c for c in (rdr.fieldnames or [])}
            col_alias = cols.get("alias") or "alias"
            col_canon = cols.get("canonical") or "canonical"
            col_cat   = cols.get("category") or cols.get("industry")  # fallback

            for row in rdr:
                alias_raw = (row.get(col_alias) or "").strip()
                canon     = (row.get(col_canon) or "").strip()
                cat       = (row.get(col_cat) or "").strip() if col_cat else ""

                if not alias_raw or not canon:
                    continue

                # alias อาจคั่นด้วย comma/slash
                for a in [x.strip() for x in re.split(r"[,/]", alias_raw) if x.strip()]:
                    alias2canon.setdefault(a.lower(), canon)

                if cat and canon:
                    canon2cat.setdefault(canon, cat)
    except FileNotFoundError:
        # ไม่มีไฟล์ ก็พึ่ง fallback อย่างเดียว
        pass

    # ผสาน fallback aliases (ไม่ override ของ CSV)
    for a, c in DEFAULT_ALIASES.items():
        alias2canon.setdefault(a.lower(), c)

    return alias2canon, canon2cat


def normalize_skills(raw: List[str], csv_path: Path = DATA) -> List[str]:
    """
    รับลิสต์สกิลหยาบ → แตก token → map alias→canonical → dedupe (รักษาลำดับแรก)
    คืนค่าเป็นลิสต์สตริงของ canonical skills
    (ให้ตรงกับการใช้งานใน structure_builder.py)
    """
    alias2canon, _ = load_skill_map(csv_path)
    seen: set = set()
    out: List[str] = []

    tokens: List[str] = []
    for item in (raw or []):
        tokens.extend(_split_tokens(item))

    for t in tokens:
        can = alias2canon.get(t.lower(), t)
        key = can.lower()
        if key not in seen:
            seen.add(key)
            out.append(can)

    return out

