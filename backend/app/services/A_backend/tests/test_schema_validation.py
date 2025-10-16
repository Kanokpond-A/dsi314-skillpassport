# A_backend/tests/test_schema_validation.py
import json, glob
from pathlib import Path
from jsonschema import Draft202012Validator

# อ้าง path แบบแน่นอนจากรากโปรเจกต์
ROOT   = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "A_backend/schemas/parsed_resume.schema.json"
FILES  = ROOT / "shared_data/latest_parsed"

def test_parsed_files_match_schema():
    # โหลดสคีมา
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
