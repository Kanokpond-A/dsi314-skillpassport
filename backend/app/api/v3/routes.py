from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.app.services.parsers.gemini_parser import parse_with_gemini
from backend.app.services.scoring.scoring import (
    calculate_universal_score,
    get_default_weights,
)

router = APIRouter(prefix="/api/v3")

@router.post("/ucb/from-pdf")
async def ucb_from_pdf(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    file_bytes = await file.read()

    # 1) ส่ง PDF → Gemini Parser
    parsed_resume = parse_with_gemini(file_bytes)
    if not parsed_resume:
        raise HTTPException(status_code=500, detail="Gemini parsing failed.")

    # 2) คำนวณคะแนนด้วย logic
    weights = get_default_weights()
    score_result = calculate_universal_score(parsed_resume, weights)

    # 3) ส่งกลับ frontend
    return {
        "parsed_resume": parsed_resume,
        "score": score_result
    }
