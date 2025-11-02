import json, subprocess, sys, glob
from pathlib import Path

THIS = Path(__file__).resolve()

def _find_repo_root(start: Path) -> Path:
    """เดินขึ้นไปหาจุดที่มีโฟลเดอร์ backend/ และ shared_data/"""
    p = start
    for _ in range(7):
        if (p / "backend").exists() and (p / "shared_data").exists():
            return p
        p = p.parent
    # fallback: 5 ระดับจากไฟล์เทส (โครงสร้างเดิม)
    return start.parents[5]

ROOT  = _find_repo_root(THIS)
ABACK = ROOT / "backend" / "app" / "services" / "A_backend"

SCORING = (ABACK / "normalize_scoring" / "scoring.py").resolve()
STRUCT  = (ABACK / "preprocess" / "structure_builder.py").resolve()

FILES_DIR = (ROOT / "shared_data" / "latest_parsed").resolve()
RAW_TMP   = (ROOT / "shared_data" / "examples" / "_raw_tmp.json").resolve()
UCB_TMP   = (ROOT / "shared_data" / "latest_ucb" / "_tmp.json").resolve()

# ป้องกันพลาด: ต้องมีไฟล์สองตัวนี้จริง
assert SCORING.exists(), f"SCORING not found at {SCORING}"
assert STRUCT.exists(),  f"STRUCT not found at {STRUCT}"

def _ensure_one_parsed() -> Path:
    """มีไฟล์ parsed ใช้ ถ้าไม่มีให้ build จาก RAW sample"""
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(glob.glob(str(FILES_DIR / "*.json")))
    if files:
        return Path(files[0]).resolve()

    assert RAW_TMP.exists(), f"RAW sample not found at {RAW_TMP}"
    out = FILES_DIR / "parsed_resume.json"
    cmd = [sys.executable, str(STRUCT), "--in", str(RAW_TMP), "--out", str(out)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    assert p.returncode == 0, f"structure_builder failed:\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
    assert out.exists(), f"expected parsed file at {out}"
    return out.resolve()

def test_ucb_payload_fields():
    src = _ensure_one_parsed()
    UCB_TMP.parent.mkdir(parents=True, exist_ok=True)

    # เรียก scoring.py ด้วย absolute path
    cmd = [sys.executable, str(SCORING), "--in", str(src), "--out", str(UCB_TMP), "--redact"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    assert p.returncode == 0, f"scoring failed:\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"

    d = json.load(open(UCB_TMP, encoding="utf-8"))
    for k in ["candidate_id","headline","skills","contacts","fit_score","reasons","gaps","evidence"]:
        assert k in d, f"missing field: {k}"

