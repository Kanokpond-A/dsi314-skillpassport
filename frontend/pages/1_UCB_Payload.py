# frontend/pages/1_UCB_Payload.py

import streamlit as st
import json
import time
import sys
import os
from pathlib import Path

# --- 1. (สำคัญ) เพิ่ม Path ไปยัง Backend (เหมือนเดิม) ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
sys.path.append(PROJECT_ROOT)

# Path สำหรับบันทึกไฟล์ UCB (Warehouse) (เหมือนเดิม)
UCB_DIR = Path(PROJECT_ROOT) / "shared_data" / "latest_ucb"

# --- 2. (สำคัญ) Import โค้ดส่วน B (A_backend) (เหมือนเดิม) ---
try:
    from backend.app.services.A_backend.parsers import pdf_parser, docx_parser
    from backend.app.services.A_backend.preprocess import structure_builder, field_extractor
    from backend.app.services.A_backend.normalize_scoring import scoring, skills_normalizer
except ModuleNotFoundError:
    st.error("เกิดข้อผิดพลาด: ไม่พบโมดูล Backend (กรุณาตรวจสอบ __init__.py และ Path)")
    st.stop()
except ImportError as e:
    st.error(f"Import Error: {e}")
    st.stop()


# ---------------- Page Config ----------------
st.set_page_config(page_title="Resume Parser", layout="wide") 
st.title("Resume Parser (สกัดข้อมูลและ Skills)") 
st.caption("อัปโหลดเรซูเม่ (PDF/DOCX) เพื่อสกัดข้อมูล (Parse) และสกัดทักษะ (Skill Extraction)")

# --- Session State (เหมือนเดิม) ---
if "parsed_data" not in st.session_state:
    st.session_state.parsed_data = None
if "file_uploader_key" not in st.session_state:
    st.session_state.file_uploader_key = 0

# --- 3. ฟังก์ชัน Helper (เหมือนเดิม) ---
def save_uploaded_file_temp(uploaded_file):
    temp_file_path = f"./temp_{uploaded_file.name}" 
    with open(temp_file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return temp_file_path

# ▼▼▼ (แก้ไข) 2: แก้ไขฟังก์ชัน Parse ให้เพิ่ม "Fallback Logic" ▼▼▼
def parse_resume_text(uploaded_file):
    """
    ฟังก์ชันนี้จะสกัดข้อมูล, สร้าง JSON ที่ถูกต้องสำหรับ Warehouse,
    บันทึกลง Warehouse, และคืนผลลัพธ์
    คืนค่า: (parsed_data, save_path)
    """
    temp_path = save_uploaded_file_temp(uploaded_file)
    raw_text = ""
    try:
        # --- A. อ่าน Resume (เหมือนเดิม) ---
        if uploaded_file.type == "application/pdf":
            raw_text, _ = pdf_parser.extract_text_standard(Path(temp_path))
        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            raw_text = docx_parser.read_docx_text(Path(temp_path))
        else:
            st.error("ไฟล์ Resume ไม่รองรับ (.pdf หรือ .docx)")
            return None, None
        
        # --- B. สกัดข้อมูล (เหมือนเดิม) ---
        fields = field_extractor.extract_all(raw_text)
        fields_dict = fields.asdict() # ดึง 6 ฟิลด์หลักออกมาเป็น Dict

        alias_map = scoring.load_alias_map()
        mined_skills, evidence = scoring.mine_skills_from_text(raw_text, alias_map)
        canon_all = mined_skills 

        # --- C. (แก้ไข) สร้าง JSON ให้ตรงกับที่ Warehouse (0_Candidate_Warehouse.py) อ่าน ---
        
        # (เพิ่ม) 1. ตรรกะสำรอง (Fallback Logic) สำหรับชื่อ
        file_stem = Path(uploaded_file.name).stem # ดึงชื่อไฟล์ (ไม่มี .pdf)
        extracted_name = fields_dict.get("name")
        
        # ถ้า `extracted_name` เป็น NULL (None) หรือว่างเปล่า, ให้ใช้ `file_stem` แทน
        candidate_name = extracted_name if extracted_name else file_stem

        parsed_data = {
            # 2. แฟลตฟิลด์หลักออกมา (Warehouse อ่านจาก top-level)
            "name": candidate_name, # <-- (แก้ไข) ใช้ชื่อที่มี Fallback
            "headline": fields_dict.get("last_job_title"), # ใช้ last_job_title เป็น headline
            "experience_years": fields_dict.get("experience_years"),
            "availability": fields_dict.get("availability"),
            "expected_salary": fields_dict.get("expected_salary"),
            "location": fields_dict.get("location"),
            "contacts": {}, # field_extractor.py ไม่ได้สกัดส่วนนี้

            # 3. โครงสร้าง skills (Warehouse อ่าน .all)
            "skills": { 
                "all": canon_all, 
                "input": [],
                "mined": canon_all
            },
            
            # 4. Snapshot (Warehouse อ่าน score/reasons/gaps จากที่นี่)
            "snapshot": {
                "fit_score": 0, # ตั้งเป็น 0 เพราะไม่มี JD
                "top_reasons": {"message": "N/A - No JD provided"},
                "gaps": {"message": "N/A - No JD provided"}
            },

            # 5. Evidence (Warehouse อ่านจาก top-level)
            "evidence": evidence,

            # 6. Metadata
            "jd_title": None,
            "resume_id": file_stem # Key สำหรับ Warehouse
        }

        # --- D. (เพิ่ม) บันทึกไฟล์ลง Warehouse ---
        try:
            # (แก้ไข) ใช้ file_stem ที่เราสร้างไว้แล้ว
            save_path = UCB_DIR / f"{file_stem}.json"
            
            UCB_DIR.mkdir(parents=True, exist_ok=True)
            
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(parsed_data, f, indent=2, ensure_ascii=False)
            
            return parsed_data, str(save_path) 
            
        except Exception as save_e:
            st.error(f"เกิดข้อผิดพลาดระหว่างบันทึกไฟล์: {save_e}")
            return parsed_data, None 

    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดระหว่าง Parse/Skill Extraction: {e}")
        return None, None
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
# ▲▲▲ (สิ้นสุดการแก้ไขฟังก์ชัน) ▲▲▲


# (ฟังก์ชันแสดงผลการ์ด - แก้ไขเล็กน้อย)
def display_results_as_cards(parsed_data):
    # ▼▼▼ (แก้ไข) ดึงข้อมูลจากโครงสร้างใหม่ (ที่แฟลตแล้ว) ▼▼▼
    
    # ดึงข้อมูลจากระดับ Top-level
    name = parsed_data.get('name', 'N/A')
    headline = parsed_data.get('headline', 'No Title Found')
    location = parsed_data.get('location') or "N/A"
    availability = parsed_data.get('availability') or "N/A"
    salary = parsed_data.get('expected_salary') or "N/A"
    experience = parsed_data.get('experience_years', 0)
    
    # ดึงข้อมูลจาก Skills
    skills_data = parsed_data.get("skills", {})
    all_skills = skills_data.get("all", [])
    
    # ดึงข้อมูลจาก Evidence
    evidence = parsed_data.get("evidence", {}) # <-- อ่านจาก Top-level
    
    # ดึงข้อมูลจาก Snapshot
    snapshot = parsed_data.get("snapshot", {})
    fit_score = snapshot.get("fit_score") # <-- อ่านจาก Snapshot
    reason_msg = snapshot.get("top_reasons", {}).get("message", "N/A") # <-- อ่านจาก Snapshot

    # --- การ์ดที่ 1: ข้อมูลผู้สมัคร (Profile Card) ---
    st.subheader(f"ข้อมูลผู้สมัคร: {name}")
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**{headline}**")
            st.text(f"Location: {location}")
            st.text(f"Availability: {availability}")
            st.text(f"Salary: {salary}")
        with col2:
            st.metric(label="Experience (Years)", value=experience)
            if fit_score is None: st.metric(label="Fit Score", value="N/A")
            else: st.metric(label="Fit Score", value=f"{fit_score}") # (จะแสดงเป็น 0)

    st.write("") 

    # --- การ์ดที่ 2: ทักษะ (Skills Card) ---
    st.subheader("ทักษะที่สกัดได้")
    with st.container(border=True):
        if not all_skills: st.text("ไม่พบทักษะที่สกัดได้")
        else:
            st.multiselect("Skills", options=all_skills, default=all_skills, disabled=True, label_visibility="collapsed")
        if evidence:
            with st.expander("แสดงหลักฐานที่พบ (Show Evidence)"):
                for skill, quotes in evidence.items():
                    st.markdown(f"**{skill}**")
                    for quote in quotes: st.caption(f"• {quote.strip()}")

    st.write("") 

    # --- การ์ดที่ 3: วิเคราะห์คะแนน (Score Analysis) ---
    st.subheader("วิเคราะห์คะแนน")
    st.info(f"{reason_msg}")


# --- 4. หน้า UI (เหมือนเดิม) ---
with st.container(border=True):
    st.subheader("อัปโหลดเรซูเม่")
    uploaded_file = st.file_uploader(
        "เลือกไฟล์เรซูเม่ (.pdf หรือ .docx)", 
        type=["pdf", "docx"], 
        key=f"resume_upload_{st.session_state.file_uploader_key}", 
        label_visibility="collapsed"
    )

st.divider()

# --- 5. ปุ่มประมวลผล (เหมือนเดิม) ---
if st.button("สกัดข้อมูล (Parse Resume)", type="primary", use_container_width=True):
    if uploaded_file is not None:
        status_placeholder = st.empty()
        status_placeholder.info("กำลังสกัดข้อมูล (Parsing & Extracting Skills)...")
        progress_bar = st.progress(0, "เริ่มต้น")
        
        parsed_data, save_path = parse_resume_text(uploaded_file)
        
        if parsed_data:
            progress_bar.progress(100, "เสร็จสิ้น!")
            if save_path:
                status_placeholder.success(f"สกัดข้อมูลเสร็จสิ้น! บันทึกผลลัพธ์ลง Warehouse แล้ว ({Path(save_path).name})")
            else:
                status_placeholder.warning(f"สกัดข้อมูลเสร็จสิ้น แต่บันทึกลง Warehouse ไม่สำเร็จ")

            st.session_state.parsed_data = parsed_data
            st.rerun() 
        else:
            status_placeholder.error("ล้มเหลวระหว่างขั้นตอน Parsing")
            st.session_state.parsed_data = None 
    else:
        st.warning("กรุณาอัปโหลดไฟล์เรซูเม่ก่อน")
        st.session_state.parsed_data = None

if st.button("ล้างข้อมูล (Clear)", use_container_width=True):
    st.session_state.parsed_data = None 
    st.session_state.file_uploader_key += 1 
    st.rerun() 

# --- 6. ส่วนแสดงผล (เหมือนเดิม) ---
if st.session_state.parsed_data is not None:
    
    display_results_as_cards(st.session_state.parsed_data)
    st.divider() 
    
    json_string = json.dumps(
        st.session_state.parsed_data, 
        indent=2, 
        ensure_ascii=False
    )
    
    file_name_prefix = st.session_state.parsed_data.get("name") or st.session_state.parsed_data.get("resume_id") or "resume_export"
    safe_file_name = file_name_prefix.replace(" ", "_").lower()

    st.download_button(
        label="ดาวน์โหลดข้อมูล (Download JSON)",
        data=json_string,
        file_name=f"{safe_file_name}_parsed.json",
        mime="application/json",
        use_container_width=True
    )