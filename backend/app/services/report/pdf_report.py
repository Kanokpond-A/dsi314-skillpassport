# backend/app/services/report/pdf_report.py
from fpdf import FPDF
from io import BytesIO
from typing import Dict, List

TITLE = "UCB Summary Report"

def _line(pdf: FPDF, text: str, ln: int = 1):
    pdf.cell(0, 8, txt=text, ln=ln)

def build_ucb_pdf(name: str, hr_view: Dict) -> BytesIO:
    """
    สร้าง PDF จาก hr_view ของ score_applicant()
    Return: BytesIO พร้อมอ่าน (seek(0) แล้ว)
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Header
    pdf.set_font("Arial", "B", 16)
    _line(pdf, TITLE, ln=1)
    pdf.ln(2)

    # Candidate summary
    pdf.set_font("Arial", "", 12)
    _line(pdf, f"Name: {name}")
    _line(pdf, f"Score: {hr_view['score']}  ({hr_view['level']})")
    s = hr_view["summary"]
    _line(pdf, f"Matched %: {s['matched_percent']}%")
    _line(pdf, f"Evidence: {s['evidence_count']} item(s), bonus +{s['evidence_bonus']} pts")
    pdf.ln(2)

    # Skills
    matched = ", ".join(s.get("matched_skills", [])) or "-"
    missing = ", ".join(s.get("missing_skills", [])) or "-"
    _line(pdf, f"Matched Skills: {matched}")
    _line(pdf, f"Missing Skills: {missing}")
    pdf.ln(2)

    # Missing detail table
    detail: List[dict] = s.get("missing_skills_detail", [])
    if detail:
        pdf.set_font("Arial", "B", 12)
        _line(pdf, "Missing Skills Detail")
        pdf.set_font("Arial", "", 11)
        for row in detail:
            _line(pdf, f"- {row['skill']} "
                       f"(impact ~{row['impact_points']} pts): {row['recommendation']}")
        pdf.ln(1)

    # Notes
    notes = hr_view.get("notes", [])
    if notes:
        pdf.set_font("Arial", "B", 12)
        _line(pdf, "Notes")
        pdf.set_font("Arial", "", 11)
        for n in notes:
            _line(pdf, f"- {n}")

    # Output
    buf = BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf
