# backend/app/services/A_backend/tests/test_schema_validation.py
import json, glob
from pathlib import Path
from jsonschema import Draft202012Validator

# หา ROOT ของโปรเจกต์จากตำแหน่งไฟล์เทส
ROOT = Path(__file__).resolve().parents[5]   # .../dsi314-skillpassport
FILES_DIR = ROOT / "shared_data/latest_parsed"
SCHEMA_PATH = ROOT / "backend/app/services/A_backend/schemas/parsed_resume.schema.json"

def _list_parsed_jsons():
    """ดึงเฉพาะไฟล์ parsed_resume ที่จะตรวจ schema (ตัดไฟล์ extras ออก)"""
    all_jsons = sorted(glob.glob(str(FILES_DIR / "*.json")))
    return [p for p in all_jsons
            if Path(p).name.startswith("_extras_") is False]

def test_parsed_files_match_schema():
    # โหลด schema
    schema = json.load(open(SCHEMA_PATH, "r", encoding="utf-8"))
    validator = Draft202012Validator(schema)

    files = _list_parsed_jsons()
    assert files, f"no files in {FILES_DIR} — ลองสร้างด้วย structure_builder.py หรือ run_all.py ก่อน"

    bad = []
    for p in files:
        data = json.load(open(p, "r", encoding="utf-8"))
        errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
        if errors:
            msgs = []
            for e in errors[:5]:
                path = "$" + "".join(
                    f"[{repr(seg)}]" if isinstance(seg, int) else f".{seg}"
                    for seg in e.path
                )
                msgs.append(f"{path}: {e.message}")
            more = f" (+{len(errors)-5} more)" if len(errors) > 5 else ""
            bad.append(f"{p}:\n- " + "\n- ".join(msgs) + more)

    assert not bad, "schema errors:\n\n" + "\n\n".join(bad)




