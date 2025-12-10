from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
import shutil
from pathlib import Path

from backend.app.services.database import get_db, CandidateDB
from backend.app.services.parsers.gemini_parser import parse_with_gemini
from backend.app.services.scoring.scoring import calculate_universal_score
import backend.app.services.jd_manager as jd_manager
from pydantic import BaseModel

router = APIRouter(prefix="/api/v3")

# Path สำหรับบันทึกไฟล์ PDF (ต้องตรงกับ main.py)
# ใช้วิธีหา path แบบ relative เพื่อความชัวร์
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent # ถอยไป backend
STATIC_RESUMES_DIR = BASE_DIR / "static" / "resumes"
STATIC_RESUMES_DIR.mkdir(parents=True, exist_ok=True)

class JobProfile(BaseModel):
    title: str
    description: str

# ==========================================
# 1. API เดิม (เพิ่มการบันทึกข้อมูล)
# ==========================================
@router.post("/ucb/from-pdf")
async def process_pdf(
    file: UploadFile = File(...),
    job_description: str = Form(""),
    job_title: str = Form("General Candidate"),
    db: Session = Depends(get_db) # ✅ Inject DB ตรงนี้เลย
):
    try:
        # 1. Save File to Disk (สำคัญมาก ไม่งั้นไฟล์หาย)
        file_location = STATIC_RESUMES_DIR / file.filename
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Reset cursor ของไฟล์เพื่อให้ Gemini อ่านต่อได้
        file.file.seek(0)
        file_content = await file.read()
        
        # 2. AI Parsing
        parsed_resume = parse_with_gemini(file_content)
        if not parsed_resume:
             raise HTTPException(status_code=400, detail="Failed to parse resume PDF")

        # 3. Scoring
        score_result = calculate_universal_score(
            parsed_data=parsed_resume, 
            weights_config={},  
            job_description_text=job_description 
        )

        # 4. Prepare Response
        final_response = {
            "filename": file.filename,
            "parsed_resume": parsed_resume,
            "score": score_result, 
            "job_title": job_title
        }

        # 5. Save to DB
        try:
            c_info = parsed_resume.get("candidate_info", {})
            new_candidate = CandidateDB(
                filename=file.filename,
                candidate_name=c_info.get("name", "Unknown"),
                email=c_info.get("email", ""),
                phone=c_info.get("phone", ""),
                final_score=score_result.get("final_score", 0),
                full_json_data=final_response
            )
            db.add(new_candidate)
            db.commit()
            db.refresh(new_candidate)
            
            # ใส่ ID กลับไปให้ Frontend ใช้
            final_response["db_id"] = new_candidate.id
            
        except Exception as db_e:
            db.rollback()
            print(f"❌ Database Error: {db_e}")

        return final_response

    except Exception as e:
        print(f"Error process_pdf: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 2. API ใหม่สำหรับ Warehouse (ดึงประวัติ)
# ==========================================
@router.get("/ucb/history")
def get_candidate_history(db: Session = Depends(get_db)):
    try:
        candidates = db.query(CandidateDB).order_by(CandidateDB.created_at.desc()).all()
        results = []
        for c in candidates:
            data = c.full_json_data if c.full_json_data else {}
            resume = data.get("parsed_resume", {})
            c_info = resume.get("candidate_info", {})
            skills = resume.get("skills", {})
            
            # ดึง job_title จาก JSON ถ้ามี
            job_title = data.get("job_title", "General Candidate")

            results.append({
                "candidate_id": c.candidate_name or "Unknown",
                "db_id": c.id,
                "filename": c.filename,
                "job_title": job_title, # ส่งกลับไปด้วย
                "matching": c.final_score or 0,
                "headline": c.email or "No Email",
                "skills": {
                    "normalized": skills.get("hard_skills", [])
                },
                "gaps": [],
                "created_at": c.created_at,
                "raw_data": data
            })
        return results
    except Exception as e:
        print(f"❌ Error fetching history: {e}")
        return []

# ==========================================
# 3. API สำหรับลบข้อมูล
# ==========================================
@router.delete("/ucb/history/all")
def delete_all_candidates(db: Session = Depends(get_db)):
    try:
        num_deleted = db.query(CandidateDB).delete()
        db.commit()
        return {"detail": f"Deleted {num_deleted} candidates"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/ucb/history/{db_id}")
def delete_candidate(db_id: int, db: Session = Depends(get_db)):
    candidate = db.query(CandidateDB).filter(CandidateDB.id == db_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    db.delete(candidate)
    db.commit()
    return {"detail": "Deleted successfully"}

# ==========================================
@router.get("/jobs")
async def get_job_profiles():
    return jd_manager.get_all_jobs()

@router.post("/jobs")
async def save_job_profile(job: JobProfile):
    try:
        saved_data = jd_manager.save_job(job.title, job.description)
        return {"message": "Job saved successfully", "data": saved_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))