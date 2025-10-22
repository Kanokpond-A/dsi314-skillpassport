# === 1. IMPORT เครื่องมือที่จำเป็น ===
import tempfile
import subprocess
import sys
import os
import json
from pathlib import Path  # 👈 (แก้ไข: เพิ่มบรรทัดนี้เข้ามา)
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from io import BytesIO
from fpdf import FPDF
from backend.app.services.scoring import score_applicant, ScoringConfig
from backend.app.services.report.pdf_report import build_ucb_pdf
from backend.app.services.analytics.summary import build_summary
from backend.app.core.privacy import redact_payload
from fastapi import Query

# === 2. IMPORT ตัวทำความสะอาดสกิล (ใช้ Path ที่ถูกต้อง) ===
from backend.app.services.parser_a1.normalize_scoring.skills_normalizer import normalize_skills

# === 3. กำหนด Path ไปยัง Root ของโปรเจกต์ ===
# (สมมติว่า routes.py อยู่ลึก 4 ระดับจาก dsi314-skillpassport)
ROOT_DIR = Path(__file__).resolve().parents[4]

# === 4. กำหนด Path ไปยังสคริปต์เครื่องมือ (ใช้ Path ที่ถูกต้อง) ===
PDF_PARSER_SCRIPT = ROOT_DIR / "backend/app/services/parser_a1/parsers/pdf_parser.py"
STRUCTURE_BUILDER_SCRIPT = ROOT_DIR / "backend/app/services/parser_a1/preprocess/structure_builder.py"


router = APIRouter(prefix="/api/v1", tags=["v1"])


# ----- 5. Class Models -----
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
    
    file_bytes = await file.read()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_pdf_path = os.path.join(tmpdir, "uploaded.pdf")
        tmp_raw_json_path = os.path.join(tmpdir, "raw.json")
        tmp_parsed_json_path = os.path.join(tmpdir, "parsed.json")

        try:
            with open(tmp_pdf_path, "wb") as f:
                f.write(file_bytes)

            subprocess.run(
                [sys.executable, str(PDF_PARSER_SCRIPT), "--in", tmp_pdf_path, "--out", tmp_raw_json_path, "--lang", "eng"],
                check=True, capture_output=True, text=True, encoding='utf-8'
            )

            subprocess.run(
                [sys.executable, str(STRUCTURE_BUILDER_SCRIPT), "--in", tmp_raw_json_path, "--out", tmp_parsed_json_path],
                check=True, capture_output=True, text=True, encoding='utf-8'
            )

            with open(tmp_parsed_json_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

        except subprocess.CalledProcessError as e:
            print("Stderr:", e.stderr)
            print("Stdout:", e.stdout)
            return JSONResponse(status_code=500, content={"error": "Failed to process file", "details": e.stderr})
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": str(e)})

    clean_skills = normalize_skills(raw_data.get("skills", []))
    
    real_data = {
        "name": raw_data.get("name"),
        "education": raw_data.get("education", []),
        "skills": clean_skills,
        "evidence": raw_data.get("evidence", [])
    }
    
    return real_data

@router.post("/ucb")
async def ucb_json(parsed: ParsedResume):
    data = redact_payload(parsed.model_dump())
    result = score_applicant(data.get("skills", []), data.get("evidence", []), ScoringConfig())
    hr = result["hr_view"]
    return {
        "name": parsed.name,
        "score": hr["score"],
        "level": hr["level"],
        "summary": hr["summary"],
        "breakdown": hr["breakdown"],
    }

@router.post("/ucb-pdf")
async def ucb_pdf_endpoint(parsed: ParsedResume):
    data = redact_payload(parsed.model_dump())
    result = score_applicant(data.get("skills", []), data.get("evidence", []), ScoringConfig())
    hr = result["hr_view"]
    buf = build_ucb_pdf(data.get("name","Unknown"), hr)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{data.get("name","Candidate")}_UCB.pdf"'}
    )

@router.post("/score")
async def score(parsed: ParsedResume):
    result = score_applicant(parsed.skills, parsed.evidence, ScoringConfig())
    mv = result["machine_view"]
    return {
        "name": parsed.name,
        "skills": parsed.skills,
        "fit_score": mv["fit_score"],
        "gaps": mv["gaps"],
        "evidence": parsed.evidence
    }

@router.post("/score-hr")
async def score_hr(parsed: ParsedResume):
    result = score_applicant(parsed.skills, parsed.evidence, ScoringConfig())
    hr = result["hr_view"]
    return {
        "name": parsed.name,
        "score": hr["score"],
        "level": hr["level"],
        "summary": hr["summary"],
        "breakdown": hr["breakdown"],
        "notes": hr["notes"]
    }

@router.get("/summary")
def summary(
    refresh: bool = Query(False, description="true = คำนวณใหม่, false = ใช้ cache"),
    limit: int | None = Query(None, ge=1, description="จำกัดจำนวนแถว candidates")
):
    return build_summary(refresh=refresh, limit=limit)

