import argparse, csv, datetime as dt, os, json
from jsonschema import Draft202012Validator

SCHEMA = json.load(open("tools/pilot_log.schema.json", "r", encoding="utf-8"))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--mode", required=True, choices=["before","after"])
    ap.add_argument("--resume", required=True, help="ชื่อไฟล์ JSON เช่น a.json")
    ap.add_argument("--seconds", type=float, required=True)
    ap.add_argument("--thumb", choices=["up","down"], required=True)
    ap.add_argument("--reason", default="")
    ap.add_argument("--out", default="shared_data/pilot_log.csv")
    args = ap.parse_args()

    row = {
        "ts": dt.datetime.now().isoformat(timespec="seconds"),
        "user": args.user,
        "mode": args.mode,
        "resume": args.resume,
        "seconds": args.seconds,
        "thumb": args.thumb,
        "reason": args.reason
    }
    # validate
    Draft202012Validator(SCHEMA).validate(row)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    new_file = not os.path.exists(args.out)
    with open(args.out, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if new_file: w.writeheader()
        w.writerow(row)
    print("OK ->", args.out, row)

if __name__ == "__main__":
    main()
