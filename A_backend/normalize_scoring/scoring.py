# A_backend/normalize_scoring/scoring.py
import os, re, json, argparse
from skills_normalizer import normalize_skills  # ไฟล์อยู่โฟลเดอร์เดียวกัน

# ---- ตั้งค่า JD ตัวอย่าง (แก้ได้ภายหลัง) ----
JOB_REQ = {
    "title_keywords": ["data analyst", "data engineer", "business intelligence"],
    "must_skills": ["Python", "SQL", "Tableau"],
    "nice_skills": ["Airflow", "Power BI", "Docker", "Excel"],
}

# ---- ฟังก์ชันย่อยให้คะแนน ----
def score_title(name_or_roles):
    text = " ".join(name_or_roles).lower()
    return 1.0 if any(k in text for k in JOB_REQ["title_keywords"]) else 0.0

def score_skills(norm_skills):
    must, nice = set(JOB_REQ["must_skills"]), set(JOB_REQ["nice_skills"])
    s = set(norm_skills)
    must_hit = len(s & must) / (len(must) or 1)
    nice_hit = len(s & nice) / (len(nice) or 1)
    score = must_hit * 0.8 + nice_hit * 0.2
    gaps = sorted(list(must - s))
    return score, gaps

def estimate_years(experiences):
    # heuristic เบาๆ: นับจำนวนก้อนประสบการณ์ = ปี (cap 5)
    return min(5, len(experiences or []))

def score_contacts(contacts):
    ok = int(bool(contacts.get("email"))) + int(bool(contacts.get("phone")))
    return 1.0 if ok >= 1 else 0.0

def build_headline(parsed):
    role = (parsed.get("experiences") or [{}])[0].get("role", "") if parsed.get("experiences") else ""
    skills = ", ".join((parsed.get("skills") or [])[:5])
    return f"{role or 'Candidate'} — {skills}"

# ---- main ----
def main():
    ap = argparse.ArgumentParser(description="Generate UCB payload with fit_score")
    ap.add_argument("--in",  dest="inp",  required=True, help="path to parsed_resume.json")
    ap.add_argument("--out", dest="out", required=True, help="path to ucb_payload.json")
    args = ap.parse_args()

    parsed = json.load(open(args.inp, "r", encoding="utf-8"))

    # Normalize skills
    norm_sk = normalize_skills(parsed.get("skills", []))

    # Sub-scores
    skills_score, gaps = score_skills(norm_sk)
    title_score = score_title([parsed.get("name", "")] + [e.get("role", "") for e in (parsed.get("experiences") or [])])
    years = estimate_years(parsed.get("experiences"))
    exp_score = min(1.0, years / 3.0)  # 0..1
    info_score = score_contacts(parsed.get("contacts", {}))

    # Weighted total: 40/20/20/20
    total = round(100 * (0.40 * skills_score + 0.20 * exp_score + 0.20 * title_score + 0.20 * info_score))

    reasons = []
    if skills_score > 0: reasons.append("matched required/nice skills")
    if years > 0: reasons.append(f"experience blocks ≈ {years}")
    if title_score > 0: reasons.append("role keywords matched")
    if info_score > 0: reasons.append("contacts detected")

    payload = {
        "candidate_id": os.path.splitext(os.path.basename(args.inp))[0],
        "headline": build_headline(parsed),
        "skills": {"normalized": norm_sk, "raw": parsed.get("skills", [])},
        "fit_score": total,
        "reasons": reasons,
        "gaps": gaps,
        "evidence": {},  # phase ต่อไปค่อย map path
        "meta": {"generated_at": None, "schema_version": "1.0.0"},
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(payload, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[OK] score={total} → {args.out}")

if __name__ == "__main__":
    main()

