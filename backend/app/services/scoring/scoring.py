# backend/app/services/A_backend/normalize_scoring/scoring.py
import argparse, json, csv, re, sys
from pathlib import Path
from typing import Dict, List, Tuple, Set, Iterable, Optional

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE.parent / "data"         # backend/app/services/A_backend/data
SKILLS_MASTER = DATA_DIR / "skills_master.csv"
SKILLS_FALLBACK = DATA_DIR / "skills.csv"  # ใช้ถ้ามี (ไม่บังคับ)

# ----------------------- Utils -----------------------

SEP = re.compile(r"[,\u2022•·/|;]+|\n+")
WS = re.compile(r"\s+")

def _norm_token(s: str) -> str:
    return WS.sub(" ", (s or "").strip()).strip().lower()

def _sentences(text: str) -> List[str]:
    # ตัดเป็นประโยคแบบคร่าว ๆ
    s = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    return [WS.sub(" ", x).strip() for x in s if x and x.strip()]

# ----------------------- Alias Map -----------------------

def load_alias_map() -> Dict[str, Tuple[str, str]]:
    """
    อ่าน skills_master.csv เป็น map: alias(lower) -> (canonical, industry)
    รองรับ comment (#...) และบรรทัดว่าง
    """
    path = SKILLS_MASTER if SKILLS_MASTER.exists() else SKILLS_FALLBACK
    if not path or not path.exists():
        print(f"[WARN] skills map not found at {SKILLS_MASTER} / {SKILLS_FALLBACK}; mining/normalize will be minimal.")
        return {}
    mp: Dict[str, Tuple[str, str]] = {}
    with open(path, "r", encoding="utf-8") as f:
        rdr = csv.reader(f)
        for row in rdr:
            if not row or len(row) < 2:
                continue
            alias = (row[0] or "").strip()
            if not alias or alias.startswith("#"):
                continue
            canonical = (row[1] or "").strip() or alias
            industry = (row[2] or "").strip() if len(row) >= 3 else ""
            mp[_norm_token(alias)] = (canonical, industry)
    return mp

# ----------------------- Canonicalization -----------------------

def normalize_tokens(tokens: Iterable[str], alias_map: Dict[str, Tuple[str, str]]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for t in tokens:
        if not t: 
            continue
        # แตกชิ้นย่อยเพิ่ม (รองรับเคสที่ skills เป็นก้อนข้อความยาว)
        parts = [x.strip() for x in SEP.split(str(t)) if x and x.strip()]
        for p in parts:
            key = _norm_token(p)
            if not key: 
                continue
            if key in alias_map:
                canon = alias_map[key][0]
            else:
                # ถ้าไม่อยู่ใน alias_map ให้เดาว่าชื่อเดิมนี่แหละ (แต่เก็บรูปเดิม ไม่บังคับ lower/title)
                canon = p.strip()
            if canon not in seen:
                seen.add(canon); out.append(canon)
    return out

# ----------------------- Mining from text -----------------------

def mine_skills_from_text(text: str, alias_map: Dict[str, Tuple[str, str]]) -> Tuple[List[str], Dict[str, List[str]]]:
    """
    คืน (skills_mined_canonical, evidence_map)
    evidence_map: canonical -> [ประโยค/บรรทัดที่พบ] (อย่างมาก 3 ชิ้น/สกิล)
    """
    if not text or not alias_map:
        return [], {}

    # สร้าง regex ต่อ alias ทั้งหมดแบบ word-ish
    # ใช้ \b ไม่พอสำหรับเครื่องหมาย/ตัวเลขบางเคส → ใช้ lookaround คร่าว ๆ
    patt = r"(?<![A-Za-z0-9_])({})(?![A-Za-z0-9_])"
    # แยกเป็นชุด ๆ เพื่อหลีกเลี่ยง pattern ใหญ่เกินไป
    aliases = list(alias_map.keys())
    mined: Set[str] = set()
    evidence: Dict[str, List[str]] = {}
    sents = _sentences(text)

    for sent in sents:
        low = sent.lower()
        for a in aliases:
            # เร็ว ๆ: เช็ค substring ก่อน แล้วค่อย regex
            if a in low:
                if re.search(patt.format(re.escape(a)), low):
                    canon = alias_map[a][0]
                    if canon not in evidence:
                        evidence[canon] = []
                    if len(evidence[canon]) < 3:
                        evidence[canon].append(sent.strip())
                    mined.add(canon)
    return list(sorted(mined)), evidence

# ----------------------- Contacts redaction -----------------------

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(\+?\d[\d\- ()]{7,}\d)")

def maybe_redact_contacts(contacts: dict, do: bool) -> dict:
    if not do:
        return contacts or {}
    c = dict(contacts or {})
    if "email" in c and c["email"]:
        c["email"] = EMAIL_RE.sub("***@***", str(c["email"]))
    if "phone" in c and c["phone"]:
        p = str(c["phone"])
        c["phone"] = re.sub(r"\d", "X", p[:-2]) + p[-2:] if len(p) > 2 else "XX"
    return c

# ----------------------- JD Profile -----------------------

def load_jd_profile(jd_path: Optional[Path]) -> dict:
    """
    โครงสร้างที่รองรับ:
    {
      title: "...",
      required: [ "Python", "SQL", ... ],
      nice_to_have: [ "Tableau", ... ],
      weights: { required: 60, nice: 40 }
    }
    """
    if not jd_path:
        return {}
    try:
        import yaml  # optional
    except Exception:
        print("[WARN] PyYAML not installed; ignore JD file.")
        return {}
    try:
        d = yaml.safe_load(open(jd_path, "r", encoding="utf-8"))
        return d or {}
    except Exception as e:
        print(f"[WARN] cannot read JD: {jd_path}: {e}")
        return {}

def score_against_jd(canon_all: List[str], jd: dict) -> Tuple[int, dict, dict, dict]:
    """
    คืน (fit_score, reasons, gaps, evidence_dummy)
    - reasons: {'required_hit': [...], 'nice_hit': [...]}  (canonical)
    - gaps:    {'required_miss': [...], 'nice_miss': [...]}
    - evidence_dummy: วางที่นี่เพื่อให้ schema มี field 'evidence' (เราแสดง evidence จาก mining แยกอีกที)
    """
    if not jd:
        return 0, {}, {}, {}

    required = set(jd.get("required") or [])
    nice = set(jd.get("nice_to_have") or [])
    weights = jd.get("weights") or {"required": 60, "nice": 40}

    have = set(canon_all or [])

    req_hit = sorted(required & have)
    req_miss = sorted(required - have)
    nice_hit = sorted(nice & have)
    nice_miss = sorted(nice - have)

    req_score = (len(req_hit) / len(required) * weights.get("required", 60)) if required else 0
    nice_score = (len(nice_hit) / len(nice) * weights.get("nice", 40)) if nice else 0
    fit = int(round(req_score + nice_score))

    reasons = {"required_hit": req_hit, "nice_hit": nice_hit}
    gaps = {"required_miss": req_miss, "nice_miss": nice_miss}

    return fit, reasons, gaps, {}

# ----------------------- Build text from parsed -----------------------

def _gather_text(parsed: dict) -> str:
    parts: List[str] = []
    parts.append(parsed.get("name") or "")
    # contacts lines
    c = parsed.get("contacts") or {}
    parts += [c.get("email") or "", c.get("phone") or "", c.get("location") or ""]

    # skills raw (เผื่อ parser ใส่เป็นก้อนข้อความ)
    sk = parsed.get("skills") or []
    if isinstance(sk, list):
        parts += [str(x) for x in sk]
    else:
        parts.append(str(sk))

    # experiences bullets
    for exp in parsed.get("experiences") or []:
        parts.append(exp.get("company") or "")
        parts.append(exp.get("role") or "")
        for b in exp.get("bullets") or []:
            parts.append(b)

    # education
    for ed in parsed.get("education") or []:
        parts += [ed.get("institution") or "", ed.get("degree") or "", ed.get("major") or ""]

    return "\n".join([p for p in parts if p])

# ----------------------- Main -----------------------

def main():
    ap = argparse.ArgumentParser(description="parsed_resume.json -> UCB json with fit_score")
    ap.add_argument("--in",  dest="inp", required=True, help="path to parsed_resume.json")
    ap.add_argument("--out", dest="out", required=True, help="output UCB json")
    ap.add_argument("--jd",  dest="jd", default=None, help="JD profile YAML (optional)")
    ap.add_argument("--redact", action="store_true", help="redact PII in contacts")
    args = ap.parse_args()

    src_path = Path(args.inp)
    out_path = Path(args.out)

    try:
        parsed = json.load(open(src_path, "r", encoding="utf-8"))
    except Exception as e:
        print(f"[ERR] cannot read parsed json: {src_path}: {e}")
        raise SystemExit(2)

    # 1) โหลด alias map
    alias_map = load_alias_map()

    # 2) สร้างชุด skills จาก parsed["skills"] (normalize ให้เป็น canonical เสมอ)
    parsed_skills = parsed.get("skills") or []
    parsed_canon = normalize_tokens(parsed_skills if isinstance(parsed_skills, list) else [parsed_skills], alias_map)

    # 3) ขุดจาก text เพิ่ม (แล้วแปลง canonical)
    full_text = _gather_text(parsed)
    mined_raw, mined_ev = mine_skills_from_text(full_text, alias_map)
    mined_canon = normalize_tokens(mined_raw, alias_map)  # เผื่อ alias แปลก

    # 4) รวมชุดทั้งหมด
    canon_all = sorted(set(parsed_canon) | set(mined_canon))

    # 5) โหลด JD และคำนวณคะแนน
    jd = load_jd_profile(Path(args.jd)) if args.jd else {}
    fit_score, reasons, gaps, _ = score_against_jd(canon_all, jd)

    # 6) payload
    ucb = {
        "candidate_id": parsed.get("source_file") or src_path.stem,
        "headline": parsed.get("name") or "",
        "skills": {
            "input": parsed_canon,       # จาก parsed
            "mined": mined_canon,        # จาก text mining
            "all": canon_all,            # union
        },
        "contacts": maybe_redact_contacts(parsed.get("contacts"), do=args.redact),
        "fit_score": fit_score,
        "reasons": reasons,
        "gaps": gaps,
        # รวม evidence เฉพาะจาก mining (map canonical -> ประโยคที่พบ)
        "evidence": mined_ev,
        "jd_title": (jd.get("title") if jd else None) or "",
        "required_hit": reasons.get("required_hit", []),
        "nice_hit": reasons.get("nice_hit", []),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(ucb, f, ensure_ascii=False, indent=2)
    print(f"[OK] wrote UCB -> {out_path} (fit_score={fit_score})")


if __name__ == "__main__":
    main()








