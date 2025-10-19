from pathlib import Path
import glob, json, re

PII_PATTERNS = [
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),  # email
    re.compile(r"\+?\d[\d\-\s()]{7,}\d"),                            # phone
]

def test_ucb_contacts_redacted():
    # ตรวจที่โฟลเดอร์ redacted_ucb ถ้ามี; ถ้าไม่มีให้ตรวจ latest_ucb (ที่คุณใส่ --redact)
    cand_dirs = ["shared_data/redacted_ucb", "shared_data/latest_ucb"]
    target = next((d for d in cand_dirs if Path(d).exists()), None)
    assert target, "no output directory to check (expected shared_data/redacted_ucb or latest_ucb)"
    files = sorted(glob.glob(f"{target}/*.json"))
    assert files, f"no json files in {target}"

    for p in files:
        d = json.load(open(p, encoding="utf-8"))
        # contacts ต้องไม่มี email/phone ที่เป็นข้อความจริง
        c = d.get("contacts", {})
        for v in c.values():
            if not isinstance(v, str): continue
            assert "•" in v or v == "" or v.lower() in {"n/a","na"}, f"PII leak in contacts of {p}"
        # กันกรณี PII หลุดไปช่องอื่น ๆ แบบง่าย ๆ
        raw_text = json.dumps(d, ensure_ascii=False)
        for pat in PII_PATTERNS:
            assert not pat.search(raw_text), f"PII-like pattern found in {p}"
