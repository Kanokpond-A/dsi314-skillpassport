# Ensure project root on sys.path for pytest
import sys
from pathlib import Path

THIS = Path(__file__).resolve()
ROOT = None
for cand in [THIS.parent, *THIS.parents]:
    if (cand / "backend").exists() and (cand / "shared_data").exists():
        ROOT = cand
        break
if ROOT is None:  # fallback
    ROOT = THIS.parents[5]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
