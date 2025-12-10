import os
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse

# from .api.v1.routes import router as v1_router
# from .api.v2.routes import router as v2_router
from .api.v3.routes import router as v3_router
from .core.logging import get_logger, request_id_ctx

from dotenv import load_dotenv
from backend.app.services.models import Candidate, ResumeAnalysis
from backend.app.services.database import Base

from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os

# --- Load .env ก่อนใช้งานทุกอย่างที่อ้างอิง ENV ---
load_dotenv()  

app = FastAPI(title="UCB Backend", version="0.1.0")
logger = get_logger("ucb.app")

static_path = os.path.join("backend", "static")
resumes_path = os.path.join(static_path, "resumes")
os.makedirs(resumes_path, exist_ok=True)

# หาตำแหน่งโฟลเดอร์ backend/static (ถอยหลัง 2 ขั้นจาก main.py)
# main.py อยู่ที่ backend/app/ -> ถอยไปที่ backend/ -> เข้าไปที่ static/
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = BASE_DIR / "backend" / "static"

# สร้างโฟลเดอร์ถ้ายังไม่มี (กัน Error)
(STATIC_DIR / "resumes").mkdir(parents=True, exist_ok=True)
FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

# สั่ง Mount: ให้ URL ที่ขึ้นต้นด้วย /static ไปดึงไฟล์จากโฟลเดอร์ backend/static
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# --- รายชื่อ Origin ที่เราอนุญาต ---
origins = [
    "http://localhost",      # สำหรับ Live Server ทั่วไป
    "http://localhost:8080", # ตัวอย่าง Port อื่น
    "http://127.0.0.1:5500", # ตัวอย่าง Port ของ VS Code Live Server
    "null",                  # สำหรับการเปิดไฟล์ HTML โดยตรง
    # เพิ่ม Origin อื่นๆ ที่คุณต้องการอนุญาตที่นี่
]

# --- เพิ่ม CORS Middleware 
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,      
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- เพิ่ม Router หลังจาก Middleware ---
# app.include_router(v1_router)
# app.include_router(v2_router)
app.include_router(v3_router)

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    rid = request.headers.get("X-Request-ID", str(uuid4()))
    token = request_id_ctx.set(rid)
    try:
        logger.info(f"Incoming {request.method} {request.url.path}")
        resp = await call_next(request)
        resp.headers["X-Request-ID"] = rid
        logger.info(f"Completed {request.method} {request.url.path} -> {resp.status_code}")
        return resp
    finally:
        request_id_ctx.reset(token)

app.add_middleware(
    CORSMiddleware,
    # เปลี่ยนเป็น ["*"] เพื่ออนุญาตทุกที่ (แก้ปัญหา Origin 'null' จากการเปิดไฟล์ตรงๆ) -> เปลี่ยนเป็น origins เพราะสะดวกตอน Dev แต่อันตรายตอน Deploy จริง การใช้ allow_origins=["*"] ทำให้เว็บไหนก็ได้ยิง API มาหาเรา ซึ่งไม่ปลอดภัยเมื่อขึ้น Production
    allow_origins = origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Exception Handlers ---
@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    rid = request_id_ctx.get()
    logger.warning(f"ValidationError {request.url.path} | req={rid} | detail={exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"error": "Invalid request payload", "details": exc.errors(), "request_id": rid},
    )

# (หมายเหตุ: ฟังก์ชัน internal_handler นี้ยังไม่ได้ถูกใช้เป็น Exception Handler จริงๆ
#  ถ้าต้องการใช้ ต้องเพิ่ม @app.exception_handler(Exception) เข้าไป)
async def internal_handler(request: Request, exc: Exception):
    rid = request_id_ctx.get()
    logger.error(f"UnhandledError {request.url.path} | req={rid} | {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "request_id": rid},
    )

@app.get("/", include_in_schema=False)
async def index():
    """ให้บริการไฟล์ home.html จากโฟลเดอร์ frontend โดยตรงเมื่อเข้า root /"""
    # ตรวจสอบว่าไฟล์ home.html อยู่ที่ Path ที่คาดหวังหรือไม่
    if (FRONTEND_DIR / "home.html").exists():
        # ถ้ามี ให้ส่งไฟล์ HTML นั้นไป
        return FileResponse(FRONTEND_DIR / "home.html")
    # ถ้าไม่มี ให้คืนค่า JSON (เหมือนเดิม) หรือ 404
    return {"message": "Welcome to UCB API. Frontend files not found in /frontend directory."}

# === 🔍 DEBUG: Print all registered routes ===
print("🛣️  Registered Routes:")
for route in app.routes:
    if hasattr(route, "path"):
        print(f"   - {route.path}")
    elif hasattr(route, "path_format"):
        print(f"   - {route.path_format}")
print("========================================")