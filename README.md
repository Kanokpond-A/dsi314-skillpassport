## Hello World


### Quick Run (W3) — Scoring → UCB

```bash
python A_backend/normalize_scoring/scoring.py \
  --in shared_data/latest_parsed/a.json \
  --out shared_data/latest_ucb/a.json
pytest -q
```


### Quick Run (W4) — One command

```bash
python A_backend/app/parsers/run_all.py --lang eng --skip-existing
pytest -q
```



### Quick Run (W4) — One command

```bash
python A_backend/app/parsers/run_all.py --lang eng --skip-existing
pytest -q
```



### Quick Run (W5) — Mini Dashboard

```bash
pip install streamlit
streamlit run frontend/streamlit_app.py
```


### Quick Run (W5) — Pilot & Metrics

```bash
python tools/log_time.py --user hr1 --mode before --resume a.json --seconds 95 --thumb down --reason "หาสกิลไม่เจอ"
python tools/log_time.py --user hr1 --mode after  --resume a.json --seconds 55 --thumb up   --reason "เห็น gaps ชัด"
python tools/metrics.py
```
## Quick Run

Parse PDFs:  python A_backend/parsers/batch_parse_pdfs.py
Validate:    python A_backend/tests/validate_parsed.py
Run tests:   pytest -q


OCR lang: use --lang eng or --lang eng+tha (if installed)

###Run FastAPI
```bash
uvicorn backend.app.main:app --reload
```
