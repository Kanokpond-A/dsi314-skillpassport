import argparse, json, re, os

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(\+?\d[\d\- ]{7,}\d)")

def clean(text:str)->str:
    text = text.replace("\u00a0"," ")
    text = re.sub(r"[ \t]+"," ",text)
    text = re.sub(r"\n{3,}","\n\n",text)
    return text.strip()

def first_name_line(text):
    for ln in text.splitlines()[:5]:
        if ln.strip() and len(ln.strip())<60 and not re.search(r"resume|curriculum vitae", ln, re.I):
            return ln.strip()
    return ""

def contacts(text):
    return {
        "email": (EMAIL_RE.search(text) or [None])[0] if EMAIL_RE.search(text) else "",
        "phone": (PHONE_RE.search(text) or [None])[0] if PHONE_RE.search(text) else "",
        "location": ""
    }

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)   # raw_text JSON from parser
    ap.add_argument("--out", dest="out", required=True)  # parsed_resume.json
    args = ap.parse_args()

    raw = json.load(open(args.inp,"r",encoding="utf-8"))
    text = clean(raw.get("raw_text",""))
    name = first_name_line(text)
    con = contacts(text)

    parsed = {
        "source_file": raw.get("source_file",""),
        "name": name,
        "contacts": con,
        "education": [],
        "experiences": [],
        "skills": []
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(parsed, open(args.out,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    print("[OK] built parsed_resume.json →", args.out)
