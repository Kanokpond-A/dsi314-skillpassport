from fpdf import FPDF
from io import BytesIO
from typing import Dict, List
import math
import tempfile
import os

# (Import Matplotlib)
try:
    import matplotlib
    matplotlib.use('Agg') # ใช้ Agg backend ซึ่งไม่ต้องใช้ GUI
    import matplotlib.pyplot as plt
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    print("WARNING: Matplotlib or Numpy not found. Radar chart in PDF will be skipped.")
    MATPLOTLIB_AVAILABLE = False


TITLE = "UCB Summary Report"

# --- ฟังก์ชันช่วย ---
def set_section_style(pdf: FPDF, level: int = 1):
    if level == 1: pdf.set_font("Arial", "B", 14); pdf.set_text_color(34, 47, 62)
    else: pdf.set_font("Arial", "B", 12); pdf.set_text_color(44, 62, 80)

def set_body_style(pdf: FPDF):
    pdf.set_font("Arial", "", 11); pdf.set_text_color(52, 73, 94)

def draw_line(pdf: FPDF):
    pdf.set_draw_color(223, 230, 233)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + pdf.w - 2 * pdf.l_margin, pdf.get_y())
    pdf.ln(2)

def _line(pdf: FPDF, text: str, ln: int = 1):
    """
    เขียน 1 บรรทัด โดย encode แบบ latin-1 (แทนที่ตัวอักษรที่ FPDF ไม่รู้จักด้วย '?')
    (fpdf2 จริงๆ รองรับ UTF-8 ถ้า add_font uni=True แต่ Arial ไม่มี)
    """
    try:
        safe_text = str(text).encode('latin-1', 'replace').decode('latin-1')
        pdf.cell(0, 8, txt=safe_text, ln=ln)
    except Exception as e:
        print(f"[PDF Error] Failed to write line: {e}")
        pdf.cell(0, 8, txt="[Error rendering line]", ln=ln)

def write_bullet_item(pdf: FPDF, text: str):
     """เขียนข้อความแบบมี bullet point (ใช้ - แทน •)"""
     bullet = "-" # ใช้ขีดที่ปลอดภัย
     try:
         safe_text = str(text).encode('latin-1', 'replace').decode('latin-1')
         pdf.cell(5, 8, txt=bullet, align="C") # ใช้ขีด
         pdf.multi_cell(0, 8, txt=safe_text) # multi_cell สำหรับข้อความยาว
     except Exception as e: 
         print(f"[-] Error in write_bullet_item: {e}")
         try:
              pdf.cell(5, 8, txt="-", align="C")
              pdf.multi_cell(0, 8, txt="[Error displaying item]")
         except: pass 


# --- ฟังก์ชันสร้างกราฟ Radar ---
def create_radar_chart_image(score_components: Dict) -> str | None:
    if not MATPLOTLIB_AVAILABLE:
        print("[Chart] Matplotlib not available. Skipping chart.")
        return None
    
    # (แก้ไข) ตรวจสอบ `score_components`
    if not score_components or not isinstance(score_components, dict) or len(score_components) < 3:
        print(f"[Chart] Not enough data for radar chart (need >= 3, got {len(score_components)}).")
        return None

    # (บังคับลำดับแกน)
    desired_order = ["Skills Match", "Experience", "Title Match", "Contact Info"]
    labels = []
    stats = []
    
    label_mapping_short = { # (ย่อชื่อสำหรับ PDF)
        "Skills Match": "Skills",
        "Experience": "Experience",
        "Title Match": "Title",
        "Contact Info": "Contacts"
    }

    # (แก้ไข) ใช้ไวยากรณ์ Python
    for key in desired_order:
        if key in score_components: # 👈 Pythonic check
             labels.append(label_mapping_short.get(key, key)) # 👈 .get(key)
             value = score_components.get(key) or 0 # 👈 .get(key)
             stats.append(max(0, min(1, value))) # 👈 Python's max/min
        else:
             labels.append(label_mapping_short.get(key, key))
             stats.append(0)
             print(f"[Chart] Warning: Key '{key}' not found in score_components.")

    if len(labels) < 3: 
        print("[Chart] Final labels < 3. Skipping chart.")
        return None

    num_vars = len(labels)
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    stats += stats[:1] # ปิดวงจร
    angles += angles[:1]
    
    fig = None 
    try:
        fig, ax = plt.subplots(figsize=(4, 4), subplot_kw=dict(polar=True)) # ลดขนาด
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels, fontsize=9)
        ax.set_yticks(np.arange(0, 1.1, 0.25)) # 0, 0.25, 0.5, 0.75, 1.0
        ax.set_yticklabels([f"{i*100:.0f}%" for i in np.arange(0, 1.1, 0.25)], fontsize=7, color="grey")
        ax.set_ylim(0, 1) # สเกล 0-1
        
        ax.plot(angles, stats, linewidth=1, linestyle='solid', color='blue')
        ax.fill(angles, stats, 'blue', alpha=0.3)
        
        ax.spines['polar'].set_visible(False)
        ax.grid(color='grey', linestyle='--', linewidth=0.5)

        # ใช้ tempfile.NamedTemporaryFile อย่างปลอดภัย
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
            fig_path = tmp_file.name
        
        fig.savefig(fig_path, format='png', dpi=90, bbox_inches='tight')
        plt.close(fig) # ปิด figure หลัง save
        print(f"[Chart] Saved radar chart image to: {fig_path}")
        return fig_path # คืนค่า Path

    except Exception as e:
        print(f"[-] Error creating radar chart image: {e}")
        if fig: plt.close(fig) 
        return None

# --- ฟังก์ชันสร้าง PDF หลัก ---
def build_ucb_pdf(name: str, hr_view: Dict) -> BytesIO:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_left_margin(15)
    pdf.set_right_margin(15)

    # --- Header ---
    set_section_style(pdf, level=1)
    _line(pdf, TITLE)
    pdf.ln(5)

    # --- Candidate summary ---
    set_section_style(pdf, level=2)
    _line(pdf, "Candidate Summary")
    draw_line(pdf)
    set_body_style(pdf)
    _line(pdf, f"Name: {name}")
    _line(pdf, f"Overall Score: {hr_view.get('score', 'N/A')} ({hr_view.get('level', 'N/A')})")
    s = hr_view.get("summary", {})
    _line(pdf, f"Skill Match Percentage: {s.get('matched_percent', 'N/A')}%")
    pdf.ln(5)

    # --- แทรกกราฟ Score Components ---
    components = hr_view.get("score_components")
    chart_image_path = None
    if components and isinstance(components, dict) and len(components) >= 3:
        set_section_style(pdf, level=2)
        _line(pdf, "Score Components Radar Chart")
        draw_line(pdf)
        set_body_style(pdf)
        
        chart_image_path = create_radar_chart_image(components) 
        
        if chart_image_path:
            try:
                img_width = pdf.w * 0.5 # ลดขนาดรูป
                pdf.image(chart_image_path, x=pdf.get_x() + (pdf.w - img_width - 2*pdf.l_margin)/2 , w=img_width)
                pdf.ln(5)
            except Exception as img_err:
                print(f"[-] Error embedding chart image: {img_err}")
                _line(pdf, "[Error displaying chart image]")
            finally:
                 if chart_image_path and os.path.exists(chart_image_path):
                     try: os.remove(chart_image_path); print(f"[Chart] Removed temporary image: {chart_image_path}")
                     except OSError as del_err: print(f"[-] Error removing temporary image {chart_image_path}: {del_err}")
        else:
             _line(pdf, "[Could not generate chart image (data < 3 points or Matplotlib error)]"); pdf.ln(5)
    
    # --- Skills Overview ---
    set_section_style(pdf, level=2)
    _line(pdf, "Skills Overview")
    draw_line(pdf)
    set_body_style(pdf)
    matched = ", ".join(s.get("matched_skills", [])) or "None found"
    missing = ", ".join(s.get("missing_skills", [])) or "None"
    _line(pdf, f"Matched Skills: {matched}")
    _line(pdf, f"Missing Must-Have Skills: {missing}")
    pdf.ln(5)

    # --- Missing Skills Detail ---
    detail: List[dict] = s.get("missing_skills_detail", [])
    if detail:
        set_section_style(pdf, level=2)
        _line(pdf, "Missing Skills Detail & Recommendations")
        draw_line(pdf)
        set_body_style(pdf)
        for row in detail:
            skill = row.get('skill', 'N/A')
            impact = row.get('impact_points', '?')
            rec = row.get('recommendation', 'N/A')
            write_bullet_item(pdf, f"{skill} (Impact: ~{impact} pts): {rec}")
        pdf.ln(5)

    # --- Notes ---
    notes = hr_view.get("notes", [])
    if notes:
        set_section_style(pdf, level=2)
        _line(pdf, "Notes & Observations")
        draw_line(pdf)
        set_body_style(pdf)
        for n in notes:
            write_bullet_item(pdf, n)
        pdf.ln(5)

    # === ✅✅✅ (แก้ไขส่วน Output - ใช้วิธีที่ 3) ✅✅✅ ===
    buf = None
    try:
        # (สำหรับ fpdf2 - เวอร์ชันใหม่)
        # 1. เรียก .output() เพื่อให้มันคืนค่าเป็น bytes
        pdf_bytes = pdf.output() 
        buf = BytesIO(pdf_bytes)
        
    except (AttributeError, TypeError):
        # (Fallback สำหรับ fpdf 1.7 - เวอร์ชันเก่า)
        # ใช้วิธีบันทึกลง Temp File แล้วอ่าน Bytes กลับมา
        print("[PDF Fallback] Using temporary file for old fpdf version.")
        pdf_file = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
                pdf_file = tmp_pdf.name
                pdf.output(pdf_file) # 👈 1.7 รองรับการเขียนลง file path
            
            with open(pdf_file, 'rb') as f: # 'rb' = read bytes
                pdf_bytes = f.read()
            
            buf = BytesIO(pdf_bytes) # 👈 สร้าง BytesIO จาก bytes ที่อ่านได้
        
        except Exception as e_fallback:
             print(f"[-] Error during PDF fallback output: {e_fallback}")
             raise e_fallback # โยน Error ต่อ
        finally:
            if pdf_file and os.path.exists(pdf_file):
                 try: os.remove(pdf_file); print(f"[PDF Fallback] Removed temp PDF: {pdf_file}")
                 except OSError: pass # ไม่เป็นไรถ้าลบไม่ได้

    except Exception as e_out:
         print(f"[-] Error during PDF output generation: {e_out}")
         raise e_out

    # --- 👆 สิ้นสุดการแก้ไข ---

    if buf:
        buf.seek(0)
        return buf
    else:
        # ถ้า buf ยังเป็น None (เกิด Error แปลกๆ)
        raise Exception("PDF buffer could not be created.")

