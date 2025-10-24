import os, json, argparse, re, yaml
from collections import defaultdict
from typing import List, Dict
from .skills_normalizer import normalize_skills  # ต้องอยู่โฟลเดอร์เดียวกัน

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

# (1) นี่คือเครื่องมือที่เราจะใช้ from .skills_normalizer import normalize_skills
# (2) นี่คือสิ่งที่คุณ "ต้องการ" (เช่น JD ของตำแหน่งงาน)
# (คุณอาจจะย้ายไปไว้ไฟล์อื่น หรือรับมาจาก API ก็ได้ แต่นี่คือตัวอย่าง)
JOB_REQUIREMENTS = {
    "required": ["Python", "SQL", "FastAPI", "Docker"],
    "weights": [0.35, 0.25, 0.2, 0.2],
    "keywords": ["Agile", "Git"],
    "min_exp": 2 # (ปี)
}

# (3) นี่คือฟังก์ชันที่ routes.py เรียกใช้
def calculate_ucb_score(parsed_data: dict, redact_pii: bool = True):
    """
    คำนวณคะแนน UCB จากข้อมูล parsed_data ที่ได้จาก structure_builder
    """
    
    # -----------------------------------------------------------
    # (A) ส่วนที่ 1: เตรียมข้อมูล (Input)
    # -----------------------------------------------------------
    raw_skills_list = parsed_data.get("skills_raw", [])
    experiences = parsed_data.get("experiences", [])
    contacts = parsed_data.get("contacts", {})
    name_and_roles = [parsed_data.get("name", "")] + [e.get("role", "") for e in experiences]

    # -----------------------------------------------------------
    # (B) ส่วนที่ 2: คำนวณ "คะแนนจริง" (Process) 
    # -----------------------------------------------------------
    
    # (B.1) ใช้ "normalize_skills"
    print(f"[Scoring] Normalizing skills...")
    clean_skills = normalize_skills(raw_skills_list)
    print(f"[Scoring] Clean skills found: {clean_skills}")

    # (B.2) คำนวณคะแนน Skills (สำหรับ Breakdown และ Summary)
    req_skills = JOB_REQUIREMENTS.get("required", [])
    req_weights = JOB_REQUIREMENTS.get("weights", [])
    
    real_breakdown = []
    matched_skills_list = []
    missing_skills_list = []
    skills_score_percent = 0.0 # (ค่าเริ่มต้นสำหรับ Skills Match)
    matched_weight = 0.0

    if req_skills and len(req_skills) == len(req_weights):
        total_weight = sum(req_weights)

        for skill, weight in zip(req_skills, req_weights):
            if skill in clean_skills:
                # (!!!) นี่คือ Bug ที่แก้ไขแล้ว (!!!)
                matched_weight += weight 
                
                # (1) สำหรับ Summary
                matched_skills_list.append(skill) 
                
                # (2) สำหรับ Breakdown
                real_breakdown.append({ 
                    "skill": skill,
                    "level": "พบ", 
                    "weight": weight
                })
            else:
                # (1) สำหรับ Summary
                missing_skills_list.append(skill) 

                # (2) สำหรับ Breakdown
                real_breakdown.append({ 
                    "skill": skill,
                    "level": "ไม่พบ", 
                    "weight": weight
                })
        
        # คำนวณ % Skills (หลังจาก Loop)
        if total_weight > 0:
            skills_score_percent = matched_weight / total_weight

    # (B.3) คำนวณคะแนนส่วนอื่นๆ (สำหรับกราฟ)
    # (ใช้ฟังก์ชันจริงที่อยู่ด้านบนของไฟล์ ไม่ใช้ค่า Hardcode)
    
    # คำนวณ % ประสบการณ์ (0.0 - 1.0)
    exp_score_percent = min(estimate_years(experiences) / 3.0, 1.0) # (เช่น ถ้ามี 3 exp = 1.0)
    
    # คำนวณ % ชื่อตำแหน่ง (0.0 - 1.0)
    title_score_percent = score_title(name_and_roles)
    
    # คำนวณ % ข้อมูลติดต่อ (0.0 - 1.0)
    contact_score_percent = score_contacts(contacts)
    
    # (B.4) คำนวณคะแนนรวม (Final Score)
    # (ใช้คะแนนจากกราฟ 4 ส่วนมาคำนวณ)
    all_scores = [skills_score_percent, exp_score_percent, title_score_percent, contact_score_percent]
    real_final_score = (sum(all_scores) / len(all_scores)) * 100

    # (B.5) สรุประดับ (Level)
    real_level = "Needs Improvement"
    if real_final_score >= 85:
        real_level = "Excellent Match"
    elif real_final_score >= 70:
        real_level = "Good Match"

    # -----------------------------------------------------------
    # (C) ส่วนที่ 3: แพ็กผลลัพธ์ (Output)
    # -----------------------------------------------------------
    
    # (C.1) สร้าง "summary" (ที่ JS ต้องการ)
    # (ลบตัวที่ซ้ำซ้อนออก)
    real_summary = {
        "matched_skills": matched_skills_list,
        "missing_skills": missing_skills_list,
        "matched_percent": round(skills_score_percent * 100, 1)
    }
    
    # (C.2) สร้าง "score_components" ที่ถูกต้องสำหรับกราฟ
    # (ลบตัวที่ซ้ำซ้อนออก)
    real_score_components = {
        "Skills Match": skills_score_percent,   # <--- Key ต้องตรงกับ JS
        "Experience": exp_score_percent,      # <--- Key ต้องตรงกับ JS
        "Title Match": title_score_percent,   # <--- Key ต้องตรงกับ JS
        "Contact Info": contact_score_percent   # <--- Key ต้องตรงกับ JS
    }
    
    # (C.3) สร้าง hr_view_data (สุดท้าย)
    # (ลบตัวที่ซ้ำซ้อนออก)
    hr_view_data = {
        "score": round(real_final_score, 0),    # <-- (B.4)
        "level": real_level,                    # <-- (B.5)
        "summary": real_summary,                # <-- (C.1)
        "breakdown": real_breakdown,            # <-- (B.2)
        "notes": [],                          
        "score_components": real_score_components # <-- (C.2)
    }

    # (D) ส่วนที่ 4: คืนค่า
    
    if redact_pii:
        # (คุณสามารถเพิ่มโค้ดลบ PII ที่นี่ได้)
        pass

    print(f"[Scoring] Output Score: {real_final_score}")
    return {
        "hr_view": hr_view_data
    }

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




