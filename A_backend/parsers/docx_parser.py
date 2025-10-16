import argparse, json, os
from docx import Document

def extract_text_from_docx(path):
    doc = Document(path)
    return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    args = ap.parse_args()

    raw = extract_text_from_docx(args.inp)
    out = {"source_file": os.path.basename(args.inp), "raw_text": raw}
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("[OK] DOCX parsed →", args.out)
