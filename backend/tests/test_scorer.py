import pytest
from backend.app.services.scoring import ScoringConfig, score_applicant

def test_basic_matching_no_evidence():
    cfg = ScoringConfig(required_weights={"Python": 0.5, "SQL": 0.5})
    res = score_applicant(["Python"], evidence=[], cfg=cfg)
    hr = res["hr_view"]; mv = res["machine_view"]
    assert 49.0 <= hr["score"] <= 51.0
    assert "SQL" in hr["summary"]["missing_skills"]
    assert mv["fit_score"] == pytest.approx(hr["score"]/100.0, rel=1e-3)

def test_alias_and_bonus_cap():
    cfg = ScoringConfig(required_weights={"FastAPI": 1.0},
                        aliases={"fast api":"FastAPI"}, evidence_bonus_each=5, evidence_bonus_cap=10)
    res = score_applicant(["fast api"], evidence=[{}, {}, {}], cfg=cfg)
    hr = res["hr_view"]
    assert hr["score"] == 100.0
    assert hr["summary"]["evidence_bonus"] == 10.0

def test_missing_all():
    cfg = ScoringConfig(required_weights={"Python":1.0,"SQL":1.0})
    res = score_applicant([], evidence=[], cfg=cfg)
    assert res["hr_view"]["score"] == 0.0
    assert set(res["hr_view"]["summary"]["missing_skills"]) == {"Python","SQL"}

@pytest.mark.parametrize("skills, expected", [
    (["Python"], "Moderate fit"),
    (["Python","SQL"], "Strong fit"),
])
def test_band_labels(skills, expected):
    cfg = ScoringConfig(required_weights={"Python":0.5,"SQL":0.5},
                        bands=[(85,"Excellent fit"),(70,"Strong fit"),
                               (50,"Moderate fit"),(0,"Needs improvement")])
    res = score_applicant(skills, evidence=[], cfg=cfg)
    assert res["hr_view"]["level"] == expected
