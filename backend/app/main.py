from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from .api.v1.routes import router as v1_router

from .core.logging import get_logger, request_id_ctx
from uuid import uuid4

app = FastAPI(title="UCB Backend", version="0.1.0")
app.include_router(v1_router)

logger = get_logger("ucb.app")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    rid = request_id_ctx.get()
    logger.warning(f"ValidationError {request.url.path} | req={rid} | detail={exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"error": "Invalid request payload", "details": exc.errors(), "request_id": rid},
    )

async def internal_handler(request: Request, exc: Exception):
    rid = request_id_ctx.get()
    logger.error(f"UnhandledError {request.url.path} | req={rid} | {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "request_id": rid},
    )