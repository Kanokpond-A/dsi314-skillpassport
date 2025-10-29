# backend/app/services/A_backend/tests/test_schema_validation.py
import json, glob
from pathlib import Path
from jsonschema import Draft202012Validator

def _walk_up(path: Path):
    cur = path.resolve()
    yield cur
    for p in cur.parents:
        yield p

def _pick_files_dir(start: Path) -> Path:
    """
    เดินขึ้นทีละระดับ แล้วมองหา shared_data/latest_parsed
    เลือกอันที่มีไฟล์ .json อยู่จริงก่อน
    """
    candidates = []
    for root in _walk_up(start):
        d = root / "shared_data" / "latest_parsed"
        if d.exists():
            candidates.append(d)

    # เลือกไดเรกทอรีที่มี .json มากที่สุด (กันกรณีมี 2 แห่ง แต่อันหนึ่งว่าง)
    best = None
    best_count = -1
    for d in candidates:
        count = len(list(d.glob("*.json")))
        if count > best_count:
            best, best_count = d, count

    if best is None:
        raise FileNotFoundError("ไม่พบโฟลเดอร์ shared_data/latest_parsed ในเส้นทางใดๆ ที่ไล่ขึ้นมา")
    return best

THIS = Path(__file__).resolve()
ROOT = max(_walk_up(THIS), key=lambda p: p.parts.count(""))  # ไม่ได้ใช้ต่อ แต่เผื่ออยากพิมพ์ดู
FILES_DIR = _pick_files_dir(THIS)

# หา schema แบบยืดหยุ่นสองตำแหน่ง
SCHEMA_CANDIDATES = [
    # โครงสร้างยาว
    next((p for p in _walk_up(THIS) if (p / "backend/app/services/A_backend/schemas/parsed_resume.schema.json").exists()), None),
    # โครงสร้างสั้น
    next((p for p in _walk_up(THIS) if (p / "A_backend/schemas/parsed_resume.schema.json").exists()), None),
]
SCHEMA_PATH = None
for base in SCHEMA_CANDIDATES:
    if base:
        # base คือโฟลเดอร์รากที่พบสคีมา
        if (base / "backend/app/services/A_backend/schemas/parsed_resume.schema.json").exists():
            SCHEMA_PATH = base / "backend/app/services/A_backend/schemas/parsed_resume.schema.json"
            break
        if (base / "A_backend/schemas/parsed_resume.schema.json").exists():
            SCHEMA_PATH = base / "A_backend/schemas/parsed_resume.schema.json"
            break

if SCHEMA_PATH is None:
    raise FileNotFoundError(
        "ไม่พบ parsed_resume.schema.json ในตำแหน่งมาตรฐานทั้งสอง:\n"
        "- backend/app/services/A_backend/schemas/parsed_resume.schema.json\n"
        "- A_backend/schemas/parsed_resume.schema.json"
    )

def test_parsed_files_match_schema():
    # โหลด schema
    schema = json.load(open(SCHEMA_PATH, "r", encoding="utf-8"))
    validator = Draft202012Validator(schema)

    # รวมไฟล์ .json ทั้งหมดจากโฟลเดอร์ที่เลือกได้
    files = sorted(glob.glob(str(FILES_DIR / "*.json")))
    assert files, f"no files in {FILES_DIR} — ลองสร้างด้วย structure_builder.py ก่อน"

    # ตรวจทีละไฟล์
    bad = []
    for p in files:
        data = json.load(open(p, "r", encoding="utf-8"))
        errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
        if errors:
            msgs = []
            for e in errors[:5]:
                path = "$" + "".join(f"[{repr(seg)}]" if isinstance(seg, int) else f".{seg}" for seg in e.path)
                msgs.append(f"{path}: {e.message}")
            more = f" (+{len(errors)-5} more)" if len(errors) > 5 else ""
            bad.append(f"{p}:\n- " + "\n- ".join(msgs) + more)

    assert not bad, "schema errors:\n\n" + "\n\n".join(bad)



