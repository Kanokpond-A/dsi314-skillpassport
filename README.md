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
