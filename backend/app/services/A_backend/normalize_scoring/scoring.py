import os, json, argparse, re, yaml
from collections import defaultdict
from typing import List, Dict, Any
# (ตรวจสอบ Path ของ import นี้ให้ถูกต้อง - ใช้ .skills_normalizer เพราะอยู่ในโฟลเดอร์เดียวกัน)
from .skills_normalizer import normalize_skills

# ---- ตั้งค่า JD ตัวอย่าง (ค่าเริ่มต้น) ----
DEFAULT_JOB_REQ = {
    "title_keywords": ["data analyst", "data engineer", "business intelligence"],
    "must_skills": ["Python", "SQL", "Tableau"],
    "nice_skills": ["Airflow", "Power BI", "Docker", "Excel"],
    # (เพิ่มน้ำหนักคะแนน - อาจจะย้ายไป JD config)
    "weights": {
        "skills": 0.40,
        "experience": 0.20,
        "title": 0.20,
        "contacts": 0.20
    }
}

# (ใช้ global variable สำหรับ JOB_REQ ที่โหลดได้)
CURRENT_JOB_REQ = DEFAULT_JOB_REQ.copy()


PII_KEYS = {"email", "phone", "location", "address", "linkedin", "github", "line", "facebook"}

# ---------------- ฟังก์ชันย่อยให้คะแนน (เหมือนเดิม แต่ใช้ CURRENT_JOB_REQ) ----------------
def score_title(name_or_roles: List[str]) -> float:
    text = " ".join(name_or_roles).lower()
    keywords = CURRENT_JOB_REQ.get("title_keywords", [])
    return 1.0 if any(k.lower() in text for k in keywords) else 0.0

def score_skills(norm_skills: List[str]):
    must_set = set(s.lower() for s in CURRENT_JOB_REQ.get("must_skills", []))
    nice_set = set(s.lower() for s in CURRENT_JOB_REQ.get("nice_skills", []))
    s_set = set(s.lower() for s in norm_skills) # คาดว่า norm_skills เป็น lowercase แล้ว
    
    must_matches = s_set & must_set
    nice_matches = s_set & nice_set

    # คำนวณคะแนน (ป้องกันหารด้วยศูนย์)
    must_hit = len(must_matches) / len(must_set) if must_set else 1.0
    nice_hit = len(nice_matches) / len(nice_set) if nice_set else 1.0

    score = must_hit * 0.8 + nice_hit * 0.2

    # หา Gaps (สกิลที่ต้องมี แต่ขาดไป - เทียบแบบ case-insensitive)
    missing_must = sorted(list(must_set - s_set))
    # (แปลงกลับเป็น Case เดิมจาก JD เพื่อแสดงผล)
    original_must_map = {s.lower(): s for s in CURRENT_JOB_REQ.get("must_skills", [])}
    gaps = [original_must_map.get(m, m) for m in missing_must] # คืนค่า Gaps ด้วยชื่อเดิม

    # หา matched skills (คืนค่าด้วยชื่อเดิมจาก JD หรือชื่อที่ Normalize แล้ว)
    original_nice_map = {s.lower(): s for s in CURRENT_JOB_REQ.get("nice_skills", [])}
    matched_skills_orig_case = [original_must_map.get(m, m) for m in must_matches] + \
                               [original_nice_map.get(n, n) for n in nice_matches]
    
    # (ปรับปรุง: คืนค่า matched skills ตาม Case ที่อยู่ใน norm_skills)
    norm_skills_map = {s.lower(): s for s in norm_skills}
    final_matched = []
    seen_lower = set()
    for skill_lower in (must_matches | nice_matches): # วนลูปจาก set ของ lowercase ที่ match
         if skill_lower in norm_skills_map: # ถ้ามีใน norm_skills
              final_matched.append(norm_skills_map[skill_lower]) # ใช้ Case จาก norm_skills
              seen_lower.add(skill_lower)
         # (Fallback: ถ้าไม่มีใน norm_skills แต่มีใน JD map - อาจไม่ควรเกิดขึ้นถ้า normalize ถูก)
         elif skill_lower in original_must_map and skill_lower not in seen_lower:
              final_matched.append(original_must_map[skill_lower])
              seen_lower.add(skill_lower)
         elif skill_lower in original_nice_map and skill_lower not in seen_lower:
              final_matched.append(original_nice_map[skill_lower])
              seen_lower.add(skill_lower)

    return score, gaps, sorted(list(set(final_matched))) # คืนค่า unique

def estimate_years(experiences: List[dict]) -> int:
    # (ปรับปรุง: ลองดูจาก date range ถ้ามี)
    years = 0
    if experiences:
        # วิธีเดิม: นับจำนวนก้อน
        years = len(experiences)
        # (วิธีใหม่ - ลองคำนวณจาก start/end - ยังไม่ implement)
    return min(5, years) # Cap ที่ 5 ปี

def score_contacts(contacts: dict | None) -> float:
    if not contacts: return 0.0
    ok = int(bool(contacts.get("email"))) + int(bool(contacts.get("phone")))
    # (อาจจะเพิ่มเงื่อนไข location ถ้าจำเป็น)
    # ok += int(bool(contacts.get("location")))
    return 1.0 if ok >= 1 else 0.0

def build_headline(parsed: dict) -> str:
    # ใช้ name ถ้าหา role ไม่เจอ
    name = parsed.get("name", "Candidate")
    role = ""
    if parsed.get("experiences"):
        try:
            # หา Role ล่าสุด (ถ้ามี end date เป็น present หรือไม่มี end date)
            latest_exp = sorted(parsed["experiences"], key=lambda x: str(x.get("end_date", x.get("end", "0"))), reverse=True)
            current_exp = [exp for exp in latest_exp if str(exp.get("end_date", exp.get("end", ""))).lower() == "present" or not exp.get("end_date", exp.get("end"))]
            
            if current_exp:
                 role = current_exp[0].get("title", current_exp[0].get("role", "")) # รองรับทั้ง title/role
            elif latest_exp: # ถ้าไม่มีอัน present เอาอันล่าสุด
                 role = latest_exp[0].get("title", latest_exp[0].get("role", ""))
        except Exception:
             # Fallback
             try:
                 role = parsed["experiences"][0].get("title", parsed["experiences"][0].get("role", ""))
             except (IndexError, TypeError):
                 role = "" # Handle empty experiences list or other errors

    # ใช้ skills ที่ normalize แล้ว
    skills_list = (parsed.get("skills_normalized") or parsed.get("skills_raw") or parsed.get("skills") or [])[:3] # เอา 3 สกิลแรก
    skills_str = ", ".join(skills_list)
    return f"{name} — {role or 'Candidate'}{f' | {skills_str}' if skills_str else ''}"


def redact_contacts(contacts: dict | None, enable: bool) -> dict | None:
    if not contacts:
        return None # หรือ {} ขึ้นอยู่กับ Schema
    if not enable:
        return contacts
    safe = {}
    for k, v in contacts.items():
        is_pii = k.lower() in PII_KEYS
        has_value = isinstance(v, str) and v.strip()
        safe[k] = "•••" if is_pii and has_value else v
    return safe

def build_evidence(parsed: dict, norm_skills: List[str]) -> Dict[str, List[str]]:
     return {} # Placeholder - ยังไม่ implement การหา evidence อัตโนมัติ

# === สร้างฟังก์ชันใหม่สำหรับเรียกใช้จาก API ===
def calculate_ucb_score(parsed_data: dict, jd_config: dict | None = None, redact_pii: bool = True) -> dict:
    """
    คำนวณคะแนน UCB จาก Dictionary ข้อมูล parsed_resume
    Args:
        parsed_data: Dict ที่มีโครงสร้างเหมือน parsed_resume.json
        jd_config: Dict ของ Job Description (ถ้ามี, จะใช้แทน DEFAULT_JOB_REQ)
        redact_pii: True ถ้าต้องการซ่อนข้อมูลส่วนตัว
    Return:
        Dict ที่มีผลลัพธ์ UCB Payload (fit_score, reasons, etc.)
    """
    global CURRENT_JOB_REQ
    if jd_config and isinstance(jd_config, dict):
        # ใช้ JD ที่ส่งมา ถ้าถูกต้อง (Merge กับ Default)
        CURRENT_JOB_REQ = {**DEFAULT_JOB_REQ, **jd_config} 
        print(f"[INFO] Using provided JD config for scoring (Keys: {list(jd_config.keys())}).")
    else:
        # ใช้ JD เริ่มต้น
        CURRENT_JOB_REQ = DEFAULT_JOB_REQ.copy()
        print("[INFO] Using default JD config for scoring.")


    # --- คำนวณคะแนน (Logic เดิมจาก main) ---
    # (ใช้ skills ที่ normalize แล้วจาก parsed_data ที่ส่งเข้ามา)
    norm_sk = parsed_data.get("skills", []) # คาดว่าถูก normalize มาแล้ว
    # (Fallback เผื่อยังใช้ key เก่า)
    if not norm_sk and parsed_data.get("skills_normalized"):
         norm_sk = parsed_data.get("skills_normalized")
    if not norm_sk and parsed_data.get("skills_raw"): # ถ้าไม่มี normalized เลย ใช้ raw
         norm_sk = normalize_skills(parsed_data.get("skills_raw")) # Normalize อีกครั้ง

    print(f"[INFO] Scoring with {len(norm_sk)} normalized skills.") # Log จำนวนสกิล

    # Sub-scores
    skills_score_raw, gaps, matched_skills = score_skills(norm_sk)
    # (รองรับทั้ง key 'name' และ 'full_name')
    # (รองรับทั้ง key 'experiences' และ 'experience')
    title_source = [parsed_data.get("name", parsed_data.get("full_name", ""))] + \
                   [e.get("title", e.get("role", "")) for e in (parsed_data.get("experiences", parsed_data.get("experience", [])) or [])]
    
    title_score_raw = score_title(title_source)
    years = estimate_years(parsed_data.get("experiences", parsed_data.get("experience", [])))
    exp_score_raw = min(1.0, years / 5.0) # 👈 ปรับปรุง: 5 ปี = 1.0 (จาก estimate_years)
    info_score_raw = score_contacts(parsed_data.get("contacts")) # (ใช้ contacts dict)

    # Weighted total
    weights = CURRENT_JOB_REQ.get("weights", DEFAULT_JOB_REQ["weights"])
    total_score = round(100 * (
        weights.get("skills", 0.40) * skills_score_raw +
        weights.get("experience", 0.20) * exp_score_raw +
        weights.get("title", 0.20) * title_score_raw +
        weights.get("contacts", 0.20) * info_score_raw
    ))
    total_score = max(0, min(100, total_score)) # Clamp 0-100

    print(f"[INFO] Sub-scores: Skills={skills_score_raw:.2f}, Exp={exp_score_raw:.2f}, Title={title_score_raw:.2f}, Contacts={info_score_raw:.2f}")


    # --- สร้างผลลัพธ์ (hr_view, machine_view) ---
    if total_score >= 85: level = "Excellent"
    elif total_score >= 70: level = "Strong"
    elif total_score >= 50: level = "Moderate"
    else: level = "Needs improvement"

    summary_details = {
        "matched_percent": round(skills_score_raw * 100),
        "evidence_count": 0, # Placeholder
        "evidence_bonus": 0, # Placeholder
        "matched_skills": matched_skills,
        "missing_skills": gaps,
        "missing_skills_detail": [{"skill": g, "impact_points": "?", "recommendation": "Consider training"} for g in gaps]
    }

    breakdown = []
    all_jd_skills = set(s.lower() for s in CURRENT_JOB_REQ.get("must_skills", []) + CURRENT_JOB_REQ.get("nice_skills", []))
    norm_sk_lower = set(s.lower() for s in norm_sk)
    for skill_lower in all_jd_skills:
         orig_skill = next((s for s in CURRENT_JOB_REQ.get("must_skills", []) + CURRENT_JOB_REQ.get("nice_skills", []) if s.lower() == skill_lower), skill_lower)
         skill_level = "Found" if skill_lower in norm_sk_lower else "Missing"
         breakdown.append({"skill": orig_skill, "level": skill_level})
    
    # (เพิ่ม Other skills ที่ผู้สมัครมี)
    other_skills = [s for s in norm_sk if s.lower() not in all_jd_skills]
    for skill in other_skills[:10]: # แสดงไม่เกิน 10 สกิล
        breakdown.append({"skill": skill, "level": "Other"})


    notes = []
    if years >= 3: notes.append(f"Relevant experience duration seems adequate (~{years} blocks).")
    elif years > 0: notes.append(f"Some experience detected (~{years} blocks).")
    else: notes.append("No relevant experience blocks found.")
    
    if title_score_raw > 0: notes.append("Keywords in name/roles match JD titles.")
    else: notes.append("No keywords in name/roles match JD titles.")

    if info_score_raw == 0: notes.append("Warning: Contact information (email/phone) missing.")
    
    if not norm_sk: notes.append("Warning: No skills extracted or normalized.")
    elif skills_score_raw == 0: notes.append("Skills found, but no match with JD.")


    hr_view = {
        "score": total_score,
        "level": level,
        "summary": summary_details,
        "breakdown": breakdown,
        "notes": notes,
        "score_components": { # 👈✅ เพิ่ม Comma ที่นี่
            "Skills Match": round(skills_score_raw, 2),
            "Experience": round(exp_score_raw, 2),
            "Title Match": round(title_score_raw, 2),
            "Contact Info": round(info_score_raw, 2)
        }
    }

    machine_view = {
         "fit_score": round(skills_score_raw, 2),
         "gaps": gaps
    }

    evidence = build_evidence(parsed_data, norm_sk)
    safe_contacts = redact_contacts(parsed_data.get("contacts"), enable=redact_pii)

    final_payload = {
        "candidate_id": parsed_data.get("candidate_id", parsed_data.get("resume_id", os.path.splitext(os.path.basename(parsed_data.get("source_file","unknown")))[0])),
        "headline": build_headline(parsed_data),
        "skills_info": {"normalized": norm_sk, "raw": parsed_data.get("skills_raw", parsed_data.get("skills", []))},
        "contacts": safe_contacts,
        "fit_score_total": total_score,
        "reasons": notes, # 👈 (เปลี่ยน) ใช้ notes แทน reasons เดิม
        "gaps_must": gaps,
        "evidence": evidence,
        "meta": {
            "generated_at": None, # Should be: datetime.now().isoformat()
            "schema_version": "1.2.0", # (อัปเดต version)
            "jd_source": str(jd_config) if jd_config else "default"
        },
        "hr_view": hr_view,
        "machine_view": machine_view
    }

    print(f"[OK] Calculated score: {total_score}")
    return final_payload
# === สิ้นสุดฟังก์ชันใหม่ ===


# === ฟังก์ชัน main เดิม (สำหรับรันผ่าน Terminal) ยังคงอยู่ ===
def main():
    ap = argparse.ArgumentParser(description="Generate UCB payload with fit_score + evidence")
    ap.add_argument("--in",  dest="inp",  required=True, help="path to parsed_resume.json")
    ap.add_argument("--out", dest="out", required=True, help="path to ucb_payload.json")
    ap.add_argument("--redact", action="store_true", default=False, help="ซ่อนข้อมูลส่วนตัว")
    ap.add_argument("--no-redact", dest="redact", action="store_false")
    ap.add_argument("--jd", type=str, default=None, help="path to JD config YAML (optional)")
    args = ap.parse_args()

    # --- โหลด JD config ---
    jd_cfg_dict = None
    if args.jd:
        try:
            with open(args.jd, "r", encoding="utf-8") as f:
                jd_cfg_dict = yaml.safe_load(f)
                if not isinstance(jd_cfg_dict, dict):
                     print(f"⚠️ Warning: JD file '{args.jd}' is not a valid dictionary. Using default JD.")
                     jd_cfg_dict = None
                else:
                     print(f"[INFO] Loaded JD config from {args.jd}")
        except Exception as e:
            print(f"⚠️ Error loading JD config from '{args.jd}': {e}. Using default JD.")
            jd_cfg_dict = None

    # --- โหลด Parsed Resume ---
    try:
        input_path = Path(args.inp)
        if not input_path.exists():
             raise FileNotFoundError(f"Input file not found at {args.inp}")
        parsed = json.load(open(input_path, "r", encoding="utf-8"))
    except Exception as e:
        print(f"[-] Error loading parsed resume from '{args.inp}': {e}")
        return

    # --- เรียกใช้ฟังก์ชันคำนวณคะแนน ---
    try:
        # (Normalize skills ภายใน main ก่อนส่งให้ calculate_ucb_score)
        raw_skills = parsed.get("skills_raw", parsed.get("skills", [])) # รองรับ cả 2 keys
        norm_sk = normalize_skills(raw_skills)
        parsed["skills"] = norm_sk # 👈 อัปเดต skills ใน parsed dict ให้เป็นตัวที่ normalize แล้ว
        parsed["skills_normalized"] = norm_sk # (เผื่อ schema 0.2.0)
        parsed["skills_raw"] = raw_skills # (เก็บ raw ไว้)

        payload = calculate_ucb_score(parsed, jd_config=jd_cfg_dict, redact_pii=args.redact)
        total = payload.get("fit_score_total", 0)

        # --- บันทึกผลลัพธ์ ---
        output_path = Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        json.dump(payload, open(output_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"[OK] score={total} -> {args.out}  (redact={'on' if args.redact else 'off'})") # แก้ไข \u2192

    except Exception as e:
         print(f"[-] Error calculating UCB score: {e}")
         import traceback
         traceback.print_exc() # พิมพ์ Error เต็มๆ ตอนรัน Terminal


if __name__ == "__main__":
    try:
        import yaml
    except ImportError:
        print(f"[-] Error: PyYAML is required to load JD config. Please run 'pip install pyyaml'")
        yaml = None

    main()