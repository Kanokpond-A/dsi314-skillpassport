# frontend/streamlit_app.py (เวอร์ชันปรับปรุง Layout)
import json, glob, io, csv, math, datetime, subprocess, re
from collections import Counter, defaultdict
from pathlib import Path
import streamlit as st
import pandas as pd

from backend.app.services.A_backend.normalize_scoring import skills_normalizer, scoring

# ---------------- Page Config (เหมือนเดิม) ----------------
st.set_page_config(page_title="UCB Candidate Search & Shortlist", layout="wide")

# ---------------- Path Definitions (เหมือนเดิม) ----------------
# (แก้ไขส่วนนี้ หาก Path ของคุณไม่ตรง)
ROOT = Path(__file__).resolve().parents[1] if (Path.cwd() / "frontend").exists() else Path.cwd()
SHARED = ROOT / "shared_data"
UCB_DIR = SHARED / "latest_ucb"
# (เพิ่ม Path ของโค้ดส่วน B)
RUN_ALL_SCRIPT = ROOT / "backend" / "app" / "services" / "A_backend" / "app" / "parsers" / "run_all.py"


# ---------------- Helper Functions (คัดลอกจากโค้ดเดิมของคุณ) ----------------
# (เราจะเก็บฟังก์ชัน Helper และ Data Loaders ทั้งหมดของคุณไว้)

def _bar_or_fallback(*, chart_fn, kwargs_width, kwargs_legacy):
    """Use new width API; fallback to use_container_width for older Streamlit."""
    try:
        return chart_fn(**kwargs_width)
    except TypeError:
        return chart_fn(**kwargs_legacy)

def redact_contacts(c: dict):
    # ... (โค้ด Helper นี้เหมือนเดิม) ...
    PII_KEYS = {"email", "phone", "location", "address", "linkedin", "github", "line", "facebook"}
    if not isinstance(c, dict): return {}
    return {
        k: ("•••" if isinstance(v, str) and k.lower() in PII_KEYS and v else v)
        for k, v in c.items()
    }

def _ensure_list(x):
    if x is None: return []
    if isinstance(x, list): return x
    if isinstance(x, dict): return list(x.values())
    return [x]

def stringify_list(lst, sep=", "):
    return sep.join(lst) if lst else "—"

def row_text(r):
    bag = []
    bag += [r.get("file",""), r.get("headline","")]
    bag += r.get("skills_all", []) + r.get("gaps_list", []) + r.get("reasons", [])
    return " ".join([x for x in bag if isinstance(x, str)]).lower()

# ---------------- UCB Loader Functions (คัดลอกจากโค้ดเดิม) ----------------
def _skills_to_list(sk):
    # ... (โค้ด Helper นี้เหมือนเดิม) ...
    skills_all, skills_in, skills_mined = [], [], []
    if isinstance(sk, dict):
        if "all" in sk:
            skills_all  = _ensure_list(sk.get("all"))
            skills_in   = _ensure_list(sk.get("input"))
            skills_mined= _ensure_list(sk.get("mined"))
        elif "normalized" in sk:
            skills_all = _ensure_list(sk.get("normalized"))
        else:
            skills_all = _ensure_list(sk)
    elif isinstance(sk, list):
        skills_all = sk
    seen, out = set(), []
    for s in skills_all:
        if s not in seen:
            seen.add(s); out.append(s)
    skills_all = out
    return skills_all, skills_in, skills_mined

def _reasons_to_list(reasons):
    # ... (โค้ด Helper นี้เหมือนเดิม) ...
    if isinstance(reasons, list):
        return reasons, [], []
    if isinstance(reasons, dict):
        req = _ensure_list(reasons.get("required_hit"))
        nice = _ensure_list(reasons.get("nice_hit"))
        merged = []
        if req:  merged.append("Matched required: " + ", ".join(req))
        if nice: merged.append("Matched nice-to-have: " + ", ".join(nice))
        return merged, req, nice
    return [], [], []

def _gaps_to_list(gaps):
    # ... (โค้ด Helper นี้เหมือนเดิม) ...
    if isinstance(gaps, list):
        return gaps, [], []
    if isinstance(gaps, dict):
        req_m = _ensure_list(gaps.get("required_miss"))
        nice_m= _ensure_list(gaps.get("nice_miss"))
        merged = []
        if req_m:  merged.append("Missing required: " + ", ".join(req_m))
        if nice_m: merged.append("Missing nice: " + ", ".join(nice_m))
        return merged, req_m, nice_m
    return [], [], []

def _to_float(val, default=0.0):
    """Converts a value to float, handling strings or None."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

@st.cache_data(show_spinner=False)
def load_ucb_data():
    """ (นี่คือฟังก์ชัน load_ucb() จากโค้ดเดิมของคุณ) """
    rows, all_skills = [], set()
    files = sorted(UCB_DIR.glob("*.json"))
    if not files:
        st.warning(f"ไม่พบไฟล์ UCB JSON ใน: {UCB_DIR}")
        return [], []
        
    for p in files:
        try:
            d = json.load(open(p, encoding="utf-8"))
            # (เพิ่ม ucb_id หรือ resume_id ถ้ามี เพื่อใช้เป็น Key)
            candidate_key = d.get("ucb_id") or d.get("resume_id") or p.name

            skills_all, skills_in, skills_mined = _skills_to_list(d.get("skills", []))
            reasons_list, req_hit, nice_hit = _reasons_to_list(d.get("snapshot", {}).get("top_reasons", []))
            gaps_list, req_miss, nice_miss = _gaps_to_list(d.get("snapshot", {}).get("gaps", []))
            
            # (พยายามดึงข้อมูลจากหลายๆ ที่)
            snapshot = d.get("snapshot", {})
            header = d.get("header", {})
            
            rows.append({
                "key": candidate_key, # Key สำหรับการเลือก
                "file": p.name,
                "name": d.get("name") or header.get("name") or "(No Name)",
                "headline": d.get("headline") or header.get("headline") or "—",
                "fit_score": int(snapshot.get("fit_score", 0)),
                "experience_years": d.get("experience_years") or header.get("total_experience_years") or "—",
                "availability": d.get("availability") or header.get("availability") or "—",
                "expected_salary": d.get("expected_salary") or header.get("expected_salary") or "—",
                "location": d.get("location") or header.get("location") or "—",
                "skills_all": skills_all,
                "skills_in": skills_in,
                "skills_mined": skills_mined,
                "reasons": reasons_list,
                "req_hit": req_hit,
                "nice_hit": nice_hit,
                "gaps_list": gaps_list,
                "req_miss": req_miss,
                "nice_miss": nice_miss,
                "contacts": redact_contacts(d.get("contacts") or header.get("contacts", {})),
                "evidence": d.get("evidence") or {},
                "raw": d,
            })
            all_skills.update(skills_all)
        except Exception as e:
            rows.append({
                "key": p.name, "file": p.name, "headline": f"<Error: {e}>", "fit_score": 0,
                "skills_all": [], "skills_in": [], "skills_mined": [],
                "reasons": [], "req_hit": [], "nice_hit": [],
                "gaps_list": [f"error:{e}"], "req_miss": [], "nice_miss": [],
                "contacts": {}, "evidence": {}, "raw": {}, "name": f"<Error: {p.name}>"
            })
    return rows, sorted(all_skills)

def force_refresh():
    load_ucb_data.clear()
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()

# ---------------- (ใหม่) Session State สำหรับเก็บ Candidate ที่ถูกเลือก ----------------
if "selected_key" not in st.session_state:
    st.session_state.selected_key = None


# ======================================================================
# UI (ปรับปรุงใหม่ทั้งหมด)
# ======================================================================

# --- (ย้าย Sidebar Runner มาไว้ใน Expander) ---
with st.sidebar:
    st.header("Run Pipeline (Optional)")
    if st.button("↻ Refresh Data", use_container_width=True, type="primary"):
        force_refresh()
    
    with st.expander("Run Backend Pipeline"):
        in_dir = st.text_input("Input folder", str(ROOT / "samples"))
        jd = st.text_input("JD profile", str(ROOT / "config" / "jd_profiles" / "data-analyst.yml"))
        if st.button("Run", use_container_width=True):
            if not RUN_ALL_SCRIPT.exists():
                st.error(f"ไม่พบสคริปต์: {RUN_ALL_SCRIPT}")
            else:
                args = ["python", str(RUN_ALL_SCRIPT), "--in-dir", in_dir]
                if jd: args += ["--jd", jd]
                
                with st.spinner("Running Backend ..."):
                    proc = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True)
                if proc.returncode != 0:
                    st.error("Pipeline failed:")
                    st.code(proc.stderr or proc.stdout)
                else:
                    st.success("Pipeline finished. Click 'Refresh Data' to see results.")
                    st.code(proc.stdout)

# --- โหลดข้อมูล (เหมือนเดิม) ---
rows, ALL_SKILLS = load_ucb_data()

# --- (ใหม่) 1. แถบค้นหาและฟิลเตอร์ (ตามภาพ S__316628999.jpg) ---
st.header("Candidate Search & Shortlist")
q = st.text_input("", placeholder="🔍 Python, Data Engineer, ETL Pipeline, AWS Glue...", key="q_search")

f1, f2, f3, f4, f5 = st.columns(5)
with f1:
    loc_sel = st.multiselect("Location", sorted(list(set(r.get("location","") for r in rows if r.get("location")))))
with f2:
    min_s, max_s = st.slider("Fit Score", 0, 100, (0, 100), key="score_range")
with f3:
    # (เพิ่มฟิลเตอร์ Experience)
    exp_years = sorted(list(set(r.get("experience_years",0) for r in rows if isinstance(r.get("experience_years"), (int, float)))))
    min_exp = st.selectbox("Min Experience", [0] + exp_years)
with f4:
    # (เพิ่มฟิลเตอร์ Availability)
    avail = sorted(list(set(r.get("availability","") for r in rows if r.get("availability"))))
    avail_sel = st.multiselect("Availability", avail)
with f5:
    sort_by = st.selectbox("Sort by", ["fit_score", "experience_years", "file", "headline"], index=0, key="sort_by")
    asc = st.toggle("Ascending", value=False, key="ascending")


# --- (ใหม่) 2. ตรรกะการกรอง (จากโค้ดเดิม + ที่เพิ่มใหม่) ---
def match(r):
    if not (min_s <= r["fit_score"] <= max_s):
        return False
    if q and (q.lower() not in row_text(r)):
        return False
    if loc_sel and r.get("location") not in loc_sel:
        return False
    if min_exp > 0 and (not isinstance(r.get("experience_years"), (int, float)) or r.get("experience_years") < min_exp):
        return False
    if avail_sel and r.get("availability") not in avail_sel:
        return False
    return True

filtered = [r for r in rows if match(r)]
filtered = sorted(filtered, key=lambda r: r.get(sort_by, 0) or 0, reverse=not asc)


# --- (ใหม่) 3. แถบสรุปผล (Stat Cards) (จากโค้dเดิม) ---
count = len(filtered)
avg = int(sum(r["fit_score"] for r in filtered) / count) if count else 0
# (คำนวณ Must-have และ Available จากฟิลเตอร์)
must_have_count = sum(1 for r in filtered if (r.get("req_hit") and len(r["req_hit"]) > 0)) # (ตัวอย่าง Logic)
available_count = sum(1 for r in filtered if r.get("availability") == "New" or "พร้อม" in r.get("availability", "")) # (ตัวอย่าง Logic)

k1, k2, k3, k4 = st.columns(4)
k1.metric("พบผู้สมัครทั้งหมด (ที่ตรงฟิลเตอร์)", count)
k2.metric("ตรง Must-have (ตัวอย่าง)", must_have_count)
k3.metric("พร้อมเริ่มงาน (ตัวอย่าง)", available_count)
k4.metric("Average Score", avg)

st.divider()

# --- (ใหม่) 4. Layout 2 คอลัมน์ (List/Detail) ---
list_col, detail_col = st.columns([2, 1]) # อัตราส่วน 2:1

with list_col:
    st.subheader(f"Results ({count})")
    
    # (Render List)
    list_container = st.container(height=700) # สร้างกล่องที่ Scroll ได้
    if not filtered:
        list_container.info("ไม่พบผู้สมัครที่ตรงกับเงื่อนไข")
    
    for r in filtered:
        item_key = r["key"]
        card = list_container.container(border=True)
        c1, c2, c3 = card.columns([1, 4, 1])
        
        # (Avatar/Checkbox)
        with c1:
            st.checkbox("", key=f"cb_{item_key}")
            # (Avatar)
            st.image(f"https://ui-avatars.com/api/?name={r.get('name', 'N A')}&background=random&color=fff", width=50)

        # (Info)
        with c2:
            st.markdown(f"**{r.get('name', 'N/A')}**")
            st.caption(f"{r.get('headline', 'N/A')}")
            # (ปุ่มสำหรับเลือก)
            if st.button("ดูรายละเอียด", key=f"btn_{item_key}", use_container_width=True):
                st.session_state.selected_key = item_key
        
        # (Score)
        with c3:
            st.markdown(f"### {r.get('fit_score', 0)}")
            st.caption("Score")


with detail_col:
    st.subheader("Candidate Detail")
    
    # (Render Detail Pane)
    if st.session_state.selected_key is None:
        detail_container = st.container(height=700)
        detail_container.info("คลิก 'ดูรายละเอียด' จากด้านซ้ายเพื่อดูข้อมูล")
    else:
        # หา Candidate ที่ถูกเลือก
        r = next((x for x in filtered if x["key"] == st.session_state.selected_key), None)
        
        if not r:
            st.error("ไม่พบข้อมูลผู้สมัคร (กรุณา Refresh)")
        else:
            detail_container = st.container(height=700) # สร้างกล่องที่ Scroll ได้
            
            # (นี่คือ Logic การแสดงผลที่ดึงมาจาก "Compare" ในโค้ดเดิมของคุณ)
            detail_container.markdown(f"## {r.get('name', 'N/A')}")
            detail_container.metric(f"Fit Score", r.get('fit_score', 0))
            
            if detail_container.button("Add to Shortlist", type="primary", use_container_width=True):
                st.toast(f"เพิ่ม {r.get('name')} เข้า Shortlist แล้ว!") # (ตัวอย่าง Action)

            with detail_container.expander("Top Skills Match & Gaps", expanded=True):
                st.write("**Top Reasons (จุดแข็ง)**")
                for reason in r.get("reasons", []): st.write(f"✅ {reason}")
                
                st.write("**Gaps (จุดอ่อน)**")
                for gap in r.get("gaps_list", []): st.write(f"❌ {gap}")

            with detail_container.expander("Key Evidence Snippets (จาก Skills)", expanded=True):
                ev = r.get("evidence") or {}
                if ev:
                    for k, v in ev.items():
                        st.markdown(f"**{k}**:")
                        for s in _ensure_list(v)[:3]: st.write(f"• {s}")
                else:
                    st.info("No evidence captured.")
            
            with detail_container.expander("Basic Info"):
                st.write(f"**Experience:** {r.get('experience_years', 'N/A')} ปี")
                st.write(f"**Location:** {r.get('location', 'N/A')}")
                st.write(f"**Availability:** {r.get('availability', 'N/A')}")
                st.write(f"**Expected Salary:** {r.get('expected_salary', 'N/A')}")
            
            with detail_container.expander("Contacts (Redacted)"):
                st.json(r.get("contacts", {}))
            
            with detail_container.expander("Raw JSON"):
                st.json(r.get("raw", {}))

# --- (ลบส่วน Charts และ Compare Two เดิมออก) ---
# ...

# --- Footer (เหมือนเดิม) ---
st.divider()
st.caption("UCB Search Dashboard v2.0 (Streamlit)")