import argparse, json
from pathlib import Path

def read_docx_text(path: Path) -> str:
    import docx  # python-docx
    d = docx.Document(str(path))
    paras = [p.text.strip() for p in d.paragraphs if p.text and p.text.strip()]
    return "\n".join(paras)

def main():
    ap = argparse.ArgumentParser(description="DOCX → RAW JSON")
    ap.add_argument("--in",  dest="inp",  required=True, help="path to input .docx")
    ap.add_argument("--out", dest="out", required=True, help="path to RAW json")
    args = ap.parse_args()

    src = Path(args.inp)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    text = read_docx_text(src)

    payload = {
        "source_file": src.name,
        "pages": 1,             # DOCX ไม่แบ่งหน้าแบบ PDF; ใส่ 1 เป็นค่าอ้างอิง
        "ocr_used": False,      # DOCX ไม่ต้อง OCR
        "text": text.strip(),
    }
    json.dump(payload, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[OK] docx→raw {src.name} → {out_path}")

if __name__ == "__main__":
    main()
