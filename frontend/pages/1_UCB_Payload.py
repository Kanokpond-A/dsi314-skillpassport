import streamlit as st
import pandas as pd
import subprocess
import sys
import json
from pathlib import Path
import os
import time
import re 
from typing import Dict, List, Any, Optional 
import logging


# --- Setup Logging ---
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("streamlit_app_p1_batch")

# --- การตั้งค่า Path ---
# (สมมติว่ารัน streamlit run จากรากโปรเจกต์)
RUN_ALL_SCRIPT = Path("backend/app/services/parser_a1/parsers/run_all.py") 
JD_TEMPLATE_DIR = Path("config/jd_profiles") 
UCB_DIR = Path("shared_data/latest_ucb")

# ==================================================================
# --- [ส่วนที่ 1: ตรรกะ JD Parser + Skill Card UI] ---
# ==================================================================

SKILL_PATTERNS = re.compile(
    r"\b("
    r"python|sql|excel|r|tableau|power\s*bi|looker|bi|"
    r"etl|airflow|dbt|aws|gcp|azure|spark|pyspark|"
    r"ml|machine\s*learning|statistics|"
    r"fastapi|django|flask|docker|kubernetes"
    r")\b",
    re.IGNORECASE
)

def _normalize_skill(skill: str) -> str:
    """ ทำให้สกิลเป็น Title Case เพื่อความสอดคล้อง """
    s = (skill or "").strip().lower()
    if s == "py": return "Python"
    if s in ("postgres", "postgresql", "mysql"): return "SQL"
    if s in ("power bi", "powerbi"): return "Power BI"
    if s == "machine learning": return "ML"
    return s.title()

def parse_jd_from_text(text: str) -> Dict[str, Any]:
    """
    สกัดสกิลจากข้อความ JD ดิบ
    [แก้ไข] เปลี่ยน Key เป็น 'required' และ 'nice_to_have' ให้ตรงกับ scoring.py
    """
    if not text or not text.strip():
        return {"required": [], "nice_to_have": [], "name": "No JD Provided", "source": "fallback"}
        
    matches = SKILL_PATTERNS.findall(text)
    normalized_skills = sorted(list(set(_normalize_skill(m) for m in matches)))
    log.info(f"[JD Parser Logic] Found skills in text: {normalized_skills}")
    
    return {
        "required": normalized_skills, 
        "nice_to_have": [], # สมมติว่า Skill จาก Text เป็น required ทั้งหมด
        "name": f"Parsed JD (found {len(normalized_skills)} skills)",
        "source": "text",
        "weights": {"required": 100, "nice": 0} # ให้น้ำหนัก required 100%
    }

def render_skill_pills(skills: List[str], color: str = "blue"):
    """
    สร้าง HTML/CSS สำหรับแสดงผลรายการ Skill เป็นแท็กกลมๆ
    """
    color_map = {
        "green": ("#28a745", "#ffffff"),
        "red":   ("#dc3545", "#ffffff"),
        "blue":  ("#f1f2f6", "#333333")
    }
    if color not in color_map: color = "blue"
    bg_color, text_color = color_map[color]
    
    if not skills:
        if color == "green": return '<div style="background-color: #f0f0f0; border-radius: 8px; padding: 10px; text-align: center; color: #777;">ไม่พบ Skill ที่ตรงกัน</div>'
        elif color == "red": return '<div style="background-color: #f0f0f0; border-radius: 8px; padding: 10px; text-align: center; color: #777;">ไม่พบ Skill ที่ขาด (ตรงตาม JD ทั้งหมด!)</div>'
        else: return '<div style="background-color: #f0f0f0; border-radius: 8px; padding: 10px; text-align: center; color: #777;">N/A</div>'
    
    # [แก้ไข] แก้ไข f-string ที่ลืมปิด (SyntaxError)
    pills_html = "".join(
        f"""<span style="display: inline-block; padding: 4px 12px; margin: 4px 3px; border-radius: 16px; font-size: 0.9em; font-weight: 500; line-height: 1.6; background-color: {bg_color}; color: {text_color}; border: 1px solid {bg_color};">
            {skill}
         </span>"""
        for skill in skills
    )
    return f'<div style="line-height: 1.5;">{pills_html}</div>'

# [เพิ่ม] ฟังก์ชันสำหรับโหลด UCB JSON (คัดลอกจากหน้า 2)
@st.cache_data # เราใช้ cache ที่นี่ได้ เพราะเราจะล้างมันในหน้า 2
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
# --- [ส่วนที่ 2: ฟังก์ชันหลัก (ปรับปรุงสำหรับ Batch Upload)] ---
# ==================================================================

def run_pipeline(
    uploaded_files: List[st.runtime.uploaded_file_manager.UploadedFile], 
    jd_tab_choice: str, 
    # [แก้ไข] jd_template_file อาจเป็น None (ของ Python) ได้
    jd_template_file: Optional[str], 
    jd_input_text: str, 
    pass_threshold, 
    lang, 
    redact
) -> List[str]: # [แก้ไข] เพิ่มการคืนค่าเป็น List[str] (รายชื่อ stems)
    """
    [อัปเดต] รัน Pipeline และคืนค่า List ของ stems ที่ประมวลผล
    """
    if not uploaded_files:
        # [แก้ไข] แก้ไข typo SyntaxError (เรซูเม'่ -> เรซูเม่)
        st.error("กรุณาอัปโหลดไฟล์เรซูเม่ก่อน")
        return [] # คืนค่า List ว่าง

    log.info(f"Starting batch pipeline for: {len(uploaded_files)} files")
    
    INPUT_DIR = Path("streamlit_inputs")
    INPUT_DIR.mkdir(exist_ok=True)
    
    log.info(f"Cleaning {INPUT_DIR}...")
    for f in INPUT_DIR.glob("*"): 
        f.unlink()
        
    OUTPUT_METRICS = Path("shared_data/metrics.json")
    OUTPUT_SCORES = Path("shared_data/scores.csv") 

    # [แก้ไข] สร้าง List ของ stems (ชื่อไฟล์) ที่จะประมวลผล
    output_stems = []
    log.info(f"Saving {len(uploaded_files)} files to {INPUT_DIR}")
    for uploaded_file in uploaded_files:
        with open(INPUT_DIR / uploaded_file.name, "wb") as out_f:
            out_f.write(uploaded_file.getvalue())
        output_stems.append(Path(uploaded_file.name).stem) # เก็บชื่อไฟล์ (ไม่มี .pdf)
        
    # 5. ประมวลผล JD (เหมือนเดิม)
    jd_profile_path = None
    # [แก้ไข] เช็คว่า jd_template_file (ตัวแปร) is not None
    if jd_tab_choice == "Template" and jd_template_file is not None:
        jd_profile_path = JD_TEMPLATE_DIR / jd_template_file
        if not jd_profile_path.exists():
            st.error(f"ไม่พบไฟล์ JD Template: {jd_profile_path}")
            return [] # คืนค่า List ว่าง
        st.info(f"ใช้ JD Template: `{jd_profile_path}`")
    elif jd_tab_choice == "Text" and jd_input_text.strip():
        try:
            jd_data = parse_jd_from_text(jd_input_text)
            jd_profile_path = Path("streamlit_jd.json") 
            with open(jd_profile_path, "w", encoding="utf-8") as f:
                json.dump(jd_data, f, ensure_ascii=False, indent=2)
            with st.expander("ดู JD Profile ที่สร้างอัตโนมัติ (จาก Text)"):
                st.json(jd_data)
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการประมวลผล JD: {e}")
            return [] # คืนค่า List ว่าง
    
    # 6. สร้างคำสั่ง (Command) (เหมือนเดิม)
    cmd = [
        sys.executable, str(RUN_ALL_SCRIPT),
        "--in", str(INPUT_DIR), 
        "--pass-threshold", str(pass_threshold),
        "--lang", lang,
    ]
    if redact: cmd.append("--redact")
    if jd_profile_path: 
        cmd.append("--jd")
        cmd.append(str(jd_profile_path)) 
    else:
        st.warning("ไม่ได้ป้อน JD, ระบบจะรันโดยไม่คำนวณ Fit Score (V1)")
    cmd.append("--report") 

    # 7. [อัปเดต] รัน subprocess
    st.session_state["v1_metrics"] = None
    st.session_state["v1_scores_df"] = None
    
    try:
        st.info(f"กำลังรันคำสั่ง: {' '.join(map(str, cmd))}")
        process = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding="utf-8")
        st.subheader("ผลการรัน (V1 Pipeline Log)")
        st.code(process.stdout, language="bash")
        if process.stderr:
            st.warning("Process Stderr:"); st.code(process.stderr, language="bash")
        
        # (Race Condition Sleep)
        metrics_data = None
        for _ in range(5): 
            try:
                with open(OUTPUT_METRICS, 'r', encoding='utf-8') as f:
                    metrics_data = json.load(f)
                break 
            except (FileNotFoundError, json.JSONDecodeError):
                time.sleep(0.2) 

        if not metrics_data:
            st.error(f"Pipeline รันสำเร็จ แต่ไม่พบไฟล์ {OUTPUT_METRICS}")
            return [] # คืนค่า List ว่าง

        st.session_state["v1_metrics"] = metrics_data
        
        try:
            st.session_state["v1_scores_df"] = pd.read_csv(OUTPUT_SCORES)
        except FileNotFoundError:
            log.warning(f"Could not find {OUTPUT_SCORES} (but metrics.json was found)")
            st.session_state["v1_scores_df"] = pd.DataFrame() 
        
        log.info("run_all.py finished successfully.")
        st.success("Ingestion Pipeline (V1) รันสำเร็จ!")
        
        # [แก้ไข] คืนค่า List ของ stems ที่ประมวลผลสำเร็จ
        return output_stems 
        
    except subprocess.CalledProcessError as e:
        st.error(f"Pipeline ล้มเหลว (V1):\n{e.stderr}")
        st.code(e.stdout, language="log") 
        log.error(f"run_all.py failed: {e.stderr}")
        return [] # คืนค่า List ว่าง
    except FileNotFoundError:
        st.error(f"ไม่พบสคริปต์ '{RUN_ALL_SCRIPT}' หรือไฟล์ผลลัพธ์ (metrics.json/scores.csv)")
        log.error(f"Script or output file not found: {RUN_ALL_SCRIPT}")
        return [] # คืนค่า List ว่าง

# ==================================================================
# --- [ส่วนที่ 3: UI ของหน้า 1 (ปรับปรุงสำหรับ Batch Upload)] ---
# ==================================================================

if "v1_metrics" not in st.session_state: st.session_state.v1_metrics = None
if "v1_scores_df" not in st.session_state: st.session_state.v1_scores_df = None
# [ใหม่] เพิ่ม State สำหรับเก็บ Stems ที่เพิ่งประมวลผล
if "v1_processed_stems" not in st.session_state: st.session_state.v1_processed_stems = []

st.title("Unified Candidate Brief (UCB) Upload & Ingestion")
st.markdown("อัปโหลดเรซูเม่ (PDF/DOCX)") #**หลายไฟล์พร้อมกัน** เพื่อสั่งรัน `run_all.py` (ระบบ Batch V1)

with st.expander("อัปโหลดและตั้งค่า", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        # [แก้ไข] เปลี่ยนเป็น accept_multiple_files=True
        uploaded_files = st.file_uploader(
            "อัปโหลดเรซูเม่ (รองรับหลายไฟล์)", 
            type=["pdf", "docx"], 
            accept_multiple_files=True 
        )
        lang = st.radio(
            "ภาษา OCR (สำหรับ PDF รูปภาพ)", 
            ["eng", "eng+tha"], index=1, horizontal=True
        )
    with col2:
        st.subheader("Job Description (JD)")
        st.caption("เลือก 1 วิธี (JD นี้จะใช้กับเรซูเม่ 'ทุกไฟล์' ที่อัปโหลด)")
        
        # [แก้ไข] Logic การสแกนไฟล์ JD (ลบ "None" ที่เป็น String ออก)
        try:
            if JD_TEMPLATE_DIR.is_dir():
                scanned_files = sorted([f.name for f in JD_TEMPLATE_DIR.glob("*.yml")])
                jd_files = scanned_files # <-- List ที่จะแสดงใน dropdown
                
                if not jd_files:
                    st.warning(f"ไม่พบไฟล์ .yml ในโฟลเดอร์: {JD_TEMPLATE_DIR}")
                    default_index = 0
                else:
                    # หา 'generic.yml' เพื่อตั้งเป็น Default
                    default_profile = "generic.yml"
                    if default_profile in jd_files:
                        default_index = jd_files.index(default_profile)
                    else:
                        default_index = 0 # ใช้ไฟล์แรกสุดเป็น Default
            else:
                 st.error(f"ไม่พบโฟลเดอร์ JD: {JD_TEMPLATE_DIR}")
                 jd_files = [] # List ว่าง
                 default_index = 0
        except Exception as e:
            jd_files = [] # List ว่าง
            default_index = 0
            st.error(f"ไม่สามารถสแกนโฟลเดอร์ JD: {e}")

        tab_template, tab_text = st.tabs(["เลือกจาก Template", "วางข้อความ JD"])
        with tab_template:
            # [แก้ไข] ลบ "None" ออกจาก options
            jd_template_select_value = st.selectbox(
                "เลือก Template (แนะนำ)", 
                options=jd_files, # <-- ใช้ List ที่ไม่มี "None"
                index=default_index 
            )
        with tab_text:
            jd_text_input_value = st.text_area(
                "วางข้อความ JD ดิบ (ทางเลือก)", 
                placeholder="วางข้อความ JD ดิบๆ ที่นี่...",
                height=150
            )
        
        # [แก้ไข] Logic การสลับแท็บแบบใหม่ (ตรวจสอบ Text Area)
        # เราจะยึด Text Area เป็นหลัก
        if jd_text_input_value.strip():
            # ถ้าผู้ใช้พิมพ์ใน Text Area ให้ใช้โหมด Text
            jd_tab_choice = "Text"
            jd_template_select = None # บังคับให้ Template เป็น None (ของ Python)
            jd_input_text = jd_text_input_value
        else:
            # ถ้า Text Area ว่าง ให้ใช้โหมด Template
            jd_tab_choice = "Template"
            jd_template_select = jd_template_select_value # ใช้ค่าจาก Dropdown
            jd_input_text = "" # Text Area ว่าง

with st.container(border=True):
    st.subheader("ตัวเลือก (จาก run_all.py)")
    col_t1, col_t2 = st.columns(2)
    pass_threshold = col_t1.slider("เกณฑ์คะแนนผ่าน V1", 0, 100, 70, 5)
    redact_pii = col_t2.checkbox("ปิดบังข้อมูลส่วนตัว (Redact PII)", value=True)

# [แก้ไข] เปลี่ยน disabled logic
if st.button("เริ่มประมวลผล (Run Ingestion)", type="primary", use_container_width=True, disabled=(not uploaded_files)):
    with st.spinner(f"กำลังรัน Ingestion Pipeline สำหรับ {len(uploaded_files)} ไฟล์..."): # [แก้ไข]
        # [แก้ไข] รับค่า stems ที่ประมวลผลแล้ว
        processed_stems = run_pipeline(
            uploaded_files=uploaded_files, # [แก้ไข]
            jd_tab_choice=jd_tab_choice,
            jd_template_file=jd_template_select,
            jd_input_text=jd_input_text,
            pass_threshold=pass_threshold, 
            lang=lang, 
            redact=redact_pii
        )
        # [แก้ไข] บันทึก Stems ลง Session State
        st.session_state.v1_processed_stems = processed_stems
        # (Streamlit จะ Rerun 1 ครั้งหลังปุ่ม)
        
st.divider()
st.subheader("Ingestion Result") #(V1 Scoring)
st.caption("ข้อมูลนี้มาจาก `metrics.json` และ `scores.csv` ที่ `run_all.py` สร้างขึ้น")

if st.session_state.v1_metrics:
    m = st.session_state.v1_metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ไฟล์ที่ประมวลผล (Total)", m.get("total", 0))
    c2.metric("สำเร็จ (OK)", m.get("ok", 0))
    c3.metric("คะแนนเฉลี่ย (Average Fit)", f"{m.get('avg_fit', 0)} %")
    c4.metric("เวลา (ms)", m.get("elapsed_ms", 0))
    
if st.session_state.v1_scores_df is not None:
    if not st.session_state.v1_scores_df.empty:
        st.dataframe(st.session_state.v1_scores_df, use_container_width=True)
    else:
        log.info("v1_scores_df is empty, not displaying dataframe.")
else:
    st.info("ผลลัพธ์ V1 (metrics/scores) จะแสดงที่นี่หลังจากรัน Pipeline")

# --- [แก้ไข] แสดง Skills Card Report สำหรับไฟล์ที่เพิ่งอัปโหลด ---
st.markdown("---")
st.subheader("Skills Card Reports") #(ไฟล์ที่เพิ่งอัปโหลด)

if st.session_state.v1_processed_stems:
    st.success(f"แสดงผลลัพธ์สำหรับ {len(st.session_state.v1_processed_stems)} ไฟล์ ที่เพิ่งประมวลผล:")
    
    # วนลูปแสดง Skills Card ของแต่ละไฟล์
    for stem in st.session_state.v1_processed_stems:
        st.markdown(f"---") # คั่นระหว่างการ์ด
        ucb_data = load_ucb_json(stem)
        
        if ucb_data:
            ucb = ucb_data
            reasons_data = ucb.get('reasons', {})
            gaps_data = ucb.get('gaps', {})
            
            # [แก้ไข] ตรวจสอบ Type (เผื่อไฟล์เก่า/เสียหาย)
            if isinstance(reasons_data, dict):
                matched_skills = (
                    reasons_data.get('required_hit', []) + 
                    reasons_data.get('nice_hit', [])
                )
            else: matched_skills = []

            if isinstance(gaps_data, dict):
                missing_skills = (
                    gaps_data.get('required_miss', []) + 
                    gaps_data.get('nice_miss', [])
                )
            else: missing_skills = []
            
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

            # (นี่คือ UI การ์ดที่คัดลอกมาจากเวอร์ชัน Single File)
            with st.container(border=True):
                col_name, col_score = st.columns([3, 1])
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
                    st.markdown(f"**<span style='color: #28a745;'> Matched Skills ({len(matched_skills)})</span>**", unsafe_allow_html=True)
                    st.html(render_skill_pills(matched_skills, "green"))
                
                with col_miss:
                    st.markdown(f"**<span style='color: #dc3545;'> Missing Skills ({len(missing_skills)})</span>**", unsafe_allow_html=True)
                    st.html(render_skill_pills(missing_skills, "red"))
                    
                if other_skills_filtered:
                    st.markdown("---")
                    st.markdown(f"**ทักษะอื่นๆ ที่พบในเรซูเม่ ({len(other_skills_filtered)})**")
                    st.html(render_skill_pills(other_skills_filtered, "blue"))
        else:
            st.error(f"ไม่สามารถโหลด Skills Card สำหรับไฟล์: {stem}.json")

else:
    st.info("รายละเอียด Skills Card จะแสดงที่นี่หลังจากรัน Pipeline สำเร็จ")