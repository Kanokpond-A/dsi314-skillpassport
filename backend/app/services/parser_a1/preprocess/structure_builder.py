import argparse, json, re, os, unicodedata
from pathlib import Path

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(\+?\d[\d\- ()]{7,}\d)")

DATE_RE  = re.compile(
    r"(?P<y1>20\d{2}|19\d{2})(?:[./\- ]?(?P<m1>0?[1-9]|1[0-2]))?"
    r"\s*(?:–|-|to|until|through|ถึง|จนถึง|—)\s*"
    r"(?P<y2>present|ปัจจุบัน|ปจบ\.?|20\d{2}|19\d{2})(?:[./\- ]?(?P<m2>0?[1-9]|1[0-2]))?",
    re.I,
)

SECTION_HEADERS = {
    "experience": ["experience","work history","employment","ประสบการณ์","การทำงาน"],
    "education":  ["education","การศึกษา","วุฒิ"],
    "skills":     ["skills","technical skills","ทักษะ","สกิล","ความสามารถ"],
}

def norm_text(t:str)->str:
    t = unicodedata.normalize("NFKC", t).replace("\u00a0"," ")
    t = re.sub(r"[ \t]+"," ", t)
    t = t.replace("\r","")
    return t.strip()

def first_name_line(text):
    for ln in text.splitlines()[:6]:
        s = ln.strip()
        if s and len(s) < 70 and not re.search(r"resume|curriculum vitae", s, re.I):
            return s
    return ""

def contacts(text):
    email  = EMAIL_RE.search(text)
    phone  = PHONE_RE.search(text)
    return {"email": email.group(0) if email else "", "phone": phone.group(0) if phone else "", "location": ""}

def locate_sections(text):
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
        sections[key] = "\n".join(lines[i+1:j]).strip()
    return sections

def parse_date_span(s):
    m = DATE_RE.search(s)
    if not m: return ("","")
    y1, m1, y2, m2 = m.group("y1","m1","y2","m2")
    def fmt(y,m):
        if not y: return ""
        if re.match(r"present|ปัจจุบัน|ปจบ", y, re.I): return "present"
        return f"{y}-{int(m):02d}" if m else f"{y}"
    return fmt(y1,m1), fmt(y2,m2)

def split_bullets(block):
    items = []
    for ln in block.splitlines():
        ln = ln.strip("•·●-–• \t").strip()
        if ln: items.append(ln)
    return items

def extract_experiences(text):
    out = []
    chunks = [c.strip() for c in re.split(r"\n{2,}", text) if c.strip()]
    for c in chunks:
        start, end = parse_date_span(c)
        first = c.splitlines()[0]
        role, company = "", ""
        if " at " in first:
            role, company = first.split(" at ", 1)
        elif " @ " in first:
            role, company = first.split(" @ ", 1)
        elif " - " in first:
            a, b = first.split(" - ", 1)
            company, role = (b, a) if len(b) > len(a) else (a, b)
        bullets = split_bullets(c)
        out.append({"company": company.strip(), "role": role.strip(),
                    "start": start, "end": end, "bullets": bullets})
    return out

def extract_education(text):
    out = []
    chunks = [c.strip() for c in re.split(r"\n{2,}", text) if c.strip()]
    for c in chunks:
        degree = ""
        m = re.search(r"(B\.Sc\.|BEng|BBA|M\.Sc\.|MBA|Bachelor|Master|Ph\.D\.|ปริญญาตรี|โท|เอก)", c, re.I)
        if m: degree = m.group(0)
        inst = ""
        m2 = re.search(r"(University|College|มหาวิทยาลัย|วิทยาลัย)[^,\n]*", c, re.I)
        if m2: inst = m2.group(0).strip()
        start, end = parse_date_span(c)
        out.append({"degree": degree, "institution": inst, "start": start, "end": end})
    return out

BASIC_SKILL_SEP = re.compile(r"[,\u2022•·/|]+")
def extract_skills(text):
    # แตกด้วย , • / | แล้ว trim ช่องว่าง
    toks = [t.strip() for t in BASIC_SKILL_SEP.split(text) if t.strip()]
    # เอาคำสั้น ๆ ที่ไม่ใช่สกิลจริงออกคร่าว ๆ
    toks = [t for t in toks if len(t) > 1 and not re.match(r"^(and|with|of|the|พื้นฐาน)$", t, re.I)]
    # ทำให้เป็น unique แต่คงลำดับ
    seen, out = set(), []
    for t in toks:
        k = t.lower()
        if k not in seen:
            seen.add(k); out.append(t)
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)    # RAW JSON จาก parser
    ap.add_argument("--out", dest="out", required=True)   # parsed_resume.json
    args = ap.parse_args()

    raw = json.load(open(args.inp,"r",encoding="utf-8"))
    text = norm_text(raw.get("raw_text",""))

    sections = locate_sections(text)
    parsed = {
        "source_file": raw.get("source_file",""),
        "name": first_name_line(text),
        "contacts": contacts(text),
        "education": extract_education(sections.get("education","")),
        "experiences": extract_experiences(sections.get("experience","")),
        "skills": extract_skills(sections.get("skills","")),
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(parsed, open(args.out,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    print("[OK] built parsed_resume.json →", args.out)
