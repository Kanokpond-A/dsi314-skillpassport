import csv, re
def load_skill_dict(path="A_backend/normalize_scoring/skills.csv"):
    d={}
    for row in csv.DictReader(open(path,encoding="utf-8")):
        canon=row["canonical"].strip()
        aliases=[canon]+[a.strip() for a in row["alias"].split("|") if a.strip()]
        for a in aliases:
            d[a.lower()]=canon
    return d

def normalize_skills(raw_skills, dict_path=None):
    sd = load_skill_dict(dict_path or "A_backend/normalize_scoring/skills.csv")
    out=[]
    seen=set()
    for s in raw_skills:
        k=s.strip().lower()
        best=None
        # ตรงตัวก่อน
        if k in sd: best=sd[k]
        else:
            # จับแบบ contains ง่ายๆ (พอใช้ก่อน)
            for alias, canon in sd.items():
                if alias in k:
                    best=canon; break
        if not best: best=s.strip()
        if best not in seen:
            seen.add(best); out.append(best)
    return out
