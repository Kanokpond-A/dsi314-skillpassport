import argparse
import json
from pathlib import Path
import pytesseract
from pdf2image import convert_from_path, convert_from_bytes

def extract_text_from_pdf_bytes(file_bytes, lang="eng"):
    """
    สกัดข้อความจาก PDF ที่เป็น bytes (สำหรับใช้ใน API)
    """
    try:
        # 1. แปลง bytes ให้เป็นรูปภาพ
        print(f"[+] (API) Converting PDF bytes to images...")
        images = convert_from_bytes(file_bytes)

        # 2. วนลูปทีละภาพเพื่อสกัดข้อความ (เหมือนใน main)
        pages_content = []
        for i, image in enumerate(images):
            print(f"[+] (API) Reading text from page {i + 1}/{len(images)}...")
            text = pytesseract.image_to_string(image, lang=lang)
            pages_content.append({
                "page_num": i + 1,
                "text": text
            })

        # 3. สร้างโครงสร้าง JSON ผลลัพธ์ (เหมือนใน main)
        output_data = {
            "source_file": "uploaded_file", # (API ไม่รู้ชื่อไฟล์ แต่ไม่เป็นไร)
            "page_count": len(pages_content),
            "pages": pages_content
        }
        
        print(f"[OK] (API) Successfully extracted text from bytes.")
        return output_data # 👈 คืนค่าเป็น dict กลับไป

    except Exception as e:
        print(f"[-] (API) An error occurred during PDF (bytes) processing: {e}")
        # โยน Error กลับไปให้ routes.py จัดการ
        raise e

def main():
    """
    สคริปต์สำหรับสกัดข้อความดิบ (raw text) จากไฟล์ PDF
    โดยใช้ Tesseract OCR ผ่านไลบรารี pytesseract และ pdf2image
    """
    ap = argparse.ArgumentParser(description="Extract raw text from a PDF file.")
    ap.add_argument("--in", dest="inp", required=True, help="Path to the input PDF file")
    ap.add_argument("--out", dest="out", required=True, help="Path to the output JSON file")
    ap.add_argument("--lang", default="eng", help="Tesseract language model(s) to use (e.g., 'eng' or 'eng+tha')")
    args = ap.parse_args()

    input_path = Path(args.inp)
    output_path = Path(args.out)

    if not input_path.exists():
        print(f"[-] Error: Input file not found at {input_path}")
        return

    try:
        # 1. แปลงหน้า PDF ทั้งหมดให้เป็นรูปภาพในหน่วยความจำ
        print(f"[+] Converting PDF pages to images for '{input_path.name}'...")
        images = convert_from_path(input_path)

        # 2. วนลูปทีละภาพ (ทีละหน้า) เพื่อสกัดข้อความด้วย Tesseract
        pages_content = []
        for i, image in enumerate(images):
            print(f"[+] Reading text from page {i + 1}/{len(images)}...")
            text = pytesseract.image_to_string(image, lang=args.lang)
            pages_content.append({
                "page_num": i + 1,
                "text": text
            })

        # 3. สร้างโครงสร้าง JSON ผลลัพธ์
        output_data = {
            "source_file": str(input_path.name),
            "page_count": len(pages_content),
            "pages": pages_content
        }

        # 4. เขียนผลลัพธ์ลงในไฟล์ JSON
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"[OK] Successfully extracted text to '{output_path}'")

    except Exception as e:
        print(f"[-] An error occurred during PDF processing: {e}")

if __name__ == "__main__":
    main()

