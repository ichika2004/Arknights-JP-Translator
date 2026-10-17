"""Safely enrich existing JP/TW skill_database.json using CN as fallback.
Never edits JP numbers; preserves all existing fields. Backups before write.
"""
import argparse
import json
import shutil
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, default=Path.cwd())
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    root = args.root.resolve()
    db_path = root/'data/generated/skill_database.json'
    cn_path = root/'data/raw/cn/skill_table.json'
    cn_chars_path = root/'data/raw/cn/character_table.json'
    cn_patch_path = root/'data/raw/cn/char_patch_table.json'
    for path in (db_path, cn_path, cn_chars_path, cn_patch_path):
        if not path.is_file():
            raise SystemExit(f'Missing {path}')
    try:
        from opencc import OpenCC
    except ImportError:
        raise SystemExit('Install: python -m pip install opencc-python-reimplemented')
    convert = OpenCC('s2twp').convert
    db, skills = read(db_path), read(cn_path)
    chars, patch = read(cn_chars_path), read(cn_patch_path)
    chars.update(patch.get('patchChars', {}))
    stats = Counter()
    for cid, char in db.get('characters', {}).items():
        entry = chars.get(cid, {})
        if not isinstance(entry, dict): entry={}
        if not (char.get('name_zh_tw') or char.get('name_zh_tw_candidate')) and entry.get('name'):
            char['name_zh_tw_candidate'] = convert(entry['name'])
            char['name_translation_source'] = 'cn_opencc'
            stats['character_names_from_cn'] += 1
        for skill in char.get('skills', []):
            sid = skill.get('skill_id')
            cn_info = skills.get(sid, {})
            cn_levels = cn_info.get('levels', []) if isinstance(cn_info, dict) else []
            if not cn_levels:
                stats['skills_not_in_cn'] += 1
            for i, level in enumerate(skill.get('levels', [])):
                c = cn_levels[i] if i < len(cn_levels) and isinstance(cn_levels[i], dict) else {}
                if not c:
                    stats['levels_without_cn'] += 1
                if level.get('description_zh_tw_candidate_raw'):
                    level.setdefault('translation_source', 'tw_candidate_unverified')
                    stats['levels_with_existing_tw'] += 1
                elif isinstance(c.get('description'), str) and c['description'].strip():
                    level['description_zh_tw_candidate_raw'] = convert(c['description'])
                    level['translation_source'] = 'cn_opencc_unverified'
                    stats['levels_filled_cn'] += 1
                else:
                    level.setdefault('translation_source', 'jp_fallback')
                    stats['levels_still_missing'] += 1
                if not level.get('name_zh_tw_candidate') and isinstance(c.get('name'), str) and c['name'].strip():
                    level['name_zh_tw_candidate'] = convert(c['name'])
                    level['name_translation_source'] = 'cn_opencc_unverified'
                    stats['level_names_filled_cn'] += 1
            sources = {lvl.get('translation_source') for lvl in skill.get('levels', [])}
            if 'cn_opencc_unverified' in sources:
                skill['translation_status'] = 'tw_or_cn_candidate_unverified'
    print(json.dumps(dict(stats), ensure_ascii=False, indent=2))
    if args.dry_run:
        print('Dry run: no files modified')
        return
    backup = db_path.with_suffix('.before_cn_fallback.json')
    if not backup.exists():
        shutil.copy2(db_path, backup)
    db['cn_fallback_note'] = 'Unverified CN simplified-to-traditional translations; JP blackboard/SP/duration authoritative; validate placeholder compatibility.'
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', suffix='.json', dir=db_path.parent, delete=False) as f:
        tmp = Path(f.name)
        json.dump(db, f, ensure_ascii=False, indent=2)
    tmp.replace(db_path)
    report_path = db_path.parent/'cn_fallback_report.json'
    report_path.write_text(json.dumps(dict(stats), ensure_ascii=False, indent=2), encoding='utf-8')
    print('Saved:', db_path)
    print('Backup:', backup)
    print('Report:', report_path)

if __name__=='__main__':
    main()
