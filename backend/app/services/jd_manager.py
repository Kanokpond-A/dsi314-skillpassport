import json
import os
from pathlib import Path
from typing import List, Dict

# 1. ระบุตำแหน่งโฟลเดอร์ให้แม่นยำ (ใช้โค้ดเดิมที่ถูกต้องแล้ว)
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[3] # ถอย 4 ชั้นไปหา Root
JD_STORAGE_PATH = PROJECT_ROOT / "config" / "jd_profiles"

# สร้างโฟลเดอร์รอไว้เสมอ
JD_STORAGE_PATH.mkdir(parents=True, exist_ok=True)

print(f"📂 JD Manager Active. Path: {JD_STORAGE_PATH}")

def get_all_jobs() -> List[Dict]:
    """อ่านไฟล์ Job Profile ทั้งหมดในโฟลเดอร์"""
    jobs = []
    
    # Debug: ดูซิว่าในโฟลเดอร์มีไฟล์อะไรบ้าง (ไม่สนนามสกุล)
    try:
        all_files = list(JD_STORAGE_PATH.iterdir())
        print(f"🔍 Checking folder... Found {len(all_files)} files: {[f.name for f in all_files]}")
        
        for file_path in all_files:
            # อ่านเฉพาะไฟล์นามสกุล .json
            if file_path.suffix.lower() == '.json':
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        jobs.append(data)
                except Exception as e:
                    print(f"❌ Corrupted JSON {file_path.name}: {e}")
            else:
                # แจ้งเตือนถ้ามีไฟล์แปลกปลอม (เช่น .txt)
                if file_path.name != "SYSTEM_TEST.txt":
                    print(f"⚠️ Skipping non-json file: {file_path.name}")

    except Exception as e:
        print(f"❌ Error accessing folder: {e}")
        return []

    print(f"✅ Loaded {len(jobs)} profiles successfully.")
    return jobs

def save_job(title: str, description: str):
    # (ใช้โค้ดเดิมได้เลยครับ หรือจะ Copy ใหม่ก็ได้)
    print(f"💾 Saving Job: '{title}'")
    safe_filename = "".join(c for c in title.strip().replace(" ", "_").lower() if c.isalnum() or c in ('_', '-')) 
    if not safe_filename: safe_filename = "untitled"
    
    file_path = JD_STORAGE_PATH / f"{safe_filename}.json"
    
    data = {"id": f"{safe_filename}.json", "title": title.strip(), "description": description.strip()}
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        f.flush()
        os.fsync(f.fileno())
        
    print(f"✅ File saved: {file_path}")
    return data