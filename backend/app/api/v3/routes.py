from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List

# Import ไฟล์ database ที่เราเพิ่งสร้าง
from backend.app.services.database import get_db, CandidateDB
from backend.app.services.parsers.gemini_parser import parse_with_gemini, analyze_match_with_gemini
from backend.app.services.scoring.scoring import calculate_universal_score, get_default_weights
import backend.app.services.jd_manager as jd_manager
from pydantic import BaseModel

router = APIRouter(prefix="/api/v3")

class JobProfile(BaseModel):
    title: str
    description: str


# ==========================================
# 1. API เดิม (เพิ่มการบันทึกข้อมูล)
# ==========================================
@router.post("/ucb/from-pdf")
async def ucb_from_pdf(
    file: UploadFile = File(...), 
    job_description: str = Form(None), # รับค่ามาเช็คเองข้างใน
    db: Session = Depends(get_db)
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # 🛑 2. เพิ่ม Logic บังคับ JD ตรงนี้
    if not job_description or len(job_description.strip()) < 10:
        raise HTTPException(
            status_code=400, 
            detail="Job Description is required for analysis."
        )

    file_bytes = await file.read()

    try:
        # ระบุตำแหน่งไฟล์: backend/static/resumes/ชื่อไฟล์.pdf
        save_path = f"backend/static/resumes/{file.filename}"
        with open(save_path, "wb") as f:
            f.write(file_bytes)
        print(f"✅ Saved resume to: {save_path}")
    except Exception as e:
        print(f"⚠️ Failed to save resume file: {e}")

    # 1) Parse
    parsed_resume = parse_with_gemini(file_bytes)
    if not parsed_resume:
        raise HTTPException(status_code=500, detail="Gemini parsing failed.")

    # 2) Matching
    match_result = {}
    if job_description and len(job_description) > 10:
        # ส่งไปให้ AI เทียบกันเลย
        match_result = analyze_match_with_gemini(parsed_resume, job_description)
    else:
        # ถ้าไม่มี JD ก็ใช้คะแนนกลางๆ (Universal Score) ไปก่อน
        weights = get_default_weights()
        base_score = calculate_universal_score(parsed_resume, weights)
        match_result = {
            "match_percentage": base_score['final_score'],
            "matched_reasons": ["(No Job Description provided for detailed matching)"],
            "missing_gaps": []
        }

    # 3) Result Compilation
    final_response = {
        "parsed_resume": parsed_resume,
        "score": {
            "final_score": match_result.get("match_percentage", 0),
            # ส่งรายละเอียด Matched/Gap ไปให้ Frontend แสดงในการ์ด
            "analysis": match_result 
        }
    }

    # 🔥 4) บันทึกลง Database (SQL) 🔥
    # แก้ไข Logic ตรงนี้ให้ปลอดภัยขึ้น
    try:
        c_info = parsed_resume.get("candidate_info", {})
        
        new_candidate = CandidateDB(
            filename=file.filename,
            candidate_name=c_info.get("name", "Unknown"),
            email=c_info.get("email", ""),
            final_score=match_result.get("match_percentage", 0),
            full_json_data=final_response
        )
        
        db.add(new_candidate)
        db.commit()          # พยายามบันทึก
        db.refresh(new_candidate)
        
        final_response["db_id"] = new_candidate.id
        
    except Exception as e:
        db.rollback()        # <--- เพิ่มบรรทัดนี้: ยกเลิกการเปลี่ยนแปลงทันทีถ้า Error
        print(f"Database Error: {e}")
        # Option: อาจจะ raise HTTPException กลับไปบอก Frontend ด้วยก็ได้
        # raise HTTPException(status_code=500, detail="Database save failed")

    return final_response


# ==========================================
# 2. API ใหม่สำหรับ Warehouse (ดึงประวัติ)
# ==========================================
@router.get("/ucb/history")
def get_candidate_history(db: Session = Depends(get_db)):
    try:
        # ดึงข้อมูลทั้งหมด
        candidates = db.query(CandidateDB).order_by(CandidateDB.created_at.desc()).all()
        
        results = []
        for c in candidates:
            # 🛡️ ป้องกัน Error: ถ้า data เป็น None ให้ใส่ dict ว่างๆ แทน
            data = c.full_json_data if c.full_json_data else {}
            
            # ใช้ .get แบบปลอดภัย
            resume = data.get("parsed_resume", {})
            # match = data.get("score", {}) # (บรรทัดนี้ในโค้ดเก่าไม่ได้ใช้ แต่ถ้าใช้ก็ปลอดภัยไว้ก่อน)
            
            # ดึงข้อมูลแบบปลอดภัย (Safe Access)
            c_info = resume.get("candidate_info", {})
            skills = resume.get("skills", {})
            
            results.append({
                "candidate_id": c.candidate_name or "Unknown",
                "db_id": c.id,
                "filename": c.filename,
                "matching": c.final_score or 0, # ใช้ชื่อ final_score ตาม Model
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
        # ส่ง List ว่างกลับไปแทนที่จะปล่อยให้ Server พัง
        return []

# ==========================================
# 3. API สำหรับลบข้อมูล
# ==========================================
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
    # ต้องมี return นะครับ
    return jd_manager.get_all_jobs()

@router.post("/jobs")
async def save_job_profile(job: JobProfile):
    # 1. รับข้อมูลจากหน้าบ้านผ่านตัวแปร job
    print(f"📥 API received SAVE request: {job.title}") # Debug Log
    
    # 2. ส่งให้ jd_manager บันทึก
    try:
        saved_data = jd_manager.save_job(job.title, job.description)
        return {"message": "Job saved successfully", "data": saved_data}
    except Exception as e:
        print(f"❌ API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))