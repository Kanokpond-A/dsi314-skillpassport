# backend/app/services/A_backend/preprocess/aggregate_export.py
import argparse, csv, json, re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ----------------------------
# Settings & Paths
# ----------------------------
HERE = Path(__file__).resolve().parent
DATA_DIR = HERE.parent / "data"
SKILLS_CSV = DATA_DIR / "skills_master.csv"

PII_KEYS = {
    "email", "phone", "location", "address",
    "linkedin", "github", "line", "facebook",
    "linkedin_url", "github_url", "portfolio_url",
}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(\+?\d[\d\- ()]{7,}\d)")
DATE_RX  = re.compile(r"^(?P<y>\d{4})(?:-(?P<m>\d{2}))?$", re.I)

# ----------------------------
# IO helpers
# ----------------------------
def _read_json(p: Path) -> dict:
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

def _try_read_extras_for(parsed_path: Path) -> Optional[dict]:
    extras = parsed_path.parent / f"_extras_{parsed_path.stem}.json"
    if extras.exists():
        try:
            return _read_json(extras)
        except Exception:
            return None
    return None

# ----------------------------
# PII helpers
# ----------------------------
def _scrub_text_pii(s: Optional[str]) -> Optional[str]:
    if not s or not isinstance(s, str):
        return s
    s = EMAIL_RE.sub("[redacted-email]", s)
    s = PHONE_RE.sub("[redacted-phone]", s)
    return s

def redact_contacts(contacts: Optional[dict]) -> dict:
    contacts = contacts or {}
    out = {}
    for k, v in contacts.items():
        if k in PII_KEYS:
            out[k] = ""  # drop PII fields entirely
        else:
            out[k] = _scrub_text_pii(v if isinstance(v, str) else "")
    return out

# ----------------------------
# Evidence
# ----------------------------
def evidence_from_experiences(experiences: List[dict], max_items: int = 3) -> List[str]:
    ev: List[str] = []
    for exp in experiences or []:
        for b in (exp.get("bullets") or []):
            b = (b or "").strip()
            if b and len(b) > 15:
                ev.append(b)
                if len(ev) >= max_items:
                    return [_scrub_text_pii(x) for x in ev]
    # fallback: role/company heads
    for exp in experiences or []:
        head = " - ".join([exp.get("role", ""), exp.get("company", "")]).strip(" -")
        if head:
            ev.append(head)
            if len(ev) >= max_items:
                break
    return [_scrub_text_pii(x) for x in ev[:max_items]]

# ----------------------------
# Industry fallback (vote from skills_master.csv)
# ----------------------------
def _load_canon_to_category(csv_path: Path = SKILLS_CSV) -> Dict[str, str]:
    """
    Return mapping canonical -> category/industry (lowercased key, value as-is).
    Accepts either 'category' or 'industry' column.
    """
    out: Dict[str, str] = {}
    if not csv_path.exists():
        return out
    with csv_path.open(encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        cols = {c.lower(): c for c in (rdr.fieldnames or [])}
        col_can = cols.get("canonical") or "canonical"
        col_cat = cols.get("category") or cols.get("industry")
        for row in rdr:
            can = (row.get(col_can) or "").strip()
            if not can:
                continue
            cat = (row.get(col_cat) or "").strip() if col_cat else ""
            if cat and can not in out:
                out[can] = cat
    return out

def infer_industry_from_skills(skills: List[str]) -> str:
    """
    Vote the most common category/industry from canonical skills.
    Returns "" if nothing can be inferred.
    """
    if not skills:
        return ""
    canon2cat = _load_canon_to_category()
    counts: Dict[str, int] = {}
    for s in skills:
        cat = canon2cat.get(s)
        if cat:
            counts[cat] = counts.get(cat, 0) + 1
    if not counts:
        return ""
    # pick max by count, tie-break by alphabetical
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

# ----------------------------
# Experience-years fallback (from date strings)
# ----------------------------
def _ym_from_str(s: str) -> Optional[Tuple[int, int]]:
    """
    Accepts 'YYYY' or 'YYYY-MM'. Month default = 1.
    """
    m = DATE_RX.match(s or "")
    if not m:
        return None
    y = int(m.group("y"))
    mm = int(m.group("m") or "1")
    if mm < 1 or mm > 12:
        mm = 1
    return (y, mm)

def _months_between(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    return (b[0] - a[0]) * 12 + (b[1] - a[1])

def estimate_years_from_experiences(experiences: List[dict]) -> Optional[float]:
    """
    Sum duration across experiences using start/end ('YYYY' or 'YYYY-MM').
    Ignores records without valid start or end. If 'end' == '' → skip (unknown).
    Returns rounded years (2 decimals) or None.
    """
    months = 0
    for e in experiences or []:
        st = _ym_from_str((e.get("start") or "").strip())
        en_raw = (e.get("end") or "").strip()
        if not st:
            continue
        if not en_raw or re.match(r"(?i)present", en_raw):
            # ไม่มี end → ไม่เดางานปัจจุบัน (เพื่อเลี่ยงบวม)
            continue
        en = _ym_from_str(en_raw)
        if not en:
            continue
        diff = _months_between(st, en)
        if diff > 0:
            months += diff
    if months <= 0:
        return None
    return round(months / 12.0, 2)

# ----------------------------
# Merge & Redact
# ----------------------------
def merge_candidate(parsed: dict, extras: Optional[dict]) -> dict:
    """
    Combine parsed (structure_builder) + extras (field_extractor).
    Fallbacks:
      - industry: if empty -> infer from canonical skills using skills_master.csv
      - experience_years: if empty -> estimate from experiences dates
    """
    extras = extras or {}
    contacts = parsed.get("contacts") or {}
    skills = parsed.get("skills") or []
    experiences = parsed.get("experiences") or []

    # base values
    industry = parsed.get("industry") or ""
    if not industry:
        industry = infer_industry_from_skills(skills) or ""

    experience_years = extras.get("experience_years")
    if experience_years in (None, "", 0):
        experience_years = estimate_years_from_experiences(experiences)

    out: Dict[str, object] = {
        "name": parsed.get("name") or extras.get("name") or "",
        "industry": industry or "",
        "skills": skills,
        "experience_years": experience_years,
        "expected_salary": extras.get("expected_salary") or "",
        "availability": extras.get("availability") or "",
        "location": extras.get("location") or contacts.get("location") or "",
        "evidence_snippets": evidence_from_experiences(experiences),
        # keep contacts raw for internal use; will be redacted on export (unless --no-redact)
        "contacts": contacts,
        "source_file": parsed.get("source_file") or "",
        "_raw_debug": {
            "education": parsed.get("education") or [],
            "experiences": experiences,
        },
    }
    return out

def _deep_scrub(obj):
    """
    Scrub email/phone inside any nested free text (extra guard),
    excluding _raw_debug since it will be removed entirely.
    """
    if isinstance(obj, dict):
        return {k: _deep_scrub(v) for k, v in obj.items() if k != "_raw_debug"}
    if isinstance(obj, list):
        return [_deep_scrub(v) for v in obj]
    if isinstance(obj, str):
        return _scrub_text_pii(obj)
    return obj

def redact_candidate(c: dict) -> dict:
    c = dict(c)

    # remove debug payload entirely to avoid false positives with date ranges
    if "_raw_debug" in c:
        c.pop("_raw_debug", None)

    # contacts
    c["contacts"] = redact_contacts(c.get("contacts"))

    # scrub free-text fields
    for k in ["name", "expected_salary", "availability", "location"]:
        c[k] = _scrub_text_pii(c.get(k))

    # evidence snippets
    c["evidence_snippets"] = [_scrub_text_pii(x) for x in (c.get("evidence_snippets") or [])]

    # extra safety pass for any nested text (except _raw_debug already removed)
    c = _deep_scrub(c)
    return c

# ----------------------------
# Batch load & export
# ----------------------------
def load_all(parsed_dir: Path) -> List[dict]:
    out: List[dict] = []
    for p in sorted(parsed_dir.glob("*.json")):
        if p.name.startswith("_extras_"):
            continue
        try:
            parsed = _read_json(p)
        except Exception:
            continue
        extras = _try_read_extras_for(p)
        cand = merge_candidate(parsed, extras)
        out.append(cand)
    return out

def export(cands: List[dict], out_path: Path, redact: bool = True):
    if redact:
        cands = [redact_candidate(c) for c in cands]
    else:
        # แม้ --no-redact ก็กันไม่ให้ _raw_debug หลุดออกไปในอาร์ติแฟกต์ที่ส่งต่อ
        cands = [{k: v for k, v in c.items() if k != "_raw_debug"} for c in cands]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"candidates": cands}, f, ensure_ascii=False, indent=2)
    print(f"[OK] wrote {out_path} (candidates={len(cands)}, redact={'on' if redact else 'off'})")

# ----------------------------
# CLI
# ----------------------------
def main():
    ap = argparse.ArgumentParser(description="Aggregate parsed resumes → parsed_resume.json (with redaction + fallbacks)")
    ap.add_argument("--in",  dest="inp", default="shared_data/latest_parsed", help="Folder of parsed JSON files")
    ap.add_argument("--out", dest="out", default="shared_data/parsed_resume.json", help="Output JSON file")
    ap.add_argument("--no-redact", action="store_true", help="Disable PII redaction")
    args = ap.parse_args()

    in_dir = Path(args.inp)
    out_fp = Path(args.out)
    cands = load_all(in_dir)
    export(cands, out_fp, redact=(not args.no_redact))

if __name__ == "__main__":
    main()



