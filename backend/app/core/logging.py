# backend/app/core/logging.py
import logging, os
from contextvars import ContextVar

# ── ระดับ log ปรับได้ด้วยตัวแปรแวดล้อม: LOG_LEVEL=DEBUG/INFO/WARN/ERROR
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# ── เก็บ request_id ต่อคำขอ
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True

def get_logger(name: str = "ucb"):
    """คืน logger ที่มีฟิลเตอร์ request_id + ฟอร์แมตอ่านง่าย"""
    logger = logging.getLogger(name)
    if not logger.handlers: #กัน duplicate handler
        handler = logging.StreamHandler()
        fmt = "%(asctime)s %(levelname)s %(name)s [req=%(request_id)s] %(message)s"
        handler.setFormatter(logging.Formatter(fmt))
        handler.addFilter(RequestIdFilter())
        logger.addHandler(handler)
        logger.setLevel(LOG_LEVEL)
        logger.propagate = False #ป้องกัน log ซ้ำ
    return logger
