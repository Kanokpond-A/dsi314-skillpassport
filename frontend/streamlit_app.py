# frontend/streamlit_app.py
import json, glob, io, csv, math, datetime
from collections import Counter, defaultdict
from pathlib import Path
import streamlit as st
import pandas as pd

# ---------------- Page Config ----------------
st.set_page_config(page_title="UCB Mini Dashboard", layout="wide")

UCB_DIR = Path("shared_data/latest_ucb")
PARSED_DIR = Path("shared_data/latest_parsed")
LOG_FILE = Path("shared_data/pilot_log.csv")  # optional metrics
PII_KEYS = {
    "email", "phone", "location", "address",
    "linkedin", "github", "line", "facebook",
    "linkedin_url", "github_url", "portfolio_url"
}

PASS_THRESHOLD = 70  # HR-friendly quick benchmark

# ---------------- Helpers ----------------
def _bar_or_fallback(*, chart_fn, kwargs_width, kwargs_legacy):
    """Use new width API; fallback to use_container_width for older Streamlit."""
    try:
        return chart_fn(**kwargs_width)
    except TypeError:
        # older streamlit
        return chart_fn(**kwargs_legacy)

def redact_contacts(c: dict):
    """Mask PII values with ••• (payload already redacted, but double-guard)."""
    if not isinstance(c, dict):
        return {}
    return {
        k: ("•••" if isinstance(v, str) and k.lower() in PII_KEYS and v else v)
        for k, v in c.items()
    }

@st.cache_data(show_spinner=False)
def load_ucb():
    rows, all_skills = [], set()
    for p in sorted(UCB_DIR.glob("*.json")):
        try:
            d = json.load(open(p, encoding="utf-8"))
            norm_sk = list(d.get("skills", {}).get("normalized", []))
            gaps = list(d.get("gaps", []))
            rows.append({
                "file": p.name,
                "headline": d.get("headline", ""),
                "fit_score": int(d.get("fit_score", 0)),
                "skills": norm_sk,
                "gaps": gaps,
                "reasons": d.get("reasons", []),
                "contacts": redact_contacts(d.get("contacts", {})),
                "raw": d,
            })
            all_skills.update(norm_sk)
        except Exception as e:
            rows.append({
                "file": p.name, "headline": "<error>", "fit_score": 0,
                "skills": [], "gaps": [f"error:{e}"], "reasons": [],
                "contacts": {}, "raw": {}
            })
    return rows, sorted(all_skills)

def force_refresh():
    load_ucb.clear()
    try:
        st.rerun()  # Streamlit >= 1.30
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
    return " ".join([
        r["file"], r["headline"],
        " ".join(r["skills"]),
        " ".join(r["gaps"]),
        " ".join(r["reasons"]),
    ]).lower()

# ---------------- Data ----------------
rows, ALL_SKILLS = load_ucb()

# ---------------- Sidebar (Filters) ----------------
with st.sidebar:
    st.header("Filters")
    q = st.text_input("Search (file / headline / skills / gaps)", "", key="q_search")
    min_s, max_s = st.slider("Score range", 0, 100, (0, 100), key="score_range")
    must_have = st.multiselect("Must-have skills", ALL_SKILLS, placeholder="Select skills", key="must_skills")
    sort_by = st.selectbox("Sort by", ["fit_score", "file", "headline"], index=0, key="sort_by")
    asc = st.toggle("Ascending", value=False, key="ascending")
    st.caption("PII is masked for internal testing.")

    st.divider()
    if st.button("↻ Refresh", key="refresh_btn"):
        force_refresh()

def match(r):
    if not (min_s <= r["fit_score"] <= max_s):
        return False
    if q and (q.lower() not in row_text(r)):
        return False
    if must_have and not set(must_have).issubset(set(r["skills"])):
        return False
    return True

filtered = [r for r in rows if match(r)]
filtered = sorted(filtered, key=lambda r: r[sort_by], reverse=not asc)

# ---------------- Header ----------------
st.markdown("## UCB Mini Dashboard")
st.caption("Shortlist faster. Compare candidates. Understand skill gaps. — **HR view**")

# ---------------- KPIs ----------------
count = len(filtered)
avg = int(sum(r["fit_score"] for r in filtered) / count) if count else 0
passed = sum(1 for r in filtered if r["fit_score"] >= PASS_THRESHOLD)
pass_rate = f"{(passed * 100 // count) if count else 0}%"
top_sk = Counter(s for r in filtered for s in r["skills"]).most_common(3)
top_gap = Counter(g for r in filtered for g in r["gaps"]).most_common(3)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Candidates (after filters)", count)
k2.metric("Average score", avg)
k3.metric(f"Pass rate ≥ {PASS_THRESHOLD}", pass_rate)
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
    gap_counts = Counter(g for r in filtered for g in r["gaps"])
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
        c1, c2 = st.columns([1, 5])
        c1.markdown(f"### {r['fit_score']}")
        c1.caption("Fit score")
        c2.markdown(f"**{r['headline'] or '—'}**")
        st.caption(f"Skills: {stringify_list(r['skills'])}")
        with st.expander("Reasons / Gaps", expanded=False):
            st.write("**Reasons**")
            st.write("- " + "\n- ".join(r["reasons"]) if r["reasons"] else "—")
            st.write("**Gaps**")
            st.write(stringify_list(r["gaps"]))
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
    "skills": stringify_list(r["skills"]),
    "gaps": stringify_list(r["gaps"]),
} for r in filtered]

st.dataframe(table_rows, use_container_width=True)

buf = io.StringIO()
w = csv.writer(buf)
w.writerow(["file", "fit_score", "headline", "skills", "gaps"])
for r in filtered:
    w.writerow([r["file"], r["fit_score"], r["headline"], stringify_list(r["skills"]), stringify_list(r["gaps"])])
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
        panel.write("- " + "\n- ".join(d.get("reasons", [])) if d.get("reasons") else "—")
        panel.write("**Gaps**")
        panel.write(stringify_list(d.get("gaps", [])))

    with panel.expander("Skills (normalized)"):
        panel.write(stringify_list(d.get("skills", {}).get("normalized", [])))

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
st.caption("Tip: Use the **Refresh** button in the sidebar to reload fresh files. PII remains masked.")
