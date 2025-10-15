import json, glob, os
import streamlit as st

st.set_page_config(page_title="UCB Mini Dashboard", layout="wide")

@st.cache_data
def load_ucb():
    rows = []
    for p in sorted(glob.glob("shared_data/latest_ucb/*.json")):
        try:
            d = json.load(open(p, encoding="utf-8"))
            rows.append({
                "file": os.path.basename(p),
                "headline": d.get("headline",""),
                "fit_score": d.get("fit_score", 0),
                "skills": ", ".join(d.get("skills",{}).get("normalized", [])),
                "gaps": ", ".join(d.get("gaps", [])),
                "reasons": "; ".join(d.get("reasons", [])),
                "raw": d,
            })
        except Exception as e:
            rows.append({"file": os.path.basename(p), "headline":"<error>", "fit_score":0, "skills":"", "gaps": str(e), "reasons":"", "raw": {}})
    return rows

rows = load_ucb()
st.title("UCB Mini Dashboard")
st.caption("ค้นหา/เรียงคะแนน และเปรียบเทียบผู้สมัครแบบ side-by-side")

# --- Filters ---
col1, col2, col3 = st.columns([2,1,1])
with col1:
    q = st.text_input("ค้นหา (ชื่อไฟล์/headline/skills/gaps)", "")
with col2:
    min_s, max_s = st.slider("ช่วงคะแนน", 0, 100, (0,100))
with col3:
    sort_by = st.selectbox("เรียงตาม", ["fit_score","file","headline"])

def match(row):
    text = (row["file"]+" "+row["headline"]+" "+row["skills"]+" "+row["gaps"]).lower()
    return (q.lower() in text) and (min_s <= row["fit_score"] <= max_s)

filtered = [r for r in rows if match(r)]
filtered = sorted(filtered, key=lambda r: r[sort_by])

st.write(f"พบผู้สมัคร: **{len(filtered)}** ราย")
st.dataframe(
    [{k: r[k] for k in ["file","fit_score","headline","skills","gaps"]} for r in filtered],
    use_container_width=True
)

# --- Compare two ---
st.subheader("Compare two candidates")
left, right = st.columns(2)
options = [r["file"] for r in filtered]
c1 = left.selectbox("เลือกคนที่ 1", options, index=0 if options else None)
c2 = right.selectbox("เลือกคนที่ 2", options, index=1 if len(options)>1 else 0 if options else None)

def render(panel, file):
    if not file: 
        panel.info("ยังไม่ได้เลือกไฟล์")
        return
    r = next((x for x in filtered if x["file"]==file), None)
    if not r:
        panel.warning("ไม่พบไฟล์ในผลกรอง")
        return
    d = r["raw"]
    panel.metric("Fit Score", r["fit_score"])
    panel.write(f"**Headline:** {r['headline']}")
    with panel.expander("Skills (normalized)"):
        panel.write(", ".join(d.get("skills",{}).get("normalized", [])))
    with panel.expander("Reasons"):
        panel.write("\n- " + "\n- ".join(d.get("reasons", [])))
    with panel.expander("Gaps"):
        panel.write(", ".join(d.get("gaps", [])))
    with panel.expander("Raw JSON"):
        panel.json(d)

render(left, c1)
render(right, c2)

st.caption("Tip: แก้ CSV/JSON แล้วกด **R** เพื่อ refresh (หรือปุ่ม rerun)")
