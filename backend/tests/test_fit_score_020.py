import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.services.scoring.logic_020 import calculate_fit_score


def test_fit_score_basic_case():
    candidate = {
        "skills": ["Python", "SQL"],
        "required_skills": ["Python", "SQL"],
        "experience_years": 3,
        "availability": "Immediate",
        "expected_salary": "50000",
        "budget_max": "60000",
        "education_level": "bachelor",
        "required_education": "bachelor",
        "languages": [{"name": "English", "level": "professional"}],
        "certifications": ["AWS Certified"],
        "portfolio": "https://portfolio.site/demo"
    }
    score = calculate_fit_score(candidate)
    print(f"Fit score = {score}")
    assert 90 <= score <= 100
