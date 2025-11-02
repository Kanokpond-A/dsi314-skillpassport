# app/scoring/scoring.py
import argparse, json, sys
from pathlib import Path
from jd_parser import parse_jd  # import ภายในโฟลเดอร์เดียวกัน

def score_by_overlap(resume_skills, jd_skills):
    rs = {s.strip().lower() for s in resume_skills or [] if s}
    js = {s.strip().lower() for s in jd_skills or [] if s}
    if not js:
        return 0.0, {"reason": "no_required_skills_in_jd"}
    overlap = rs & js
    score = round(len(overlap) / max(1, len(js)), 2)
    details = {
        "matched": sorted(overlap),
        "missing": sorted(js - rs),
        "extra": sorted(rs - js),
        "required_count": len(js),
        "resume_count": len(rs),
    }
    return score, details

def load_resume_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        sys.exit(f"[ERROR] resume file not found: {path}")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

def main():
    parser = argparse.ArgumentParser(description="Calculate fit_score between Resume and JD.")
    parser.add_argument("--resume", required=True, help="Path to resume JSON")
    parser.add_argument("--jd-inline", help="Inline JD JSON string")
    parser.add_argument("--jd-text", help="Free-text JD")
    parser.add_argument("--jd-template", help="Template key in jd_templates.yml")
    args = parser.parse_args()

    resume = load_resume_json(args.resume)
    jd = parse_jd(args)  # คืน dict มาตรฐาน: {required_skills: [...], name: ... , source: ...}

    fit, details = score_by_overlap(resume.get("skills", []), jd.get("required_skills", []))
    out = {
        "fit_score": fit,
        "jd_used": jd.get("name", jd.get("source", "unknown")),
        "jd_required_skills": jd.get("required_skills", []),
        "details": details
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
