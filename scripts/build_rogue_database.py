"""Phase 16: cautious Arknights Integrated Strategies bilingual extractor.

The script aligns leaves by identical JSON paths only. Classification is a
heuristic to aid auditing; it is NOT a claim that a record is a known collectible
or event. Absent TW text remains untranslated unless explicit CN fallback asked.
"""
import argparse
import csv
import json
import re
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw' / 'roguelike'
OUTPUT = ROOT / 'data' / 'generated'
FILENAME = 'roguelike_topic_table.json'
DEFAULT_URLS = {
    'jp': 'https://raw.githubusercontent.com/ArknightsAssets/ArknightsGamedata/master/jp/gamedata/excel/' + FILENAME,
    'tw': 'https://raw.githubusercontent.com/ArknightsAssets/ArknightsGamedata/master/tw/gamedata/excel/' + FILENAME,
    'cn': 'https://raw.githubusercontent.com/ArknightsAssets/ArknightsGamedata/master/cn/gamedata/excel/' + FILENAME,
}
TEXT_KEYS = re.compile(r'(name|desc|text|title|content|option|choice|hint|effect|detail|tip|remark|label|reward|cost|intro|story|comment|note)', re.I)
META_KEYS = re.compile(r'(icon|image|path|url|key|hash|id|sort|color|type|tag|group|code|version|asset)', re.I)
TOPIC_MARKERS = ('topic', 'detail', 'rogue')
COLLECTIBLE_MARKERS = ('relic', 'collect', 'treasure', 'artifact')
EVENT_MARKERS = ('event', 'encounter', 'node', 'scenario')
OPTION_MARKERS = ('option', 'choice', 'select', 'decision')


def download(lang, refresh=False):
    path = RAW / lang / FILENAME
    if path.exists() and not refresh:
        print(f'[cache] {lang}: {path}')
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    url = DEFAULT_URLS[lang]
    print(f'[download] {lang}: {url}', flush=True)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'ArknightsJPTranslator-Phase16/1.0'}), timeout=90) as res:
            data = res.read()
        parsed = json.loads(data.decode('utf-8-sig'))
        if not isinstance(parsed, dict):
            raise ValueError('Unexpected root JSON type')
        tmp = path.with_suffix('.json.tmp')
        tmp.write_bytes(data)
        tmp.replace(path)
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        print(f'[unavailable] {lang}: {exc}')
        return None
    return path


def flatten(obj, prefix=()):
    """Flatten scalar text leaves; positional arrays are kept but tagged later."""
    if isinstance(obj, dict):
        for key, val in obj.items():
            yield from flatten(val, prefix + (str(key),))
    elif isinstance(obj, list):
        for i, val in enumerate(obj):
            yield from flatten(val, prefix + (str(i),))
    elif isinstance(obj, str) and obj.strip():
        if not prefix:
            return
        leaf = prefix[-1]
        if TEXT_KEYS.search(leaf) and not META_KEYS.fullmatch(leaf):
            yield '/'.join(prefix), obj


def bucket(path):
    low = path.lower().split('/')
    if any(OPTION_MARKERS[0] in x or x in OPTION_MARKERS for x in low):
        return 'option_candidate'
    if any(any(m in x for m in COLLECTIBLE_MARKERS) for x in low):
        return 'collectible_candidate'
    if any(any(m in x for m in EVENT_MARKERS) for x in low):
        return 'event_candidate'
    return 'other_text'


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--refresh', action='store_true', help='Redownload raw files')
    ap.add_argument('--offline', action='store_true', help='Use only local raw files')
    ap.add_argument('--cn-fallback', action='store_true', help='Include CN text as unverified fallback; never call it official TW')
    args = ap.parse_args()

    paths = {}
    for lang in ('jp', 'tw', 'cn'):
        path = RAW / lang / FILENAME
        paths[lang] = path if args.offline and path.exists() else (None if args.offline else download(lang, args.refresh))
    if paths['jp'] is None:
        raise SystemExit('Missing Japanese source: save it to data/raw/roguelike/jp/roguelike_topic_table.json')

    sources = {lang: load(path) for lang, path in paths.items() if path}
    leaves = {lang: dict(flatten(doc)) for lang, doc in sources.items()}
    jp = leaves['jp']
    tw = leaves.get('tw', {})
    cn = leaves.get('cn', {})
    print('Text leaves:', {k: len(v) for k, v in leaves.items()})
    rows = []
    summary = Counter()
    for json_path, ja in sorted(jp.items()):
        zh_tw = tw.get(json_path)
        zh_cn = cn.get(json_path)
        source = 'tw_exact_path' if zh_tw is not None else 'untranslated'
        zh = zh_tw
        if zh is None and args.cn_fallback and zh_cn is not None:
            zh = zh_cn
            source = 'cn_original_unverified'
        # Paths with numbered list segments can shift between locales.
        array_path = any(part.isdigit() for part in json_path.split('/'))
        risk = 'array_index_verify' if array_path else 'review_text_alignment'
        kind = bucket(json_path)
        summary[(kind, source)] += 1
        rows.append({'path': json_path, 'kind_candidate': kind,
                     'jp': ja, 'tw': zh_tw, 'cn': zh_cn,
                     'display_zh': zh, 'translation_source': source,
                     'review_status': risk})
    OUTPUT.mkdir(parents=True, exist_ok=True)
    output = {'schema_version': 1, 'status': 'candidate_unverified',
              'warning': 'Path alignment is a candidate only. Never assume array indices and localized IDs are stable.',
              'input_files': {k: str(v.relative_to(ROOT)) for k, v in paths.items() if v},
              'top_level_keys': {k: list(doc) for k, doc in sources.items()},
              'summary': {f'{k[0]}::{k[1]}': v for k, v in sorted(summary.items())},
              'entries': rows}
    out = OUTPUT / 'rogue_database_candidates.json'
    out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    csv_path = OUTPUT / 'rogue_review.csv'
    with csv_path.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys() if rows else ['path','kind_candidate','jp','tw','cn','display_zh','translation_source','review_status'])
        w.writeheader()
        w.writerows(rows)
    print('Saved', out)
    print('Saved', csv_path)
    print('Summary:', dict(summary))
    if 'tw' not in sources:
        print('WARNING: TW file unavailable. No official Traditional Chinese translations produced.')


if __name__ == '__main__':
    main()
