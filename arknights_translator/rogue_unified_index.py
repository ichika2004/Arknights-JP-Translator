"""Phase 17.3: build/search category-aware roguelike bilingual index. Standard library only."""
from __future__ import annotations
import json
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

CATEGORIES = {'items': 'item', 'choiceScenes': 'scene', 'choices': 'choice'}
FIELDS = {
    'item': ('name', 'description', 'usage', 'shortUsage', 'obtainApproach', 'unlockCondDesc'),
    'scene': ('title', 'description'),
    'choice': ('title', 'description', 'lockedCoverDesc'),
}
NAME_FIELD = {'item': 'name', 'scene': 'title', 'choice': 'title'}
TEXT_TERMS = ('宿願', '構想', '遺願', '思緒', '願い', '構想', '祈願', 'アイデア')


def clean(value):
    text = unicodedata.normalize('NFKC', str(value or '')).lower()
    return re.sub(r'[\s「」『』“”"\'・･、。!！?？:\-]+', '', text)


def read_json(path):
    with Path(path).open('r', encoding='utf-8-sig') as f:
        return json.load(f)


def make_index(jp, tw):
    out = []
    stats = Counter()
    for topic, jp_topic in (jp.get('details') or {}).items():
        tw_topic = (tw.get('details') or {}).get(topic, {})
        for source, category in CATEGORIES.items():
            for record_id, source_record in (jp_topic.get(source) or {}).items():
                if not isinstance(source_record, dict):
                    continue
                target_record = (tw_topic.get(source) or {}).get(record_id) or {}
                if not isinstance(target_record, dict):
                    target_record = {}
                fields = {field: {'jp': source_record.get(field) or '',
                                  'tw': target_record.get(field) or ''}
                          for field in FIELDS[category]}
                meta = {}
                if category == 'item':
                    meta = {k: source_record.get(k) for k in ('type', 'subType', 'rarity', 'iconId')}
                elif category == 'choice':
                    meta = {k: source_record.get(k) for k in ('type', 'nextSceneId')}
                elif category == 'scene':
                    meta = {k: source_record.get(k) for k in ('background', 'subTypeId')}
                row = {'key': f'{topic}/{category}/{record_id}', 'topic_id': topic,
                       'category': category, 'source': source, 'record_id': record_id,
                       'fields': fields, 'meta': meta,
                       'translation_source': 'tw_exact_id' if target_record else 'missing_tw'}
                out.append(row)
                stats[(topic, category)] += 1
                if not fields[NAME_FIELD[category]]['tw']:
                    stats[(topic, category, 'missing_tw_name')] += 1
    return out, stats


def match(index, query, topic=None, category=None, min_score=.85, margin=.06, limit=12):
    """Return a unique confident match or an explicit ambiguity; never merge categories blindly."""
    query_key = clean(query)
    if len(query_key) < 2:
        return {'status': 'not_found', 'candidates': []}
    scored = []
    for row in index:
        if topic and row['topic_id'] != topic:
            continue
        if category and row['category'] != category:
            continue
        key = clean(row['fields'][NAME_FIELD[row['category']]]['jp'])
        if not key:
            continue
        score = SequenceMatcher(None, query_key, key).ratio()
        if score >= min_score:
            scored.append((score, row))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    if not scored:
        return {'status': 'not_found', 'candidates': []}
    top_score = scored[0][0]
    ties = [(score, row) for score, row in scored if top_score-score < margin]
    # An undifferentiated query across item/scene/choice types should not auto-resolve.
    variants = {(row['category'], tuple((f, str(v.get('tw') or '')) for f, v in row['fields'].items()))
                for _, row in ties}
    candidates = [{'score': round(score, 4), **row} for score, row in ties[:limit]]
    if len(variants) > 1:
        return {'status': 'ambiguous', 'candidates': candidates, 'total_candidates': len(ties)}
    return {'status': 'matched', 'result': candidates[0],
            'shared_across_topics': len(ties) > 1,
            'candidate_count': len(ties)}


def walk_text(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk_text(child, (*path, str(key)))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from walk_text(child, (*path, str(i)))
    elif isinstance(value, str) and value.strip():
        yield path, value


def term_audit(jp, tw, terms=TEXT_TERMS, max_hits=300):
    """Search ALL gamedata strings, including modules/customizeData, by structural path."""
    hits = []
    jp_leaves = dict(walk_text(jp))
    tw_leaves = dict(walk_text(tw))
    for path in sorted(set(jp_leaves) | set(tw_leaves)):
        jp_text = jp_leaves.get(path, '')
        tw_text = tw_leaves.get(path, '')
        found = [term for term in terms if term in jp_text or term in tw_text]
        if found:
            hits.append({'path': '/'.join(path), 'terms': list(dict.fromkeys(found)),
                         'jp': jp_text, 'tw': tw_text})
    return hits[:max_hits], len(hits)


def build(root=Path('.')):
    root = Path(root)
    raw = root / 'data' / 'raw' / 'roguelike'
    jp = read_json(raw/'jp'/'roguelike_topic_table.json')
    tw = read_json(raw/'tw'/'roguelike_topic_table.json')
    records, stats = make_index(jp, tw)
    hits, hit_total = term_audit(jp, tw)
    out = root/'data'/'generated'
    out.mkdir(parents=True, exist_ok=True)
    paths = {'index': out/'rogue_unified_index.json',
             'terms': out/'rogue_mechanism_term_audit.json',
             'report': out/'rogue_unified_report.json'}
    report = {
        'total_records': len(records),
        'categories': dict(Counter(row['category'] for row in records)),
        'by_topic_category': {f'{k[0]}/{k[1]}': v for k,v in stats.items() if len(k)==2},
        'missing_tw_name_by_group': {f'{k[0]}/{k[1]}': v for k,v in stats.items() if len(k)==3},
        'term_hits_total': hit_total,
        'term_hits_saved': len(hits),
        'notes': ['This index does not infer scene-to-choice relationships.',
                  'Term audit searches full raw JSON; its results do not imply game-mechanic classification.',
                  'Same record ID across languages is a translation candidate, not manual verification.'],
    }
    for key, value in [('index',records),('terms',hits),('report',report)]:
        paths[key].write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    return paths,report
