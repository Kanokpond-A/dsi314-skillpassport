import statistics
import time

def generate_cohort_analysis(candidates_list):
    """
    วิเคราะห์ภาพรวมของผู้สมัครทั้งหมด (Cohort Analysis)
    รับ input เป็น list ของ dict ที่มี keys: {'parsed_data', 'score_result'}
    """
    
    # 1. เตรียมตัวแปรเก็บข้อมูล
    all_scores = []
    all_skills_found = []
    skill_counts = {}
    
    # ดึงข้อมูลจาก Candidates แต่ละคน
    processed_candidates = []
    
    for cand in candidates_list:
        # ดึงคะแนน (Universal Score)
        final_score = cand.get('score_result', {}).get('final_score', 0)
        all_scores.append(final_score)
        
        # ดึง Skill ที่เจอ (จาก Gemini Parsed Data)
        # ระวัง: ต้องเช็คว่า structure ตรงกับที่เราออกแบบ
        parsed = cand.get('parsed_data', {})
        hard_skills = parsed.get('skills', {}).get('hard_skills', [])
        
        for skill in hard_skills:
            # Normalize skill name (ตัวเล็กหมด)
            s_norm = skill.lower().strip()
            all_skills_found.append(s_norm)
            skill_counts[s_norm] = skill_counts.get(s_norm, 0) + 1
            
        # สร้าง Data ย่อสำหรับแสดงในตารางสรุป
        processed_candidates.append({
            "name": parsed.get('candidate_info', {}).get('name', 'Unknown'),
            "score": final_score,
            "skills": hard_skills[:5], # โชว์แค่ 5 อันแรก
            "experience_years": parsed.get('analysis', {}).get('years_of_experience', 0),
            "risk_level": parsed.get('analysis', {}).get('job_hopping_risk', 'Unknown')
        })

    # 2. คำนวณสถิติ (Statistics)
    count = len(all_scores)
    if count == 0:
        return {"meta": {"count": 0}, "metrics": {}, "candidates": []}

    avg_score = statistics.mean(all_scores)
    median_score = statistics.median(all_scores)
    max_score = max(all_scores)
    min_score = min(all_scores)

    # 3. หาสกิลยอดฮิต (Top Skills Found)
    # เรียงลำดับจากมากไปน้อย
    sorted_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)
    top_skills = [{"name": k, "count": v} for k, v in sorted_skills[:10]]

    # 4. สร้าง Payload ส่งกลับไปให้ Frontend Dashboard
    payload = {
        "meta": {
            "generated_at": int(time.time()),
            "total_candidates": count
        },
        "metrics": {
            "avg_score": round(avg_score, 2),
            "median_score": round(median_score, 2),
            "max_score": round(max_score, 2),
            "min_score": round(min_score, 2)
        },
        "market_insights": {
            "top_skills_found": top_skills
            # ในอนาคตเพิ่ม "missing_skills" ได้ถ้าเทียบกับ JD
        },
        "candidates_leaderboard": sorted(processed_candidates, key=lambda x: x['score'], reverse=True)
    }

    return payload