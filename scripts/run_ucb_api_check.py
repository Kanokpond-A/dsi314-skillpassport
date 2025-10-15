import httpx
import json

BASE_URL = "http://127.0.0.1:8000/api/v1"

# 🧩 ตัวอย่าง payload ที่เหมือนข้อมูลจริงจาก A1
sample_resume = {
    "name": "Alice Smith",
    "education": ["Bachelor of Economics", "Data Science Certificate"],
    "skills": ["Python", "SQL", "Data Visualization"],
    "evidence": ["cert_python.pdf", "project_dashboard.pdf"]
}

def test_ucb_json():
    print("🚀 Testing /ucb (JSON summary)")
    res = httpx.post(f"{BASE_URL}/ucb", json=sample_resume)
    print("Status:", res.status_code)
    if res.status_code == 200:
        print("✅ JSON Response:")
        print(json.dumps(res.json(), indent=2))
    else:
        print("❌ Error:", res.text)

def test_ucb_pdf():
    print("\n📄 Testing /ucb-pdf (PDF export)")
    res = httpx.post(f"{BASE_URL}/ucb-pdf", json=sample_resume)
    print("Status:", res.status_code)
    if res.status_code == 200:
        with open("ucb_test_output.pdf", "wb") as f:
            f.write(res.content)
        print("✅ PDF saved as ucb_test_output.pdf")
    else:
        print("❌ Error:", res.text)

if __name__ == "__main__":
    test_ucb_json()
    test_ucb_pdf()
