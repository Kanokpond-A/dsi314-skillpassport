# frontend/streamlit_app.py
import json, glob, io, csv, math
from collections import Counter, defaultdict
from pathlib import Path
import streamlit as st
import pandas as pd

st.set_page_config(page_title="UCB Mini Dashboard", layout="wide")

UCB_DIR = Path("shared_data/latest_ucb")
PARSED_DIR = Path("shared_data/latest_parsed")
LOG_FILE = Path("shared_data/pilot_log.csv")  # ถ้ามีจะแสดง Metrics ให้ด้วย
PII_KEYS = {"email","phone","location","address","linkedin","github","line","facebook"}

# ---------- Helpers ----------
def redact_contacts(c: dict):
    """แทนค่าคอนแทคที่เป็น PII ด้วย ••• เสมอ"""
    if not isinstance(c, dict): return {}
    return {k: ("•••" if isinstance(v, str) and k.lower() in PII_KEYS and v else v) for k,v in c.items()}

@st.cache_data(show_spinner=False)
def load_ucb():
    rows, all_skills = [], set()
    for p in sorted(UCB_DIR.glob("*.json")):
        try:
            d = json.load(open(p, encoding="utf-8"))
            norm_sk = list(d.get("skills",{}).get("normalized", []))
            gaps = list(d.get("gaps", []))
            rows.append({
                "file": p.name,
                "headline": d.get("headline",""),
                "fit_score": int(d.get("fit_score", 0)),
                "skills": norm_sk,
                "gaps": gaps,
                "reasons": d.get("reasons", []),
                "contacts": redact_contacts(d.get("contacts", {})),
                "raw": d,
            })
            all_skills.update(norm_sk)
        except Exception as e:
            rows.append({"file": p.name, "headline":"<error>", "fit_score":0,
                         "skills":[], "gaps":[f"error:{e}"], "reasons":[], "contacts":{}, "raw": {}})
    return rows, sorted(all_skills)

def force_refresh():
    # ล้าง cache ของ load_ucb แล้ว rerun หน้า
    load_ucb.clear()
    try:
        st.rerun()                 # Streamlit ≥ 1.30
    except AttributeError:
        st.experimental_rerun()    # เผื่อเวอร์ชันเก่า

def stringify_list(lst, sep=", "):
    return sep.join(lst) if lst else "—"

def score_bucket(x, step=10):
    return f"{(x//step)*step:02d}-{((x//step)*step+step-1):02d}"

def safe_unlink(p: Path) -> bool:
    try:
        if p.exists(): p.unlink(); return True
    except Exception:
        pass
    return False

# ---------- Header ----------
st.title("UCB Mini Dashboard")
top_left, top_mid, top_right = st.columns([3,2,1])
with top_left:
    st.caption("ค้นหา/กรอง/ดูเหตุผล และเปรียบเทียบผู้สมัครแบบมืออาชีพ • ข้อมูลติดต่อถูกซ่อนโดยอัตโนมัติ")
with top_mid:
    st.info("⚠️ เพื่อการทดสอบภายในเท่านั้น (PII ถูกปิดทับแล้ว)")
with top_right:
    if st.button("↻ Refresh cache", use_container_width=True):
        force_refresh()

rows, ALL_SKILLS = load_ucb()

# ---------- Control Panel ----------
st.subheader("Filters")
c1, c2, c3, c4 = st.columns([2,1.2,1.2,1.2])
with c1:
    q = st.text_input("ค้นหา (ไฟล์ / headline / skills / gaps)", "")
with c2:
    min_s, max_s = st.slider("ช่วงคะแนน", 0, 100, (0,100))
with c3:
    must_have = st.multiselect("ต้องมีสกิลเหล่านี้", ALL_SKILLS, placeholder="เลือกสกิลจำเป็น")
with c4:
    sort_by = st.selectbox("เรียงตาม", ["fit_score","file","headline"])
asc = st.toggle("เรียงจากน้อยไปมาก", value=False)

def row_text(r):
    return " ".join([
        r["file"], r["headline"],
        " ".join(r["skills"]),
        " ".join(r["gaps"]),
        " ".join(r["reasons"]),
    ]).lower()

def match(r):
    if not (min_s <= r["fit_score"] <= max_s): return False
    if q and (q.lower() not in row_text(r)): return False
    if must_have and not set(must_have).issubset(set(r["skills"])): return False
    return True

filtered = [r for r in rows if match(r)]
filtered = sorted(filtered, key=lambda r: r[sort_by], reverse=not asc)

# ---------- KPIs ----------
st.subheader("Overview")
k1,k2,k3,k4 = st.columns(4)
count = len(filtered)
avg = int(sum(r["fit_score"] for r in filtered)/count) if count else 0
top_sk = Counter(s for r in filtered for s in r["skills"]).most_common(3)
top_gap = Counter(g for r in filtered for g in r["gaps"]).most_common(3)
k1.metric("จำนวนผู้สมัคร (ที่กรอง)", count)
k2.metric("คะแนนเฉลี่ย", avg)
k3.metric("Top skills", stringify_list([f"{k} ({v})" for k,v in top_sk]))
k4.metric("Top gaps", stringify_list([f"{k} ({v})" for k,v in top_gap]))

# ---------- Charts (ง่ายๆ ช่วย HR มองภาพรวม) ----------
st.markdown("**Distribution**")
g1, g2 = st.columns(2)

with g1:
    # histogram 10 คะแนนต่อถัง
    buckets = Counter(score_bucket(r["fit_score"]) for r in filtered)
    labels = sorted(buckets.keys(), key=lambda s: int(s.split("-")[0]))
    df_hist = pd.DataFrame({
        "bucket": labels,
        "count": [buckets[l] for l in labels]
    })
    st.bar_chart(df_hist, x="bucket", y="count", use_container_width=True)

with g2:
    # Top 10 gaps
    gap_counts = Counter(g for r in filtered for g in r["gaps"])
    top10_gaps = gap_counts.most_common(10)
    df_gaps = pd.DataFrame({
        "gap":   [g for g, _ in top10_gaps],
        "count": [c for _, c in top10_gaps]
    })
    st.bar_chart(df_gaps, x="gap", y="count", use_container_width=True)


# ---------- Table ----------
st.subheader("Candidates")
st.write(f"พบผู้สมัคร: **{len(filtered)}** ราย")
table_rows = []
for r in filtered:
    table_rows.append({
        "file": r["file"],
        "fit_score": r["fit_score"],
        "headline": r["headline"],
        "skills": stringify_list(r["skills"]),
        "gaps": stringify_list(r["gaps"]),
    })
st.dataframe(table_rows, use_container_width=True)

# Export filtered CSV
buf = io.StringIO()
w = csv.writer(buf)
w.writerow(["file","fit_score","headline","skills","gaps"])
for r in filtered:
    w.writerow([r["file"], r["fit_score"], r["headline"], stringify_list(r["skills"]), stringify_list(r["gaps"])])
st.download_button("⬇️ Export filtered to CSV", buf.getvalue().encode("utf-8"), "ucb_filtered.csv", "text/csv")

# ---------- Compare two ----------
st.subheader("Compare two candidates")
left, right = st.columns(2)
options = [r["file"] for r in filtered]
c1 = left.selectbox("เลือกคนที่ 1", options, index=0 if options else None, key="pick1")
c2 = right.selectbox("เลือกคนที่ 2", options, index=1 if len(options)>1 else (0 if options else None), key="pick2")

def render(panel, file):
    if not file:
        panel.info("ยังไม่ได้เลือกไฟล์"); return
    r = next((x for x in filtered if x["file"]==file), None)
    if not r:
        panel.warning("ไม่พบไฟล์ในผลกรอง"); return
    d = r["raw"]

    panel.metric("Fit Score", r["fit_score"])
    panel.write(f"**Headline:** {r['headline']}")
    with panel.expander("Contacts (redacted)"):
        panel.json(r.get("contacts", {}))
    with panel.expander("Skills (normalized)"):
        panel.write(stringify_list(d.get("skills",{}).get("normalized", [])))
    with panel.expander("Reasons"):
        rs = d.get("reasons", [])
        panel.write("\n- " + "\n- ".join(rs) if rs else "—")
    with panel.expander("Gaps"):
        panel.write(stringify_list(d.get("gaps", [])))
    with panel.expander("Raw JSON"):
        panel.json(d)

    # Delete actions
    with panel.expander("🛑 Danger zone"):
        base = Path(file).stem
        p_ucb = UCB_DIR / f"{base}.json"
        p_parsed = PARSED_DIR / f"{base}.json"
        if panel.button(f"🗑️ ลบไฟล์ของ {file}", key=f"del-{file}"):
            ok1 = safe_unlink(p_ucb); ok2 = safe_unlink(p_parsed)
            panel.success(f"ลบแล้ว: UCB={ok1}, Parsed={ok2}. กด ↻ Refresh cache เพื่ออัปเดตตาราง.")

render(left, c1)
render(right, c2)

# ---------- Pilot Metrics (optional, if log exists) ----------
st.subheader("Pilot metrics (ถ้ามี log)")
if LOG_FILE.exists():
    import csv as _csv
    before, after, thumbs = [], [], Counter()
    with open(LOG_FILE, encoding="utf-8") as f:
        r = _csv.DictReader(f)
        for row in r:
            (before if row.get("mode")=="before" else after).append(float(row.get("seconds",0)))
            if row.get("thumb") in ("up","down"): thumbs[row["thumb"]] += 1
    if before and after:
        mean_b = sum(before)/len(before)
        mean_a = sum(after)/len(after)
        red = (mean_b-mean_a)/mean_b*100 if mean_b else 0
        m1,m2,m3 = st.columns(3)
        m1.metric("เฉลี่ยก่อนใช้ (วินาที)", f"{mean_b:.1f}")
        m2.metric("เฉลี่ยหลังใช้ (วินาที)", f"{mean_a:.1f}")
        m3.metric("เวลาลดลง", f"{red:.1f}%")
    st.write(f"Thumbs: 👍 {thumbs.get('up',0)}  |  👎 {thumbs.get('down',0)}")
else:
    st.info("ยังไม่มีไฟล์ log (`shared_data/pilot_log.csv`)")

# ---------- Footer ----------
st.caption("Tip: แก้ไฟล์แล้วใช้ปุ่ม **↻ Refresh cache** หรือกด R เพื่อ rerun แอป")
