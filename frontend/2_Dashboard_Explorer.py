import streamlit as st
import pandas as pd
import json
from pathlib import Path
# [แก้ไข] เพิ่ม Optional เข้าไปใน import (แก้ NameError)
from typing import Dict, List, Any, Optional

# --- การตั้งค่า Path ---
# (ต้องตรงกับ Path ที่ 1_UCB_Payload.py อ้างอิง)
UCB_DIR = Path("shared_data/latest_ucb")
SUMMARY_CSV = Path("shared_data/ucb_summary.csv") 

# ==================================================================
# --- [ส่วนที่ 1: คัดลอกฟังก์ชัน Skill Card UI จากหน้า 1] ---
# (เพื่อให้การแสดงผล 2 หน้าเหมือนกัน)
# ==================================================================

# (เราคัดลอก `render_skill_pills` มาจาก 1_UCB_Payload.py)
def render_skill_pills(skills: List[str], color: str = "blue"):
    """
    สร้าง HTML/CSS สำหรับแสดงผลรายการ Skill เป็นแท็กกลมๆ
    color: 'green' (matched), 'red' (missing), 'blue' (other)
    """
    
    color_map = {
        "green": ("#28a745", "#ffffff"), # (bg, text)
        "red":   ("#dc3545", "#ffffff"),
        "blue":  ("#f1f2f6", "#333333")  # (สีเทาอ่อน)
    }
    
    if color not in color_map:
        color = "blue"
        
    bg_color, text_color = color_map[color]
    
    if not skills:
        if color == "green":
            return '<div style="background-color: #f0f0f0; border-radius: 8px; padding: 10px; text-align: center; color: #777;">ไม่พบ Skill ที่ตรงกัน</div>'
        elif color == "red":
            return '<div style="background-color: #f0f0f0; border-radius: 8px; padding: 10px; text-align: center; color: #777;">ไม่พบ Skill ที่ขาด (ตรงตาม JD ทั้งหมด!)</div>'
        else:
             return '<div style="background-color: #f0f0f0; border-radius: 8px; padding: 10px; text-align: center; color: #777;">N/A</div>'

    
    # [แก้ไข] แก้ไข f-string ที่ลืมปิด (SyntaxError)
    pills_html = "".join(
        f"""<span style="display: inline-block; padding: 4px 12px; margin: 4px 3px; border-radius: 16px; font-size: 0.9em; font-weight: 500; line-height: 1.6; background-color: {bg_color}; color: {text_color}; border: 1px solid {bg_color};">
            {skill}
         </span>"""
        for skill in skills
    )
    
    return f'<div style="line-height: 1.5;">{pills_html}</div>'

# ==================================================================
# --- [ส่วนที่ 2: ฟังก์ชันโหลดข้อมูล (Data Loading)] ---
# ==================================================================

@st.cache_data
def load_summary_data() -> pd.DataFrame:
    """
    โหลด ucb_summary.csv (ที่ run_all.py สร้าง)
    """
    if not SUMMARY_CSV.exists():
        st.error(f"ไม่พบไฟล์สรุป: {SUMMARY_CSV}")
        return pd.DataFrame(columns=["file", "fit_score"])
    try:
        df = pd.read_csv(SUMMARY_CSV)
        # สร้าง 'stem' (ชื่อไฟล์ไม่มี .json) เพื่อใช้เป็น Key
        df['stem'] = df['file'].str.replace(".json", "", regex=False)
        return df
    except Exception as e:
        st.error(f"ไม่สามารถอ่าน {SUMMARY_CSV}: {e}")
        return pd.DataFrame(columns=["file", "fit_score", "stem"])

@st.cache_data
def load_ucb_json(filename_stem: str) -> Optional[Dict[str, Any]]:
    """
    โหลดไฟล์ UCB JSON (รายละเอียด) 1 ไฟล์
    """
    json_path = UCB_DIR / f"{filename_stem}.json"
    if not json_path.exists():
        st.error(f"ไม่พบไฟล์ UCB: {json_path}")
        return None
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"ไม่สามารถอ่าน {json_path}: {e}")
        return None

# ==================================================================
# --- [ส่วนที่ 3: UI ของหน้า Dashboard] ---
# ==================================================================

st.set_page_config(page_title="Dashboard Explorer", layout="wide")
st.title("Dashboard & Candidate Explorer")
st.caption(f"แสดงข้อมูลจาก {UCB_DIR} และ {SUMMARY_CSV}")

# [ใหม่] เพิ่มปุ่ม Refresh Data
if st.button("Refresh ข้อมูล (ล้าง Cache)"):
    # ล้าง Cache ของ @st.cache_data ทั้งหมด
    st.cache_data.clear()
    st.success("ล้าง Cache ข้อมูลแล้ว! ข้อมูลจะถูกโหลดใหม่")
    # (Streamlit จะ Rerun อัตโนมัติและโหลดข้อมูลใหม่)

# 1. โหลดข้อมูลหลัก
df_summary = load_summary_data()

if df_summary.empty:
    st.info("ยังไม่มีข้อมูลสรุป (ucb_summary.csv)")
    st.stop()

# 2. UI Filters (Sidebar)
st.sidebar.markdown("## 1. กรองผู้สมัคร")
search_term = st.sidebar.text_input("ค้นหา (ชื่อไฟล์):")
score_range = st.sidebar.slider(
    "กรองคะแนน (Fit Score):", 
    min_value=0, 
    max_value=100, 
    value=(0, 100) # (min, max)
)

# 3. กรอง DataFrame
df_filtered = df_summary[
    (df_summary['file'].str.contains(search_term, case=False, na=False)) &
    (df_summary['fit_score'] >= score_range[0]) &
    (df_summary['fit_score'] <= score_range[1])
]

# 4. แสดงผล Metrics สรุป
st.subheader("ภาพรวม")
col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric("ผู้สมัครทั้งหมด (ใน .csv)", len(df_summary))
col_m2.metric("ผู้สมัครที่กรองเจอ", len(df_filtered))
col_m3.metric(
    "คะแนนเฉลี่ย (ที่กรองเจอ)", 
    f"{df_filtered['fit_score'].mean():.0f} %" if not df_filtered.empty else "N/A"
)

# 5. แสดงตาราง
st.subheader("ตารางผู้สมัคร (ที่กรองแล้ว)")
st.dataframe(df_filtered[['file', 'fit_score']], use_container_width=True)

st.divider()

# ==================================================================
# --- [ส่วนที่ 4: UI แสดงผล Skills Card (อัปเดต)] ---
# ==================================================================
st.subheader("ดูรายละเอียดผู้สมัคร (Skills Card)")

# สร้างตัวเลือกจาก "ผู้สมัครที่กรองแล้ว"
# (เราใช้ 'stem' (ไม่มี .json) เป็น ID)
filtered_candidates_map = dict(zip(df_filtered['stem'], df_filtered['file']))

if not filtered_candidates_map:
    st.info("ไม่พบผู้สมัครที่ตรงกับการกรอง")
    st.stop()

# --- [ใหม่] เพิ่ม Tabs สำหรับ 1 คน หรือ เปรียบเทียบ ---
tab_single, tab_compare = st.tabs(["ดูรายละเอียด (1 คน)", "เปรียบเทียบ (หลายคน)"])

# --- [แท็บที่ 1: ดู 1 คน (ของเดิม)] ---
with tab_single:
    selected_stem = st.selectbox(
        "เลือกผู้สมัครเพื่อดูรายละเอียด:",
        options=filtered_candidates_map.keys(),
        format_func=lambda stem: filtered_candidates_map.get(stem, stem) # โชว์ชื่อไฟล์เต็ม
    )

    if selected_stem:
        ucb_data = load_ucb_json(selected_stem)
        
        if ucb_data:
            # --- [เริ่ม] คัดลอก Logic การแสดงผลจาก 1_UCB_Payload.py ---
            ucb = ucb_data
            
            # [แก้ไข] เพิ่มการตรวจสอบ Type (ป้องกัน Attribute Error จากไฟล์เก่า)
            reasons_data = ucb.get('reasons', {})
            gaps_data = ucb.get('gaps', {})
            
            if isinstance(reasons_data, dict):
                matched_skills = (
                    reasons_data.get('required_hit', []) + 
                    reasons_data.get('nice_hit', [])
                )
            else:
                st.warning(f"พบโครงสร้าง 'reasons' ที่ไม่ถูกต้องในไฟล์ {selected_stem}.json")
                matched_skills = [] 

            if isinstance(gaps_data, dict):
                missing_skills = (
                    gaps_data.get('required_miss', []) + 
                    gaps_data.get('nice_miss', [])
                )
            else:
                st.warning(f"พบโครงสร้าง 'gaps' ที่ไม่ถูกต้องในไฟล์ {selected_stem}.json")
                missing_skills = [] 
            
            fit_score = ucb.get('fit_score', 0)
            candidate_name = ucb.get('headline', 'N/A')
            candidate_id = ucb.get('candidate_id', 'N/A')
            other_skills = ucb.get('skills', {}).get('all', [])
            
            matched_set = set(matched_skills)
            missing_set = set(missing_skills)
            other_skills_filtered = [
                s for s in other_skills 
                if s not in matched_set and s not in missing_set
            ]

            with st.container(border=True):
                col_name, col_score = st.columns([3, 1])
                # (แสดงผลเหมือนหน้า 1...)
                with col_name:
                    st.markdown(f"**ผู้สมัคร:** `{candidate_name or 'N/A'}`")
                    st.caption(f"ไฟล์: `{candidate_id}`")
                with col_score:
                    st.markdown(f"<div style='text-align: right; font-weight: 600;'>Fit Score</div>"
                                f"<div style='text-align: right; font-size: 2.2em; font-weight: 700; color: #007bff; line-height: 1.1;'>{fit_score}%</div>", 
                                unsafe_allow_html=True)
                
                st.divider()
                st.markdown(f"**Skill Analysis (เทียบกับ JD '{ucb.get('jd_title', 'N/A')}')**")
                
                col_match, col_miss = st.columns(2)
                with col_match:
                    st.markdown(f"**<span style='color: #28a745;'>Matched Skills ({len(matched_skills)})</span>**", unsafe_allow_html=True)
                    st.html(render_skill_pills(matched_skills, "green"))
                
                with col_miss:
                    st.markdown(f"**<span style='color: #dc3545;'>Missing Skills ({len(missing_skills)})</span>**", unsafe_allow_html=True)
                    st.html(render_skill_pills(missing_skills, "red"))
                    
                if other_skills_filtered:
                    st.markdown("---")
                    st.markdown(f"**ทักษะอื่นๆ ที่พบในเรซูเม่ ({len(other_skills_filtered)})**")
                    st.html(render_skill_pills(other_skills_filtered, "blue"))
            # --- [สิ้นสุด] Logic การแสดงผล ---

# --- [แท็บที่ 2: เปรียบเทียบ (ของใหม่)] ---
with tab_compare:
    selected_stems_compare = st.multiselect(
        "เลือกผู้สมัคร 2 คนขึ้นไปเพื่อเปรียบเทียบ:",
        options=filtered_candidates_map.keys(),
        format_func=lambda stem: filtered_candidates_map.get(stem, stem) # โชว์ชื่อไฟล์เต็ม
    )
    
    if len(selected_stems_compare) < 2:
        st.info("กรุณาเลือกผู้สมัครอย่างน้อย 2 คนเพื่อเปรียบเทียบ")
    else:
        st.subheader(f"เปรียบเทียบผู้สมัคร {len(selected_stems_compare)} คน")
        
        # สร้างคอลัมน์ตามจำนวนคนที่เลือก
        cols = st.columns(len(selected_stems_compare))
        
        # วนลูปแสดงผลในแต่ละคอลัมน์
        for i, stem in enumerate(selected_stems_compare):
            with cols[i]:
                ucb_data = load_ucb_json(stem)
                if ucb_data:
                    # --- [เริ่ม] Logic แสดงผล (ย่อส่วน) ---
                    ucb = ucb_data
                    reasons_data = ucb.get('reasons', {})
                    gaps_data = ucb.get('gaps', {})
                    
                    # (เราจะดึงแค่ส่วนที่จำเป็นสำหรับการ์ดเปรียบเทียบ)
                    if isinstance(reasons_data, dict):
                        matched_skills = (reasons_data.get('required_hit', []) + reasons_data.get('nice_hit', []))
                    else: matched_skills = []
                    
                    if isinstance(gaps_data, dict):
                        missing_skills = (gaps_data.get('required_miss', []) + gaps_data.get('nice_miss', []))
                    else: missing_skills = []
                    
                    fit_score = ucb.get('fit_score', 0)
                    candidate_name = ucb.get('headline', 'N/A')
                    candidate_id = ucb.get('candidate_id', 'N/A')

                    # สร้างการ์ด (ย่อส่วน)
                    with st.container(border=True):
                        st.markdown(f"**{candidate_name or 'N/A'}**")
                        st.caption(f"`{candidate_id}`")
                        st.markdown(f"<div style='text-align: left; font-size: 1.8em; font-weight: 700; color: #007bff; line-height: 1.1;'>{fit_score}%</div>", 
                                    unsafe_allow_html=True)
                        st.divider()
                        st.markdown(f"**<span style='color: #28a745;'>Matched ({len(matched_skills)})</span>**", unsafe_allow_html=True)
                        st.html(render_skill_pills(matched_skills, "green"))
                        st.markdown("---")
                        st.markdown(f"**<span style='color: #dc3545;'>Missing ({len(missing_skills)})</span>**", unsafe_allow_html=True)
                        st.html(render_skill_pills(missing_skills, "red"))
                    # --- [สิ้นสุด] Logic แสดงผล (ย่อส่วน) ---
                else:
                    st.error(f"ไม่สามารถโหลด {stem}")