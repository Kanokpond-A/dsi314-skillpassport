import google.generativeai as genai
import os
import json
import logging

# ดึง Key จาก Docker Environment
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def parse_with_gemini(file_bytes, mime_type="application/pdf"):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')

        # 🔥 แก้ไข Prompt ตรงนี้ครับ
        prompt = """
        You are an expert Technical Recruiter AI. 
        Your task is to extract FULL details from this resume.
        
        CRITICAL INSTRUCTIONS:
        1. Extract ALL technical skills found. Do not summarize or pick only the top 5. List EVERYTHING.
        2. Normalize skill names (e.g., convert "ReactJS" -> "React", "Node.js" -> "Node.js").
        3. If you find metrics (numbers/%) in work experience, extract them explicitly.
        
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
        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text.replace("```json", "").replace("```", "")
        
        parsed_data = json.loads(raw_text)
        
        return parsed_data

    except Exception as e:
        logging.error(f"Gemini Parsing Error: {e}")
        return None

def parse_job_description_with_gemini(jd_text):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Extract required skills from this Job Description.
        Output JSON: {{ "required_skills": ["List", "of", "tech", "skills"], "min_experience_years": 0 }}
        
        JD Text:
        {jd_text[:2000]} 
        """
        
        response = model.generate_content(prompt)
        # ... (Clean JSON logic เหมือนเดิม) ...
        return json.loads(cleaned_text)
    except:
        return {"required_skills": [], "min_experience_years": 0}

def get_standard_skills_for_role(role_name):
    """
    ถาม AI ว่าอาชีพนี้ควรมีสกิลอะไรบ้าง (แทนการใช้ไฟล์ YAML)
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        List the top 10 most important technical skills required for a "{role_name}" role in 2025.
        Return JSON: {{ "required_skills": ["Skill1", "Skill2", ...] }}
        """
        response = model.generate_content(prompt)
        # ... (clean json logic) ...
        return json.loads(cleaned_text)
    except:
        return {"required_skills": []}