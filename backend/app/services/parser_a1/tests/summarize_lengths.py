import json, glob, os
rows=[]
for p in glob.glob("shared_data/latest_parsed/*.json"):
    d=json.load(open(p,encoding="utf-8"))
    rows.append((os.path.basename(p), len(json.dumps(d,ensure_ascii=False))))
rows.sort(key=lambda x:x[1])
for name, ln in rows[:10]:
    print(f"{name:20s} len={ln}")