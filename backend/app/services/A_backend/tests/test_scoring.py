import json, glob, subprocess, sys, pathlib
def test_ucb_payload_fields():
    srcs = glob.glob("shared_data/latest_parsed/*.json")
    assert srcs, "no parsed files"
    pathlib.Path("shared_data/latest_ucb").mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable,"A_backend/normalize_scoring/scoring.py",
                    "--in", srcs[0], "--out", "shared_data/latest_ucb/_tmp.json"], check=True)
    d = json.load(open("shared_data/latest_ucb/_tmp.json"))
    for k in ["candidate_id","headline","skills","fit_score","reasons","gaps"]:
        assert k in d
