import argparse
import pathlib
import subprocess
import sys

def run(cmd):
    print("→", " ".join(map(str, cmd)))
    subprocess.run(cmd, check=True)

def main():
    ap = argparse.ArgumentParser(description="Batch parse PDFs → parsed_resume.json")
    ap.add_argument("--samples", default="samples", help="โฟลเดอร์ไฟล์ PDF ต้นทาง")
    ap.add_argument("--out", default="shared_data/latest_parsed", help="โฟลเดอร์ผลลัพธ์")
    ap.add_argument("--raw", default="shared_data/examples/_raw_tmp.json", help="ไฟล์ RAW ชั่วคราว")
    ap.add_argument("--lang", default="eng", help="ภาษา OCR เช่น eng หรือ eng+tha")
    ap.add_argument("--pattern", default="*.pdf", help="แพทเทิร์นไฟล์ เช่น *.pdf")
    ap.add_argument("--skip-existing", action="store_true", help="มีไฟล์ .json แล้วให้ข้าม")
    args = ap.parse_args()

    samples_dir = pathlib.Path(args.samples)
    out_dir = pathlib.Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = pathlib.Path(args.raw); raw_path.parent.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(samples_dir.glob(args.pattern))
    if not pdfs:
        print(f"⚠️  ไม่พบไฟล์ที่ตรงกับ {args.pattern} ใน {samples_dir.resolve()}")
        sys.exit(1)

    ok, fail = 0, 0
    failures = []

    for p in pdfs:
        out_path = out_dir / f"{p.stem}.json"
        if args.skip_existing and out_path.exists():
            print(f"⏩  skip (exists) {out_path}")
            continue
        try:
            # 1) PDF → raw text JSON (มี OCR fallback ใน pdf_parser.py)
            run([sys.executable, "A_backend/parsers/pdf_parser.py",
                 "--in", str(p), "--out", str(raw_path), "--lang", args.lang])

            # 2) raw → parsed_resume.json
            run([sys.executable, "A_backend/preprocess/structure_builder.py",
                 "--in", str(raw_path), "--out", str(out_path)])

            print(f"[OK] {out_path}\n")
            ok += 1
        except subprocess.CalledProcessError:
            print(f"[FAIL] {p}\n")
            failures.append(str(p))
            fail += 1

    print(f"เสร็จสิ้น: ✅ สำเร็จ {ok} ไฟล์ | ❌ พัง {fail} ไฟล์")
    if failures:
        print("ไฟล์ที่พัง:")
        for f in failures:
            print(" -", f)

if __name__ == "__main__":
    main()
