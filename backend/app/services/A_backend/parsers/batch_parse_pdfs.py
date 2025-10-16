import pathlib, subprocess, sys

SAMPLES_DIR = pathlib.Path("samples")
RAW_TMP     = pathlib.Path("shared_data/examples/_raw_tmp.json")
OUT_DIR     = pathlib.Path("shared_data/latest_parsed")

def run(cmd):
    print("→", " ".join(cmd))
    subprocess.run(cmd, check=True)

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_TMP.parent.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(p for p in SAMPLES_DIR.glob("*.pdf"))
    if not pdfs:
        print("⚠️  ไม่พบไฟล์ PDF ในโฟลเดอร์ samples/")
        sys.exit(1)

    ok, fail = 0, 0
    for p in pdfs:
        try:
            # 1) PDF → raw text JSON
            run(["python","A_backend/parsers/pdf_parser.py",
                 "--in", str(p), "--out", str(RAW_TMP)])
            # 2) raw → parsed_resume.json (ไฟล์ปลายทางชื่อเดียวกับ PDF)
            out_path = OUT_DIR / f"{p.stem}.json"
            run(["python","A_backend/preprocess/structure_builder.py",
                 "--in", str(RAW_TMP), "--out", str(out_path)])
            print(f"[OK] {out_path}\n")
            ok += 1
        except subprocess.CalledProcessError:
            print(f"[FAIL] {p}\n")
            fail += 1

    print(f"สรุป: สำเร็จ {ok} ไฟล์, พัง {fail} ไฟล์")

if __name__ == "__main__":
    main()
