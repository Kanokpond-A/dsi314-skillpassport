# frontend/streamlit_app.py
import json, glob, io, csv, math, datetime, subprocess
from collections import Counter, defaultdict
from pathlib import Path
import streamlit as st
import pandas as pd

# ---------------- Page Config ----------------
st.set_page_config(page_title="UCB Mini Dashboard", layout="wide")

ROOT = Path(__file__).resolve().parents[1] if (Path.cwd() / "frontend").exists() else Path.cwd()
SHARED = ROOT / "shared_data"

UCB_DIR    = SHARED / "latest_ucb"
PARSED_DIR = SHARED / "latest_parsed"
LOG_FILE   = SHARED / "pilot_log.csv"  # optional
SUMMARY_CSV = SHARED / "ucb_summary.csv"
METRICS_JSON = SHARED / "metrics.json"

# optional: pipeline runner
RUN_ALL = ROOT / "backend" / "app" / "services" / "A_backend" / "app" / "parsers" / "run_all.py"

PII_KEYS = {
    "email", "phone", "location", "address",
    "linkedin", "github", "line", "facebook",
    "linkedin_url", "github_url", "portfolio_url"
}

# ---------------- Helpers ----------------
def _bar_or_fallback(*, chart_fn, kwargs_width, kwargs_legacy):
    """Use new width API; fallback to use_container_width for older Streamlit."""
    try:
        return chart_fn(**kwargs_width)
    except TypeError:
        # older streamlit
        return chart_fn(**kwargs_legacy)

def redact_contacts(c: dict):
    """Mask PII values with ••• (payload may already be redacted; double-guard)."""
    if not isinstance(c, dict):
        return {}
    return {
        k: ("•••" if isinstance(v, str) and k.lower() in PII_KEYS and v else v)
        for k, v in c.items()
    }

def _ensure_list(x):
    if x is None: return []
    if isinstance(x, list): return x
    if isinstance(x, dict): return list(x.values())
    return [x]

def _skills_to_list(sk):
    """
    Normalize skills field across payload versions:
    - new: {"input":[...], "mined":[...], "all":[...]}
    - old: {"normalized":[...]} or just list
    Returns (skills_all, skills_in, skills_mined)
    """
    skills_all, skills_in, skills_mined = [], [], []
    if isinstance(sk, dict):
        if "all" in sk:
            skills_all  = _ensure_list(sk.get("all"))
            skills_in   = _ensure_list(sk.get("input"))
            skills_mined= _ensure_list(sk.get("mined"))
        elif "normalized" in sk:
            skills_all = _ensure_list(sk.get("normalized"))
        else:
            # flatten any dict to list of unique strings
            skills_all = _ensure_list(sk)
    elif isinstance(sk, list):
        skills_all = sk
    # dedupe keep-order
    seen, out = set(), []
    for s in skills_all:
        if s not in seen:
            seen.add(s); out.append(s)
    skills_all = out
    return skills_all, skills_in, skills_mined

def _reasons_to_list(reasons):
    """
    Normalize reasons: may be list or dict {"required_hit":[...], "nice_hit":[...]}
    """
    if isinstance(reasons, list):
        return reasons, [], []
    if isinstance(reasons, dict):
        req = _ensure_list(reasons.get("required_hit"))
        nice = _ensure_list(reasons.get("nice_hit"))
        merged = []
        if req:  merged.append("Matched required: " + ", ".join(req))
        if nice: merged.append("Matched nice-to-have: " + ", ".join(nice))
        return merged, req, nice
    return [], [], []

def _gaps_to_list(gaps):
    """
    Normalize gaps: may be list or dict {"required_miss":[...], "nice_miss":[...]}
    """
    if isinstance(gaps, list):
        return gaps, [], []
    if isinstance(gaps, dict):
        req_m = _ensure_list(gaps.get("required_miss"))
        nice_m= _ensure_list(gaps.get("nice_miss"))
        merged = []
        if req_m:  merged.append("Missing required: " + ", ".join(req_m))
        if nice_m: merged.append("Missing nice: " + ", ".join(nice_m))
        return merged, req_m, nice_m
    return [], [], []

@st.cache_data(show_spinner=False)
def load_ucb():
    rows, all_skills = [], set()
    files = sorted(UCB_DIR.glob("*.json"))
    for p in files:
        try:
            d = json.load(open(p, encoding="utf-8"))
            skills_all, skills_in, skills_mined = _skills_to_list(d.get("skills", []))
            reasons_list, req_hit, nice_hit = _reasons_to_list(d.get("reasons", []))
            gaps_list, req_miss, nice_miss = _gaps_to_list(d.get("gaps", []))
            ev = d.get("evidence") or {}
            rows.append({
                "file": p.name,
                "headline": d.get("headline", ""),
                "fit_score": int(d.get("fit_score", 0)),
                "skills_all": skills_all,
                "skills_in": skills_in,
                "skills_mined": skills_mined,
                "reasons": reasons_list,
                "req_hit": req_hit,
                "nice_hit": nice_hit,
                "gaps_list": gaps_list,
                "req_miss": req_miss,
                "nice_miss": nice_miss,
                "contacts": redact_contacts(d.get("contacts", {})),
                "evidence": ev if isinstance(ev, dict) else {},
                "raw": d,
            })
            all_skills.update(skills_all)
        except Exception as e:
            rows.append({
                "file": p.name, "headline": "<error>", "fit_score": 0,
                "skills_all": [], "skills_in": [], "skills_mined": [],
                "reasons": [f"error:{e}"], "req_hit": [], "nice_hit": [],
                "gaps_list": [], "req_miss": [], "nice_miss": [],
                "contacts": {}, "evidence": {}, "raw": {}
            })
    return rows, sorted(all_skills)

def force_refresh():
    load_ucb.clear()
    load_metrics.clear()
    load_summary.clear()
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()

def stringify_list(lst, sep=", "):
    return sep.join(lst) if lst else "—"

def score_bucket(x, step=10):
    return f"{(x//step)*step:02d}-{((x//step)*step+step-1):02d}"

def safe_unlink(p: Path) -> bool:
    try:
        if p.exists():
            p.unlink()
            return True
    except Exception:
        pass
    return False

def row_text(r):
    bag = []
    bag += [r["file"], r["headline"]]
    bag += r["skills_all"] + r["gaps_list"] + r["reasons"]
    return " ".join([x for x in bag if isinstance(x, str)]).lower()

@st.cache_data(show_spinner=False)
def load_summary():
    if SUMMARY_CSV.exists():
        try:
            df = pd.read_csv(SUMMARY_CSV)
            df.columns = [c.strip().lower() for c in df.columns]
            return df
        except Exception:
            pass
    # fallback from UCBs
    rows, _ = load_ucb()
    return pd.DataFrame([{"file": r["file"], "fit_score": r["fit_score"]} for r in rows])

@st.cache_data(show_spinner=False)
def load_metrics():
    if METRICS_JSON.exists():
        try:
            return json.load(open(METRICS_JSON, encoding="utf-8"))
        except Exception:
            return {}
    return {}

# ---------------- Data ----------------
rows, ALL_SKILLS = load_ucb()

# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("Run (optional)")
    in_dir = st.text_input("Input folder", str(ROOT / "samples"))
    lang   = st.text_input("OCR lang", "eng+tha")
    jd     = st.text_input("JD profile", str(ROOT / "config" / "jd_profiles" / "data-analyst.yml"))
    validate = st.checkbox("Validate schema", True)
    include_docx = st.checkbox("Include .docx", False)
    redact = st.checkbox("Redact PII", True)
    pass_threshold = st.slider("Pass threshold", 0, 100, 50, 5)
    if st.button("Run pipeline", use_container_width=True):
        if not RUN_ALL.exists():
            st.error(f"run_all.py not found at {RUN_ALL}")
        else:
            args = ["python", str(RUN_ALL),
                    "--in-dir", in_dir, "--lang", lang,
                    "--report", "--pass-threshold", str(pass_threshold)]
            if validate: args.append("--validate")
            if include_docx: args.append("--docx")
            args.append("--redact" if redact else "--no-redact")
            if jd: args += ["--jd", jd]
            with st.spinner("Running pipeline..."):
                proc = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True)
            if proc.returncode != 0:
                st.error("Pipeline failed:")
                st.code(proc.stderr or proc.stdout)
            else:
                st.success("Pipeline finished.")
                st.code(proc.stdout)
                force_refresh()

    st.divider()
    st.header("Filters")
    q = st.text_input("Search (file/headline/skills/gaps)", "", key="q_search")
    min_s, max_s = st.slider("Score range", 0, 100, (0, 100), key="score_range")
    must_have = st.multiselect("Must-have skills", ALL_SKILLS, placeholder="Select skills", key="must_skills")
    sort_by = st.selectbox("Sort by", ["fit_score", "file", "headline"], index=0, key="sort_by")
    asc = st.toggle("Ascending", value=False, key="ascending")
    st.caption("PII masked for internal testing.")
    if st.button("↻ Refresh files & metrics", use_container_width=True):
        force_refresh()

def match(r):
    if not (min_s <= r["fit_score"] <= max_s):
        return False
    if q and (q.lower() not in row_text(r)):
        return False
    if must_have and not set(must_have).issubset(set(r["skills_all"])):
        return False
    return True

filtered = [r for r in rows if match(r)]
filtered = sorted(filtered, key=lambda r: r[sort_by], reverse=not asc)

# ---------------- Header ----------------
st.markdown("## UCB Mini Dashboard")
st.caption("Shortlist faster. Compare candidates. Understand skill gaps. — **HR view**")

# ---------------- KPIs ----------------
metrics = load_metrics()
count = len(filtered)
avg = int(sum(r["fit_score"] for r in filtered) / count) if count else 0
passed = sum(1 for r in filtered if r["fit_score"] >= pass_threshold)
pass_rate = f"{(passed * 100 // count) if count else 0}%"
top_sk = Counter(s for r in filtered for s in r["skills_all"]).most_common(3)
top_gap = Counter(g for r in filtered for g in r["gaps_list"]).most_common(3)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Candidates (after filters)", count)
k2.metric("Average score", avg)
k3.metric(f"Pass rate ≥ {pass_threshold}", pass_rate)
k4.metric("Top skills / Top gaps",
          f"{stringify_list([f'{k} ({v})' for k, v in top_sk])}  |  "
          f"{stringify_list([f'{k} ({v})' for k, v in top_gap])}")

st.divider()

# ---------------- Charts ----------------
g1, g2 = st.columns(2)

with g1:
    st.subheader("Score distribution")
    buckets = Counter(score_bucket(r["fit_score"]) for r in filtered)
    labels = sorted(buckets.keys(), key=lambda s: int(s.split("-")[0]))
    df_hist = pd.DataFrame({"bucket": labels, "count": [buckets[l] for l in labels]})
    _bar_or_fallback(
        chart_fn=st.bar_chart,
        kwargs_width={"data": df_hist, "x": "bucket", "y": "count", "width": "stretch"},
        kwargs_legacy={"data": df_hist, "x": "bucket", "y": "count", "use_container_width": True},
    )

with g2:
    st.subheader("Top gaps (10)")
    gap_counts = Counter(g for r in filtered for g in r["gaps_list"])
    top10_gaps = gap_counts.most_common(10)
    df_gaps = pd.DataFrame({"gap": [g for g, _ in top10_gaps], "count": [c for _, c in top10_gaps]})
    _bar_or_fallback(
        chart_fn=st.bar_chart,
        kwargs_width={"data": df_gaps, "x": "gap", "y": "count", "width": "stretch"},
        kwargs_legacy={"data": df_gaps, "x": "gap", "y": "count", "use_container_width": True},
    )

st.divider()

# ---------------- Candidate Cards (quick scan) ----------------
st.subheader("Candidates")
st.caption("Click a row below for full JSON or use Compare to see side-by-side.")

def render_card(r, key_prefix):
    card = st.container(border=True)
    with card:
        c1, c2, c3, c4 = st.columns([1, 2, 2, 2])
        c1.markdown(f"### {r['fit_score']}")
        c1.caption("Fit score")
        c2.markdown(f"**{r['headline'] or '—'}**")
        c3.caption("Req hit")
        c3.write(stringify_list(r["req_hit"]))
        c4.caption("Nice hit")
        c4.write(stringify_list(r["nice_hit"]))
        st.caption(f"Skills: {stringify_list(r['skills_all'])}")
        with st.expander("Reasons / Gaps", expanded=False):
            st.write("**Reasons**")
            st.write("- " + "\n- ".join(r["reasons"]) if r["reasons"] else "—")
            st.write("**Gaps**")
            st.write(stringify_list(r["gaps_list"]))
        with st.expander("Contacts (redacted)"):
            st.json(r.get("contacts", {}), expanded=False)

for idx, r in enumerate(filtered[:12]):  # show top 12 cards
    render_card(r, key_prefix=f"card-{idx}")

st.divider()

# ---------------- Table (exportable) ----------------
st.subheader("All results (table)")
table_rows = [{
    "file": r["file"],
    "fit_score": r["fit_score"],
    "headline": r["headline"],
    "skills_all": stringify_list(r["skills_all"]),
    "req_hit": stringify_list(r["req_hit"]),
    "nice_hit": stringify_list(r["nice_hit"]),
    "gaps": stringify_list(r["gaps_list"]),
} for r in filtered]

st.dataframe(table_rows, use_container_width=True)

buf = io.StringIO()
w = csv.writer(buf)
w.writerow(["file", "fit_score", "headline", "skills_all", "req_hit", "nice_hit", "gaps"])
for r in filtered:
    w.writerow([
        r["file"], r["fit_score"], r["headline"],
        stringify_list(r["skills_all"]), stringify_list(r["req_hit"]),
        stringify_list(r["nice_hit"]), stringify_list(r["gaps_list"])
    ])
st.download_button("⬇️ Export filtered to CSV", buf.getvalue().encode("utf-8"),
                   "ucb_filtered.csv", "text/csv", key="dl_csv")

st.divider()

# ---------------- Compare Two ----------------
st.subheader("Compare two candidates")
left, right = st.columns(2)
options = [r["file"] for r in filtered]

c1 = left.selectbox("Candidate A", options, index=0 if options else None, key="pick_A")
c2 = right.selectbox("Candidate B", options, index=1 if len(options) > 1 else (0 if options else None), key="pick_B")

def render_compare(panel, file, key_prefix):
    if not file:
        panel.info("Select a candidate")
        return
    r = next((x for x in filtered if x["file"] == file), None)
    if not r:
        panel.warning("Not in filtered results")
        return
    d = r["raw"]

    # compact summary
    k1, k2 = panel.columns([1, 6])
    k1.metric("Fit", r["fit_score"])
    k2.write(f"**{r['headline'] or '—'}**")

    with panel.expander("Reasons / Gaps"):
        panel.write("**Reasons**")
        panel.write("- " + "\n- ".join(r.get("reasons", [])) if r.get("reasons") else "—")
        panel.write("**Gaps**")
        panel.write(stringify_list(r.get("gaps_list", [])))

    with panel.expander("Skills (input / mined / all)"):
        panel.write("**Input**: " + stringify_list(r["skills_in"]))
        panel.write("**Mined**: " + stringify_list(r["skills_mined"]))
        panel.write("**All**: "   + stringify_list(r["skills_all"]))

    with panel.expander("Evidence (by skill)"):
        ev = r.get("evidence") or {}
        if ev:
            for k, v in ev.items():
                with panel.expander(k, expanded=False):
                    for s in _ensure_list(v)[:3]:
                        panel.write("• " + str(s))
        else:
            panel.info("No evidence captured.")

    with panel.expander("Contacts (redacted)"):
        panel.json(r.get("contacts", {}))

    with panel.expander("Raw JSON"):
        panel.json(d)

    # Danger zone
    with panel.expander("🛑 Danger zone"):
        base = Path(file).stem
        p_ucb = UCB_DIR / f"{base}.json"
        p_parsed = PARSED_DIR / f"{base}.json"
        if panel.button(f"Delete files for {file}", key=f"{key_prefix}-del"):
            ok1 = safe_unlink(p_ucb)
            ok2 = safe_unlink(p_parsed)
            panel.success(f"Deleted → UCB={ok1}, Parsed={ok2}. Click Refresh to update.")

render_compare(left, c1, "A")
render_compare(right, c2, "B")

st.divider()

# ---------------- Pilot Metrics (optional) ----------------
with st.expander("Pilot metrics (optional)"):
    if LOG_FILE.exists():
        import csv as _csv
        before, after, thumbs = [], [], Counter()
        with open(LOG_FILE, encoding="utf-8") as f:
            r = _csv.DictReader(f)
            for row in r:
                (before if row.get("mode") == "before" else after).append(float(row.get("seconds", 0)))
                if row.get("thumb") in ("up", "down"):
                    thumbs[row["thumb"]] += 1
        if before and after:
            mean_b = sum(before) / len(before)
            mean_a = sum(after) / len(after)
            red = (mean_b - mean_a) / mean_b * 100 if mean_b else 0
            m1, m2, m3 = st.columns(3)
            m1.metric("Avg before (s)", f"{mean_b:.1f}")
            m2.metric("Avg after (s)", f"{mean_a:.1f}")
            m3.metric("Time reduced", f"{red:.1f}%")
        st.write(f"Thumbs: 👍 {thumbs.get('up', 0)}  |  👎 {thumbs.get('down', 0)}")
    else:
        st.info("No pilot log yet (`shared_data/pilot_log.csv`).")

# ---------------- Footer ----------------
st.caption("Tip: Use the **Run pipeline** in the sidebar to regenerate, then press Refresh.")
