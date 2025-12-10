import datetime
import math

def get_default_weights():
    """
    ค่า Default Configuration สำหรับ Slider บนหน้าเว็บ
    """
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

def calculate_universal_score(parsed_data, weights_config, job_description=None):
    capabilities_result = _calculate_capabilities(parsed_data, weights_config, job_description)
    potential_result = _calculate_potential(parsed_data, weights_config)

    return {
        "final_score": capabilities_result['score'], 
        "capabilities": capabilities_result,
        "potential": potential_result
    }

# ==========================================
# 🧠 Logic แกนที่ 1: Capabilities Score
# ==========================================
def _calculate_capabilities(data, cfg, jd):
    scores = [] 
    details = {} 
    
    # A. Skill Match
    if cfg.get('cap_skills_match_enabled'):
        hard_skills_count = len(data.get('skills', {}).get('hard_skills', []))
        raw_score = min(hard_skills_count * 10, 100) 
        weight = cfg.get('cap_skills_match_w', 0)
        scores.append((raw_score, weight))
        details['skill_match'] = raw_score # ✅ มีแล้ว

    # B. Skill Recency
    if cfg.get('cap_recency_enabled'):
        raw_score = 100 
        weight = cfg.get('cap_recency_w', 0)
        scores.append((raw_score, weight))
        # details['recency'] = raw_score  <-- (ถ้าไม่ได้ใช้แสดงกราฟ ไม่ต้องใส่ก็ได้)

    # C. Project Scale
    if cfg.get('cap_scale_enabled'):
        raw_score = 40 
        metrics = []
        for job in data.get('work_experience', []):
            metrics.extend(job.get('metrics_found', []))
        scale_keywords = ['million', 'users', 'high traffic', 'scale', 'concurrent']
        for m in metrics:
            if any(k in m.lower() for k in scale_keywords):
                raw_score = 100
                break
            raw_score = min(raw_score + 10, 90)
        weight = cfg.get('cap_scale_w', 0)
        scores.append((raw_score, weight))
        details['project_scale'] = raw_score # ✅ มีแล้ว

    # D. Engineering Standards
    if cfg.get('cap_standards_enabled'):
        keywords = ['tdd', 'unit test', 'ci/cd', 'pipeline', 'code review', 'agile', 'scrum']
        found_standards = 0
        all_text = str(data) 
        for k in keywords:
            if k in all_text.lower():
                found_standards += 1
        raw_score = min(found_standards * 20, 100)
        weight = cfg.get('cap_standards_w', 0)
        scores.append((raw_score, weight))
        details['standards'] = raw_score # ✅ มีแล้ว

    # E. Duration
    if cfg.get('cap_exp_duration_enabled'):
        years = data.get('analysis', {}).get('years_of_experience', 0)
        required_years = 3 
        raw_score = min((years / required_years) * 100, 100)
        weight = cfg.get('cap_exp_duration_w', 0)
        scores.append((raw_score, weight))
        details['duration_score'] = raw_score # ✅ มีแล้ว

    # F. Company Tier
    if cfg.get('cap_company_tier_enabled'):
        top_tiers = ['google', 'microsoft', 'agoda', 'lineman', 'grab', 'scb', 'kbank']
        raw_score = 50 
        for job in data.get('work_experience', []):
            company = job.get('company', '').lower()
            if any(t in company for t in top_tiers):
                raw_score = 100 
                break
        weight = cfg.get('cap_company_tier_w', 0)
        scores.append((raw_score, weight))

    # G. Stability
    if cfg.get('cap_stability_enabled'):
        risk = data.get('analysis', {}).get('job_hopping_risk', 'Medium')
        mapping = {'Low': 100, 'Medium': 70, 'High': 40}
        raw_score = mapping.get(risk, 50)
        weight = cfg.get('cap_stability_w', 0)
        scores.append((raw_score, weight))
        details['stability_score'] = raw_score # ✅ มีแล้ว

    # Education
    if cfg.get('cap_edu_degree_enabled'):
        raw_score = 100 if data.get('education') else 50
        weight = cfg.get('cap_edu_degree_w', 0)
        scores.append((raw_score, weight))
    
    final_cap_score = _calculate_weighted_average(scores)
    
    return { "score": final_cap_score, "breakdown": details }

# ==========================================
# 🚀 Logic แกนที่ 2: Potential Score
# ==========================================
def _calculate_potential(data, cfg):
    scores = []
    details = {}
    
    # A. Career Growth
    if cfg.get('pot_career_growth_enabled'):
        growth = data.get('analysis', {}).get('career_growth', 'Steady')
        mapping = {'Fast': 100, 'Steady': 75, 'Slow': 50}
        raw_score = mapping.get(growth, 60)
        weight = cfg.get('pot_career_growth_w', 0)
        scores.append((raw_score, weight))
        details['career_growth'] = raw_score # ✅ มีแล้ว

    # B. Learning Agility
    if cfg.get('pot_learning_agility_enabled'):
        skills_count = len(data.get('skills', {}).get('hard_skills', []))
        raw_score = min(skills_count * 8, 100)
        weight = cfg.get('pot_learning_agility_w', 0)
        scores.append((raw_score, weight))
        details['learning_agility'] = raw_score # ✅ มีแล้ว

    # C. Leadership
    if cfg.get('pot_leadership_enabled'):
        lead_kw = ['lead', 'manage', 'mentor', 'head', 'chief', 'founder']
        raw_score = 0
        all_text = str(data.get('work_experience', [])).lower()
        if any(k in all_text for k in lead_kw):
            raw_score = 100
        weight = cfg.get('pot_leadership_w', 0)
        scores.append((raw_score, weight))
        
        # 🔥🔥🔥 จุดที่เคยหายไป: ต้องเพิ่มบรรทัดนี้ 🔥🔥🔥
        details['leadership'] = raw_score 

    # D. Soft Skills
    if cfg.get('pot_soft_skills_enabled'):
        soft_count = len(data.get('skills', {}).get('soft_skills', []))
        raw_score = min(soft_count * 20, 100)
        weight = cfg.get('pot_soft_skills_w', 0)
        scores.append((raw_score, weight))
        
        # 🔥🔥🔥 จุดที่เคยหายไป: เพิ่มบรรทัดนี้ด้วยเผื่อใช้ 🔥🔥🔥
        details['soft_skills'] = raw_score

    final_pot_score = _calculate_weighted_average(scores)

    return { "score": final_pot_score, "breakdown": details }

def _calculate_weighted_average(score_list):
    total_weighted_score = 0
    total_active_weight = 0
    for score, weight in score_list:
        total_weighted_score += (score * weight)
        total_active_weight += weight
    if total_active_weight == 0:
        return 0
    return round(total_weighted_score / total_active_weight, 2)