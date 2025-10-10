# from rapidfuzz import process, fuzz

# CANON = {
#     "python": ["python","ไพธอน"],
#     "sql": ["sql","เอสคิวแอล"],
#     "airflow": ["airflow","แอร์โฟลว์"],
#     "looker": ["looker","looker studio","lookerstudio"],
#     "excel": ["excel","microsoft excel"]
# }

# def normalize_skills(skills_raw):
#     names = [k for k in CANON.keys()] + sum(CANON.values(), [])
#     norm = set()
#     for s in skills_raw:
#         token = (s or "").strip().lower()
#         if not token: 
#             continue
#         best, score, _ = process.extractOne(token, names, scorer=fuzz.WRatio)
#         for key, alts in CANON.items():
#             if best == key or best in alts:
#                 norm.add(key); break
#     return sorted(norm)

# def weighted_skill_overlap(cv_skills, jd_required):
#     if not jd_required: 
#         return 0.0
#     cv = set(x.lower() for x in cv_skills)
#     got = 0.0; total = 0.0
#     for item in jd_required:
#         w = float(item.get("weight", 1.0)); total += w
#         if item["name"].lower() in cv: got += w
#     return got/total if total else 0.0

# def compute_fit(parsed_resume, jd_profile=None):
#     skills_norm = parsed_resume.get("skills_norm") or normalize_skills(parsed_resume.get("skills_raw", []))
#     req = (jd_profile or {}).get("required_skills", [])
#     skill_score = weighted_skill_overlap(skills_norm, req)
#     fit_score = int(round(skill_score * 100))
#     req_names = [x["name"].lower() for x in req]
#     have = [s for s in skills_norm if s in req_names]
#     miss = [n for n in req_names if n not in skills_norm]
#     reasons = [f"{len(have)}/{len(req_names)} required skills matched: " + ", ".join(have[:6])] if req else ["Resume parsed"]
#     gaps = miss[:2] if miss else []
#     return {
#         "fit_score": fit_score,
#         "top_reasons": reasons,
#         "gaps": gaps,
#         "skills_norm": skills_norm
#     }
