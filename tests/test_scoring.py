from backend.app.services.scoring.scoring import calculate_universal_score, get_default_weights

def test_scoring_logic():
    # 1. จำลองข้อมูลที่ Gemini อ่านได้
    mock_gemini_data = {
        "skills": {
            "hard_skills": ["Python", "Docker", "SQL", "FastAPI", "React"], # 5 Skills
            "soft_skills": ["Leadership"]
        },
        "analysis": {
            "years_of_experience": 4,
            "career_growth": "Fast",
            "job_hopping_risk": "Low"
        },
        "work_experience": [],
        "education": []
    }

    # 2. จำลองการตั้งค่า Slider ของ HR
    mock_config = get_default_weights()
    
    # 3. สั่งคำนวณ
    result = calculate_universal_score(mock_gemini_data, mock_config)
    
    # 4. ตรวจคำตอบ (Assert)
    print(f"Calculated Score: {result['final_score']}")
    
    # คะแนนต้องมากกว่า 0 แน่นอน
    assert result['final_score'] > 0 
    assert result['potential']['score'] > 50 # เพราะ Growth=Fast และ Risk=Low คะแนน Potential ควรสูง