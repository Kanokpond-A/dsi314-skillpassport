import json, glob
from jsonschema import Draft202012Validator

def test_parsed_files_match_schema():
    schema = json.load(open("A_backend/schemas/parsed_resume.schema.json","r",encoding="utf-8"))
    files = glob.glob("shared_data/latest_parsed/*.json")
    assert files, "no files in shared_data/latest_parsed"
    for p in files:
        data = json.load(open(p,"r",encoding="utf-8"))
        Draft202012Validator(schema).validate(data)

