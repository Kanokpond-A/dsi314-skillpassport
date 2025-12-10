import datetime
import math
import re
from typing import List, Dict, Any

# ==========================================
# 1. Configuration & Main Entry
# ==========================================

def get_default_weights():
    return {
        "cap_skills_match_w": 80,       "cap_skills_match_enabled": True,
        "cap_recency_w": 40,            "cap_recency_enabled": True,
        "cap_scale_w": 50,              "cap_scale_enabled": True,
        "cap_standards_w": 30,          "cap_standards_enabled": True,
        "cap_exp_duration_w": 20,       "cap_exp_duration_enabled": True,
        "cap_company_tier_w": 30,       "cap_company_tier_enabled": False,
        "cap_stability_w": 40,          "cap_stability_enabled": True,
        "cap_edu_degree_w": 30,         "cap_edu_degree_enabled": True,
        "cap_edu_tier_w": 20,           "cap_edu_tier_enabled": False,
        "cap_certs_w": 30,              "cap_certs_enabled": True,
        "cap_logistics_w": 50,          "cap_logistics_enabled": True,
        "pot_career_growth_w": 90,      "pot_career_growth_enabled": True,
        "pot_learning_agility_w": 70,   "pot_learning_agility_enabled": True,
        "pot_leadership_w": 50,         "pot_leadership_enabled": True,
        "pot_soft_skills_w": 40,        "pot_soft_skills_enabled": True
    }

def calculate_universal_score(parsed_data: Dict, weights_config: Dict, job_description_text: str = None) -> Dict[str, Any]:
    if not weights_config:
        weights_config = get_default_weights()

    # 1. เตรียมข้อมูล Keyword Matching
    candidate_skills = []
    skills_data = parsed_data.get('skills', {})
    if isinstance(skills_data.get('hard_skills'), list):
        candidate_skills.extend(skills_data['hard_skills'])
    if isinstance(skills_data.get('soft_skills'), list):
        candidate_skills.extend(skills_data['soft_skills'])

    required_keywords = []
    if job_description_text:
        required_keywords = _extract_keywords_from_text(job_description_text)
    
    # คำนวณ Match Result
    match_result = calculate_match_score(required_keywords, candidate_skills)

    # 2. คำนวณ Score 6 แกน (Capabilities)
    capabilities_result = _calculate_capabilities(parsed_data, weights_config, match_result)
    
    # 3. คำนวณ Score ศักยภาพ (Potential)
    potential_result = _calculate_potential(parsed_data, weights_config)

    # 4. Final Score
    final_score = round((capabilities_result['score'] + potential_result['score']) / 2, 1)

    ai_summary = parsed_data.get('analysis', {}).get('summary', 'No summary provided by AI.')
    match_stat = f"Matched {match_result['keywords_found']} / {match_result['keywords_total']} keywords from JD."

    return {
        "final_score": final_score, 
        "analysis": {
            "matched_criteria": match_result['matched_skills'],        
            "missing_gaps": match_result['unmatched_skills_required'], 
            "summary_comment": f"{ai_summary}\n\n[{match_stat}]",
            "years_of_experience": parsed_data.get('analysis', {}).get('years_of_experience', 0)
        },
        "capabilities": capabilities_result,
        "potential": potential_result
    }

# ==========================================
# 2. Match Logic Helpers (สูตรเดิม: Exact Match)
# ==========================================

def calculate_match_score(required_keywords: List[str], candidate_skills: List[str]) -> Dict[str, Any]:
    # 1. Normalize
    required_norm = {kw.lower().strip() for kw in required_keywords if kw}
    candidate_norm = {sk.lower().strip() for sk in candidate_skills if sk}
    
    # 2. Intersection (ต้องตรงกันเป๊ะๆ เท่านั้น)
    matched_skills = required_norm.intersection(candidate_norm)
    
    total_required = len(required_norm)
    found_count = len(matched_skills)
    
    if total_required == 0:
        match_percentage = 50.0 
    else:
        match_percentage = round((found_count / total_required) * 100, 1)
    
    unmatched_skills = list(required_norm.difference(candidate_norm))
    
    return {
        "match_percentage": match_percentage,
        "keywords_total": total_required,
        "keywords_found": found_count,
        "matched_skills": list(matched_skills),
        "unmatched_skills_required": unmatched_skills
    }

def _extract_keywords_from_text(text: str) -> List[str]:
    """
    ยังคงใช้ Regex เพื่อการตัดคำที่ถูกต้อง (จำเป็นต้องมี ไม่งั้นได้ 1 Keyword)
    """
    if not text: return []
    
    text = text.replace('•', ' ').replace('-', ' ').replace('*', ' ').replace('/', ' ')
    
    # ตัดด้วย , \n ; .
    raw_tokens = re.split(r'[,\n;\.]+', text)
    
    keywords = []
    stop_words = {'the', 'and', 'or', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'is', 'are', 'be', 'will', 'job', 'description', 'role', 'responsibilities', 'requirements', 'we', 'looking', 'summary'}

    for token in raw_tokens:
        clean_token = token.strip()
        if len(clean_token) > 1 and clean_token.lower() not in stop_words:
            keywords.append(clean_token)
            
    return keywords

def _calculate_weighted_average(score_list):
    total_weighted_score = 0
    total_active_weight = 0
    for score, weight in score_list:
        total_weighted_score += (score * weight)
        total_active_weight += weight
    if total_active_weight == 0:
        return 0
    return round(total_weighted_score / total_active_weight, 2)

# ==========================================
# 3. Detailed Scoring Logic (Capabilities - สูตรเดิม)
# ==========================================

def _calculate_capabilities(data, cfg, match_result):
    scores = [] 
    details = {} 
    
    # A. Skill Match
    if cfg.get('cap_skills_match_enabled'):
        if match_result['keywords_total'] > 0:
            raw_score = match_result['match_percentage']
        else:
            hard_skills_count = len(data.get('skills', {}).get('hard_skills', []))
            raw_score = min(hard_skills_count * 10, 100)
        weight = cfg.get('cap_skills_match_w', 0)
        scores.append((raw_score, weight))
        details['skill_match'] = raw_score

    # B. Recency
    if cfg.get('cap_recency_enabled'):
        raw_score = 80 
        weight = cfg.get('cap_recency_w', 0)
        scores.append((raw_score, weight))
        details['recency'] = raw_score 

    # C. Project Scale (ใช้ Keywords ชุดเดิม)
    if cfg.get('cap_scale_enabled'):
        raw_score = 40 
        metrics = []
        for job in data.get('work_experience', []):
            metrics.extend(job.get('metrics_found', []))
        
        # Keywords ชุดเดิม (ไม่มี Revenue, Budget)
        scale_keywords = ['million', 'users', 'high traffic', 'scale', 'concurrent']
        all_metrics_str = " ".join(metrics).lower()
        if any(k in all_metrics_str for k in scale_keywords):
            raw_score = 90
        elif metrics: 
            raw_score = 70
            
        weight = cfg.get('cap_scale_w', 0)
        scores.append((raw_score, weight))
        details['project_scale'] = raw_score

    # D. Engineering Standards (ใช้ Keywords ชุดเดิม)
    if cfg.get('cap_standards_enabled'):
        # Keywords ชุดเดิม (เน้น Software Engineer ไม่มี Visualization, Analysis)
        keywords = ['tdd', 'unit test', 'ci/cd', 'pipeline', 'code review', 'agile', 'scrum', 'git']
        
        found_standards = 0
        all_text = str(data).lower()
        for k in keywords:
            if k in all_text:
                found_standards += 1
        
        raw_score = min(found_standards * 20 + 20, 100)
        weight = cfg.get('cap_standards_w', 0)
        scores.append((raw_score, weight))
        details['standards'] = raw_score

    # E. Duration
    if cfg.get('cap_exp_duration_enabled'):
        years = data.get('analysis', {}).get('years_of_experience', 0)
        required_years = 3
        raw_score = min((years / required_years) * 100, 100)
        weight = cfg.get('cap_exp_duration_w', 0)
        scores.append((raw_score, weight))
        details['duration_score'] = raw_score

    # G. Stability
    if cfg.get('cap_stability_enabled'):
        risk = data.get('analysis', {}).get('job_hopping_risk', 'Medium')
        mapping = {'Low': 90, 'Medium': 70, 'High': 40}
        raw_score = mapping.get(risk, 60)
        weight = cfg.get('cap_stability_w', 0)
        scores.append((raw_score, weight))
        details['stability_score'] = raw_score

    # Education
    if cfg.get('cap_edu_degree_enabled'):
        raw_score = 100 if data.get('education') else 50
        weight = cfg.get('cap_edu_degree_w', 0)
        scores.append((raw_score, weight))
    
    final_cap_score = _calculate_weighted_average(scores)
    return { "score": final_cap_score, "breakdown": details }

# ==========================================
# 4. Potential Scoring Logic
# ==========================================

def _calculate_potential(data, cfg):
    scores = []
    details = {}
    
    # A. Career Growth
    if cfg.get('pot_career_growth_enabled'):
        growth = data.get('analysis', {}).get('career_growth', 'Steady')
        mapping = {'Fast': 95, 'Steady': 75, 'Slow': 50}
        raw_score = mapping.get(growth, 70)
        weight = cfg.get('pot_career_growth_w', 0)
        scores.append((raw_score, weight))
        details['career_growth'] = raw_score

    # B. Learning Agility
    if cfg.get('pot_learning_agility_enabled'):
        skills_count = len(data.get('skills', {}).get('hard_skills', []))
        raw_score = min(skills_count * 5 + 40, 100) 
        weight = cfg.get('pot_learning_agility_w', 0)
        scores.append((raw_score, weight))
        details['learning_agility'] = raw_score

    # C. Leadership
    if cfg.get('pot_leadership_enabled'):
        lead_kw = ['lead', 'manage', 'mentor', 'head', 'chief', 'senior']
        raw_score = 40
        all_text = str(data.get('work_experience', [])).lower()
        if any(k in all_text for k in lead_kw):
            raw_score = 90
        weight = cfg.get('pot_leadership_w', 0)
        scores.append((raw_score, weight))
        details['leadership'] = raw_score 

    # D. Soft Skills
    if cfg.get('pot_soft_skills_enabled'):
        soft_count = len(data.get('skills', {}).get('soft_skills', []))
        raw_score = min(soft_count * 15 + 30, 100)
        weight = cfg.get('pot_soft_skills_w', 0)
        scores.append((raw_score, weight))
        details['soft_skills'] = raw_score

    final_pot_score = _calculate_weighted_average(scores)

    return { "score": final_pot_score, "breakdown": details }