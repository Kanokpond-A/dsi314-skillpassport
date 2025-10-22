# backend/app/services/A_backend/app/parsers/run_all.py
import argparse, subprocess, sys, json, csv, statistics as stats, time, datetime
from pathlib import Path

# --- Resolve repo root ---
# File is at: backend/app/services/A_backend/app/parsers/run_all.py
# -> go up 6 levels to reach repo root
ROOT = Path(__file__).resolve().parents[6]

# --- I/O directories (relative to repo root) ---
DEFAULT_IN = ROOT / "samples"
PARSED_DIR = ROOT / "shared_data/latest_parsed"
UCB_DIR    = ROOT / "shared_data/latest_ucb"
TMP_DIR    = ROOT / "shared_data/examples"

# --- A_backend module base ---
BASE = ROOT / "backend/app/services/A_backend"
PDF_PARSER     = BASE / "parsers/pdf_parser.py"
DOCX_PARSER    = BASE / "parsers/docx_parser.py"
STRUCT_BUILDER = BASE / "preprocess/structure_builder.py"
SCORING        = BASE / "normalize_scoring/scoring.py"
SCHEMA_PATH    = ROOT / "backend/app/schemas/parsed_resume.schema.json"  # v0.2.0

def run(cmd):
    """Run a command; print helpful logs on failure."""
    print("→", " ".join(map(str, cmd)))
    p = subprocess.run(list(map(str, cmd)), capture_output=True, text=True)
    if p.returncode != 0:
        if p.stdout: print("STDOUT:\n", p.stdout[:4000])
        if p.stderr: print("STDERR:\n", p.stderr[:4000])
        raise subprocess.CalledProcessError(p.returncode, cmd, p.stdout, p.stderr)
    return p

def collect_files(indir: Path, include_docx: bool):
    files = list(sorted(indir.glob("*.pdf")))
    if include_docx:
        files += list(sorted(indir.glob("*.docx")))
    return files

def validate_parsed_json(parsed_path: Path, schema_path: Path) -> bool:
    """Validate parsed JSON against schema if jsonschema is available; otherwise noop."""
    try:
        import jsonschema  # type: ignore
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        data   = json.loads(parsed_path.read_text(encoding="utf-8"))
        jsonschema.validate(instance=data, schema=schema)
        return True
    except ModuleNotFoundError:
        print("⚠️  jsonschema not installed; skipping schema validation.")
        return True
    except Exception as e:
        print(f"❌ schema validation failed for {parsed_path.name}: {e}")
        return False

def main():
    ap = argparse.ArgumentParser(
        description="Batch: parse (PDF/DOCX) → build (v0.2.0) → score → UCB"
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
    ap.add_argument("--validate", action="store_true",
                    help="validate parsed JSON against parsed_resume.schema.json")
    args = ap.parse_args()

    in_dir = Path(args.in_dir)
    if not in_dir.exists():
        print(f"❌ input folder not found: {in_dir}")
        sys.exit(1)

    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    UCB_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    files = collect_files(in_dir, include_docx=args.docx)
    print(f"found files: {len(files)} in {in_dir} "
          f"(pdf{' + docx' if args.docx else ''})")
    if not files:
        print("⚠️  No files found. Put PDF/DOCX into the input folder and try again.")
        return

    if args.docx and not DOCX_PARSER.exists():
        print("⚠️  docx_parser.py not found. DOCX files will fail. Expected at:", DOCX_PARSER)

    # Quick existence checks
    for path_needed in (PDF_PARSER, STRUCT_BUILDER, SCORING):
        if not path_needed.exists():
            print(f"❌ required module not found: {path_needed}")
            sys.exit(1)

    ok, fail = 0, 0
    t0_all = time.time()

    for p in files:
        parsed_path = PARSED_DIR / f"{p.stem}.json"
        ucb_path    = UCB_DIR / f"{p.stem}.json"

        if args.skip_existing and parsed_path.exists() and ucb_path.exists():
            print(f"[SKIP] {p.name}")
            continue

        # unique RAW temp per file (avoid stale collisions)
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        raw_tmp = TMP_DIR / f"raw_{p.stem}_{ts}.json"

        try:
            # 1) PDF/DOCX → RAW
            if p.suffix.lower() == ".pdf":
                run([sys.executable, PDF_PARSER,
                     "--in", p, "--out", raw_tmp, "--lang", args.lang])
            else:
                run([sys.executable, DOCX_PARSER,
                     "--in", p, "--out", raw_tmp])

            # 2) RAW → parsed_resume.json (schema v0.2.0)
            run([sys.executable, STRUCT_BUILDER,
                 "--in", raw_tmp, "--out", parsed_path])

            # 2.1) Optional JSON Schema validation
            if args.validate:
                if not SCHEMA_PATH.exists():
                    print(f"⚠️  schema file not found at {SCHEMA_PATH}, skipping validation.")
                else:
                    if not validate_parsed_json(parsed_path, SCHEMA_PATH):
                        print(f"[FAIL] {p.name} (schema invalid)")
                        fail += 1
                        # keep the file for inspection but skip scoring
                        continue

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
        finally:
            # best-effort cleanup of temp raw
            try:
                if raw_tmp.exists():
                    raw_tmp.unlink()
            except Exception:
                pass

    elapsed = int((time.time() - t0_all) * 1000)
    print(f"\nSummary: OK={ok}, FAIL={fail}, total={len(files)}, "
          f"redact={'on' if args.redact else 'off'}, elapsed={elapsed}ms")

    # -------- Report (CSV + metrics.json) at repo root/shared_data --------
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
                "validated": bool(args.validate),
                "schema_path": str(SCHEMA_PATH) if args.validate else None,
            }
            metrics_path = ROOT / "shared_data/metrics.json"
            json.dump(metrics, open(metrics_path, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
            print(f"[REPORT] wrote {csv_path} & {metrics_path}")
        except Exception as e:
            print(f"[REPORT] error: {e}")

if __name__ == "__main__":
    main()




