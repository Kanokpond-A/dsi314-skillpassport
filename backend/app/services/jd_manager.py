import json
import os
from pathlib import Path
from typing import List, Dict

# ==================================================
# 🔧 Path Configuration (Smart Discovery)
# ==================================================

# 1. Get current file location
CURRENT_FILE = Path(__file__).resolve()

# 2. Define potential locations for 'config/jd_profiles'
possible_paths = [
    # Option A: Relative to the current working directory (where you ran the command)
    Path(os.getcwd()) / "config" / "jd_profiles",
    
    # Option B: Relative to this file (backend/app/services/jd_manager.py) -> Go up to Root
    CURRENT_FILE.parents[3] / "config" / "jd_profiles",
    
    # Option C: In case 'config' is inside 'backend' (backend/config/jd_profiles)
    CURRENT_FILE.parents[2] / "config" / "jd_profiles"
]

JD_STORAGE_PATH = None

print("--------------------------------------------------")
print("🔍 DEBUG: JD Manager Path Discovery")

# 3. Search for an existing folder
for path in possible_paths:
    print(f"   Checking: {path}")
    if path.exists():
        JD_STORAGE_PATH = path
        print(f"✅ Found Config Folder at: {JD_STORAGE_PATH}")
        break

# 4. Fallback: If not found, create it at the project root (Option B)
if JD_STORAGE_PATH is None:
    print("⚠️ Config folder not found. Creating new one at standard root.")
    # Default to 4 levels up (standard structure)
    JD_STORAGE_PATH = CURRENT_FILE.parents[3] / "config" / "jd_profiles"
    JD_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    print(f"📁 Created new folder at: {JD_STORAGE_PATH}")

print("--------------------------------------------------")


def get_all_jobs() -> List[Dict]:
    """Reads all Job Profile JSON files from the folder."""
    jobs = []
    
    try:
        # Check if directory exists before iterating
        if not JD_STORAGE_PATH.exists():
             print(f"❌ Error: Directory {JD_STORAGE_PATH} does not exist.")
             return []

        all_files = list(JD_STORAGE_PATH.glob("*.json"))
        print(f"📂 Reading JDs from: {JD_STORAGE_PATH}")
        print(f"📄 Found {len(all_files)} json files.")
        
        for file_path in all_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Use filename as title if missing
                    if "title" not in data:
                        data["title"] = file_path.stem.replace("_", " ").title()
                    jobs.append(data)
            except Exception as e:
                print(f"❌ Corrupted JSON {file_path.name}: {e}")

    except Exception as e:
        print(f"❌ Error accessing folder: {e}")
        return []

    return jobs

def save_job(title: str, description: str):
    print(f"💾 Saving Job: '{title}'")
    safe_filename = "".join(c for c in title.strip().replace(" ", "_").lower() if c.isalnum() or c in ('_', '-')) 
    if not safe_filename: safe_filename = "untitled"
    
    file_path = JD_STORAGE_PATH / f"{safe_filename}.json"
    
    data = {"id": f"{safe_filename}.json", "title": title.strip(), "description": description.strip()}
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"✅ File saved: {file_path}")
        return data
    except Exception as e:
        print(f"❌ Save Error: {e}")
        raise e