import json, subprocess, sys, glob
from pathlib import Path

THIS = Path(__file__).resolve()

def _find_repo_root(start: Path) -> Path:
    p = start
    for _ in range(7):
        if (p / "backend").exists() and (p / "shared_data").exists():
            return p
        p = p.parent
    return start.parents[5]

ROOT   = _find_repo_root(THIS)
ABACK  = ROOT / "backend" / "app" / "services" / "A_backend"
STRUCT = (ABACK / "preprocess" / "structure_builder.py").resolve()

PARSED_DIR = (ROOT / "shared_data" / "latest_parsed").resolve()
RAW_TMP    = (ROOT / "shared_data" / "examples" / "_raw_tmp.json").resolve()

REQUIRED_KEYS = [
    "name", "last_job_title", "experience_years",
    "expected_salary", "availability", "location",
]

def _ensure_parsed_with_extras() -> tuple[Path, Path]:
    """
    คืน (parsed_path, extras_path)
    - ถ้ามี parsed เดิมแต่ไม่มี extras → จะสร้าง parsed ใหม่ชื่อ `parsed_for_extras.json`
      จาก RAW sample เพื่อให้แน่ใจว่ามี `_extras_*.json`
    """
    PARSED_DIR.mkdir(parents=True, exist_ok=True)

    # 1) ลองใช้ไฟล์ parsed เดิมก่อน
    existing = sorted(PARSED_DIR.glob("*.json"))
    if existing:
        parsed = existing[0].resolve()
        extras = (parsed.parent / f"_extras_{parsed.stem}.json").resolve()
        if extras.exists():
            return parsed, extras

    # 2) ไม่มี extras (หรือไม่มี parsed เลย) → สร้างใหม่จาก RAW sample
    assert RAW_TMP.exists(), f"RAW sample not found at {RAW_TMP}"
    parsed = (PARSED_DIR / "parsed_for_extras.json").resolve()
    cmd = [sys.executable, str(STRUCT), "--in", str(RAW_TMP), "--out", str(parsed)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    assert p.returncode == 0, f"struct_builder failed:\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"

    extras = (parsed.parent / f"_extras_{parsed.stem}.json").resolve()
    assert extras.exists(), f"extras not generated at {extras}"
    return parsed, extras

def test_extras_generated_and_has_keys():
    parsed, extras_path = _ensure_parsed_with_extras()

    data = json.load(open(extras_path, encoding="utf-8"))

    # ต้องมีคีย์หลักครบทุกอัน (ค่าอาจเป็น None/ว่างได้)
    for k in REQUIRED_KEYS:
        assert k in data, f"missing extras key: {k}"

    # ชนิดข้อมูล (ยอมรับ None)
    assert (data["name"] is None) or isinstance(data["name"], str)
    assert (data["last_job_title"] is None) or isinstance(data["last_job_title"], str)
    assert (data["experience_years"] is None) or isinstance(data["experience_years"], (int, float))
    assert (data["expected_salary"] is None) or isinstance(data["expected_salary"], str)
    assert (data["availability"] is None) or isinstance(data["availability"], str)
    assert (data["location"] is None) or isinstance(data["location"], str)
