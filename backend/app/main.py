import os
from uuid import uuid4
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

# Import Routes
from backend.app.api.v3.routes import router as v3_router
from backend.app.core.logging import get_logger, request_id_ctx
from dotenv import load_dotenv

# Load .env
load_dotenv()  

app = FastAPI(title="UCB Backend", version="0.1.0")
logger = get_logger("ucb.app")

# Configuration Paths
CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR = CURRENT_FILE.parent.parent
STATIC_DIR = BACKEND_DIR / "static"
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"
RESUMES_DIR = STATIC_DIR / "resumes"

# Ensure directories exist
RESUMES_DIR.mkdir(parents=True, exist_ok=True)
FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

print(f"📂 Static Dir: {STATIC_DIR}")
print(f"📂 Frontend Dir: {FRONTEND_DIR}")

# Mount Static Files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# --- CORS Middleware (ประกาศครั้งเดียวพอ) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # อนุญาตทุก Origin สำหรับ Development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Middleware Logging ---
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

# --- Router (ประกาศครั้งเดียว) ---
app.include_router(v3_router)

# --- Exception Handlers ---
@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    rid = request_id_ctx.get()
    logger.warning(f"ValidationError {request.url.path} | req={rid} | detail={exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"error": "Invalid request payload", "details": exc.errors(), "request_id": rid},
    )

@app.get("/", include_in_schema=False)
async def index():
    """Serve home.html"""
    index_file = FRONTEND_DIR / "home.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Welcome to UCB API. Frontend not found.", "path_checked": str(index_file)}