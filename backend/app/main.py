from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from .api.v1.routes import router as v1_router

from .api.v2.routes import router as v2_router


from .core.logging import get_logger, request_id_ctx
from uuid import uuid4

app = FastAPI(title="UCB Backend", version="0.1.0")

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
app.include_router(v1_router)
app.include_router(v2_router, prefix="/api/v2", tags=["UCB v2"])

# --- ตั้งค่า Logger และ Middleware อื่นๆ ---
logger = get_logger("ucb.app")

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

# --- Root Endpoint (ทางเลือก) ---
@app.get("/")
def read_root():
    return {"message": "Welcome to UCB API"}

