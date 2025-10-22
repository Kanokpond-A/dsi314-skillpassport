import os, json, argparse, re, yaml
from collections import defaultdict
from typing import List, Dict
from skills_normalizer import normalize_skills  # ต้องอยู่โฟลเดอร์เดียวกัน

# ---- ตั้งค่า JD ตัวอย่าง (ค่าเริ่มต้น ถ้าไม่ส่ง --jd เข้ามา) ----
JOB_REQ = {
    "title_keywords": ["data analyst", "data engineer", "business intelligence"],
    "must_skills": ["Python", "SQL", "Tableau"],
    "nice_skills": ["Airflow", "Power BI", "Docker", "Excel"],
}

PII_KEYS = {"email", "phone", "location", "address", "linkedin", "github", "line", "facebook"}

# ---------------- ฟังก์ชันให้คะแนน ----------------
def score_title(name_or_roles: List[str]) -> float:
    text = " ".join(name_or_roles).lower()
    return 1.0 if any(k in text for k in JOB_REQ["title_keywords"]) else 0.0

def score_skills(norm_skills: List[str]):
    must, nice = set(JOB_REQ["must_skills"]), set(JOB_REQ["nice_skills"])
    s = set(norm_skills)
    must_hit = len(s & must) / (len(must) or 1)
    nice_hit = len(s & nice) / (len(nice) or 1)
    score = must_hit * 0.8 + nice_hit * 0.2
    gaps = sorted(list(must - s))
    return score, gaps

def estimate_years(experiences: List[dict]) -> int:
    return min(5, len(experiences or []))

def score_contacts(contacts: dict) -> float:
    ok = int(bool(contacts.get("email"))) + int(bool(contacts.get("phone")))
    return 1.0 if ok >= 1 else 0.0

def build_headline(parsed: dict) -> str:
    role = (parsed.get("experiences") or [{}])[0].get("role", "") if parsed.get("experiences") else ""
    skills = ", ".join((parsed.get("skills") or [])[:5])
    return f"{role or 'Candidate'} — {skills}"

def redact_contacts(contacts: dict, enable: bool) -> dict:
    if not contacts:
        return {}
    if not enable:
        return contacts
    safe = {}
    for k, v in contacts.items():
        safe[k] = "•••" if k.lower() in PII_KEYS and isinstance(v, str) and v else v
    return safe

# ---------------- Evidence helpers ----------------
def _contains(hay: str, needle: str) -> bool:
    if not hay or not needle:
        return False
    try:
        return re.search(rf"\b{re.escape(needle)}\b", hay, flags=re.I) is not None
    except re.error:
        return needle.lower() in hay.lower()

def build_evidence(parsed: dict, norm_skills: List[str]) -> Dict[str, List[str]]:
    ev = defaultdict(list)
    for i, s in enumerate(parsed.get("skills", []) or []):
        for sk in norm_skills:
            if _contains(str(s), sk) and f"skills[{i}]" not in ev[sk]:
                ev[sk].append(f"skills[{i}]")

    for ei, exp in enumerate(parsed.get("experiences", []) or []):
        role = exp.get("role") or ""
        comp = exp.get("company") or ""
        if role:
            for sk in norm_skills:
                if _contains(role, sk):
                    ev[sk].append(f"experiences[{ei}].role")
        if comp:
            for sk in norm_skills:
                if _contains(comp, sk):
                    ev[sk].append(f"experiences[{ei}].company")
        for bi, b in enumerate(exp.get("bullets", []) or []):
            b = str(b)
            for sk in norm_skills:
                if _contains(b, sk):
                    ev[sk].append(f"experiences[{ei}].bullets[{bi}]")
    for k in list(ev.keys()):
        ev[k] = ev[k][:4]
    return dict(ev)

# ---------------- main ----------------
def main():
    ap = argparse.ArgumentParser(description="Generate UCB payload with fit_score + evidence")
    ap.add_argument("--in",  dest="inp",  required=True, help="path to parsed_resume.json")
    ap.add_argument("--out", dest="out", required=True, help="path to ucb_payload.json")
    ap.add_argument("--redact", action="store_true", help="ซ่อนข้อมูลส่วนตัว (email/phone/location/links)")
    ap.add_argument("--jd", type=str, default=None, help="path to JD config YAML (optional)")  # ✅ เพิ่มส่วนนี้
    args = ap.parse_args()

    # โหลดไฟล์ JD ถ้ามี
    global JOB_REQ
    if args.jd:
        try:
            with open(args.jd, "r", encoding="utf-8") as f:
                jd_cfg = yaml.safe_load(f)
                if isinstance(jd_cfg, dict):
                    JOB_REQ.update({k: v for k, v in jd_cfg.items() if v})
                    print(f"[JD] loaded from {args.jd}")
        except Exception as e:
            print(f"⚠️  failed to load JD config ({args.jd}): {e}")

    parsed = json.load(open(args.inp, "r", encoding="utf-8"))

    # Normalize skills
    norm_sk = normalize_skills(parsed.get("skills", []))

    # Sub-scores
    skills_score, gaps = score_skills(norm_sk)
    title_score = score_title([parsed.get("name", "")] + [e.get("role", "") for e in (parsed.get("experiences") or [])])
    years = estimate_years(parsed.get("experiences"))
    exp_score = min(1.0, years / 3.0)
    info_score = score_contacts(parsed.get("contacts", {}))

    # Weighted total
    total = round(100 * (0.40 * skills_score + 0.20 * exp_score + 0.20 * title_score + 0.20 * info_score))

    reasons = []
    if skills_score > 0: reasons.append("matched required/nice skills")
    if years > 0: reasons.append(f"experience blocks ≈ {years}")
    if title_score > 0: reasons.append("role keywords matched")
    if info_score > 0: reasons.append("contacts detected")

    evidence = build_evidence(parsed, norm_sk)
    safe_contacts = redact_contacts(parsed.get("contacts", {}), enable=args.redact)

    payload = {
        "candidate_id": os.path.splitext(os.path.basename(args.inp))[0],
        "headline": build_headline(parsed),
        "skills": {"normalized": norm_sk, "raw": parsed.get("skills", [])},
        "contacts": safe_contacts,
        "fit_score": total,
        "reasons": reasons,
        "gaps": gaps,
        "evidence": evidence,
        "meta": {
            "generated_at": None,
            "schema_version": "1.1.0",
            "jd_source": args.jd or None
        },
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(payload, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[OK] score={total} -> {args.out}  (redact={'on' if args.redact else 'off'})")

if __name__ == "__main__":
    main()




