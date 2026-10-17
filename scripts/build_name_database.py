"""Build per-character multilingual name metadata; preserve distinct Amiya forms."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
AMlYA_FORMS = {"char_1001_amiya2", "char_1037_amiya3"}


def load(path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def main():
    skill_db = load(DATA / "generated" / "skill_database.json")
    en_path = DATA / "raw" / "en" / "character_table.json"
    if not en_path.exists():
        raise SystemExit(f"Missing {en_path}. Please download English character_table.json first.")
    en_db = load(en_path)
    result = {}
    for cid, char in skill_db["characters"].items():
        en_data = en_db.get(cid) or {}
        en_name = en_data.get("name") or ("Amiya" if cid in AMlYA_FORMS else None)
        result[cid] = {"name_jp": char.get("name_jp"), "name_en": en_name,
                       "name_zh_tw": char.get("name_zh_tw") or char.get("name_zh_tw_candidate")}
    dest = DATA / "generated" / "character_names.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    count = sum(bool(x["name_en"]) for x in result.values())
    print(f"Characters: {len(result)}")
    print(f"English names matched: {count}")
    print(f"Missing English names: {len(result) - count}")
    print(f"Saved: {dest}")


if __name__ == "__main__":
    main()
