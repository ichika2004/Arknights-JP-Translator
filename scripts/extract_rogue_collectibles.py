
import json
from collections import Counter
from pathlib import Path

ROOT = Path("data")
RAW = ROOT / "raw" / "roguelike"
OUT = ROOT / "generated"


def load_language(lang):
    path = RAW / lang / "roguelike_topic_table.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main():
    jp_data = load_language("jp")
    tw_data = load_language("tw")

    collectibles = {}
    special_items = {}
    other_items = {}
    report = {}

    for topic_id, jp_topic in jp_data["details"].items():
        tw_topic = tw_data.get("details", {}).get(topic_id, {})

        jp_items = jp_topic.get("items", {})
        tw_items = tw_topic.get("items", {})

        categories = Counter()
        missing_tw = 0

        for item_id, jp in jp_items.items():
            if not isinstance(jp, dict):
                continue

            tw = tw_items.get(item_id, {})
            if not isinstance(tw, dict):
                tw = {}

            item_type = jp.get("type", "")
            sub_type = jp.get("subType", "")

            record = {
                "topic_id": topic_id,
                "item_id": item_id,
                "type": item_type,
                "sub_type": sub_type,
                "name_jp": jp.get("name", ""),
                "name_tw": tw.get("name", ""),
                "description_jp": jp.get("description", ""),
                "description_tw": tw.get("description", ""),
                "usage_jp": jp.get("usage", ""),
                "usage_tw": tw.get("usage", ""),
                "short_usage_jp": jp.get("shortUsage", ""),
                "short_usage_tw": tw.get("shortUsage", ""),
                "rarity": jp.get("rarity"),
                "translation_source": (
                    "tw_exact_id" if tw else "missing_tw"
                ),
                "review_status": "pending",
            }

            if not tw:
                missing_tw += 1

            categories[f"{item_type} / {sub_type}"] += 1
            key = f"{topic_id}/{item_id}"

            if item_type == "RELIC":
                collectibles[key] = record
            elif item_type in {
                "TOTEM", "TOTEM_EFFECT",
                "FEATURE", "BAND",
                "COPPER", "COPPER_BUFF",
                "WRATH", "DISASTER",
                "DISASTER_TYPE", "FRAGMENT",
                "EXPLORE_TOOL", "ACTIVE_TOOL",
            }:
                special_items[key] = record
            else:
                other_items[key] = record

        report[topic_id] = {
            "total_items": len(jp_items),
            "missing_tw_records": missing_tw,
            "type_distribution": dict(categories),
        }

    OUT.mkdir(parents=True, exist_ok=True)

    outputs = {
        "rogue_collectibles.json": collectibles,
        "rogue_special_items.json": special_items,
        "rogue_other_items.json": other_items,
        "rogue_item_report.json": report,
    }

    for filename, data in outputs.items():
        path = OUT / filename
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Saved {path} ({len(data)} records)")

    print("\nCollection summary:")
    for topic in report:
        count = sum(
            r["topic_id"] == topic
            for r in collectibles.values()
        )
        print(f"{topic}: {count} collectibles")


if __name__ == "__main__":
    main()
