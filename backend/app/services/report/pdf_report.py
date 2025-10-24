# backend/app/services/report/pdf_report.py
from fpdf import FPDF
from io import BytesIO
from typing import Dict, List

TITLE = "UCB Summary Report"

def _line(pdf: FPDF, text: str, ln: int = 1):
    # (หมายเหตุ: FPDF มาตรฐานไม่รองรับภาษาไทย)
    # (เราจะพยายาม encode เป็น latin-1 และ 'ignore' (ลบ) อักษรที่ทำไม่ได้)
    try:
        # (!!!) แก้ไขตรงนี้ (!!!)
        # เปลี่ยนจาก 'replace' เป็น 'ignore' เพื่อลบอักษรไทยทิ้ง
        safe_text = text.encode('latin-1', 'ignore').decode('latin-1')
        pdf.cell(0, 8, txt=safe_text, ln=ln)
    except Exception as e:
        # (Fallback ในกรณีเกิด error อื่นๆ)
        print(f"[PDF Error] Failed to write line: {e}")
        pdf.cell(0, 8, txt="--- error rendering line ---", ln=ln)


def build_ucb_pdf(name: str, hr_view: Dict) -> BytesIO:
    """
    สร้าง PDF จาก hr_view ของ calculate_ucb_score()
    Return: BytesIO พร้อมอ่าน (seek(0) แล้ว)
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Header
    pdf.set_font("Arial", "B", 16)
    _line(pdf, TITLE, ln=1)
    pdf.ln(2)

    # --- (ส่วนที่แก้ไข 1: ทำให้ปลอดภัยขึ้น) ---
    pdf.set_font("Arial", "", 12)
    
    # ใช้ .get() เพื่อความปลอดภัย
    score = hr_view.get('score', 'N/A')
    level = hr_view.get('level', 'N/A')
    s = hr_view.get("summary", {}) # <--- .get() ที่นี่
    
    _line(pdf, f"Name: {name}")
    _line(pdf, f"Score: {score}  ({level})")
    
    # ใช้ .get() ที่นี่ด้วย
    matched_pct = s.get('matched_percent', 0.0)
    _line(pdf, f"Skill Match: {matched_pct}%")
    
    
    # --- (ส่วนที่แก้ไข 2: แทนที่บรรทัดที่พัง) ---
    
    # (ลบบรรทัด 'evidence_count' และ 'evidence_bonus' ที่พังออก)
    # _line(pdf, f"Evidence: {s['evidence_count']} item(s), bonus +{s['evidence_bonus']} pts")
    
    # (เพิ่มส่วนใหม่ที่อ่านจาก score_components)
    pdf.ln(2) 
    pdf.set_font("Arial", "B", 12)
    _line(pdf, "Score Components:")
    pdf.set_font("Arial", "", 11)
    
    components = hr_view.get("score_components", {})
    
    # ดึงค่าจาก Key ที่ตรงกับกราฟ Radar (และ .get() เพื่อความปลอดภัย)
    skill_pct = components.get("Skills Match", 0.0) * 100
    exp_pct = components.get("Experience", 0.0) * 100
    title_pct = components.get("Title Match", 0.0) * 100
    contact_pct = components.get("Contact Info", 0.0) * 100

    _line(pdf, f"- Skills Match: {skill_pct:.0f}%")
    _line(pdf, f"- Experience: {exp_pct:.0f}%")
    _line(pdf, f"- Title Match: {title_pct:.0f}%")
    _line(pdf, f"- Contact Info: {contact_pct:.0f}%")
    pdf.ln(2)
    
    # --- (สิ้นสุดส่วนที่แก้ไข) ---


    # Skills (ใช้ .get() เพื่อความปลอดภัย)
    pdf.set_font("Arial", "B", 12)
    matched = ", ".join(s.get("matched_skills", [])) or "-"
    missing = ", ".join(s.get("missing_skills", [])) or "-"
    _line(pdf, f"Matched Skills: {matched}")
    _line(pdf, f"Missing Skills: {missing}")
    pdf.ln(2)

    # Missing detail table (ส่วนนี้ดูโอเคแล้ว)
    detail: List[dict] = s.get("missing_skills_detail", []) # <--- Frontend อาจจะยังไม่มีส่วนนี้
    if detail:
        pdf.set_font("Arial", "B", 12)
        _line(pdf, "Missing Skills Detail")
        pdf.set_font("Arial", "", 11)
        for row in detail:
            _line(pdf, f"- {row.get('skill', 'N/A')} "
                       f"(impact ~{row.get('impact_points', 0)} pts): {row.get('recommendation', '-')}")
        pdf.ln(1)

    # Notes
    notes = hr_view.get("notes", [])
    if notes:
        pdf.set_font("Arial", "B", 12)
        _line(pdf, "Notes")
        pdf.set_font("Arial", "", 11)
        for n in notes:
            _line(pdf, f"- {n}")

    # --- (ส่วนที่แก้ไข) ---
    # Output
    buf = BytesIO()
    
    # 1. เรียก .output() เพื่อให้มันคืนค่าเป็น String
    pdf_data_str = pdf.output() 
    
    # 2. แปลง String เป็น Bytes โดยใช้ .encode('latin-1')
    pdf_data_bytes = pdf_data_str.encode('latin-1')

    # 3. เขียน bytes ลงใน buf
    buf.write(pdf_data_bytes)
    
    # 4. ย้าย seek(0) มาไว้หลังเขียน
    buf.seek(0)
    return buf