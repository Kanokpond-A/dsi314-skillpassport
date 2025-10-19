# backend/app/services/A_backend/app/parsers/run_all.py
import argparse, subprocess, sys, json, csv, statistics as stats, time
from pathlib import Path

# --- ชี้รากโปรเจกต์ (repo root) ให้ถูกต้อง ---
# โครงสร้าง: backend/app/services/A_backend/app/parsers/run_all.py  -> ขึ้นไป 6 ระดับถึงราก
ROOT = Path(__file__).resolve().parents[6]

# โฟลเดอร์อินพุต/เอาต์พุตหลักอิงจากรากโปรเจกต์
DEFAULT_IN = ROOT / "samples"
RAW        = ROOT / "shared_data/examples/_raw_tmp.json"
PARSED_DIR = ROOT / "shared_data/latest_parsed"
UCB_DIR    = ROOT / "shared_data/latest_ucb"

# ฐานของโมดูล A_backend ที่ย้ายมาอยู่ใต้ backend/app/services/A_backend
BASE = ROOT / "backend/app/services/A_backend"
PDF_PARSER     = BASE / "parsers/pdf_parser.py"
DOCX_PARSER    = BASE / "parsers/docx_parser.py"
STRUCT_BUILDER = BASE / "preprocess/structure_builder.py"
SCORING        = BASE / "normalize_scoring/scoring.py"

def run(cmd):
    """รันคำสั่งและโชว์ stdout/stderr เมื่อพัง เพื่อดีบักง่าย"""
    print("→", " ".join(map(str, cmd)))
    p = subprocess.run(list(map(str, cmd)), capture_output=True, text=True)
    if p.returncode != 0:
        if p.stdout: print("STDOUT:\n", p.stdout[:2000])
        if p.stderr: print("STDERR:\n", p.stderr[:2000])
        raise subprocess.CalledProcessError(p.returncode, cmd, p.stdout, p.stderr)
    return p

def collect_files(indir: Path, include_docx: bool):
    files = list(sorted(indir.glob("*.pdf")))
    if include_docx:
        files += list(sorted(indir.glob("*.docx")))
    return files

def main():
    ap = argparse.ArgumentParser(
        description="Batch: parse (PDF/DOCX) → build → score → UCB"
    )
    ap.add_argument("--in-dir", type=str, default=str(DEFAULT_IN),
                    help="input folder (default: samples/)")
    ap.add_argument("--lang", default="eng",
                    help="tesseract lang for PDFs (e.g., eng or eng+tha)")
    ap.add_argument("--docx", action="store_true",
                    help="include .docx in batch")
    ap.add_argument("--skip-existing", action="store_true",
                    help="skip when both parsed & ucb already exist")
    ap.add_argument("--redact", dest="redact", action="store_true", default=True,
                    help="mask PII in UCB (default: on)")
    ap.add_argument("--no-redact", dest="redact", action="store_false",
                    help="turn OFF PII masking")
    ap.add_argument("--jd", type=str, default=None,
                    help="path to JD config YAML for scoring (optional)")
    ap.add_argument("--report", action="store_true",
                    help="write summary CSV + metrics JSON after run")
    ap.add_argument("--pass-threshold", type=int, default=70,
                    help="threshold for pass-rate in report (default: 70)")
    args = ap.parse_args()

    in_dir = Path(args.in_dir)
    if not in_dir.exists():
        print(f"❌ input folder not found: {in_dir}")
        sys.exit(1)

    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    UCB_DIR.mkdir(parents=True, exist_ok=True)
    RAW.parent.mkdir(parents=True, exist_ok=True)

    files = collect_files(in_dir, include_docx=args.docx)
    print(f"found files: {len(files)} in {in_dir} "
          f"(pdf{' + docx' if args.docx else ''})")
    if not files:
        print("⚠️  No files found. Put PDF/DOCX into the input folder and try again.")
        return

    if args.docx and not DOCX_PARSER.exists():
        print("⚠️  docx_parser.py not found. DOCX files will fail. Expected at:", DOCX_PARSER)

    ok, fail = 0, 0
    t0_all = time.time()

    for p in files:
        parsed_path = PARSED_DIR / f"{p.stem}.json"
        ucb_path    = UCB_DIR / f"{p.stem}.json"

        if args.skip_existing and parsed_path.exists() and ucb_path.exists():
            print(f"[SKIP] {p.name}")
            continue

        try:
            # 1) PDF/DOCX → raw
            if p.suffix.lower() == ".pdf":
                run([sys.executable, PDF_PARSER,
                     "--in", p, "--out", RAW, "--lang", args.lang])
            else:
                run([sys.executable, DOCX_PARSER,
                     "--in", p, "--out", RAW])

            # 2) raw → parsed_resume.json
            run([sys.executable, STRUCT_BUILDER,
                 "--in", RAW, "--out", parsed_path])

            # 3) parsed_resume → UCB
            scoring_cmd = [sys.executable, SCORING,
                           "--in", parsed_path, "--out", ucb_path]
            if args.redact:
                scoring_cmd.append("--redact")
            if args.jd:
                scoring_cmd += ["--jd", args.jd]
            run(scoring_cmd)

            print(f"[OK] {p.name} → {ucb_path}")
            ok += 1

        except subprocess.CalledProcessError:
            print(f"[FAIL] {p.name}")
            fail += 1

    elapsed = int((time.time() - t0_all) * 1000)
    print(f"\nSummary: OK={ok}, FAIL={fail}, total={len(files)}, "
          f"redact={'on' if args.redact else 'off'}, elapsed={elapsed}ms")

    # -------- Report (CSV + metrics.json) ที่รากโปรเจกต์ --------
    if args.report:
        try:
            scores = []
            ucb_files = sorted(UCB_DIR.glob("*.json"))
            for fp in ucb_files:
                try:
                    d = json.load(open(fp, encoding="utf-8"))
                    scores.append(int(d.get("fit_score", 0)))
                except Exception:
                    pass

            (ROOT / "shared_data").mkdir(parents=True, exist_ok=True)
            csv_path = ROOT / "shared_data/ucb_summary.csv"
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["file", "fit_score"])
                for fp in ucb_files:
                    try:
                        d = json.load(open(fp, encoding="utf-8"))
                        w.writerow([fp.name, d.get("fit_score", 0)])
                    except Exception:
                        w.writerow([fp.name, ""])

            avg = int(stats.mean(scores)) if scores else 0
            passed = sum(1 for s in scores if s >= args.pass_threshold)
            pass_rate = (passed * 100 // max(1, len(scores))) if scores else 0
            metrics = {
                "ok": ok, "fail": fail, "total": len(files),
                "generated_ucb": len(ucb_files),
                "avg_fit": avg,
                "pass_threshold": args.pass_threshold,
                "pass_rate_pct": pass_rate,
                "elapsed_ms": elapsed,
                "input_dir": str(in_dir),
                "includes_docx": bool(args.docx),
                "lang": args.lang,
                "redact": bool(args.redact),
                "jd_profile": args.jd or None,
            }
            metrics_path = ROOT / "shared_data/metrics.json"
            json.dump(metrics, open(metrics_path, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
            print(f"[REPORT] wrote {csv_path} & {metrics_path}")
        except Exception as e:
            print(f"[REPORT] error: {e}")

if __name__ == "__main__":
    main()



