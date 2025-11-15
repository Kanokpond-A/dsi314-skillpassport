import streamlit as st
import pandas as pd
from pathlib import Path
import re
import time
import yaml
from typing import Dict, Any, List, Optional

# --- การตั้งค่า Path (สำหรับ Editor ทั้งสอง) ---
JD_TEMPLATE_DIR = Path("config/jd_profiles")
SKILLS_MASTER_PATH = Path("backend/app/services/A_backend/data/skills_master.csv")
SKILLS_FALLBACK_PATH = Path("backend/app/services/A_backend/data/skills.csv")

# ==================================================================
# --- [ส่วนที่ 1: HELPERS สำหรับ JD EDITOR (แท็บ 1)] ---
# ==================================================================

# --- Template เริ่มต้น (เปลี่ยนเป็น Dict) ---
DEFAULT_JD_DATA: Dict[str, Any] = {
    "title": "New Role",
    "title_keywords": ["new role"],
    "required": ["Python", "SQL"],
    "nice_to_have": ["Excel", "Power BI"],
    "weights": {
        "required": 60,
        "nice": 40
    }
}

def jd_get_files() -> list[str]:
    """สแกนหาไฟล์ .yml ทั้งหมดในโฟลเดอร์ JD"""
    if not JD_TEMPLATE_DIR.is_dir():
        JD_TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    files = [f.name for f in JD_TEMPLATE_DIR.glob("*.yml")]
    return sorted(files)

def jd_load_data(filename: str) -> Dict[str, Any]:
    """อ่านและ Parse เนื้อหา YAML จากไฟล์"""
    try:
        p = JD_TEMPLATE_DIR / filename
        with p.open('r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            if not isinstance(data, dict):
                st.error(f"ไฟล์ {filename} ไม่ใช่โครงสร้าง YAML ที่ถูกต้อง")
                return DEFAULT_JD_DATA.copy() # คืนค่า Default
            return data
    except Exception as e:
        st.error(f"ไม่สามารถอ่านไฟล์ {filename}: {e}")
        return DEFAULT_JD_DATA.copy() # คืนค่า Default

# [อัปเกรด] แก้ไขให้ return True/False
def jd_save_data(filename: str, data: Dict[str, Any]) -> bool:
    """บันทึก Dict ลงในไฟล์ .yml (รับประกัน Syntax ถูกต้อง)"""
    if not filename.endswith(".yml"):
        st.error("ชื่อไฟล์ต้องลงท้ายด้วย .yml เสมอ")
        return False
    try:
        JD_TEMPLATE_DIR.mkdir(parents=True, exist_ok=True) # สร้างโฟลเดอร์ถ้ายังไม่มี
        p = JD_TEMPLATE_DIR / filename
        with p.open('w', encoding='utf-8') as f:
            yaml.dump(
                data, f, 
                allow_unicode=True, sort_keys=False, 
                default_flow_style=False, indent=2
            )
        st.success(f"บันทึกไฟล์ '{filename}' สำเร็จ!")
        time.sleep(0.5)
        st.cache_data.clear() # ล้าง Cache หน้าอื่น
        return True # [อัปเกรด] คืนค่า True
    except Exception as e:
        st.error(f"ไม่สามารถบันทึกไฟล์ {filename}: {e}")
        return False # [อัปเกรด] คืนค่า False

# [อัปเกรด] แก้ไขให้ return True/False
def jd_delete_file(filename: str) -> bool:
    """ลบไฟล์ .yml"""
    try:
        p = JD_TEMPLATE_DIR / filename
        p.unlink()
        st.success(f"ลบไฟล์ '{filename}' สำเร็จ!")
        time.sleep(0.5)
        st.cache_data.clear()
        return True # [อัปเกรด] คืนค่า True
    except Exception as e:
        st.error(f"ไม่สามารถลบไฟล์ {filename}: {e}")
        return False # [อัปเกรด] คืนค่า False

def jd_clean_filename(name: str) -> str:
    """ทำความสะอาดชื่อไฟล์ที่ผู้ใช้ป้อน"""
    name = re.sub(r'[^a-z0-9_.\-]+', '-', name.lower())
    if not name.endswith(".yml"):
        if not name: name = "new_role"
        name = f"{name}.yml"
    return name

# Helper แปลง List <-> Text
def list_to_text(data_list: List[str]) -> str:
    if not isinstance(data_list, list): return ""
    return "\n".join(data_list)
def text_to_list(text: str) -> List[str]:
    return [s.strip() for s in text.split("\n") if s.strip()]

# ==================================================================
# --- [ส่วนที่ 2: HELPERS สำหรับ ALIAS EDITOR (แท็บ 2)] ---
# ==================================================================

@st.cache_data
def alias_load_map() -> pd.DataFrame:
    """โหลด skills_master.csv"""
    use_path = SKILLS_MASTER_PATH
    if not use_path.exists():
        use_path = SKILLS_FALLBACK_PATH
        if not use_path.exists():
            return pd.DataFrame(columns=["alias", "canonical", "industry"])
    try:
        df = pd.read_csv(use_path, header=None) 
        if len(df.columns) >= 2:
            df = df.iloc[:, :3] 
            df.columns = ["alias", "canonical", "industry"][:len(df.columns)]
            if "canonical" not in df.columns: df["canonical"] = pd.NA
            if "industry" not in df.columns: df["industry"] = pd.NA
            df = df[~df['alias'].astype(str).str.startswith('#', na=False)]
            df['canonical'] = df['canonical'].fillna(df['alias'])
            return df 
        else:
            return pd.DataFrame(columns=["alias", "canonical", "industry"])
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการอ่าน {use_path}: {e}")
        return pd.DataFrame(columns=["alias", "canonical", "industry"])

def alias_save_map(df: pd.DataFrame):
    """บันทึก DataFrame กลับไปยัง skills_master.csv"""
    try:
        df_to_save = df.fillna("")
        SKILLS_MASTER_PATH.parent.mkdir(parents=True, exist_ok=True) # สร้างโฟลเดอร์ data
        df_to_save.to_csv(SKILLS_MASTER_PATH, index=False, header=False, encoding="utf-8")
        st.success(f"บันทึกไฟล์ '{SKILLS_MASTER_PATH.name}' สำเร็จ!")
        st.cache_data.clear()
        time.sleep(0.5)
    except Exception as e:
        st.error(f"ไม่สามารถบันทึกไฟล์ {SKILLS_MASTER_PATH.name}: {e}")

# ==================================================================
# --- [ส่วนที่ 3: UI หลัก (รวม 2 Editors)] ---
# ==================================================================

# [อัปเกรด] เพิ่มฟังก์ชัน Callback สำหรับการสร้างไฟล์
def create_new_file_callback():
    # 1. อ่านค่าจาก Text Input (ผ่าน st.session_state)
    new_file_name_input = st.session_state.get("new_jd_input", "")
    
    if new_file_name_input:
        new_filename = jd_clean_filename(new_file_name_input)
        
        # 2. ตรวจสอบว่าไฟล์ซ้ำหรือไม่
        jd_files = jd_get_files()
        if new_filename in jd_files:
            st.sidebar.error(f"ไฟล์ '{new_filename}' มีอยู่แล้ว!")
        else:
            # 3. บันทึกไฟล์
            if jd_save_data(new_filename, DEFAULT_JD_DATA.copy()):
                # 4. [สำคัญ] ตั้งค่า State ของ Selectbox (สำหรับรอบถัดไป)
                st.session_state.jd_editor_selectbox = new_filename
                # ล้างช่อง Text Input
                st.session_state.new_jd_input = "" 
    else:
        st.sidebar.warning("กรุณาป้อนชื่อไฟล์")

# [อัปเกรด] เพิ่มฟังก์ชัน Callback สำหรับการลบไฟล์
def delete_file_callback(filename_to_delete: str):
    if jd_delete_file(filename_to_delete):
        # [สำคัญ] รีเซ็ต Selectbox กลับไปที่ค่าเริ่มต้น
        st.session_state.jd_editor_selectbox = "-- เลือกไฟล์ที่จะแก้ไข --"

# --- [เริ่ม] UI ---
st.set_page_config(page_title="Settings Editor", layout="wide")
st.title("การตั้งค่า (Settings Editor)")
st.caption("แก้ไขไฟล์ Job Descriptions และ Skill Aliases ของระบบ")

tab_jd, tab_alias = st.tabs(["ตัวจัดการ Job Description (JD)", "ตัวจัดการ Skill Alias (พจนานุกรม)"])

# --- [แท็บที่ 1: JD EDITOR (อัปเกรดเป็น Form)] ---
with tab_jd:
    st.header("ตัวจัดการ Job Description")
    st.caption(f"แก้ไขไฟล์ .yml ใน: {JD_TEMPLATE_DIR}")
    st.info("โหมด Form Editor: แก้ไขข้อมูลในช่องด้านล่าง ระบบจะสร้าง YAML ที่ถูกต้องให้คุณอัตโนมัติ")

    # --- ส่วนควบคุม (Sidebar) ---
    st.sidebar.markdown("## 1. ควบคุม JD")
    jd_files = jd_get_files()
    if not jd_files:
        st.sidebar.info("ยังไม่มีไฟล์ JD ใดๆ")
        
    options = ["-- เลือกไฟล์ที่จะแก้ไข --"] + jd_files
    selected_file = st.sidebar.selectbox(
        "เลือก JD ที่มีอยู่:",
        options=options,
        key="jd_editor_selectbox"
    )
    st.sidebar.divider()
    st.sidebar.markdown("### สร้าง JD ใหม่")
    new_file_name_input = st.sidebar.text_input(
        "ป้อนชื่อไฟล์ใหม่ (เช่น data-scientist)",
        placeholder="new-role-name",
        key="new_jd_input" # [อัปเกรด] เพิ่ม Key
    )
    
    # [อัปเกรด] เปลี่ยนไปใช้ on_click
    st.sidebar.button(
        "สร้าง JD ใหม่",
        on_click=create_new_file_callback 
    )
            
    st.sidebar.divider()

    # --- ส่วนแสดงผล (Main Area) ---
    current_file = selected_file if selected_file != "-- เลือกไฟล์ที่จะแก้ไข --" else None

    if current_file:
        st.subheader(f"กำลังแก้ไข: `{current_file}`")
        data = jd_load_data(current_file)

        with st.form(key=f"editor_form_{current_file}"):
            st.markdown("##### 1. ข้อมูลทั่วไป (Title)")
            title = st.text_input("Title", value=data.get("title", ""))
            title_keywords = st.text_area(
                "Title Keywords (1 คำต่อ 1 บรรทัด)",
                value=list_to_text(data.get("title_keywords", []))
            )
            
            st.divider()
            st.markdown("##### 2. รายการ Skills (สำคัญ)")
            col_req, col_nice = st.columns(2)
            with col_req:
                required = st.text_area(
                    "Required Skills (1 Skill ต่อ 1 บรรทัด)",
                    value=list_to_text(data.get("required", [])),
                    height=250,
                    help="Skill ที่ 'ต้องมี' (เช่น Python, SQL)"
                )
            with col_nice:
                nice_to_have = st.text_area(
                    "Nice-to-Have Skills (1 Skill ต่อ 1 บรรทัด)",
                    value=list_to_text(data.get("nice_to_have", [])),
                    height=250,
                    help="Skill ที่ 'มีก็ดี' (เช่น Excel, Power BI)"
                )
                
            st.divider()
            st.markdown("##### 3. การให้น้ำหนัก (Weights)")
            weights_data = data.get("weights", {"required": 60, "nice": 40})
            
            req_weight = st.slider(
                "น้ำหนักของ Required Skills (%)", 
                0, 100, 
                weights_data.get("required", 60), 
                5,
                help="ระบบจะคำนวณน้ำหนัก Nice-to-Have ให้อัตโนมัติ"
            )
            nice_weight = 100 - req_weight
            st.text(f"น้ำหนักของ Nice-to-Have: {nice_weight}% (คำนวณอัตโนมัติ)")
            
            st.divider()
            submitted = st.form_submit_button("บันทึกการเปลี่ยนแปลง", type="primary")

        if submitted:
            new_data = {
                "title": title,
                "title_keywords": text_to_list(title_keywords),
                "required": text_to_list(required),
                "nice_to_have": text_to_list(nice_to_have),
                "weights": { "required": req_weight, "nice": nice_weight }
            }
            # [อัปเกรด] เราบันทึกใน Form Submit ได้เลย
            if jd_save_data(current_file, new_data):
                # (ไม่จำเป็นต้อง Rerun เพราะการบันทึกไม่ได้เปลี่ยน Selectbox)
                st.success("บันทึกข้อมูลสำเร็จ!")
            
        st.divider()
        with st.expander("ลบไฟล์ (Delete)"):
            st.warning(f"คุณแน่ใจหรือไม่ว่าต้องการลบ {current_file}?")
            # [อัปเกรด] เปลี่ยนไปใช้ on_click
            st.button(
                f"ยืนยันการลบ {current_file}", 
                type="secondary",
                on_click=delete_file_callback,
                args=(current_file,) # ส่งชื่อไฟล์เข้าไปใน Callback
            )
    else:
        st.info("กรุณาเลือกไฟล์ JD จากเมนูด้านซ้ายเพื่อเริ่มแก้ไข หรือสร้างไฟล์ใหม่")

# --- [แท็บที่ 2: ALIAS EDITOR (ย้ายโค้ดจากหน้า 4 มา)] ---
with tab_alias:
    st.header("ตัวจัดการ Skill Alias (พจนานุกรม Skill)")
    st.caption(f"แก้ไขไฟล์: {SKILLS_MASTER_PATH}")
    st.warning(
        "การแก้ไขไฟล์นี้จะส่งผลต่อการ 'Mining' Skill จากเรซูเม่ (ใน `scoring.py`)\n"
        "- **alias:** คำที่พบในเรซูเม่ (เช่น `Statistical analysis`, `powerbi`)\n"
        "- **canonical:** คำมาตรฐานที่ใช้เทียบกับ JD (เช่น `Statistics`, `Power BI`)\n"
        "- **industry:** (ไม่บังคับ)"
    )

    df_full = alias_load_map()
    if df_full.empty:
        st.info("ไม่พบข้อมูล Skill Map (skills_master.csv)")
        df_to_display = pd.DataFrame(columns=["alias", "canonical", "industry"])
    else:
        st.info(f"พบ Skill Aliases ทั้งหมด {len(df_full)} รายการ")
        df_to_display = df_full.copy()

    st.markdown("##### ค้นหา / กรอง Skill Alias")
    col_search, col_industry = st.columns(2)
    with col_search:
        search_term = st.text_input(
            "ค้นหา (Alias หรือ Canonical):",
            placeholder="เช่น python, sql, power bi...",
            key="alias_search" # Key ที่ไม่ซ้ำ
        )
    with col_industry:
        all_industries = sorted(list(
            df_to_display[df_to_display['industry'].notna() & (df_to_display['industry'].str.strip() != '')]['industry'].unique()
        ))
        selected_industries = st.multiselect(
            "กรองตาม Industry:",
            options=all_industries,
            placeholder="เลือก 1 Industry หรือมากกว่า",
            key="alias_industry_filter" # Key ที่ไม่ซ้ำ
        )

    is_filtered = False
    if search_term:
        df_to_display = df_to_display[
            df_to_display['alias'].str.contains(search_term, case=False, na=False) |
            df_to_display['canonical'].str.contains(search_term, case=False, na=False)
        ]
        is_filtered = True
    if selected_industries:
        df_to_display = df_to_display[
            df_to_display['industry'].isin(selected_industries)
        ]
        is_filtered = True
    if is_filtered:
        st.info(f"แสดงผล {len(df_to_display)} รายการ (จากทั้งหมด {len(df_full)})")

    st.markdown("##### แก้ไข Skill Alias Map")
    st.caption("คุณสามารถเพิ่มแถว (+), แก้ไข, หรือลบแถว (ถังขยะ) จากข้อมูลที่กรองแล้วได้")

    edited_df = st.data_editor(
        df_to_display.fillna(""), 
        num_rows="dynamic",
        use_container_width=True,
        key="alias_data_editor", # Key ที่ไม่ซ้ำ
        column_config={
            "alias": st.column_config.TextColumn("Alias (คำที่พบในเรซูเม่)", required=True),
            "canonical": st.column_config.TextColumn("Canonical (คำมาตรฐาน)", required=True),
            "industry": st.column_config.TextColumn("Industry (ไม่บังคับ)"),
        }
    )

    st.divider()
    if st.button("บันทึกการเปลี่ยนแปลง (skills_master.csv)", type="primary"):
        try:
            df_original = df_full.copy()
            original_seen_aliases = set(df_to_display['alias'].dropna())
            edited_seen_aliases = set(edited_df['alias'].dropna())
            deleted_aliases = original_seen_aliases - edited_seen_aliases
            
            unseen_aliases = set(df_original['alias'].dropna()) - original_seen_aliases
            df_unseen = df_original[df_original['alias'].isin(unseen_aliases)]
            
            df_final = pd.concat([df_unseen, edited_df])
            
            if df_final.empty and not df_original.empty and not is_filtered:
                st.error("การบันทึกนี้จะลบข้อมูลทั้งหมด! กรุณายกเลิก")
            elif df_final['alias'].isnull().any() or df_final['canonical'].isnull().any():
                st.error("กรุณากรอกข้อมูลในคอลัมน์ 'alias' และ 'canonical' ให้ครบทุกแถว")
            else:
                alias_save_map(df_final)
                st.rerun()

        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดระหว่างการ Merge ข้อมูล: {e}")