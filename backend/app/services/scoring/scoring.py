import datetime
import math

def get_default_weights():
    """
    ค่า Default Configuration สำหรับ Slider บนหน้าเว็บ
    """
    return {
        # --- Axis 1: Capabilities ---
        "cap_skills_match_w": 80,       "cap_skills_match_enabled": True,
        "cap_recency_w": 40,            "cap_recency_enabled": True,
        "cap_scale_w": 50,              "cap_scale_enabled": True,
        "cap_standards_w": 30,          "cap_standards_enabled": True,
        
        "cap_exp_duration_w": 20,       "cap_exp_duration_enabled": True,
        "cap_company_tier_w": 30,       "cap_company_tier_enabled": False, # Default ปิดเพื่อลด Bias
        "cap_stability_w": 40,          "cap_stability_enabled": True,
        
        "cap_edu_degree_w": 30,         "cap_edu_degree_enabled": True,
        "cap_edu_tier_w": 20,           "cap_edu_tier_enabled": False,     # Default ปิด
        "cap_certs_w": 30,              "cap_certs_enabled": True,

        "cap_logistics_w": 50,          "cap_logistics_enabled": True, # Salary/Location

        # --- Axis 2: Potential ---
        "pot_career_growth_w": 90,      "pot_career_growth_enabled": True,
        "pot_learning_agility_w": 70,   "pot_learning_agility_enabled": True,
        "pot_leadership_w": 50,         "pot_leadership_enabled": True,
        "pot_soft_skills_w": 40,        "pot_soft_skills_enabled": True
    }

def calculate_universal_score(parsed_data, weights_config, job_description=None):
    """
    ฟังก์ชันหลักสำหรับคำนวณคะแนนทั้งหมด
    :param parsed_data: Dictionary ข้อมูลที่ได้จาก Gemini Parser
    :param weights_config: Dictionary ค่า Slider ที่รับมาจาก Frontend
    :param job_description: (Optional) ข้อมูล JD เพื่อใช้เทียบ Skill Match
    """
    
    # 1. คำนวณ Capabilities Score (ความพร้อมทำงาน)
    capabilities_result = _calculate_capabilities(parsed_data, weights_config, job_description)
    
    # 2. คำนวณ Potential Score (ศักยภาพ)
    potential_result = _calculate_potential(parsed_data, weights_config)

    return {
        "final_score": capabilities_result['score'], # หรือจะใช้สูตรผสม (Cap*0.7 + Pot*0.3) ก็ได้
        "capabilities": capabilities_result,
        "potential": potential_result
    }

# ==========================================
# 🧠 Logic แกนที่ 1: Capabilities Score
# ==========================================
def _calculate_capabilities(data, cfg, jd):
    scores = [] # เก็บ tuple (raw_score, weight)
    details = {} # เก็บรายละเอียดเพื่อส่งกลับไปโชว์
    
    # --- 1. Technical Capabilities ---
    
    # A. Skill Match %
    if cfg.get('cap_skills_match_enabled'):
        # ในโปรเจกต์จริง ต้องเทียบกับ JD.required_skills
        # Mock logic: ถือว่า Gemini วิเคราะห์มาให้แล้ว หรือนับจำนวน Skill ที่เจอ
        hard_skills_count = len(data.get('skills', {}).get('hard_skills', []))
        raw_score = min(hard_skills_count * 10, 100) # สมมติเจอ 10 skill = 100 คะแนน
        weight = cfg.get('cap_skills_match_w', 0)
        scores.append((raw_score, weight))
        details['skill_match'] = raw_score

    # B. Skill Recency (ความสดใหม่)
    if cfg.get('cap_recency_enabled'):
        # Mock logic: ดูปีล่าสุดจาก work experience
        current_year = datetime.datetime.now().year
        last_job_year = current_year # Default
        if data.get('work_experience'):
             # สมมติ Gemini แกะปีสิ้นสุดมาให้ หรือใช้ปีปัจจุบัน
             pass 
        raw_score = 100 # สมมติว่าสดใหม่ (Implement logic ปีลบกันได้)
        weight = cfg.get('cap_recency_w', 0)
        scores.append((raw_score, weight))

    # C. Project Complexity / Scale
    if cfg.get('cap_scale_enabled'):
        # ตรวจหา keywords: High Traffic, Users, Revenue ใน metrics
        raw_score = 40 # Base score
        metrics = []
        for job in data.get('work_experience', []):
            metrics.extend(job.get('metrics_found', []))
        
        scale_keywords = ['million', 'users', 'high traffic', 'scale', 'concurrent']
        for m in metrics:
            if any(k in m.lower() for k in scale_keywords):
                raw_score = 100
                break
            raw_score = min(raw_score + 10, 90) # เจอ metric ทั่วไปบวกเพิ่ม
            
        weight = cfg.get('cap_scale_w', 0)
        scores.append((raw_score, weight))
        details['project_scale'] = raw_score

    # D. Engineering Standards
    if cfg.get('cap_standards_enabled'):
        keywords = ['tdd', 'unit test', 'ci/cd', 'pipeline', 'code review', 'agile', 'scrum']
        found_standards = 0
        all_text = str(data) # Search ทั้ง resume
        for k in keywords:
            if k in all_text.lower():
                found_standards += 1
        
        raw_score = min(found_standards * 20, 100)
        weight = cfg.get('cap_standards_w', 0)
        scores.append((raw_score, weight))
        details['standards'] = raw_score

    # --- 2. Professional Experience ---

    # E. Duration (ปีประสบการณ์)
    if cfg.get('cap_exp_duration_enabled'):
        years = data.get('analysis', {}).get('years_of_experience', 0)
        # สมมติ JD ต้องการ 3 ปี
        required_years = 3 
        raw_score = min((years / required_years) * 100, 100)
        weight = cfg.get('cap_exp_duration_w', 0)
        scores.append((raw_score, weight))
        details['duration_score'] = raw_score

    # F. Company Tier (เกรดบริษัท)
    if cfg.get('cap_company_tier_enabled'):
        # ต้องมี DB บริษัท Tier 1 (Google, Agoda, SCB, etc.)
        top_tiers = ['google', 'microsoft', 'agoda', 'lineman', 'grab', 'scb', 'kbank']
        raw_score = 50 # Base (SME)
        for job in data.get('work_experience', []):
            company = job.get('company', '').lower()
            if any(t in company for t in top_tiers):
                raw_score = 100 # Tier 1
                break
        
        weight = cfg.get('cap_company_tier_w', 0)
        scores.append((raw_score, weight))

    # G. Stability (ความมั่นคง)
    if cfg.get('cap_stability_enabled'):
        risk = data.get('analysis', {}).get('job_hopping_risk', 'Medium')
        mapping = {'Low': 100, 'Medium': 70, 'High': 40}
        raw_score = mapping.get(risk, 50)
        weight = cfg.get('cap_stability_w', 0)
        scores.append((raw_score, weight))
        details['stability_score'] = raw_score

    # --- 3. Education --- (ตัวอย่าง Education แบบย่อ)
    if cfg.get('cap_edu_degree_enabled'):
        # Mock: มี degree = 100
        raw_score = 100 if data.get('education') else 50
        weight = cfg.get('cap_edu_degree_w', 0)
        scores.append((raw_score, weight))
    
    # คำนวณ Weighted Average
    final_cap_score = _calculate_weighted_average(scores)
    
    return {
        "score": final_cap_score,
        "breakdown": details
    }

# ==========================================
# 🚀 Logic แกนที่ 2: Potential Score
# ==========================================
def _calculate_potential(data, cfg):
    scores = []
    details = {}
    
    # A. Career Growth (จาก Gemini Analysis)
    if cfg.get('pot_career_growth_enabled'):
        growth = data.get('analysis', {}).get('career_growth', 'Steady')
        mapping = {'Fast': 100, 'Steady': 75, 'Slow': 50}
        raw_score = mapping.get(growth, 60)
        
        weight = cfg.get('pot_career_growth_w', 0)
        scores.append((raw_score, weight))
        details['career_growth'] = raw_score

    # B. Learning Agility (ความถี่ Skill ใหม่)
    if cfg.get('pot_learning_agility_enabled'):
        # Logic: ดูจำนวน tech skill ทั้งหมด (ยิ่งเยอะ ยิ่งน่าจะเรียนรู้ไว)
        skills_count = len(data.get('skills', {}).get('hard_skills', []))
        raw_score = min(skills_count * 8, 100)
        
        weight = cfg.get('pot_learning_agility_w', 0)
        scores.append((raw_score, weight))
        details['learning_agility'] = raw_score

    # C. Leadership
    if cfg.get('pot_leadership_enabled'):
        # หา keyword: Lead, Manage, Head, Founder
        lead_kw = ['lead', 'manage', 'mentor', 'head', 'chief', 'founder']
        raw_score = 0
        all_text = str(data.get('work_experience', [])).lower()
        if any(k in all_text for k in lead_kw):
            raw_score = 100
        
        weight = cfg.get('pot_leadership_w', 0)
        scores.append((raw_score, weight))

    # D. Soft Skills & Communication
    if cfg.get('pot_soft_skills_enabled'):
        soft_count = len(data.get('skills', {}).get('soft_skills', []))
        raw_score = min(soft_count * 20, 100)
        
        weight = cfg.get('pot_soft_skills_w', 0)
        scores.append((raw_score, weight))

    final_pot_score = _calculate_weighted_average(scores)

    return {
        "score": final_pot_score,
        "breakdown": details
    }

# ==========================================
# 🧮 Helper: ตัวคำนวณคณิตศาสตร์
# ==========================================
def _calculate_weighted_average(score_list):
    """
    รับ list ของ tuple: [(raw_score, weight), (raw_score, weight), ...]
    คำนวณ: (Sum(score*weight)) / Sum(active_weights)
    """
    total_weighted_score = 0
    total_active_weight = 0
    
    for score, weight in score_list:
        total_weighted_score += (score * weight)
        total_active_weight += weight
        
    if total_active_weight == 0:
        return 0
        
    return round(total_weighted_score / total_active_weight, 2)