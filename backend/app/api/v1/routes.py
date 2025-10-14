from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from io import BytesIO
from fpdf import FPDF

router = APIRouter(prefix="/api/v1", tags=["v1"])

# ----- models (ย้ายไปไฟล์แยกก็ได้ภายหลัง) -----
class ParsedResume(BaseModel):
    name: str
    education: list = []
    skills: list = []
    evidence: list = []

class UCBPayload(BaseModel):
    name: str
    skills: list
    fit_score: float
    gaps: list
    evidence: list

# ----- endpoints -----
@router.get("/health")
def health():
    return {"status": "ok"}

@router.post("/parse-resume")
async def parse_resume(file: UploadFile | None = File(default=None)):
    sample = {
        "name": "Jane Doe",
        "education": [{"degree": "B.Eng", "year": 2023}],
        "skills": ["Python", "FastAPI", "SQL"],
        "evidence": [{"type": "pdf", "page": 2}]
    }
    return JSONResponse(sample)

@router.post("/score", response_model=UCBPayload)
async def score(parsed: ParsedResume):
    fit = min(1.0, 0.2 + 0.1 * len(parsed.skills))
    gaps = ["Docker"] if "Docker" not in parsed.skills else []
    return UCBPayload(
        name=parsed.name,
        skills=parsed.skills,
        fit_score=round(fit, 2),
        gaps=gaps,
        evidence=parsed.evidence
    )

@router.post("/ucb-pdf")
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
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline; filename=ucb.pdf"}
    )
