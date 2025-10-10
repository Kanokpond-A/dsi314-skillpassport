from fpdf import FPDF
from fastapi.responses import StreamingResponse
from io import BytesIO

@app.post("/ucb-pdf")
async def ucb_pdf(payload: UCBPayload):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=14)
    pdf.cell(0, 10, txt=f"UCB for: {payload.name}", ln=1)
    pdf.cell(0, 10, txt=f"Skills: {', '.join(payload.skills)}", ln=1)
    pdf.cell(0, 10, txt=f"Fit score: {payload.fit_score}", ln=1)
    if payload.gaps:
        pdf.cell(0, 10, txt=f"Gaps: {', '.join(payload.gaps)}", ln=1)
    buf = BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition":"inline; filename=ucb.pdf"})
