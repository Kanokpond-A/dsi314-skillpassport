# validate_schema.py
import json
from jsonschema import validate, Draft7Validator
from pathlib import Path

schema = json.loads(Path("backend/schemas/ucb_payload.schema.json").read_text(encoding="utf-8"))
data = json.loads(Path("shared_data/ucb_payload.json").read_text(encoding="utf-8"))

Draft7Validator.check_schema(schema)  # ถ้าสคีมาไม่ถูกจะ throw
validate(instance=data, schema=schema)
print("OK ✔")
