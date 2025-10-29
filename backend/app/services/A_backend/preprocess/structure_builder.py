# backend/app/services/A_backend/preprocess/structure_builder.py
import argparse
import csv
import importlib.util
import json
import os
import re
import unicodedata
from dataclasses import is_dataclass, asdict as dc_asdict
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# ---------- Regex ----------
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(\+?\d[\d\- ()]{7,}\d)")
DATE_RE = re.compile(
    r"(?P<y1>20\d{2}|19\d{2})(?:[./\- ]?(?P<m1>0?[1-9]|1[0-2]))?"
    r"\s*(?:–|-|to|until|through|ถึง|จนถึง|—)\s*"
    r"(?P<y2>present|ปัจจุบัน|ปจบ\.?|20\d{2}|19\d{2})(?:[./\- ]?(?P<m2>0?[1-9]|1[0-2]))?",
    re.I,
)

SECTION_HEADERS = {
    "experience": ["experience", "work history", "employment", "ประสบการณ์", "การทำงาน"],
    "education":  ["education", "การศึกษา", "วุฒิ"],
    "skills":     ["skills", "technical skills", "ทักษะ", "สกิล", "ความสามารถ"],
    "projects":   ["projects", "portfolio", "โปรเจกต์", "โครงงาน"],
}

# ---------- Paths (for skills_master.csv) ----------
# structure_builder.py -> preprocess/ (parents[1] = A_backend)
A_BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = A_BACKEND_DIR / "data"
SKILLS_CSV = DATA_DIR / "skills_master.csv"


# ---------- Utils ----------
def norm_text(t: str) -> str:
    t = unicodedata.normalize("NFKC", t or "").replace("\u00a0", " ")
    t = re.sub(r"[ \t]+", " ", t).replace("\r", "")
    return t.strip()


def first_name_line(text: str) -> str:
    for ln in (text or "").splitlines()[:6]:
        s = ln.strip()
        if s and len(s) < 70 and not re.search(r"resume|curriculum vitae", s, re.I):
            return s
    return ""


def contacts(text: str) -> dict:
    email = EMAIL_RE.search(text or "")
    phone = PHONE_RE.search(text or "")
    loc = ""
    for ln in (text or "").splitlines()[:10]:
        if re.search(r"(Bangkok|Thailand|กรุงเทพ|ถนน|แขวง|เขต)", ln, re.I):
            loc = ln.strip()
            break
    return {
        "email": email.group(0) if email else "",
        "phone": phone.group(0) if phone else "",
        "location": loc,
    }


def locate_sections(text: str) -> Dict[str, str]:
    lines = (text or "").splitlines()
    marks: List[Tuple[int, str]] = []
    for i, ln in enumerate(lines):
        for key, heads in SECTION_HEADERS.items():
            if any(re.search(rf"\b{re.escape(h)}\b", ln, re.I) for h in heads):
                marks.append((i, key))
    marks.sort()
    marks.append((len(lines), "_end"))
    sections: Dict[str, str] = {}
    for (i, key), (j, _) in zip(marks, marks[1:]):
        if key == "_end":
            continue
        sections[key] = "\n".join(lines[i + 1 : j]).strip()
    return sections


def parse_date_span(s: str) -> Tuple[str, str]:
    m = DATE_RE.search(s or "")
    if not m:
        return ("", "")
    y1, m1, y2, m2 = m.group("y1", "m1", "y2", "m2")

    def fmt(y, m):
        if not y:
            return ""
        if re.match(r"present|ปัจจุบัน|ปจบ", y, re.I):
            return "present"
        return f"{y}-{int(m):02d}" if m else f"{y}"

    return fmt(y1, m1), fmt(y2, m2)


def split_bullets(block: str) -> List[str]:
    items: List[str] = []
    for ln in (block or "").splitlines():
        ln = ln.strip("•·●-–• \t").strip()
        if ln:
            items.append(ln)
    return items


# ---------- Extractors ----------
def extract_experiences(text: str) -> List[dict]:
    out: List[dict] = []
    if not text:
        return out
    chunks = [c.strip() for c in re.split(r"\n{2,}", text) if c.strip()]
    for c in chunks:
        start, end = parse_date_span(c)
        first = c.splitlines()[0] if c.splitlines() else ""
        role, company = "", ""
        if " at " in first:
            role, company = first.split(" at ", 1)
        elif " @ " in first:
            role, company = first.split(" @ ", 1)
        elif " - " in first:
            a, b = first.split(" - ", 1)
            company, role = (b, a) if len(b) > len(a) else (a, b)
        out.append(
            {
                "company": company.strip(),
                "role": role.strip(),
                "start": start,
                "end": end if end else "",
                "bullets": split_bullets(c),
            }
        )
    return out


def extract_education(text: str) -> List[dict]:
    out: List[dict] = []
    if not text:
        return out
    chunks = [c.strip() for c in re.split(r"\n{2,}", text) if c.strip()]
    for c in chunks:
        degree, inst = "", ""
        m = re.search(
            r"(B\.Sc\.|BEng|BBA|M\.Sc\.|MBA|Bachelor|Master|Ph\.D\.|ปริญญาตรี|โท|เอก)",
            c,
            re.I,
        )
        if m:
            degree = m.group(0)
        m2 = re.search(r"(University|College|มหาวิทยาลัย|วิทยาลัย)[^,\n]*", c, re.I)
        if m2:
            inst = m2.group(0).strip()
        start, end = parse_date_span(c)
        out.append({"degree": degree, "institution": inst, "start": start, "end": end if end else ""})
    return out


BASIC_SKILL_SEP = re.compile(r"[,\u2022•·/|]+")


def extract_skills(text: str) -> List[str]:
    if not text:
        return []
    toks = [t.strip() for t in BASIC_SKILL_SEP.split(text) if t.strip()]
    toks = [t for t in toks if len(t) > 1 and not re.match(r"^(and|with|of|the|พื้นฐาน)$", t, re.I)]
    seen, out = set(), []
    for t in toks:
        k = t.lower()
        if k not in seen:
            seen.add(k)
            out.append(t)
    return out


# ---------- Skill mining with alias -> canonical ----------
def load_skill_map() -> Dict[str, str]:
    """Read skills_master.csv; map alias(lower) -> canonical"""
    mp: Dict[str, str] = {}
    if not SKILLS_CSV.exists():
        print(f"[WARN] skills_master.csv not found at {SKILLS_CSV}")
        return mp
    with open(SKILLS_CSV, encoding="utf-8") as f:
        rd = csv.DictReader(f)
        for row in rd:
            alias = (row.get("alias") or "").strip()
            canon = (row.get("canonical") or "").strip()
            if not alias or not canon:
                continue
            # รองรับ alias หลายค่าที่คั่นด้วย comma / slash
            aliases = [a.strip() for a in re.split(r"[,/]", alias) if a.strip()]
            for a in aliases:
                mp[a.lower()] = canon
    return mp


def _contains_token(text_lower: str, alias_lower: str) -> bool:
    """match คำแบบระวังขอบคำ (สำหรับข้อความ a-z0-9); ถ้าเป็นไทย/พิเศษ ใช้ substring"""
    if re.search(r"[A-Za-z0-9]", alias_lower):
        return re.search(rf"(?i)(?<!\w){re.escape(alias_lower)}(?!\w)", text_lower) is not None
    return alias_lower in text_lower


def mine_skills_with_alias_map(text: str, alias2canon: Optional[Dict[str, str]] = None) -> List[str]:
    text_lower = (text or "").lower()
    alias2canon = alias2canon or load_skill_map()
    seen, out = set(), []
    for alias_lower, canon in alias2canon.items():
        if _contains_token(text_lower, alias_lower):
            if canon not in seen:
                seen.add(canon)
                out.append(canon)
    return out


# ---------- Safe import: field_extractor (เขียน _extras_<stem>.json ถ้ามี) ----------
def _load_field_extractor():
    fe_path = Path(__file__).resolve().parent / "field_extractor.py"
    if not fe_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("field_extractor", fe_path)
    if not spec or not spec.loader:
        return None
    mod = importlib.util.module_from_spec(spec)  # type: ignore
    spec.loader.exec_module(mod)  # type: ignore
    return mod


# ---------- RAW helpers ----------
def _raw_to_text(raw: dict) -> str:
    """รองรับ RAW หลายรูปแบบ: {'text'}, {'raw_text'}, หรือ {'pages':[{'text':...}]}"""
    if isinstance(raw.get("text"), str):
        return raw["text"]
    if isinstance(raw.get("raw_text"), str):
        return raw["raw_text"]
    pages = raw.get("pages")
    if isinstance(pages, list):
        parts = []
        for p in pages:
            if isinstance(p, dict):
                parts.append(p.get("text", ""))
            else:
                parts.append(str(p))
        return "\n\n".join(parts)
    return ""


# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser(
        description="RAW -> parsed_resume.json (v0.2.0) + optional _extras_<stem>.json"
    )
    ap.add_argument("--in", dest="inp", required=True, help="RAW JSON (from pdf/docx parser)")
    ap.add_argument("--out", dest="out", required=True, help="Output parsed_resume.json")
    args = ap.parse_args()

    raw = json.load(open(args.inp, "r", encoding="utf-8"))
    text = norm_text(_raw_to_text(raw))

    sections = locate_sections(text)

    # --- skills from 'Skills' section
    skills_from_section = extract_skills(sections.get("skills", ""))

    # --- fallback: mine from whole text using skills_master.csv
    if not skills_from_section:
        try:
            mined = mine_skills_with_alias_map(text)
            if mined:
                skills_from_section = mined
        except Exception as e:
            print(f"[WARN] mining skills failed: {e}")

    # ------- parsed_resume.json ตาม schema v0.2.0 -------
    parsed = {
        "source_file": raw.get("source_file", ""),
        "name": first_name_line(text),
        "contacts": contacts(text),
        "education": extract_education(sections.get("education", "")),
        "experiences": extract_experiences(sections.get("experience", "")),
        "skills": skills_from_section,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(parsed, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[OK] built parsed_resume.json (len={len(text)}) → {out_path}")

    # ------- เขียน _extras_<stem>.json ถ้า field_extractor พร้อม -------
    try:
        fe = _load_field_extractor()
        if fe and hasattr(fe, "extract_all"):
            extras_obj = fe.extract_all(text)
            if is_dataclass(extras_obj):
                extras = dc_asdict(extras_obj)
            elif hasattr(extras_obj, "asdict"):
                extras = extras_obj.asdict()  # type: ignore
            elif isinstance(extras_obj, dict):
                extras = extras_obj
            else:
                # fallback generic
                extras = dict(extras_obj.__dict__) if hasattr(extras_obj, "__dict__") else {}
            extras_path = out_path.parent / f"_extras_{out_path.stem}.json"
            json.dump(extras, open(extras_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            print(f"[OK] wrote extras → {extras_path}")
        else:
            print("[WARN] field_extractor not available; skip extras")
    except Exception as e:
        print(f"[WARN] extras skipped: {e}")


if __name__ == "__main__":
    main()
