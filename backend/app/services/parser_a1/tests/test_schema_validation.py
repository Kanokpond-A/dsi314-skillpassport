import json, glob
from pathlib import Path
from jsonschema import Draft202012Validator

# === แก้ไขตรงนี้ (1/2) ===
# อ้าง Path ไปยังรากของโปรเจกต์ (dsi314-skillpassport)
# (ปรับเลข parents จาก 4 เป็น 5 เพื่อให้ชี้ไปยังโฟลเดอร์รากที่ถูกต้อง)
ROOT   = Path(__file__).resolve().parents[5] 

# === แก้ไขตรงนี้ (2/2) ===
# สร้าง Path ไปยังไฟล์ Schema ที่ถูกต้อง (ไม่มี A_backend)
# (สมมติว่า schemas folder อยู่ที่ backend/app/schemas)
SCHEMA = ROOT / "backend/app/schemas/parsed_resume.schema.json"
FILES  = ROOT / "shared_data/latest_parsed"


def test_parsed_files_match_schema():
    # โหลดสคีมา
    # (ตรวจสอบให้แน่ใจว่าไฟล์ SCHEMA มีอยู่จริงตาม Path ที่กำหนด)
    if not SCHEMA.exists():
        # เพิ่ม assert นี้เพื่อให้หาข้อผิดพลาดง่ายขึ้น
        assert False, f"Schema file not found at: {SCHEMA}"

    schema = json.load(open(SCHEMA, "r", encoding="utf-8"))
    validator = Draft202012Validator(schema)

    # หาไฟล์ทั้งหมด
    files = sorted(glob.glob(str(FILES / "*.json")))
    assert files, "no files in shared_data/latest_parsed"

    # ตรวจทีละไฟล์
    for p in files:
        data = json.load(open(p, "r", encoding="utf-8"))
        errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
        assert not errors, f"schema errors in {p}: " + "; ".join(e.message for e in errors)