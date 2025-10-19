# A_backend/app/parsers/run_all.py
import argparse, subprocess, sys, glob, pathlib, json, os

ROOT = pathlib.Path(__file__).resolve().parents[3]  # repo root
PDFS = ROOT / "samples"
RAW  = ROOT / "shared_data/examples/_raw_tmp.json"
PARSED_DIR = ROOT / "shared_data/latest_parsed"
UCB_DIR    = ROOT / "shared_data/latest_ucb"

def run(cmd):
    print("→", " ".join(map(str, cmd)))
    subprocess.run(list(map(str, cmd)), check=True)

def main():
    ap = argparse.ArgumentParser(description="Parse all PDFs then score to UCB")
    ap.add_argument("--lang", default="eng", help="tesseract lang (e.g., eng or eng+tha)")
    ap.add_argument("--skip-existing", action="store_true", help="skip if target exists")
    args = ap.parse_args()

    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    UCB_DIR.mkdir(parents=True, exist_ok=True)
    RAW.parent.mkdir(parents=True, exist_ok=True)

    ok, fail = 0, 0
    pdfs = sorted(PDFS.glob("*.pdf"))
    print(f"found PDFs: {len(pdfs)}")

    for p in pdfs:
        parsed_path = PARSED_DIR / f"{p.stem}.json"
        ucb_path    = UCB_DIR / f"{p.stem}.json"
        if args.skip_existing and parsed_path.exists() and ucb_path.exists():
            print(f"[SKIP] {p.name}")
            continue
        try:
            # 1) PDF -> raw
            run([sys.executable, ROOT/"A_backend/parsers/pdf_parser.py",
                 "--in", p, "--out", RAW, "--lang", args.lang])
            # 2) raw -> parsed_resume
            run([sys.executable, ROOT/"A_backend/preprocess/structure_builder.py",
                 "--in", RAW, "--out", parsed_path])
            # 3) parsed_resume -> UCB
            run([sys.executable, ROOT/"A_backend/normalize_scoring/scoring.py",
                 "--in", parsed_path, "--out", ucb_path])
            print(f"[OK] {p.name} → {ucb_path}")
            ok += 1
        except subprocess.CalledProcessError:
            print(f"[FAIL] {p.name}")
            fail += 1

    print(f"\nSummary: OK={ok}, FAIL={fail}, total={len(pdfs)}")

if __name__ == "__main__":
    main()
