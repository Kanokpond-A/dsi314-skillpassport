import argparse, json, re, os, unicodedata
from pathlib import Path

# ---------------- Regular Expressions ----------------
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
    "projects":   ["projects", "portfolio", "โปรเจกต์", "โครงงาน"]
}

# ---------------- Utility Functions ----------------
def norm_text(t: str) -> str:
    t = unicodedata.normalize("NFKC", t).replace("\u00a0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = t.replace("\r", "")
    return t.strip()

def first_name_line(text: str) -> str:
    for ln in text.splitlines()[:6]:
        s = ln.strip()
        if s and len(s) < 70 and not re.search(r"resume|curriculum vitae", s, re.I):
            return s
    return ""

def contacts(text: str) -> dict:
    email = EMAIL_RE.search(text)
    phone = PHONE_RE.search(text)
    loc = ""
    # crude heuristic: find a line with a Thai province or common address keyword
    for ln in text.splitlines()[:10]:
        if re.search(r"(Bangkok|Thailand|กรุงเทพ|ถนน|แขวง|เขต)", ln, re.I):
            loc = ln.strip()
            break
    return {
        "email": email.group(0) if email else "",
        "phone": phone.group(0) if phone else "",
        "location": loc
    }

def locate_sections(text: str) -> dict:
    lines = text.splitlines()
    marks = []
    for i, ln in enumerate(lines):
        for key, heads in SECTION_HEADERS.items():
            if any(re.search(rf"\b{re.escape(h)}\b", ln, re.I) for h in heads):
                marks.append((i, key))
    marks.sort()
    marks.append((len(lines), "_end"))
    sections = {}
    for (i, key), (j, _) in zip(marks, marks[1:]):
        if key == "_end": continue
        sections[key] = "\n".join(lines[i + 1:j]).strip()
    return sections

def parse_date_span(s: str):
    m = DATE_RE.search(s)
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

def split_bullets(block: str):
    items = []
    for ln in block.splitlines():
        ln = ln.strip("•·●-–• \t").strip()
        if ln:
            items.append(ln)
    return items

# ---------------- Extractors ----------------
def extract_experience(text: str):
    out = []
    chunks = [c.strip() for c in re.split(r"\n{2,}", text) if c.strip()]
    for c in chunks:
        start, end = parse_date_span(c)
        first = c.splitlines()[0]
        title, company = "", ""
        if " at " in first:
            title, company = first.split(" at ", 1)
        elif " @ " in first:
            title, company = first.split(" @ ", 1)
        elif " - " in first:
            a, b = first.split(" - ", 1)
            # guess which part is company vs title
            company, title = (b, a) if len(b) > len(a) else (a, b)
        bullets = split_bullets(c)
        out.append({
            "title": title.strip(),
            "company": company.strip(),
            "location": "",
            "start_date": start,
            "end_date": end if end else None,
            "is_current": bool(end in ["present", None]),
            "bullets": bullets
        })
    return out

def extract_education(text: str):
    out = []
    chunks = [c.strip() for c in re.split(r"\n{2,}", text) if c.strip()]
    for c in chunks:
        degree, major, inst = "", "", ""
        m = re.search(r"(B\.Sc\.|BEng|BBA|M\.Sc\.|MBA|Bachelor|Master|Ph\.D\.|ปริญญาตรี|โท|เอก)", c, re.I)
        if m: degree = m.group(0)
        m2 = re.search(r"(University|College|มหาวิทยาลัย|วิทยาลัย)[^,\n]*", c, re.I)
        if m2: inst = m2.group(0).strip()
        m3 = re.search(r"สาขา|Major[: ]+([A-Za-zก-๙ ]+)", c)
        if m3: major = m3.group(1).strip()
        start, end = parse_date_span(c)
        out.append({
            "institution": inst,
            "degree": degree,
            "major": major,
            "gpa": None,
            "start_date": start,
            "end_date": end if end else None,
            "honors": None,
            "activities": []
        })
    return out

BASIC_SKILL_SEP = re.compile(r"[,\u2022•·/|]+")
def extract_skills(text: str):
    toks = [t.strip() for t in BASIC_SKILL_SEP.split(text) if t.strip()]
    toks = [t for t in toks if len(t) > 1 and not re.match(r"^(and|with|of|the|พื้นฐาน)$", t, re.I)]
    seen, out = set(), []
    for t in toks:
        k = t.lower()
        if k not in seen:
            seen.add(k)
            out.append(t)
    return out

def extract_projects(text: str):
    """Extracts portfolio/projects if present"""
    out = []
    chunks = [c.strip() for c in re.split(r"\n{2,}", text) if c.strip()]
    for c in chunks:
        first = c.splitlines()[0]
        url = ""
        m = re.search(r"https?://\S+", c)
        if m: url = m.group(0)
        out.append({
            "title": first[:80],
            "description": c[:400],
            "technologies": [],
            "url": url
        })
    return out

# ---------------- Main CLI ----------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="RAW JSON (from pdf/docx parser)")
    ap.add_argument("--out", dest="out", required=True, help="Output parsed_resume.json")
    args = ap.parse_args()

    raw = json.load(open(args.inp, "r", encoding="utf-8"))
    text = norm_text(raw.get("raw_text", ""))

    sections = locate_sections(text)

    parsed = {
        "schema_version": "0.2.0",
        "resume_id": Path(args.inp).stem,
        "full_name": first_name_line(text),
        "email": contacts(text)["email"],
        "phone": contacts(text)["phone"],
        "location": contacts(text)["location"],
        "linkedin_url": "",
        "github_url": "",
        "portfolio_url": "",
        "headline": None,
        "summary": None,
        "experience": extract_experience(sections.get("experience", "")),
        "education": extract_education(sections.get("education", "")),
        "skills_raw": extract_skills(sections.get("skills", "")),
        "skills_normalized": [],
        "skills_category": {},
        "skills_level": {},
        "languages": [],
        "certifications": [],
        "projects": extract_projects(sections.get("projects", "")),
        "awards": [],
        "volunteering": [],
        "total_years_experience": None,
        "career_level": None,
        "last_position_title": None,
        "fit_score": None,
        "keywords_match": {},
        "source_file": raw.get("source_file", ""),
        "date_parsed": None,
        "parsed_confidence": None
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(parsed, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[OK] built parsed_resume.json → {args.out}")
