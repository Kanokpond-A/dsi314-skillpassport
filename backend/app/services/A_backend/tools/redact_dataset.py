import argparse, json
from pathlib import Path

PII_KEYS = {"email","phone","location","address","linkedin","github","line","facebook"}

def redact_contacts(c: dict) -> dict:
    if not isinstance(c, dict): return {}
    out = {}
    for k, v in c.items():
        out[k] = "•••" if isinstance(v, str) and k.lower() in PII_KEYS and v else v
    return out

def main():
    ap = argparse.ArgumentParser(description="Redact PII in all UCB files")
    ap.add_argument("--in",  dest="inp", required=True, help="input directory (e.g., shared_data/latest_ucb)")
    ap.add_argument("--out", dest="out", required=True, help="output directory (e.g., shared_data/redacted_ucb)")
    args = ap.parse_args()

    in_dir  = Path(args.inp)
    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)

    ok = 0
    for p in sorted(in_dir.glob("*.json")):
        try:
            d = json.load(open(p, encoding="utf-8"))
            # ใส่ contacts ที่ redact แล้ว (กันกรณีต้นฉบับยังไม่ redact)
            d["contacts"] = redact_contacts(d.get("contacts", {}))
            out_p = out_dir / p.name
            json.dump(d, open(out_p,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
            ok += 1
        except Exception as e:
            print("[SKIP]", p.name, "->", e)
    print(f"[DONE] redacted {ok} files -> {out_dir}")

if __name__ == "__main__":
    main()
