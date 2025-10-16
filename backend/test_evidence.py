# A_backend/tests/test_evidence.py
import json, glob, subprocess, sys, pathlib

def test_scoring_generates_evidence():
    # เลือกไฟล์ parsed ใบแรก
    files = glob.glob("shared_data/latest_parsed/*.json")
    assert files, "no parsed resumes found"
    out = "shared_data/latest_ucb/_tmp_evidence.json"
    pathlib.Path("shared_data/latest_ucb").mkdir(parents=True, exist_ok=True)

    # รัน scoring (เปิด redact หรือไม่ก็ได้)
    subprocess.run([sys.executable, "A_backend/normalize_scoring/scoring.py",
                   "--in", files[0], "--out", out, "--redact"], check=True)

    d = json.load(open(out, encoding="utf-8"))
    ev = d.get("evidence", {})
    # เงื่อนไขขั้นต่ำ: มี dict กลับมา และถ้ามีสกิล normalized อย่างน้อย 1 ตัว ต้องมี evidence อย่างน้อย 1 path
    assert isinstance(ev, dict)
    norm = d.get("skills", {}).get("normalized", [])
    if norm:
        assert any(len(paths) > 0 for paths in ev.values()), "expected at least one evidence path"
