import sys
from pathlib import Path

# ทำให้ import ได้แน่นอน
ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.services.A_backend.preprocess.skills_normalizer import normalize_skills, load_skill_map

def test_load_skill_map():
    alias2canon, canon2cat = load_skill_map()
    # alias mapping พื้นฐาน
    assert alias2canon.get("py") == "Python"
    assert alias2canon.get("บริการลูกค้า") == "Customer Service"

    # บางโปรเจกต์เก็บ category ด้วยคีย์แบบ title-case
    # บางที่อาจเป็น lowercase — ทำให้เทสต์ยืดหยุ่นโดย normalize key เป็น lowercase ก่อนตรวจ
    canon2cat_lower = { (k or "").lower(): v for k, v in canon2cat.items() }
    assert canon2cat_lower.get("python") == "Tech"

def test_normalize_basic():
    res = normalize_skills(["py", "SQL", "ms excel"])
    # ปรับให้ตรงกับ structure_builder: ผลลัพธ์เป็น list[str]
    assert isinstance(res, list)
    assert "Python" in res
    assert "SQL" in res
    assert "Excel" in res

def test_normalize_split_tokens():
    res = normalize_skills(["Python/SQL"])
    assert "Python" in res and "SQL" in res

def test_dedup_order():
    res = normalize_skills(["py", "python", "PYTHON"])
    assert res == ["Python"]  # ไม่ซ้ำ, เก็บลำดับครั้งแรก

