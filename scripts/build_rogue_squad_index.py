"""Build JP -> TW starting/monthly squad indexes from locally aligned gamedata."""
import json
from pathlib import Path
from collections import defaultdict, Counter

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw' / 'roguelike'
OUT = ROOT / 'data' / 'generated'


def load(lang):
    path = RAW / lang / 'roguelike_topic_table.json'
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def main():
    jp, tw = load('jp'), load('tw')
    bands, monthly = {}, {}
    grouped = defaultdict(list)
    summary = {}
    for topic, detail in jp['details'].items():
        twdetail = tw.get('details', {}).get(topic, {})
        references = detail.get('bandRef') or {}
        ref_by_id = {}
        for ref_id, ref in references.items():
            if isinstance(ref, dict):
                # The relationship is not inferred from the name; retain source reference.
                ref_by_id[ref_id] = ref
        counter = Counter()
        for item_id, row in (detail.get('items') or {}).items():
            if not isinstance(row, dict) or row.get('type') != 'BAND':
                continue
            twrow = (twdetail.get('items') or {}).get(item_id) or {}
            if not isinstance(twrow, dict):
                twrow = {}
            entry = {
                'topic_id': topic,
                'item_id': item_id,
                'name_jp': row.get('name') or '',
                'name_tw': twrow.get('name') or '',
                'effect_jp': row.get('usage') or '',
                'effect_tw': twrow.get('usage') or '',
                'description_jp': row.get('description') or '',
                'description_tw': twrow.get('description') or '',
                'sub_type': row.get('subType'),
                'rarity': row.get('rarity'),
                'band_ref': ref_by_id.get(item_id),
                'source_path': f'details/{topic}/items/{item_id}',
            }
            bands[f'{topic}/{item_id}'] = entry
            if entry['name_jp']:
                grouped[(topic, entry['name_jp'])].append(entry)
            counter['bands'] += 1
            if entry['name_tw']:
                counter['name_tw'] += 1
            if entry['effect_tw']:
                counter['effect_tw'] += 1
        for mid, row in (detail.get('monthSquad') or {}).items():
            if not isinstance(row, dict):
                continue
            twrow = (twdetail.get('monthSquad') or {}).get(mid) or {}
            monthly[f'{topic}/{mid}'] = {
                'topic_id': topic,
                'id': mid,
                'name_jp': row.get('teamName') or '',
                'name_tw': twrow.get('teamName') or '',
                'sub_name_jp': row.get('teamSubName') or '',
                'sub_name_tw': twrow.get('teamSubName') or '',
                'description_jp': row.get('teamDes') or '',
                'description_tw': twrow.get('teamDes') or '',
                'flavor_jp': row.get('teamFlavorDesc') or '',
                'flavor_tw': twrow.get('teamFlavorDesc') or '',
                'source_path': f'details/{topic}/monthSquad/{mid}',
            }
            counter['monthly'] += 1
        summary[topic] = dict(counter)
    ambiguities = []
    for (topic, name), entries in sorted(grouped.items()):
        variants = {(x['name_tw'], x['effect_tw']) for x in entries}
        if len(variants) > 1:
            ambiguities.append({
                'topic_id': topic, 'name_jp': name,
                'variants': [{'item_id': e['item_id'], 'name_tw': e['name_tw'],
                              'effect_tw': e['effect_tw']} for e in entries]
            })
    OUT.mkdir(parents=True, exist_ok=True)
    for filename, obj in [
        ('rogue_starting_squads.json', bands),
        ('rogue_monthly_squads.json', monthly),
        ('rogue_squad_ambiguities.json', ambiguities),
        ('rogue_squad_report.json', summary),
    ]:
        (OUT / filename).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Saved', OUT / filename, 'records:', len(obj))
    print('Total BAND:', len(bands), 'monthly:', len(monthly))
    print('Topic-name groups with different effects:', len(ambiguities))
    for row in ambiguities[:8]:
        print(row['topic_id'], row['name_jp'], len(row['variants']), 'variants')


if __name__ == '__main__':
    main()
