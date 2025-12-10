from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List

import os
from pathlib import Path

# Import ไฟล์ database ที่เราเพิ่งสร้าง
from backend.app.services.database import get_db, CandidateDB
from backend.app.services.parsers.gemini_parser import parse_with_gemini, analyze_match_with_gemini, calculate_match_score
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
async def process_pdf(
    file: UploadFile = File(...),
    job_description: str = Form("")
):
    try:
        # 1. อ่านไฟล์ PDF
        file_content = await file.read()
        
        # ✅ แก้: ใช้ parse_with_gemini แปลง PDF -> JSON
        parsed_resume = parse_with_gemini(file_content)
        
        if not parsed_resume:
             raise HTTPException(status_code=400, detail="Failed to parse resume PDF")

        # 2. คำนวณคะแนน (เรียก scoring.py)
        score_result = calculate_universal_score(
            parsed_data=parsed_resume, 
            weights_config={},  
            job_description_text=job_description 
        )

        # 3. เตรียมข้อมูลส่งกลับ Frontend
        final_response = {
            "filename": file.filename,
            "parsed_resume": parsed_resume,
            "score": score_result, 
            "job_title": "Applied Position"
        }

        # 4. บันทึกลง Database
        # (ต้องทำภายใน function scope เดียวกัน ไม่เขียนโค้ดลอยๆ นอก try/except)
        db = next(get_db()) # เรียก session แบบ manual ชั่วคราว หรือควร inject ผ่าน Depends ถ้าแยก function
        try:
            c_info = parsed_resume.get("candidate_info", {})
            new_candidate = CandidateDB(
                filename=file.filename,
                candidate_name=c_info.get("name", "Unknown"),
                email=c_info.get("email", ""),
                final_score=score_result.get("final_score", 0),
                full_json_data=final_response
            )
            db.add(new_candidate)
            db.commit()
            db.refresh(new_candidate)
            final_response["db_id"] = new_candidate.id
        except Exception as db_e:
            db.rollback()
            print(f"❌ Database Error: {db_e}")
            # ไม่ raise เพื่อให้ frontend ยังได้ผลลัพธ์การ parse แม้ save ไม่สำเร็จ

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
@router.delete("/ucb/history/all")
def delete_all_candidates(db: Session = Depends(get_db)):
    try:
        # ลบข้อมูลทั้งหมดในตาราง candidates
        num_deleted = db.query(CandidateDB).delete()
        db.commit()
        
        # (Optional) ถ้าอยากลบไฟล์ PDF ทั้งหมดด้วย ให้เพิ่มโค้ดลบไฟล์ที่นี่
        
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