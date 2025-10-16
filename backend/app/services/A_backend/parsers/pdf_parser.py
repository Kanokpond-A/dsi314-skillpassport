import argparse, json, fitz, os

def extract_text_from_pdf(path):
    doc = fitz.open(path)
    return "\n".join([p.get_text("text") for p in doc])

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    args = ap.parse_args()

    raw = extract_text_from_pdf(args.inp)
    out = {"source_file": os.path.basename(args.inp), "raw_text": raw}
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("[OK] PDF parsed →", args.out)
