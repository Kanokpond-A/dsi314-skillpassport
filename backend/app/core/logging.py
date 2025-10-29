# backend/app/core/logging.py
import logging, os
from pathlib import Path
from contextvars import ContextVar

# ── ระดับ log ปรับได้ด้วยตัวแปรแวดล้อม: LOG_LEVEL=DEBUG/INFO/WARN/ERROR
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# ── โฟลเดอร์เก็บ log (เราจะสร้างให้ถ้ายังไม่มี)
BASE_DIR = Path(__file__).resolve().parents[2]
LOG_DIR = BASE_DIR / "shared_data"
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE_PATH = LOG_DIR / "app.log"   # ถ้าอยากใช้ชื่ออื่นก็ได้ เช่น import_log.json

# ── เก็บ request_id ต่อคำขอ
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True

def _build_formatter():
    fmt = "%(asctime)s %(levelname)s %(name)s [req=%(request_id)s] %(message)s"
    return logging.Formatter(fmt)

def get_logger(name: str = "ucb"):
    """คืน logger ที่มีฟิลเตอร์ request_id + ฟอร์แมตอ่านง่าย
    และเขียนทั้ง console + file
    """
    logger = logging.getLogger(name)

    if not logger.handlers:  # กัน duplicate handler เวลาเรียกซ้ำ
        formatter = _build_formatter()
        req_filter = RequestIdFilter()

        # 1) handler สำหรับ console (เหมือนของเดิม)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.addFilter(req_filter)
        logger.addHandler(console_handler)

        # 2) handler สำหรับเขียนไฟล์ log
        file_handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.addFilter(req_filter)
        logger.addHandler(file_handler)

        logger.setLevel(LOG_LEVEL)
        logger.propagate = False  # ป้องกัน log ซ้ำจาก root

    return logger
