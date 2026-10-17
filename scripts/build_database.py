"""Match JP and TW operators/skills by stable IDs; retain unverified TW candidates."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw'
OUT = ROOT / 'data' / 'generated'


def load(region, filename):
    path = RAW / region / filename
    if not path.exists():
        raise FileNotFoundError(f'Missing {path}. Run fetch_gamedata.py first.')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def characters(region):
    data = load(region, 'character_table.json')
    patch = load(region, 'char_patch_table.json')
    data.update(patch.get('patchChars', {}))
    return data


def main():
    jp_chars, tw_chars = characters('jp'), characters('tw')
    jp_skills = load('jp', 'skill_table.json')
    tw_skills = load('tw', 'skill_table.json')
    db = {'schema_version': 1, 'source_of_truth': 'jp', 'characters': {}}
    missing = []
    counts = Counter()
    for cid, entry in jp_chars.items():
        if not isinstance(entry, dict) or not isinstance(entry.get('skills'), list) or not entry['skills']:
            continue
        tw_entry = tw_chars.get(cid, {})
        if not isinstance(tw_entry, dict):
            tw_entry = {}
        record = {'character_id': cid, 'name_jp': entry.get('name', ''),
                  'name_zh_tw_candidate': tw_entry.get('name'), 'skills': []}
        counts['jp_characters_with_skills'] += 1
        if record['name_zh_tw_candidate']:
            counts['characters_with_tw_name'] += 1
        for slot, relation in enumerate(entry['skills'], 1):
            if not isinstance(relation, dict) or not relation.get('skillId'):
                continue
            sid = relation['skillId']
            jl = jp_skills.get(sid, {}).get('levels', [])
            tl = tw_skills.get(sid, {}).get('levels', [])
            counts['jp_skills'] += 1
            if tl:
                counts['skills_with_tw_candidate'] += 1
            else:
                missing.append({'character_id': cid, 'name_jp': record['name_jp'],
                                'skill_id': sid, 'slot': slot})
            skill = {'skill_id': sid, 'slot': slot,
                     'translation_status': 'tw_candidate_unverified' if tl else 'missing_tw_skill',
                     'jp_level_count': len(jl), 'tw_level_count': len(tl), 'levels': []}
            for idx, jp_level in enumerate(jl):
                tw_level = tl[idx] if idx < len(tl) else {}
                skill['levels'].append({
                    'level': idx + 1,
                    'name_jp': jp_level.get('name'),
                    'description_jp_raw': jp_level.get('description'),
                    'name_zh_tw_candidate': tw_level.get('name'),
                    'description_zh_tw_candidate_raw': tw_level.get('description'),
                    'sp_data_jp': jp_level.get('spData'),
                    'duration_jp': jp_level.get('duration'),
                    'blackboard_jp': jp_level.get('blackboard'),
                    'tw_version_verified': False,
                })
            record['skills'].append(skill)
        if record['skills']:
            db['characters'][cid] = record
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'skill_database.json').write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / 'missing_tw_skills.json').write_text(json.dumps(missing, ensure_ascii=False, indent=2), encoding='utf-8')
    report = dict(counts)
    report['skills_missing_tw_candidate'] = len(missing)
    report['warning'] = 'TW strings are unverified candidates; JP numeric data is authoritative. Raw descriptions may contain placeholders.'
    (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print('Output:', OUT)


if __name__ == '__main__':
    main()
