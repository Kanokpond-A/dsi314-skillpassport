import csv, statistics as stats, itertools

def read(path="shared_data/pilot_log.csv"):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))

def main():
    rows = read()
    by_user = {}
    for k, g in itertools.groupby(sorted(rows, key=lambda r:(r["user"], r["mode"])), key=lambda r:r["user"]):
        by_user[k] = list(g)

    before = [float(r["seconds"]) for r in rows if r["mode"]=="before"]
    after  = [float(r["seconds"]) for r in rows if r["mode"]=="after"]
    if before and after:
        mean_before, mean_after = stats.mean(before), stats.mean(after)
        reduction = (mean_before-mean_after)/mean_before*100
    else:
        mean_before=mean_after=reduction=float("nan")

    up = sum(1 for r in rows if r["thumb"]=="up")
    down = sum(1 for r in rows if r["thumb"]=="down")

    print(f"n={len(rows)} | before={len(before)} after={len(after)}")
    print(f"mean_before={mean_before:.1f}s  mean_after={mean_after:.1f}s  reduction={reduction:.1f}%")
    print(f"thumbs: up={up} down={down}")

if __name__=="__main__":
    main()
