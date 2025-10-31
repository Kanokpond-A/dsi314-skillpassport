from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "shared_data"

PARSED_DATA_PATH = Path(
    os.getenv(
        "PARSED_DATA_PATH",
        DATA_DIR / "parsed_resume.schema.json"
    )
)

