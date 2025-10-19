import argparse, json, fitz, os, io
from PIL import Image
import pytesseract

def extract_text_from_pdf_standard(path):
    doc = fitz.open(path)
    return "\n".join([p.get_text("text") for p in doc])

def ocr_pdf_to_text(path, lang="eng"):
    """Render ทีละหน้า → OCR ด้วย Tesseract (ใช้ eng ก่อน; ถ้ามีไทยเพิ่ม 'eng+tha')"""
    doc = fitz.open(path)
    parts = []
    for p in doc:
        # render เป็นภาพความละเอียดสูงหน่อย
        pix = p.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        parts.append(pytesseract.image_to_string(img, lang=lang))
    return "\n".join(parts)

def extract_text_from_pdf_with_fallback(path, lang="eng"):
    text = extract_text_from_pdf_standard(path) or ""
    # ถ้าข้อความน้อย/ว่าง → ถือว่าน่าจะเป็นสแกน → ใช้ OCR
    if len(text.strip()) < 500:
        ocr_text = ocr_pdf_to_text(path, lang=lang)
        # ถ้า OCR ได้ยาวกว่า ให้ใช้ผล OCR
        if len(ocr_text.strip()) > len(text.strip()):
            return ocr_text
    return text

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Input PDF file path")
    ap.add_argument("--out", dest="out", required=True, help="Output JSON path for raw text")
    ap.add_argument("--lang", default="eng", help="OCR language, e.g., 'eng' or 'eng+tha'")
    args = ap.parse_args()

    raw_text = extract_text_from_pdf_with_fallback(args.inp, lang=args.lang)
    out = {"source_file": os.path.basename(args.inp), "raw_text": raw_text}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"[OK] PDF parsed (with OCR fallback) → {args.out} (len={len(raw_text)})")
