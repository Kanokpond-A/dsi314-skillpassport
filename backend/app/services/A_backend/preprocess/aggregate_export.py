# backend/app/services/A_backend/preprocess/aggregator.py
"""
Aggregate parsed resumes (structure_builder output) + optional extras (field_extractor)
→ single JSON for downstream (A2).
- Leaves blanks when info is missing (strings -> "", lists -> [], numbers -> None).
- Redacts PII on export by default (toggle with --no-redact).
"""

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

# ----------------------------
# Settings
# ----------------------------
PII_KEYS = {
    "email", "phone", "location", "address",
    "linkedin", "github", "line", "facebook",
    "linkedin_url", "github_url", "portfolio_url",
}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(\+?\d[\d\- ()]{7,}\d)")

# ----------------------------
# Helpers
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

def _scrub_text_pii(s: Optional[str]) -> Optional[str]:
    if not s or not isinstance(s, str):
        return s
    s = EMAIL_RE.sub("[redacted-email]", s)
    s = PHONE_RE.sub("[redacted-phone]", s)
    return s

def redact_contacts(contacts: Optional[dict]) -> dict:
    contacts = contacts or {}
    out: Dict[str, Any] = {}
    for k, v in contacts.items():
        if k in PII_KEYS:
            out[k] = ""  # drop PII completely (leave empty)
        else:
            out[k] = _scrub_text_pii(v if isinstance(v, str) else "")
    return out

def _blank_str(x: Optional[str]) -> str:
    """Return '' when x is falsy/non-string; otherwise strip string."""
    return (x or "").strip() if isinstance(x, str) else ""

def _blank_list(xs: Optional[List[Any]]) -> List[Any]:
    return list(xs) if isinstance(xs, list) else []

def _null_number(x: Optional[float]) -> Optional[float]:
    try:
        return float(x) if x is not None else None
    except Exception:
        return None

def _resume_id_from_source(source_file: str) -> str:
    """Stable short id for downstream joins (no PII)."""
    base = source_file or ""
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]

def evidence_from_experiences(experiences: List[dict], max_items: int = 3) -> List[str]:
    """Pick bullet highlights from experiences as evidence_snippets."""
    ev: List[str] = []
    for exp in experiences or []:
        for b in (exp.get("bullets") or []):
            b = (b or "").strip()
            if b and len(b) > 15:
                ev.append(b)
                if len(ev) >= max_items:
                    return [_scrub_text_pii(x) for x in ev]
    # fallback: use role/company heads
    for exp in experiences or []:
        head = " - ".join([exp.get("role", "") or "", exp.get("company", "") or ""]).strip(" -")
        if head:
            ev.append(head)
            if len(ev) >= max_items:
                break
    return [_scrub_text_pii(x) for x in ev[:max_items]]

def merge_candidate(parsed: dict, extras: Optional[dict]) -> dict:
    """
    Merge structure_builder parsed + field_extractor extras
    Output is A1→A2 friendly:
      - strings blank when missing
      - arrays empty when missing
      - numeric unknowns as null
    """
    extras = extras or {}
    contacts = parsed.get("contacts") or {}

    name  = _blank_str(parsed.get("name") or extras.get("name"))
    ind   = _blank_str(parsed.get("industry"))
    sk    = _blank_list(parsed.get("skills"))
    edu   = _blank_list(parsed.get("education"))
    exps  = _blank_list(parsed.get("experiences"))
    loc   = _blank_str(extras.get("location") or contacts.get("location"))
    exp_y = _null_number(extras.get("experience_years"))
    exp_sal = _blank_str(extras.get("expected_salary"))
    avail   = _blank_str(extras.get("availability"))
    source  = _blank_str(parsed.get("source_file"))
    rid     = _resume_id_from_source(source)

    out: Dict[str, Any] = {
        "resume_id": rid,
        "name": name,
        "industry": ind,
        "skills": sk,
        "experience_years": exp_y,
        "expected_salary": exp_sal,
        "availability": avail,
        "location": loc,
        "evidence_snippets": evidence_from_experiences(exps),
        # keep raw for internal QA (will be redacted)
        "contacts": contacts or {},
        "source_file": source,
        "_raw_debug": {
            "education": edu,
            "experiences": exps,
        },
    }
    return out

def redact_candidate(c: dict) -> dict:
    """Remove PII from candidate (both contacts and free text)."""
    c = dict(c)
    # contacts
    c["contacts"] = redact_contacts(c.get("contacts"))
    # scrub free-text fields
    for k in ["name", "expected_salary", "availability", "location"]:
        c[k] = _blank_str(_scrub_text_pii(c.get(k)))
    # evidence
    c["evidence_snippets"] = [_blank_str(_scrub_text_pii(x)) for x in (c.get("evidence_snippets") or [])]
    return c

def load_all(parsed_dir: Path) -> List[dict]:
    out: List[dict] = []
    for p in sorted(parsed_dir.glob("*.json")):
        if p.name.startswith("_extras_"):
            continue
        try:
            parsed = _read_json(p)
        except Exception:
            # skip unreadable files
            continue
        extras = _try_read_extras_for(p)
        cand = merge_candidate(parsed, extras)
        out.append(cand)
    return out

def export(cands: List[dict], out_path: Path, redact: bool = True):
    data = [redact_candidate(c) for c in cands] if redact else cands
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"candidates": data}, f, ensure_ascii=False, indent=2)
    print(f"[OK] wrote {out_path} (candidates={len(data)}, redact={'on' if redact else 'off'})")

# ----------------------------
# CLI
# ----------------------------
def main():
    ap = argparse.ArgumentParser(description="Aggregate parsed resumes → parsed_resume.json (with redaction)")
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

