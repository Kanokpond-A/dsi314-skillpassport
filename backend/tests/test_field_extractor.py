# tests/test_field_extractor.py

# Import by absolute file path (auto-detect location)
import importlib.util
from pathlib import Path
import pytest

THIS = Path(__file__).resolve()

# Candidate locations (project layouts we’ve seen)
cand = [
    # backend/app/services/A_backend/preprocess/field_extractor.py
    THIS.parents[3] / "app" / "services" / "A_backend" / "preprocess" / "field_extractor.py",
    # fallback: backend/app/services/A_backend/parsers/preprocess/field_extractor.py
    THIS.parents[3] / "app" / "services" / "A_backend" / "parsers" / "preprocess" / "field_extractor.py",
    # local variations used during dev
    THIS.parents[1] / "preprocess" / "field_extractor.py",
    THIS.parents[1] / "parsers" / "preprocess" / "field_extractor.py",
]

FE_PATH = next((p for p in cand if p.exists()), None)
assert FE_PATH is not None, f"field_extractor.py not found in any of: {cand}"

spec = importlib.util.spec_from_file_location("field_extractor", FE_PATH)
assert spec and spec.loader, f"cannot load spec from {FE_PATH}"
fe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fe)  # type: ignore

extract_all              = fe.extract_all
extract_name             = fe.extract_name
extract_last_job_title   = fe.extract_last_job_title
extract_experience_years = fe.extract_experience_years
extract_expected_salary  = fe.extract_expected_salary
extract_availability     = fe.extract_availability
extract_location         = fe.extract_location


# -------------------------
# Name
# -------------------------

def test_name_from_label():
    txt = "Name: Somchai Jai\nCustomer Service"
    assert extract_name(txt) == "Somchai Jai"

def test_name_from_first_lines_fallback():
    txt = "ประวัติย่อ\nนรินทร์ ศรีสุข\nอีเมล: a@b.com"
    assert extract_name(txt) == "นรินทร์ ศรีสุข"


# -------------------------
# Last job title
# -------------------------

def test_last_job_title_basic_from_dict():
    txt = "Experience\n- Customer Service at XYZ Hotel"
    jt = extract_last_job_title(txt)
    assert jt and jt.lower() == "customer service"

def test_last_job_title_from_role_dash_company():
    txt = "Experience\nMarketing Analyst - ABC Co.,Ltd."
    jt = extract_last_job_title(txt)
    assert jt and "analyst" in jt.lower()


# -------------------------
# Experience years
# -------------------------

@pytest.mark.parametrize("txt,exp", [
    ("Experience: 3 years at ABC", 3.0),
    ("ประสบการณ์ 2 ปี ที่บริษัท", 2.0),
    ("Exp 2-4 years", 3.0),  # average of range
    ("2019-01 to 2020-01\nCompany X", 1.0),  # deterministic span (no 'Present')
])
def test_experience_years(txt, exp):
    got = extract_experience_years(txt)
    assert got == pytest.approx(exp)


# -------------------------
# Expected salary
# -------------------------

@pytest.mark.parametrize("txt", [
    "Expected salary: 35,000 THB",
    "เงินเดือนที่คาดหวัง 25000 บาท",
    "Salary expectation - 30,000 - 45,000",
    "เงินเดือนที่ต้องการ: 45k-60k THB",
])
def test_expected_salary_any(txt):
    val = extract_expected_salary(txt)
    assert val is not None and isinstance(val, str) and len(val) > 0


# -------------------------
# Availability
# -------------------------

@pytest.mark.parametrize("txt,expect_contains", [
    ("Available immediately", "immediately"),
    ("พร้อมเริ่มงาน ทันที", "immediately"),
    ("Notice period: 30 days", "30"),
    ("Can start in 2 weeks", "2"),
])
def test_availability(txt, expect_contains):
    v = extract_availability(txt)
    assert v is not None and expect_contains.lower() in v.lower()


# -------------------------
# Location
# -------------------------

@pytest.mark.parametrize("txt", [
    "Location: Bangkok",
    "ที่อยู่: กรุงเทพ",
    "Experience at Phuket hotel",
    "Based in Nonthaburi, Thailand",
])
def test_location(txt):
    assert extract_location(txt) is not None


# -------------------------
# Bundle sanity
# -------------------------

def test_extract_all_bundle_minimal():
    txt = """Name: Natamon Vatavikantong
Experience
Senior Data Analyst at ABC  Jan 2021 – Dec 2022
Expected salary: 30,000 THB
Available immediately
Location: Bangkok
"""
    out = extract_all(txt).asdict()
    assert out["name"]
    assert out["last_job_title"]
    assert out["experience_years"] and out["experience_years"] > 0
    assert out["expected_salary"]
    assert out["availability"]
    assert out["location"]


