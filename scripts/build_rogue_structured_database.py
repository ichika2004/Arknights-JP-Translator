#!/usr/bin/env python3
"""Phase 16: build ID-aligned Arknights roguelike JP/TW databases.

Source: data/raw/roguelike/{jp,tw}/roguelike_topic_table.json
No network calls. This tool does not claim every item is a collectible and does
not invent scene -> choice relationships.
"""
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ITEM_TEXT = ("name", "description", "usage", "obtainApproach", "unlockCondDesc", "shortUsage")
SCENE_TEXT = ("title", "description")
CHOICE_TEXT = ("title", "description", "lockedCoverDesc")
CHOICE_META = ("type", "leftDecoType", "nextSceneId", "icon", "forceShowWhenOnlyLeave")
ITEM_META = ("type", "subType", "rarity", "sortId", "canSacrifice", "iconId", "itemIconGroupId", "tinyIconColor")


def load(path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")


def clean_text(obj, key):
    v = obj.get(key)
    return v if isinstance(v, str) else ""


def translate_fields(jp, tw, fields):
    result = {}
    missing = []
    for field in fields:
        ja = clean_text(jp, field)
        zh = clean_text(tw, field)
        result[field] = {"jp": ja, "tw": zh, "display_zh": zh or ja,
                         "source": "tw_same_id" if zh else ("jp_fallback" if ja else "empty")}
        if ja and not zh:
            missing.append(field)
    return result, missing


def build_collection(jp_details, tw_details, section, text_fields, metadata_fields, stats, rows):
    output = {}
    for topic_id in sorted(jp_details):
        jp_section = jp_details[topic_id].get(section, {})
        tw_section = tw_details.get(topic_id, {}).get(section, {})
        if not isinstance(jp_section, dict):
            stats["invalid_sections"].append(f"{topic_id}/{section}: jp not dict")
            continue
        if not isinstance(tw_section, dict):
            tw_section = {}
        topic_out = {}
        for record_id, jp_obj in jp_section.items():
            if not isinstance(jp_obj, dict):
                stats["invalid_records"].append(f"{topic_id}/{section}/{record_id}")
                continue
            tw_obj = tw_section.get(record_id, {})
            if not isinstance(tw_obj, dict):
                tw_obj = {}
            fields, missing = translate_fields(jp_obj, tw_obj, text_fields)
            metadata = {key: jp_obj.get(key) for key in metadata_fields if key in jp_obj}
            record = {
                "id": record_id,
                "topic_id": topic_id,
                "texts": fields,
                "metadata": metadata,
                "alignment": "jp_tw_same_record_id" if record_id in tw_section else "jp_only_record",
                "review_status": "needs_review" if missing or record_id not in tw_section else "candidate_same_id",
            }
            if missing:
                record["missing_tw_fields"] = missing
            topic_out[record_id] = record
            stats["total_records"][section] += 1
            stats["per_topic"][topic_id][section] += 1
            if record_id not in tw_section:
                stats["jp_only_records"][section] += 1
            for field, pair in fields.items():
                if pair["jp"]:
                    stats["populated_jp_fields"][section] += 1
                    if not pair["tw"]:
                        stats["missing_tw_fields"][section] += 1
                    rows.append({
                        "topic_id": topic_id, "collection": section, "record_id": record_id,
                        "field": field, "jp": pair["jp"], "tw": pair["tw"],
                        "translation_source": pair["source"],
                        "review_status": record["review_status"],
                    })
        output[topic_id] = topic_out
        stats["tw_only_records"][section] += len(set(tw_section) - set(jp_section))
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw/roguelike"))
    parser.add_argument("--output-root", type=Path, default=Path("data/generated"))
    args = parser.parse_args()
    jp_path = args.raw_root / "jp" / "roguelike_topic_table.json"
    tw_path = args.raw_root / "tw" / "roguelike_topic_table.json"
    for p in (jp_path, tw_path):
        if not p.is_file():
            parser.error(f"Missing data: {p}. Run the original download script first.")
    jp_root, tw_root = load(jp_path), load(tw_path)
    jp_details, tw_details = jp_root.get("details", {}), tw_root.get("details", {})
    if not isinstance(jp_details, dict) or not isinstance(tw_details, dict):
        parser.error("Unexpected JSON structure: details must be a dict")
    stats = {"total_records": Counter(), "jp_only_records": Counter(),
             "tw_only_records": Counter(), "populated_jp_fields": Counter(),
             "missing_tw_fields": Counter(), "per_topic": defaultdict(Counter),
             "invalid_sections": [], "invalid_records": []}
    rows = []
    specs = (
        ("items", ITEM_TEXT, ITEM_META, "rogue_items.json"),
        ("choiceScenes", SCENE_TEXT, ("background", "titleIcon", "subTypeId", "useHiddenMusic"), "rogue_scenes.json"),
        ("choices", CHOICE_TEXT, CHOICE_META, "rogue_choices.json"),
    )
    outputs = {}
    for section, fields, meta, filename in specs:
        data = build_collection(jp_details, tw_details, section, fields, meta, stats, rows)
        save(args.output_root / filename, data)
        outputs[section] = data
        print(f"[saved] {filename}: {sum(len(x) for x in data.values())} entries")
    # 'items' includes currencies, recruitment tickets, collectibles etc. No blanket labeling.
    types = defaultdict(Counter)
    for topic_id, items in outputs["items"].items():
        for v in items.values():
            meta = v["metadata"]
            types[topic_id][f"{meta.get('type','?')} / {meta.get('subType','?')}"] += 1
    stats_out = {k: (dict(v) if isinstance(v, Counter) else v) for k, v in stats.items()}
    stats_out["per_topic"] = {topic: dict(counts) for topic, counts in stats["per_topic"].items()}
    stats_out["item_type_distribution"] = {topic: dict(counts) for topic, counts in types.items()}
    stats_out["jp_topics"] = sorted(jp_details)
    stats_out["tw_topics"] = sorted(tw_details)
    stats_out["notes"] = [
        "Records are matched by topic ID and record ID, not by text similarity.",
        "TW same ID is a candidate translation: manual quality review remains necessary.",
        "items contains all item types, NOT exclusively collectibles.",
        "choiceScenes and choices are stored independently; no scene-choice edges are inferred.",
        "The relics collection holds buff definitions and requires separate semantic investigation.",
    ]
    save(args.output_root / "rogue_structured_report.json", stats_out)
    csv_path = args.output_root / "rogue_structured_review.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["topic_id", "collection", "record_id", "field", "jp", "tw", "translation_source", "review_status"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"[saved] {csv_path}: {len(rows)} text fields")
    print(f"[saved] {args.output_root / 'rogue_structured_report.json'}")
    print("[notice] Items are NOT yet strictly collectibles; inspect item_type_distribution in report.")

if __name__ == "__main__":
    main()
