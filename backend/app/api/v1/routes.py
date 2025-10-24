# (ไฟล์: routes.py)

# === 1. IMPORT เครื่องมือที่จำเป็น ===
import os
import json
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from io import BytesIO
from fpdf import FPDF
from backend.app.services.report.pdf_report import build_ucb_pdf
from backend.app.services.analytics.summary import build_summary # (ยังไม่ได้ใช้ แต่เก็บไว้ก่อน)
from backend.app.core.privacy import redact_payload
from fastapi import Query

# === 2. IMPORT ฟังก์ชันที่ Refactor แล้ว ===
# (ตรวจสอบ Path ให้ถูกต้องตามโครงสร้างของคุณ)
from backend.app.services.parser_a1.parsers.pdf_parser import extract_text_from_pdf_bytes
from backend.app.services.parser_a1.preprocess.structure_builder import build_structured_resume
from backend.app.services.parser_a1.normalize_scoring.skills_normalizer import normalize_skills
from backend.app.services.parser_a1.normalize_scoring.scoring import calculate_ucb_score

# ----- models -----
class ParsedResume(BaseModel):
    # (เพิ่ม Optional Fields และ Contacts)
    source_file: str | None = None
    name: str | None = None
    full_name: str | None = None # (เพิ่ม full_name)
    contacts: dict | None = None
    education: list = []
    experiences: list = []
    skills: list = []
    skills_raw: list = [] # (เพิ่ม skills_raw)
    # (เพิ่ม field อื่นๆ จาก structure_builder ถ้าจำเป็น)


# ----- ✅ ประกาศ Router -----
router = APIRouter(prefix="/api/v1", tags=["v1"]) # <--- ต้องมีบรรทัดนี้!

# ----- endpoints -----
@router.get("/health")
def health():
    return {"status": "ok"}

@router.post("/parse-resume")
async def parse_resume(file: UploadFile | None = File(default=None)):

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded or filename missing.")

    # 1. อ่านไฟล์
    file_bytes = await file.read()
    source_filename = file.filename

    try:
        # 2. เรียกใช้ฟังก์ชันสกัดข้อความ (จาก pdf_parser.py)
        print(f"[API] Calling extract_text_from_pdf_bytes for {source_filename}...")
        raw_data = extract_text_from_pdf_bytes(file_bytes, lang="eng")
        raw_data["source_file"] = source_filename # อัปเดตชื่อไฟล์จริง

        # 3. เรียกใช้ฟังก์ชันสร้างโครงสร้าง (จาก structure_builder.py)
        print(f"[API] Calling build_structured_resume...")
        parsed_data = build_structured_resume(raw_data)

        # 4. ทำความสะอาดสกิล
        print(f"[API] Normalizing skills...")
        # (ใช้ skills_raw ที่ structure_builder สกัดมา)
        raw_skills = parsed_data.get("skills_raw", []) 
        clean_skills = normalize_skills(raw_skills)
        parsed_data["skills"] = clean_skills # 👈 อัปเดต skills เป็นตัวที่ clean แล้ว
        parsed_data["skills_normalized"] = clean_skills # (เผื่อ scoring ใช้ key นี้)

        # 5. ส่ง JSON "จริง" กลับไป
        print(f"[API] Completed /parse-resume for {source_filename}. Returning parsed data.")
        return parsed_data # (FastAPI จะแปลง dict เป็น JSON)

    except ImportError as e:
         print(f"[API Error] Import Error in /parse-resume: {e}")
         raise HTTPException(status_code=500, detail=f"Server configuration error: Required module not found ({e}).")
    except Exception as e:
        print(f"[API Error] Error processing file in /parse-resume: {e}")
        # import traceback # Uncomment for detailed traceback during debugging
        # traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process resume file: {e}")


@router.post("/score-hr")
async def score_hr(parsed: ParsedResume):
    try:
        # 1. แปลง Pydantic model เป็น dict ธรรมดา
        parsed_data = parsed.model_dump(exclude_unset=True) 

        # 2. เรียกใช้ฟังก์ชันคำนวณคะแนนใหม่ (จาก scoring.py)
        print(f"[API] Calling calculate_ucb_score for {parsed_data.get('name', 'Unknown candidate')}...")
        ucb_result = calculate_ucb_score(parsed_data, redact_pii=True)

        # 3. ดึงเฉพาะส่วน hr_view ที่ Frontend ต้องการ
        hr_view = ucb_result.get("hr_view", {})
        if not hr_view:
             print("[API Warning] calculate_ucb_score did not return 'hr_view'.")
             return {"name": parsed.name, "score": 0, "level": "Error", "summary": {}, "breakdown": [], "notes": ["Scoring failed."], "score_components": {}}

        # 4. สร้าง Response ให้ตรงกับที่ Frontend (renderSuccess) คาดหวัง
        response_data = {
            "name": parsed.name or parsed_data.get("full_name") or "Unknown", # ใช้ชื่อจาก Input
            "score": hr_view.get("score"),
            "level": hr_view.get("level"),
            "summary": hr_view.get("summary"),
            "breakdown": hr_view.get("breakdown"),
            "notes": hr_view.get("notes"),
            "score_components": hr_view.get("score_components") # 👈✅ ต้องมีบรรทัดนี้
        }
        print(f"[API] Completed /score-hr. Score: {response_data.get('score', 'N/A')}")
        return response_data

    except Exception as e:
         print(f"[API Error] Error during scoring (/score-hr): {e}")
         # import traceback; traceback.print_exc() # Uncomment for debugging
         raise HTTPException(status_code=500, detail=f"Failed to score resume: {e}")


@router.post("/ucb-pdf")
async def ucb_pdf_endpoint(parsed: ParsedResume):
    try:
        # 1. แปลง Pydantic model เป็น dict
        parsed_data = parsed.model_dump(exclude_unset=True)

        # 2. เรียกใช้ฟังก์ชันคำนวณคะแนนใหม่ (จาก scoring.py)
        print(f"[API] Calling calculate_ucb_score (for PDF) for {parsed_data.get('name', 'Unknown candidate')}...")
        ucb_result = calculate_ucb_score(parsed_data, redact_pii=False) # ปิด Redact สำหรับ PDF
        hr_view = ucb_result.get("hr_view")
        if not hr_view:
             print("[API Warning] calculate_ucb_score did not return 'hr_view' for PDF.")
             raise HTTPException(status_code=500, detail="Scoring failed, cannot generate PDF.")
        
        pdf_name = parsed.name or parsed_data.get("full_name") or "Candidate" # ใช้ชื่อจาก Input

        # 3. เรียกใช้ฟังก์ชันสร้าง PDF
        print(f"[API] Calling build_ucb_pdf for {pdf_name}...")
        buf = build_ucb_pdf(pdf_name, hr_view)

        print(f"[API] Completed /ucb-pdf. Returning PDF stream.")
        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{pdf_name}_UCB.pdf"'}
        )
    except Exception as e:
        print(f"[API Error] Error generating PDF (/ucb-pdf): {e}")
        # import traceback; traceback.print_exc() # Uncomment for debugging
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF report: {e}")
    
    # (วาง import เหล่านี้ไว้บนสุดของไฟล์ ถ้ายังไม่มี)
import os
import json
from pathlib import Path
from typing import List, Dict, Any # เพิ่ม List, Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException, Response, status # เพิ่ม Response, status
# ... (import อื่นๆ ของคุณ) ...

# ----- กำหนด Path ไปยังโฟลเดอร์ข้อมูล -----
# (ใช้ Path ที่ถูกต้องบน Server ของคุณ)
BASE_SHARED_DIR = Path("./shared_data") # หรือ Path("C:/path/to/shared_data")
UCB_DIR = BASE_SHARED_DIR / "latest_ucb"
PARSED_DIR = BASE_SHARED_DIR / "latest_parsed"

# ----- ✅ ประกาศ Router (ถ้ายังไม่มี) -----
# router = APIRouter(prefix="/api/v1", tags=["v1"]) # <--- ต้องมีบรรทัดนี้!

# ... (Endpoints เดิมของคุณ: /health, /parse-resume, /score-hr, /ucb-pdf) ...


# ----- Endpoint ใหม่สำหรับ Dashboard -----

@router.get("/resumes", response_model=List[Dict[str, Any]])
async def get_all_resumes():
    """
    Endpoint สำหรับให้ Dashboard ดึงข้อมูลผู้สมัครทั้งหมด
    อ่านไฟล์ JSON ทั้งหมดจากโฟลเดอร์ latest_ucb
    """
    all_data = []
    if not UCB_DIR.exists() or not UCB_DIR.is_dir():
        print(f"[API Warning] UCB directory not found: {UCB_DIR}")
        return all_data # คืนค่า List ว่างถ้าไม่มีโฟลเดอร์

    print(f"[API] Reading resumes from: {UCB_DIR}")
    try:
        for json_file in UCB_DIR.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # เพิ่ม file_id เข้าไปในข้อมูล เพื่อให้ Frontend รู้จัก
                    data['candidate_id'] = json_file.name
                    # (อาจจะต้องดึง score/level มาไว้ที่ root level ถ้า Frontend ต้องการ)
                    # data['score'] = data.get('fit_score') # ตัวอย่าง
                    # data['level'] = determine_level(data.get('fit_score')) # ตัวอย่าง
                    all_data.append(data)
            except json.JSONDecodeError:
                print(f"[API Error] Failed to decode JSON: {json_file.name}")
            except Exception as e:
                print(f"[API Error] Failed to read file {json_file.name}: {e}")

        print(f"[API] Found {len(all_data)} resumes.")
        return all_data
    except Exception as e:
        print(f"[API Error] Error listing files in {UCB_DIR}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read resume data: {e}")


@router.delete("/resume/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(file_id: str):
    """
    Endpoint สำหรับลบไฟล์ข้อมูลของผู้สมัคร (ทั้ง ucb และ parsed)
    รับ file_id เช่น "a.json"
    """
    if not file_id or ".." in file_id or "/" in file_id or "\\" in file_id:
        raise HTTPException(status_code=400, detail="Invalid file ID format.")

    ucb_file_path = UCB_DIR / file_id
    parsed_file_path = PARSED_DIR / file_id

    deleted_ucb = False
    deleted_parsed = False

    print(f"[API] Attempting to delete files for ID: {file_id}")

    try:
        if ucb_file_path.exists() and ucb_file_path.is_file():
            os.remove(ucb_file_path)
            deleted_ucb = True
            print(f"[API] Deleted UCB file: {ucb_file_path}")
        else:
            print(f"[API Warning] UCB file not found or is not a file: {ucb_file_path}")
    except OSError as e:
        print(f"[API Error] Failed to delete UCB file {ucb_file_path}: {e}")
        # ไม่ raise error ทันที เผื่อว่าไฟล์ parsed ยังลบได้

    try:
        if parsed_file_path.exists() and parsed_file_path.is_file():
            os.remove(parsed_file_path)
            deleted_parsed = True
            print(f"[API] Deleted parsed file: {parsed_file_path}")
        else:
            print(f"[API Warning] Parsed file not found or is not a file: {parsed_file_path}")
    except OSError as e:
        print(f"[API Error] Failed to delete parsed file {parsed_file_path}: {e}")
        # ถ้าลบ ucb ได้ แต่ parsed ไม่ได้ ก็ยังถือว่ากึ่งสำเร็จ

    if not deleted_ucb and not deleted_parsed:
        # ถ้าไม่เจอไฟล์ไหนเลย ถือว่าหาไม่เจอ
        raise HTTPException(status_code=404, detail=f"Resume data for ID '{file_id}' not found.")

    # ถ้าลบได้อย่างน้อย 1 ไฟล์ ถือว่าสำเร็จ (HTTP 204 No Content)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# ----- (ถ้าคุณมี app.include_router(router) ให้วางไว้หลังสุด) -----
