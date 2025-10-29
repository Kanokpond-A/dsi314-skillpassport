# backend/app/services/A_backend/parsers/pdf_parser.py
import argparse, json, io, sys
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image
import pytesseract

def extract_text_standard(pdf_path: Path) -> tuple[str, int]:
    doc = fitz.open(pdf_path)
    parts = []
    for page in doc:
        parts.append(page.get_text("text") or "")
    text = "\n".join(parts)
    return text, len(doc)

def extract_text_ocr(pdf_path: Path, lang: str) -> tuple[str, int]:
    doc = fitz.open(pdf_path)
    parts = []
    for page in doc:
        # เรนเดอร์ให้คมพอสำหรับภาษาไทย
        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        parts.append(pytesseract.image_to_string(img, lang=lang) or "")
    text = "\n".join(parts)
    return text, len(doc)

def parse_pdf(pdf_path: Path, lang: str = "eng") -> dict:
    # 1) ลองดึงข้อความแบบ text layer ก่อน
    std_text, n_pages = extract_text_standard(pdf_path)
    std_len = len((std_text or "").strip())

    # 2) ถ้าสั้นเกินไป (เช่น < 100 ตัวอักษร) ให้ OCR
    use_ocr = False
    if std_len < 100:
        ocr_text, n_pages2 = extract_text_ocr(pdf_path, lang=lang)
        # ถ้า OCR ได้ยาวกว่าให้ใช้ OCR
        if len((ocr_text or "").strip()) > std_len:
            std_text = ocr_text
            n_pages = n_pages2
            use_ocr = True

    return {
        "source_file": pdf_path.name,
        "pages": n_pages,            # <-- int ตามสเปก RAW
        "ocr_used": use_ocr,         # <-- bool
        "text": std_text or "",      # <-- str รวมทุกหน้า
    }

def main():
    ap = argparse.ArgumentParser(description="Parse PDF -> RAW JSON (with OCR fallback)")
    ap.add_argument("--in",  dest="inp", required=True, help="path to input .pdf")
    ap.add_argument("--out", dest="out", required=True, help="path to raw JSON")
    ap.add_argument("--lang", default="eng", help="tesseract lang (e.g. 'eng' or 'eng+tha')")
    args = ap.parse_args()

    inp = Path(args.inp)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    data = parse_pdf(inp, lang=args.lang)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    text_len = len((data.get("text") or "").strip())
    print(f"[OK] PDF parsed → {out} (pages={data['pages']} ocr_used={data['ocr_used']} text_len={text_len})")

if __name__ == "__main__":
    main()

