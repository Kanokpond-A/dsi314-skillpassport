# backend/app/services/A_backend/tools/schema_adapter.py
import json, sys
from pathlib import Path
from datetime import datetime

def _walk_up(path: Path):
    cur = path.resolve()
    yield cur
    for p in cur.parents:
        yield p

def _find_repo_root(start: Path) -> Path:
    for root in _walk_up(start):
        if (root / "shared_data").exists():
            return root
    return start.resolve()

def _find_schema(root: Path) -> Path:
    cands = [
        root / "backend/app/services/A_backend/schemas/parsed_resume.schema.json",
        root / "A_backend/schemas/parsed_resume.schema.json",
    ]
    for p in cands:
        if p.exists():
            return p
    raise SystemExit("parsed_resume.schema.json not found in expected locations")

def _clean(d):
    return {k: v for k, v in d.items() if v not in (None, "", [], {})}

ALIASES_TOP = {
    "name": ["name", "full_name", "headline"],
    "source_file": ["source_file", "resume_id", "file", "path", "filename"],
}

ALIASES_CONTACT = {
    "email": ["email", ("contacts","email")],
    "phone": ["phone", ("contacts","phone")],
    "linkedin_url": ["linkedin_url", ("contacts","linkedin_url"), "linkedin"],
    "github_url": ["github_url", ("contacts","github_url"), "github"],
    "portfolio_url": ["portfolio_url", ("contacts","portfolio_url"), "website", "site"],
    "location": ["location", ("contacts","location"), "address"],
}

ALIASES_EXP = {
    "employer": ["company","employer","org"],
    "title": ["title","position","role"],
    "start_date": ["start_date","start","from"],
    "end_date": ["end_date","end","to"],
    "bullets": ["bullets","highlights","summary","desc","descriptions"],
    "duration_months": [], # computed if possible
}

ALIASES_EDU = {
    "school": ["school","university","institute","organization"],
    "degree": ["degree","qualification"],
    "field": ["field","major","program"],
    "start_date": ["start_date","start","from"],
    "end_date": ["end_date","end","to"],
    "gpa": ["gpa"],
    "bullets": ["bullets","highlights","summary","courses"],
}

def _fetch(src, key, aliases):
    for a in aliases.get(key, []):
        if isinstance(a, tuple):  # nested path e.g. ("contacts","email")
            cur = src
            ok = True
            for seg in a:
                if isinstance(cur, dict) and seg in cur:
                    cur = cur[seg]
                else:
                    ok = False
                    break
            if ok and cur not in (None, "", [], {}):
                return cur
        else:
            if a in src and src[a] not in (None, "", [], {}):
                return src[a]
    return None

def _norm_date(s):
    if not s:
        return None
    s = str(s)
    # take YYYY-MM or YYYY
    try:
        return datetime.strptime(s[:7], "%Y-%m").strftime("%Y-%m")
    except Exception:
        try:
            return datetime.strptime(s[:4], "%Y").strftime("%Y")
        except Exception:
            return s  # leave as-is

def adapt(inp_path: Path, out_path: Path):
    here = Path(__file__).resolve()
    ROOT = _find_repo_root(here)
    SCHEMA_PATH = _find_schema(ROOT)

    schema = json.load(open(SCHEMA_PATH, "r", encoding="utf-8"))
    props = schema.get("properties", {})
    required_top = set(schema.get("required", []))

    data = json.load(open(inp_path, "r", encoding="utf-8"))

    out = {}

    # -------- Top level: name / source_file (and any other declared in schema) --------
    for k in props.keys():
        if k in ("contacts","experiences","education","skills"):
            continue  # handled below
        if k in ALIASES_TOP:
            out[k] = _fetch(data, k, ALIASES_TOP)
        elif k in data:
            out[k] = data[k]
        # fill later if required and still missing

    # -------- contacts --------
    if "contacts" in props:
        contact_props = props["contacts"].get("properties", {})
        contact_req = set(props["contacts"].get("required", []))
        contacts = {}
        for ck in contact_props.keys():
            if ck in ALIASES_CONTACT:
                contacts[ck] = _fetch(data, ck, ALIASES_CONTACT)
            elif isinstance(data.get("contacts"), dict) and ck in data["contacts"]:
                contacts[ck] = data["contacts"][ck]
        # Fill required empties minimally
        for ck in contact_req:
            if not contacts.get(ck):
                contacts[ck] = "Unknown"
        out["contacts"] = _clean(contacts)

    # -------- experiences (array of objects) --------
    if "experiences" in props:
        item_schema = props["experiences"].get("items", {}).get("properties", {})
        raw = data.get("experiences") or data.get("experience") or []
        exps = []
        for it in raw:
            row = {}
            for ek in item_schema.keys():
                if ek == "duration_months":
                    # compute from dates if possible
                    s = _fetch(it, "start_date", ALIASES_EXP)
                    e = _fetch(it, "end_date", ALIASES_EXP)
                    dur = None
                    try:
                        if s and e and len(s)>=4 and len(e)>=4:
                            sY = int(s[:4]); eY = int(e[:4])
                            sM = int(s[5:7]) if len(s)>=7 and s[4] in "-/" else 1
                            eM = int(e[5:7]) if len(e)>=7 and e[4] in "-/" else 1
                            dur = max(0, (eY - sY) * 12 + (eM - sM))
                    except Exception:
                        dur = None
                    row[ek] = dur
                elif ek == "bullets":
                    b = _fetch(it, "bullets", ALIASES_EXP)
                    if isinstance(b, list): row[ek] = b
                    elif b: row[ek] = [str(b)]
                    else: row[ek] = []
                elif ek in ("start_date","end_date"):
                    row[ek] = _norm_date(_fetch(it, ek, ALIASES_EXP))
                else:
                    # employer/title/...
                    row[ek] = _fetch(it, ek, ALIASES_EXP) or it.get(ek)
            exps.append(_clean(row))
        out["experiences"] = [e for e in exps if e]

    # -------- education (array of objects) --------
    if "education" in props:
        item_schema = props["education"].get("items", {}).get("properties", {})
        raw = data.get("education") or data.get("educations") or data.get("education_history") or []
        edus = []
        for it in raw:
            row = {}
            for ek in item_schema.keys():
                if ek in ("start_date","end_date"):
                    row[ek] = _norm_date(_fetch(it, ek, ALIASES_EDU))
                elif ek == "bullets":
                    b = _fetch(it, "bullets", ALIASES_EDU)
                    if isinstance(b, list): row[ek] = b
                    elif b: row[ek] = [str(b)]
                    else: row[ek] = []
                else:
                    row[ek] = _fetch(it, ek, ALIASES_EDU) or it.get(ek)
            edus.append(_clean(row))
        out["education"] = [e for e in edus if e]

    # -------- skills (array of strings) --------
    if "skills" in props:
        skills = None
        for k in ("skills","skills_normalized","skills_raw"):
            v = data.get(k)
            if isinstance(v, list) and v:
                skills = sorted({str(s).strip() for s in v if str(s).strip()})
                break
        out["skills"] = skills or []

    # -------- fill any missing required top-level with safe defaults --------
    for k in required_top:
        if k not in out or out[k] in (None, "", [], {}):
            if k == "skills":
                out[k] = []
            elif k in ("experiences","education"):
                out[k] = []
            elif k == "contacts":
                out[k] = {"location": "Unknown"}
            else:
                out[k] = "Unknown"

    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[OK] adapted to schema → {out_path} (schema: {SCHEMA_PATH})")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: schema_adapter.py <in.json> <out.json>")
        raise SystemExit(2)
    adapt(Path(sys.argv[1]), Path(sys.argv[2]))

