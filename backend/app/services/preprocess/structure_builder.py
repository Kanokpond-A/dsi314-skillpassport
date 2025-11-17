# backend/app/services/A_backend/preprocess/structure_builder.py
import argparse, csv, importlib.util, json, re, unicodedata
from dataclasses import is_dataclass, asdict as dc_asdict
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# =========================
# Regex & Section Keywords
# =========================
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(\+?\d[\d\- ()]{7,}\d)")
DATE_RE  = re.compile(
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

# Paths
A_BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR      = A_BACKEND_DIR / "data"
SKILLS_CSV    = DATA_DIR / "skills_master.csv"

# =========================
# Text Utilities
# =========================
def norm_text(t: str) -> str:
    t = unicodedata.normalize("NFKC", (t or "")).replace("\u00a0", " ")
    t = re.sub(r"[ \t]+", " ", t).replace("\r", "")
    return t.strip()

def _looks_like_name_en(s: str) -> bool:
    parts = s.strip().split()
    if len(parts) < 2 or len(parts) > 5:
        return False
    ok = 0
    for w in parts:
        if re.fullmatch(r"[A-Z][a-zA-Z\-'.]+", w):
            ok += 1
    return ok >= 2

def _looks_like_name_th(s: str) -> bool:
    return bool(re.fullmatch(r"[ก-๙]+(?:\s+[ก-๙]+){1,3}", s.strip()))

def _is_email_or_phone_line(s: str) -> bool:
    return bool(EMAIL_RE.search(s) or PHONE_RE.search(s))

def _name_from_email(text: str) -> str:
    m = EMAIL_RE.search(text or "")
    if not m:
        return ""
    user = m.group(0).split("@",1)[0]
    user = re.sub(r"[^A-Za-zก-๙_\. -]+"," ",user)
    parts = [p for p in re.split(r"[._\- ]+", user) if p]
    if not parts:
        return ""
    parts = [p.capitalize() for p in parts]
    guess = " ".join(parts[:3]).strip()
    # ตัดคำทั่ว ๆ ไป
    guess = re.sub(r"\b(resume|cv)\b", "", guess, flags=re.I).strip()
    return guess

def _name_from_filename(source_file: str) -> str:
    if not source_file:
        return ""
    stem = Path(source_file).stem
    stem = re.sub(r"(?i)\b(resume|cv)\b", "", stem)
    stem = re.sub(r"[_\-\.]+", " ", stem)
    stem = re.sub(r"\d+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    # ไทยหรืออังกฤษ
    if _looks_like_name_th(stem):
        return stem
    # Title Case ช่วย
    tc = " ".join(w.capitalize() for w in stem.split()[:4])
    return tc if _looks_like_name_en(tc) else ""

def first_name_line(text: str, source_hint: str = "") -> str:
    lines = [(ln or "").strip() for ln in (text or "").splitlines()[:20]]
    skip_pat = re.compile(r"(?i)\b(resume|curriculum vitae|cv|contact|profile)\b")

    def looks_like_name_loose(s: str) -> bool:
        # ยอมรับไทย/อังกฤษ 2–5 คำ ไม่เอาบรรทัดที่มี @, ตัวเลขเยอะ, หรือยาวเกิน
        if "@" in s or len(s) > 70: 
            return False
        if re.search(r"\d{3,}", s):
            return False
        th = re.fullmatch(r"[ก-๙]+(?:\s+[ก-๙]+){1,4}", s)
        en = re.fullmatch(r"[A-Za-z][A-Za-z\-'.]+(?:\s+[A-Za-z][A-Za-z\-'.]+){1,4}", s)
        return bool(th or en)

    # 1) “Name: … / ชื่อ: …”
    for s in lines:
        if not s or _is_email_or_phone_line(s) or skip_pat.search(s): 
            continue
        m = re.match(r"(?i)\s*(name|ชื่อ)\s*[:：]\s*(.+)$", s)
        if m and looks_like_name_loose(m.group(2).strip()):
            return m.group(2).strip()

    # 2) ไทย/อังกฤษตามกฎเดิม
    for s in lines:
        if not s or _is_email_or_phone_line(s) or skip_pat.search(s): 
            continue
        if _looks_like_name_en(s) or _looks_like_name_th(s):
            return s.strip()

    # 3) อังกฤษตัวพิมพ์เล็ก → titlecase แล้วเช็คใหม่
    for s in lines:
        if not s or _is_email_or_phone_line(s) or skip_pat.search(s): 
            continue
        s2 = " ".join(w.capitalize() for w in s.split())
        if looks_like_name_loose(s2):
            return s2

    # 4) เดาจากอีเมล
    guess = _name_from_email(text)
    if guess:
        return guess

    # 5) เดาจากไฟล์เนม (ถ้ามี hint)
    fn = _name_from_filename(source_hint or "")
    if fn:
        return fn

    # 6) fallback: บรรทัดสั้น ๆ ที่ไม่ใช่หัวข้อ
    for s in lines[:8]:
        if s and not skip_pat.search(s) and not _is_email_or_phone_line(s):
            return s
    return ""

def contacts(text: str) -> dict:
    email = EMAIL_RE.search(text or "")
    phone = PHONE_RE.search(text or "")
    loc = ""
    for ln in (text or "").splitlines()[:15]:
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
            if any(re.search(rf"\b{re.escape(h)}\b[:：]?", ln, re.I) for h in heads):
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
        # เก็บ “- ”/“• ”/“•”/“– ” ฯลฯ
        ln = re.sub(r"^[\u2022•·\-\–\—\*\+]+\s*", "", ln).strip()
        if ln:
            items.append(ln)
    return items

# =========================
# RAW helpers
# =========================
def _raw_to_text(raw: dict) -> str:
    """รองรับ RAW หลายแบบ: {'text'}, {'raw_text'}, หรือ {'pages':[{'text':...}]}"""
    if isinstance(raw.get("text"), str):
        return raw["text"]
    if isinstance(raw.get("raw_text"), str):
        return raw["raw_text"]
    pages = raw.get("pages")
    if isinstance(pages, list):
        parts = []
        for p in pages:
            if isinstance(p, dict):
                parts.append(p.get("text", "") or "")
            else:
                parts.append(str(p))
        return "\n\n".join(parts)
    return ""

# =========================
# Experience / Education
# =========================
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
        out.append({
            "company": company.strip(),
            "role": role.strip(),
            "start": start,
            "end": end if end else "",
            "bullets": split_bullets(c),
        })
    return out

def extract_education(text: str) -> List[dict]:
    out: List[dict] = []
    if not text:
        return out
    chunks = [c.strip() for c in re.split(r"\n{2,}", text) if c.strip()]
    for c in chunks:
        degree, inst = "", ""
        m = re.search(r"(B\.Sc\.|BEng|BBA|M\.Sc\.|MBA|Bachelor|Master|Ph\.D\.|ปริญญาตรี|โท|เอก)", c, re.I)
        if m: degree = m.group(0)
        m2 = re.search(r"(University|College|มหาวิทยาลัย|วิทยาลัย)[^,\n]*", c, re.I)
        if m2: inst = m2.group(0).strip()
        start, end = parse_date_span(c)
        out.append({"degree": degree, "institution": inst, "start": start, "end": end if end else ""})
    return out

# =========================
# Skills (clean + alias/mining)
# =========================
BASIC_SKILL_SEP = re.compile(r"[,\u2022•·/|;\n]+", re.UNICODE)
STOP_HEADERS_RE = re.compile(
    r"(?i)\b(certifications?|awards?|achievements?|courses?|training|publications?|career objective|objective)\b"
)
ALWAYS_KEEP = {
    "google analytics", "google analytics 4", "power bi", "tableau", "excel",
    "python", "sql", "postgresql", "mysql", "git", "docker", "apache spark",
    "apache kafka", "tensorflow", "pytorch", "scikit-learn", "seaborn",
    "matplotlib", "looker studio", "dbt", "airflow"
}

def _truncate_at_stops(text: str) -> str:
    m = STOP_HEADERS_RE.search(text or "")
    return (text[: m.start()] if m else text).strip()

def _normalize_piece(t: str) -> str:
    t = (t or "").strip()
    t = re.sub(r"^[\-\–\—•·\*\(\[\{]+", "", t)
    t = re.sub(r"[\)\]\}]+$", "", t)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"^(and|with|skills?[:]?)\s+", "", t, flags=re.I)
    t = re.sub(r"\s+(skills?|tools?)$", "", t, flags=re.I)
    return t.strip(" .;,")

def _is_noise(tok: str) -> bool:
    if not tok:
        return True
    words = tok.split()
    if len(words) > 4 and tok.lower() not in ALWAYS_KEEP:
        return True
    if re.search(r"\b(I\'?m|I am|I have|seeking|excellent|presenting|gathering|analyzing|communication)\b", tok, re.I):
        return True
    return False

def _dedupe_keep_order(items: List[str]) -> List[str]:
    seen, out = set(), []
    for x in items:
        k = x.lower()
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out

def extract_skills(block_or_text: str) -> List[str]:
    if not block_or_text:
        return []
    text = _truncate_at_stops(block_or_text)
    raw = [p for p in BASIC_SKILL_SEP.split(text) if p and p.strip()]
    cleaned = []
    for p in raw:
        t = _normalize_piece(p)
        if not _is_noise(t):
            cleaned.append(t)
    return _dedupe_keep_order(cleaned)

# ---- alias/canonical map & mining ----
def load_skill_map() -> Dict[str, str]:
    """อ่าน skills_master.csv → map alias(lower) -> canonical"""
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
            for a in [a.strip() for a in re.split(r"[,/]", alias) if a.strip()]:
                mp[a.lower()] = canon
    return mp

def _normalize_compact(s: str) -> str:
    return re.sub(r"[ \-_.]", "", s.lower())

def _contains_word_or_substring(text_lower: str, alias_lower: str, text_compact: str) -> bool:
    if re.search(r"[A-Za-z0-9]", alias_lower):
        if re.search(rf"(?i)(?<!\w){re.escape(alias_lower)}(?!\w)", text_lower):
            return True
    else:
        if alias_lower in text_lower:
            return True
    alias_comp = _normalize_compact(alias_lower)
    return alias_comp and (alias_comp in text_compact)

def mine_skills_with_alias_map(text: str, alias2canon: Optional[Dict[str, str]] = None) -> List[str]:
    text_lower   = (text or "").lower()
    text_compact = _normalize_compact(text or "")
    alias2canon  = alias2canon or load_skill_map()
    seen, out = set(), []
    for alias_lower, canon in alias2canon.items():
        if _contains_word_or_substring(text_lower, alias_lower, text_compact):
            if canon.lower() not in seen:
                seen.add(canon.lower())
                out.append(canon)
    return out

def normalize_with_alias_map(raw_skills: List[str], alias2canon: Dict[str, str]) -> List[str]:
    if not raw_skills:
        return []
    out, seen = [], set()
    for s in raw_skills:
        can = alias2canon.get(s.lower(), s)
        kc = can.lower()
        if kc not in seen:
            seen.add(kc)
            out.append(can)
    return out

# =========================
# Simple Industry Classifier (rule-based)
# =========================
OTHER_INDUSTRY = "General / Admin / Support"

KEYWORDS_BY_INDUSTRY = {
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

def _alias_to_industry_map() -> Dict[str, str]:
    """reverse จาก CSV: canonical -> industry (เอาอันแรกที่พบ)"""
    rev: Dict[str, str] = {}
    if SKILLS_CSV.exists():
        with open(SKILLS_CSV, encoding="utf-8") as f:
            rd = csv.DictReader(f)
            for row in rd:
                can = (row.get("canonical") or "").strip()
                ind = (row.get("industry") or "").strip() or OTHER_INDUSTRY
                if can and can not in rev:
                    rev[can] = ind
    return rev

def classify_industry(text: str, canon_skills: List[str]) -> str:
    # 1) จาก canonical skills ที่ผูก industry ไว้ใน CSV
    canon2ind = _alias_to_industry_map()
    counts: Dict[str, int] = {}
    for c in canon_skills or []:
        ind = canon2ind.get(c)
        if ind:
            counts[ind] = counts.get(ind, 0) + 1
    if counts:
        return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    # 2) keyword rule-based
    t = (text or "").lower()
    for ind, pats in KEYWORDS_BY_INDUSTRY.items():
        for pat in pats:
            if re.search(pat, t, flags=re.I):
                return ind
    # 3) fallback
    return OTHER_INDUSTRY

# =========================
# Extras writer (optional)
# =========================
def _load_field_extractor():
    fe_path = Path(__file__).resolve().parent / "field_extractor.py"
    if not fe_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("field_extractor", fe_path)
    if not spec or not spec.loader:
        return None
    mod = importlib.util.module_from_spec(spec)  # type: ignore
    spec.loader.exec_module(mod)                 # type: ignore
    return mod

# --------- Sanitizer (กันพัง) ----------
def _ensure_list(x):
    return x if isinstance(x, list) else ([] if x is None else [x])

def _sanitize(parsed: dict) -> dict:
    parsed["name"] = parsed.get("name") or ""
    parsed["contacts"] = parsed.get("contacts") or {}
    parsed["skills"] = parsed.get("skills") or []
    parsed["education"] = parsed.get("education") or []
    parsed["experiences"] = parsed.get("experiences") or []
    # บังคับชนิด
    if not isinstance(parsed["skills"], list): parsed["skills"] = _ensure_list(parsed["skills"])
    if not isinstance(parsed["education"], list): parsed["education"] = _ensure_list(parsed["education"])
    if not isinstance(parsed["experiences"], list): parsed["experiences"] = _ensure_list(parsed["experiences"])
    return parsed

# =========================
# CLI
# =========================
def main():
    ap = argparse.ArgumentParser(
        description="RAW -> parsed_resume.json (v0.2.1) + optional _extras_<stem>.json"
    )
    ap.add_argument("--in",  dest="inp", required=True, help="RAW JSON (from pdf/docx parser)")
    ap.add_argument("--out", dest="out", required=True, help="Output parsed_resume.json")
    args = ap.parse_args()

    raw  = json.load(open(args.inp, "r", encoding="utf-8"))
    text = norm_text(_raw_to_text(raw))
    sections = locate_sections(text)

    # --- skills: section + mining → normalize + union ---
    alias_map = load_skill_map()
    section_sk = extract_skills(sections.get("skills", ""))
    mined_sk   = mine_skills_with_alias_map(text, alias_map)
    union = []
    seen  = set()
    for s in (section_sk or []) + (mined_sk or []):
        k = (alias_map.get(s.lower(), s)).strip() if isinstance(s,str) else ""
        if not k: continue
        lk = k.lower()
        if lk not in seen:
            seen.add(lk)
            union.append(k)
    skills = normalize_with_alias_map(union, alias_map)

    # --- industry ---
    industry = classify_industry(text, skills)

    parsed = {
        "source_file": raw.get("source_file", ""),
        "name": first_name_line(text, raw.get("source_file", "")),
        "contacts": contacts(text),
        "industry": industry,
        "education":  extract_education(sections.get("education", "")),
        "experiences": extract_experiences(sections.get("experience", "")),
        "skills": skills,
    }

    parsed = _sanitize(parsed)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(parsed, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[OK] built parsed_resume.json (len={len(text)}) -> {out_path}")

    # optional extras
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
                extras = dict(extras_obj.__dict__) if hasattr(extras_obj, "__dict__") else {}
            extras_path = out_path.parent / f"_extras_{out_path.stem}.json"
            json.dump(extras, open(extras_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            print(f"[OK] wrote extras -> {extras_path}")
        else:
            print("[WARN] field_extractor not available; skip extras")
    except Exception as e:
        print(f"[WARN] extras skipped: {e}")

if __name__ == "__main__":
    main()



