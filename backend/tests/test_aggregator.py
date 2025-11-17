import re

from backend.app.services.A_backend.preprocess.aggregate_export import (
    infer_industry_from_skills,
    estimate_years_from_experiences,
    redact_candidate,
)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\- ()]{7,}\d")

def test_infer_industry_from_skills_vote():
    # ต้องคืนหมวด/อุตสาหกรรมจาก skills_master.csv (เช่น "Tech")
    ind = infer_industry_from_skills(["Python", "SQL"])
    assert isinstance(ind, str)
    assert len(ind) > 0

def test_estimate_years_from_experiences_basic():
    exps = [
        {"start": "2019-01", "end": "2021-01"},  # 24 เดือน
        {"start": "2016",    "end": "2018-06"},  # ~30 เดือน
    ]
    yrs = estimate_years_from_experiences(exps)
    assert yrs is not None
    # 24 + 30 = 54 เดือน ≈ 4.5 ปี
    assert 4.0 <= yrs <= 6.0

def test_redact_candidate_no_pii_and_strip_debug():
    c = {
        "name": "alice@example.com",
        "availability": "+66 81-234-5678",
        "contacts": {"email": "alice@example.com", "phone": "+66 81-234-5678"},
        "evidence_snippets": [
            "Contact me at alice@example.com or +66 81-234-5678",
            "Work period 2016 - 2019",  # year-range ไม่ควรถูกแทนเป็น phone
        ],
        "_raw_debug": {"experiences": [{"bullets": ["2016 - 2019"]}]},
    }
    r = redact_candidate(c)

    # _raw_debug ต้องถูกลบทิ้งเมื่อ redact
    assert "_raw_debug" not in r

    # ข้อความอิสระต้องไม่เหลือ email/phone
    blob = " ".join([
        r.get("name", ""),
        r.get("availability", ""),
        *(r.get("evidence_snippets") or []),
    ])
    assert not EMAIL_RE.search(blob)
    assert not PHONE_RE.search(blob)

    # year-range ควรยังอยู่ (ไม่ใช่ PII)
    assert "2016 - 2019" in " ".join(r.get("evidence_snippets") or [])

    # contacts ที่เป็น PII ถูกเคลียร์
    assert r["contacts"]["email"] == ""
    assert r["contacts"]["phone"] == ""
