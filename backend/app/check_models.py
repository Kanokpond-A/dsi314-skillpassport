import google.generativeai as genai
import os
from dotenv import load_dotenv

# โหลดค่า Key
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("❌ ไม่พบ API Key! ตรวจสอบไฟล์ .env ด่วน")
else:
    print(f"✅ พบ API Key แล้ว (ขึ้นต้นด้วย {api_key[:5]}...) กำลังดึงรายชื่อโมเดล...\n")
    genai.configure(api_key=api_key)

    found_any = False
    try:
        for m in genai.list_models():
            # กรองเอาเฉพาะโมเดลที่สร้างข้อความได้
            if 'generateContent' in m.supported_generation_methods:
                print(f"- {m.name}")
                found_any = True

        if not found_any:
            print("\n⚠️ ไม่พบโมเดลที่รองรับ generateContent เลย")
    except Exception as e:
        print(f"\n❌ เกิด Error: {e}")

# ปรินท์ใน terminal: python backend/app/check_models.py