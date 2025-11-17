## UCB Project


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
streamlit run frontend/2_Dashboard_Explorer.py
```

### Quick Run (W5) — Pilot & Metrics

```bash
python tools/log_time.py --user hr1 --mode before --resume a.json --seconds 95 --thumb down --reason "หาสกิลไม่เจอ"
python tools/log_time.py --user hr1 --mode after  --resume a.json --seconds 55 --thumb up   --reason "เห็น gaps ชัด"
python tools/metrics.py
```



## A1 — Parsed Resume (Universal) · v0.2.0

**ไฟล์มาตรฐาน (output):**

- `shared_data/latest_parsed/parsed_resume.json`

**คีย์บังคับต้องมี:**

- `source_file` (string)
- `name` (string)
- `contacts.location` (string ภายในออบเจ็กต์ `contacts`)
- `education` (array of objects)
- `experiences` (array of objects)
- `skills` (array of strings)

**ตัวอย่างสั้น (minimal valid)**

```json
{
  "source_file": "samples/john_doe.pdf",
  "name": "John Doe",
  "contacts": { "location": "Bangkok" },
  "education": [
    { "school": "ABC University", "degree": "BBA", "end_date": "2022" }
  ],
  "experiences": [
    { "employer": "XYZ Co.", "title": "Analyst", "start_date": "2023-01", "end_date": "2024-06", "bullets": ["Data cleaning", "Reporting"] }
  ],
  "skills": ["Excel", "SQL"]
}
```


# A1 Parsed Resume Export

## Schema

- backend/app/services/A_backend/schemas/parsed_resume.schema.json

## How to (re)generate

# 1 สร้าง parsed (ต่อไฟล์) แล้วรวม

python backend/app/services/A_backend/preprocess/structure_builder.py --in samples/any_raw.json --out shared_data/latest_parsed/any.json
python backend/app/services/A_backend/preprocess/aggregate_export.py --in shared_data/latest_parsed --out shared_data/parsed_resume.json

# (ชุดเต็มจาก raw → ucb + shortlist)

python backend/app/services/A_backend/app/parsers/run_all.py --in-dir samples --lang eng+tha --report --validate --redact --pass-threshold 50

## QA

# validate schema

pytest -q backend/app/services/A_backend/tests/test_schema_validation.py

# verify redaction (no emails/phones)

python - <<'PY'

# (สคริปต์จากข้อ 9.2)

PY

# A1 Export → A2 Hand-off

## How to regenerate

```bash
# 1) Parse raw resumes → latest_parsed/*
python backend/app/services/A_backend/parsers/run_all.py --in samples --out-dir shared_data/latest_parsed

# 2) Aggregate with redaction + fallbacks
python backend/app/services/A_backend/preprocess/aggregate_export.py \
  --in shared_data/latest_parsed \
  --out shared_data/parsed_resume.json
```

# frontend run terminal

1.
```bash
streamlit run frontend/2_Dashboard_Explorer.py
```
2.
```bash
uvicorn backend.app.main:app --reload
```