import argparse, json, sys, io
from pathlib import Path

def extract_text_pymupdf(pdf_path: Path):
    """ดึง text layer ด้วย PyMuPDF; คืน (text, pages)"""
    import fitz  # PyMuPDF
    doc = fitz.open(pdf_path)
    texts = []
    for page in doc:
        texts.append(page.get_text("text"))
    return "\n".join(texts), len(doc)

def ocr_pdf_tesseract(pdf_path: Path, lang: str):
    """แปลง PDF เป็นภาพต่อหน้า แล้ว OCR ด้วย Tesseract; คืน (text, pages)"""
    from pdf2image import convert_from_path
    import pytesseract
    pages = convert_from_path(str(pdf_path))
    out = []
    for im in pages:
        out.append(pytesseract.image_to_string(im, lang=lang))
    return "\n".join(out), len(pages)

def main():
    ap = argparse.ArgumentParser(description="PDF → RAW JSON (with OCR fallback)")
    ap.add_argument("--in",  dest="inp",  required=True, help="path to input .pdf")
    ap.add_argument("--out", dest="out", required=True, help="path to RAW json")
    ap.add_argument("--lang", default="eng", help="OCR language, e.g., 'eng' or 'eng+tha'")
    args = ap.parse_args()

    src = Path(args.inp)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        text, pages = extract_text_pymupdf(src)
    except Exception as e:
        print(f"❌ PyMuPDF failed: {e}", file=sys.stderr)
        text, pages = "", 0

    text_norm = " ".join((text or "").split())
    ocr_used = False

    # ถ้าไม่มี text layer หรือสั้น異ปกติ ให้ลอง OCR
    if len(text_norm) < 200:
        try:
            ocr_text, pages_ocr = ocr_pdf_tesseract(src, args.lang)
            if len(ocr_text.strip()) > len(text_norm):
                text = ocr_text
                pages = pages_ocr or pages
                ocr_used = True
        except Exception as e:
            # ถ้า OCR พัง ให้เก็บเท่าที่มี
            print(f"⚠️ OCR fallback failed: {e}", file=sys.stderr)

    payload = {
        "source_file": src.name,
        "pages": int(pages or 0),
        "ocr_used": bool(ocr_used),
        "text": (text or "").strip(),
    }
    json.dump(payload, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[OK] pdf→raw {src.name} (pages={payload['pages']}, ocr_used={'yes' if ocr_used else 'no'}) → {out_path}")

if __name__ == "__main__":
    main()

