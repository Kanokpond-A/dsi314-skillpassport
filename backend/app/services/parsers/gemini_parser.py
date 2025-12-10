import google.generativeai as genai
import os
import json
import logging
from dotenv import load_dotenv
from typing import List, Dict, Any

load_dotenv()

# ดึง Key จาก Docker Environment
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
logging.basicConfig(level=logging.INFO)

def _clean_json_text(raw_text: str) -> str:
    """
    Helper function to clean up Gemini's raw text response to ensure valid JSON.
    """
    raw_text = raw_text.strip()
    if raw_text.startswith("```json"):
        return raw_text.replace("```json", "").replace("```", "").strip()
    return raw_text


def parse_with_gemini(file_bytes: bytes, mime_type: str = "application/pdf") -> Dict[str, Any] | None:
    """
    ใช้ Gemini เพื่อแยกข้อมูลโครงสร้างจากไฟล์เรซูเม่
    """
    try:
        model = genai.GenerativeModel('models/gemma-3-12b-it')

        # 🔥 แก้ไข Prompt ตรงนี้ครับ
        prompt = """
        You are an expert Technical Recruiter AI. 
        Your task is to extract FULL details from this resume.
        
        CRITICAL INSTRUCTIONS:
        1. Extract ALL technical skills found. Do not summarize or pick only the top 5. List EVERYTHING.
        2. Normalize skill names (e.g., convert "ReactJS" -> "React", "Node.js" -> "Node.js").
        3. If you find metrics (numbers/%) in work experience, extract them explicitly.
        4. ANALYSIS RULES:
           - "job_hopping_risk": If the candidate is a student or fresh graduate, do NOT count internships, part-time jobs, or academic projects as job hopping. Only label 'High' if they have frequent changes in full-time employment.
           - "years_of_experience": Sum up duration of internships and projects as valid experience.

        
        Output MUST be a valid JSON object with this exact structure:
        {
            "candidate_info": { "name": "Extract full name", "email": "", "phone": "" },
            "education": [ { "degree": "", "university": "", "year": "" } ],
            "work_experience": [
                {
                    "company": "", 
                    "role": "", 
                    "duration_years": 0.0,
                    "is_tech_company": true,
                    "description": "Full description",
                    "metrics_found": ["List all quantifiable achievements found"] 
                }
            ],
            "skills": {
                "hard_skills": ["List", "ALL", "technical", "skills", "found", "here"],
                "soft_skills": ["List", "ALL", "soft", "skills", "found"],
                "tools": ["List", "ALL", "tools", "libraries", "software"]
            },
            "analysis": {
                "years_of_experience": 0.0,
                "job_hopping_risk": "Low/Medium/High",
                "career_growth": "Fast/Steady/Slow",
                "summary": "Summarize strengths and weaknesses in Thai language"
            }
        }
        
        Return ONLY raw JSON. No markdown formatting.
        """

        response = model.generate_content([
            prompt,
            {"mime_type": mime_type, "data": file_bytes}
        ])

        # Clean JSON Cleanup
        raw_text = response.text or ""
        cleaned_text = _clean_json_text(raw_text)
        
        parsed_data = json.loads(cleaned_text)
        
        return parsed_data

    except Exception as e:
        logging.error(f"Gemini Parsing Error: {e}")
        return None

def parse_job_description_with_gemini(jd_text):
    try:
        model = genai.GenerativeModel('models/gemma-3-12b-it')
        prompt = f"""
        Extract required skills from this Job Description.
        Output JSON: {{ "required_skills": ["List", "of", "tech", "skills"], "min_experience_years": 0 }}
        
        JD Text:
        {jd_text[:2000]} 
        """
        
        response = model.generate_content(prompt)
        # ... (Clean JSON logic เหมือนเดิม) ...
        raw_text = response.text or ""
        cleaned_text = _clean_json_text(raw_text)
        return json.loads(cleaned_text)
    except Exception as e:
        logging.error(f"Gemini JD Parsing Error: {e}")
        return {"required_skills": [], "min_experience_years": 0}

def get_standard_skills_for_role(role_name: str) -> Dict[str, Any]:
    """
    ถาม AI เพื่อให้ได้รายการ Hard Skills มาตรฐานที่ครอบคลุมสำหรับบทบาทที่กำหนด
    (ไม่จำกัดจำนวน)
    """
    try:
        model = genai.GenerativeModel('models/gemma-3-12b-it')
        prompt = f"""
        List the top 10 most important technical skills required for a "{role_name}" role in 2025.
        Return JSON: {{ "required_skills": ["Skill1", "Skill2", "Skill3", ...] }}
        """
        response = model.generate_content(prompt)
        # ... (clean json logic) ...
        raw_text = response.text or ""
        cleaned_text = _clean_json_text(raw_text)

        return json.loads(cleaned_text)
    except Exception as e:
        logging.error(f"Gemini Role Skills Error: {e}")
        return {"required_skills": []}
    
# --- 3. ฟังก์ชันใหม่สำหรับการให้คะแนน (Match Scoring Function) ---

def calculate_match_score(
    required_keywords: List[str], 
    candidate_skills: List[str]
) -> Dict[str, Any]:
    """
    คำนวณเปอร์เซ็นต์ความตรงกันระหว่าง Keywords ที่ต้องการ กับ Skills ในเรซูเม่
    
    Args:
        required_keywords: รายการ Keywords ที่ HR ต้องการ (K_input)
        candidate_skills: รายการ Skills ทั้งหมดที่ดึงมาจากเรซูเม่
        
    Returns:
        Dict ที่มี Match Percentage และรายละเอียดการจับคู่
    """
    # 1. ทำความสะอาดข้อมูลเพื่อการเปรียบเทียบ
    # แปลงเป็นตัวพิมพ์เล็กและกำจัดช่องว่าง (Normalization)
    required_norm = {kw.lower().strip() for kw in required_keywords if kw}
    candidate_norm = {sk.lower().strip() for sk in candidate_skills if sk}
    
    # 2. คำนวณจำนวนทั้งหมดและจำนวนที่พบ
    total_required = len(required_norm)
    
    # ใช้ Intersection เพื่อหา Keywords ที่ตรงกัน
    matched_skills = required_norm.intersection(candidate_norm)
    found_count = len(matched_skills)
    
    # 3. คำนวณเปอร์เซ็นต์
    if total_required == 0:
        match_percentage = 0.0
    else:
        # สูตร: (K_found / K_total) * 100
        match_percentage = (found_count / total_required) * 100
        # ปัดทศนิยม 2 ตำแหน่ง
        match_percentage = round(match_percentage, 2)
    
    # 4. จัดเตรียมผลลัพธ์
    unmatched_skills = required_norm.difference(candidate_norm)
    
    return {
        "match_percentage": match_percentage,
        "keywords_total": total_required,
        "keywords_found": found_count,
        "matched_skills": list(matched_skills),
        "unmatched_skills_required": list(unmatched_skills)
    }
    
def analyze_match_with_gemini(resume_data, job_description):
    """
    ฟังก์ชันเทียบ Resume (JSON) กับ Job Description (Text)
    """
    try:
        model = genai.GenerativeModel('models/gemma-3-12b-it') # ใช้ตัวเก่งสุด

        prompt = f"""
        Act as a Senior Technical Recruiter.
        
        I will give you a Candidate Resume (JSON) and a Target Job Description.
        Your goal is to evaluate the **Matching Score (0-100%)**.

        1. **Candidate Resume:** {json.dumps(resume_data, ensure_ascii=False)}

        2. **Target Job Description:**
        "{job_description}"

        ---
        **Analysis Rules:**
        - **90-100%:** Perfect match (Have all required skills + Exp).
        - **70-89%:** Good match (Missing minor skills but trainable).
        - **<70%:** Low match (Missing critical skills or wrong domain).
        
        **Output Format (JSON Only):**
        {{
            "match_percentage": 0,
            "matched_criteria": ["List specific skills/exp that match the JD"],
            "missing_gaps": ["List specific missing skills or requirements"],
            "summary_comment": "Short reason for this score"
        }}
        """

        response = model.generate_content(prompt)

        print("--------------------------------------------------")
        print("🤖 RAW RESPONSE FROM GEMMA:")
        print(response.text)  # <--- เพิ่มบรรทัดนี้ เพื่อดูว่า AI ตอบอะไรมา
        print("--------------------------------------------------")

        cleaned_text = _clean_json_text(response.text)
        return json.loads(cleaned_text)

    except Exception as e:
        print(f"Matching Error: {e}")
        return {"match_percentage": 0, "matched_criteria": [], "missing_gaps": ["Error analyzing match"]}