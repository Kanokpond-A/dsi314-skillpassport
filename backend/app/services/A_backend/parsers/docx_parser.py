import argparse, json, time
from pathlib import Path
from docx import Document

def main():
    ap = argparse.ArgumentParser(description="Parse DOCX to raw text JSON")
    ap.add_argument("--in",  dest="inp",  required=True, help="path to input .docx")
    ap.add_argument("--out", dest="out", required=True, help="path to raw_tmp.json")
    args = ap.parse_args()

    t0 = time.time()
    doc = Document(args.inp)
    texts = []
    for p in doc.paragraphs:
        txt = (p.text or "").strip()
        if txt: texts.append(txt)
    elapsed_ms = int((time.time() - t0) * 1000)

    data = {
        "source_file": str(Path(args.inp).name),
        "pages": [{"text": "\n".join(texts)}],
        "meta": {"source": "docx", "runtime_ms": elapsed_ms}
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(data, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[OK] docx->raw lines={len(texts)} runtime={elapsed_ms}ms -> {args.out}")

if __name__ == "__main__":
    main()
