import logging
import sys
from pathlib import Path

# ตั้งค่า Logging แบบพื้นฐาน (แสดงผลทางหน้าจอ Terminal)
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout) # พ่น Log ออกหน้าจอ
        ]
    )
    
    # ถ้าอยากเก็บลงไฟล์ด้วย ให้สร้างโฟลเดอร์ logs
    # log_dir = Path("logs")
    # log_dir.mkdir(exist_ok=True)
    # file_handler = logging.FileHandler(log_dir / "app.log")
    # logging.getLogger().addHandler(file_handler)

# เรียกใช้ฟังก์ชันนี้ตอน start server ได้เลย