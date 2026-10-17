"""No OCR needed: verify ambiguity-aware name matching from saved database."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from arknights_translator.name_match import rank_names

skill_db = json.loads((ROOT / "data/generated/skill_database.json").read_text(encoding="utf-8-sig"))["characters"]
name_db = json.loads((ROOT / "data/generated/character_names.json").read_text(encoding="utf-8-sig"))
for name in ("アーミヤ", "Amiya", "エクシア", "Exusiai", "ウィシャデル", "Wis'adel", "randombadtext"):
    result = rank_names([name], skill_db, name_db)
    print(f"{name!r}: {result['status']}; id={result['character_id']}; candidates={[(c['character_id'],c['score']) for c in result['candidates']]}")
