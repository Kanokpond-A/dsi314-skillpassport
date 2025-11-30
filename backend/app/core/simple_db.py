import sqlite3
import json
import time

DB_NAME = "skillpassport.db"

def init_db():
    """สร้างตารางเก็บข้อมูลถ้ายังไม่มี"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # สร้างตาราง candidates
    # เราจะเก็บข้อมูล JSON ก้อนยักษ์ลงในช่อง TEXT ไปเลย (Simple & Fast)
    c.execute('''
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            candidate_name TEXT,
            total_score REAL,
            parsed_data TEXT,  -- เก็บ JSON จาก Gemini ตรงนี้
            score_result TEXT, -- เก็บ JSON ผลคะแนนตรงนี้
            created_at REAL
        )
    ''')
    conn.commit()
    conn.close()

def insert_candidate(filename, parsed_data, score_result):
    """บันทึกผู้สมัครลงถัง"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # ดึงชื่อผู้สมัครออกมา (ถ้ามี)
    c_name = parsed_data.get('candidate_info', {}).get('name', 'Unknown')
    score = score_result.get('final_score', 0)
    
    c.execute('''
        INSERT INTO candidates (filename, candidate_name, total_score, parsed_data, score_result, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        filename, 
        c_name, 
        score, 
        json.dumps(parsed_data, ensure_ascii=False), # แปลง Dict เป็น String
        json.dumps(score_result, ensure_ascii=False), 
        time.time()
    ))
    
    conn.commit()
    conn.close()
    return c.lastrowid

def get_all_candidates():
    """ดึงข้อมูลทั้งหมดไปโชว์ Dashboard"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row # เพื่อให้ดึงค่าโดยใช้ชื่อคอลัมน์ได้
    c = conn.cursor()
    
    c.execute('SELECT * FROM candidates ORDER BY id DESC')
    rows = c.fetchall()
    
    results = []
    for row in rows:
        results.append({
            "id": row['id'],
            "filename": row['filename'],
            "name": row['candidate_name'],
            "score": row['total_score'],
            "parsed_data": json.loads(row['parsed_data']), # แปลง String กลับเป็น Dict
            "score_result": json.loads(row['score_result']),
            "created_at": row['created_at']
        })
    
    conn.close()
    return results
```

---

### 🔗 วิธีเชื่อมต่อ (บอก A2 ให้ทำตามนี้)

ให้ A2 (คนทำ API) แก้ไฟล์ `main.py` หรือ `api` นิดเดียวครับ:

**1. ตอนเริ่มแอป (Startup):**
```python
from backend.app.core.simple_db import init_db

# สั่งสร้างไฟล์ Database ตอนเปิด Server
init_db()
```

**2. ตอนจบ Process Analyze (หลังจาก Gemini + Scoring เสร็จ):**
```python
from backend.app.core.simple_db import insert_candidate

# ... (โค้ด analyze เดิม) ...

# บันทึกลง DB
insert_candidate(file.filename, parsed_data, score_result)

return { ... }
```

**3. เพิ่ม API เส้นใหม่สำหรับ Dashboard:**
```python
from backend.app.core.simple_db import get_all_candidates

@router.get("/dashboard-data")
def get_dashboard():
    return get_all_candidates()