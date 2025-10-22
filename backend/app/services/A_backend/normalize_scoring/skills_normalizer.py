# backend/app/services/A_backend/normalize_scoring/skills_normalizer.py
from __future__ import annotations
from pathlib import Path
import csv, re

HERE = Path(__file__).resolve().parent
SKILLS_CSV = HERE / "skills.csv"

def _load_vocab():
    """
    โหลดพจนานุกรมสกิลจาก CSV:
    columns ที่รองรับ:
      - canonical (ชื่อมาตรฐาน)
      - synonyms (คำพ้องความหมาย คั่นด้วย | )
      - skill (fallback ถ้าไม่มี canonical)
    """
    vocab = []
    if not SKILLS_CSV.exists():
        raise FileNotFoundError(f"skills.csv not found at: {SKILLS_CSV}")

    with open(SKILLS_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            canonical = (row.get("canonical") or row.get("skill") or "").strip()
            if not canonical:
                continue
            syns = (row.get("synonyms") or "").split("|")
            terms = {canonical.lower()} | {s.strip().lower() for s in syns if s.strip()}
            vocab.append((canonical, terms))
    return vocab

_VOCAB = _load_vocab()

_SPLIT = re.compile(r"[,/|;•\u2022\-\n\r\t]+")

def normalize_skills(raw) -> list[str]:
    """
    รับ list ของสตริง/รายการสกิลแบบดิบ แล้วแม็ปเป็นชื่อ canonical
    """
    # รองรับทั้ง list หรือ string เดี่ยว
    if isinstance(raw, (list, tuple)):
        text = " ".join(map(str, raw))
    else:
        text = str(raw or "")

    candidates = [t.strip() for t in _SPLIT.split(text) if t.strip()]
    out = set()
    for t in candidates:
        low = t.lower()
        for canonical, terms in _VOCAB:
            if low in terms:
                out.add(canonical)
                break
    return sorted(out)

