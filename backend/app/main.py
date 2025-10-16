from fastapi import FastAPI, Request
from .api.v1.routes import router as v1_router
from .core.logging import get_logger, request_id_ctx
from uuid import uuid4

app = FastAPI(title="UCB Backend", version="0.1.0")
app.include_router(v1_router)

logger = get_logger("ucb.app")

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    # สร้าง request id ถ้า client ไม่ส่งมา
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