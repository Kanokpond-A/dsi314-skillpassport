# ใช้ Python base image
FROM python:3.11-slim

# ปิด output buffer จะได้เห็น log ทันที
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# ติดตั้ง dependency พื้นฐานของระบบ (ถ้า lib บางตัวใช้ไม่ได้ค่อยเพิ่มทีหลัง)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# โฟลเดอร์ทำงานใน container
WORKDIR /app

# copy เฉพาะ requirements ก่อน (cache layer)
COPY requirements.txt .

# ติดตั้ง python packages
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install "uvicorn[standard]" "streamlit"

# copy code ทั้ง repo เข้าไป
COPY . .

# set default command เฉยๆ (เราจะ override ด้วย docker-compose อีกที)
CMD ["python", "-m", "pytest"]
