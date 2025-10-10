# from fastapi import FastAPI
# from pydantic import BaseModel
# from typing import List, Optional, Dict, Any

# from backend.parser import load_parsed_resume
# from backend.score_engine import compute_fit, normalize_skills

# app = FastAPI(title="UCB API")

# class JDRequiredSkill(BaseModel):
#     name: str
#     weight: float = 1.0
#     min_years: float = 0.0

# class JDProfile(BaseModel):
#     jd_id: str = "jd-temp"
#     title: str = "Data Role"
#     required_skills: List[JDRequiredSkill] = []

# @app.get("/")
# def health(): 
#     return {"ok": True}

# @app.post("/score")
# def score(parsed: Dict[str, Any], jd: JDProfile):
#     parsed["skills_norm"] = normalize_skills(parsed.get("skills_raw", []))
#     res = compute_fit(parsed, jd.model_dump())
#     return {
#         "schema_version":"0.1.0",
#         "ucb_id":"ucb-temp",
#         "resume_id": parsed.get("resume_id","res-temp"),
#         "jd_id": jd.jd_id,
#         "snapshot": {k:res[k] for k in ("fit_score","top_reasons","gaps")},
#         "skills":[{"name":s} for s in res["skills_norm"]],
#         "evidence":{},
#         "redaction":{}
#     }

# @app.get("/demo")
# def demo():
#     parsed = load_parsed_resume()
#     jd = JDProfile(required_skills=[JDRequiredSkill(name="python"), JDRequiredSkill(name="sql"), JDRequiredSkill(name="airflow")])
#     return score(parsed, jd)  # type: ignore
