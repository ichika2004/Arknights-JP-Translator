"""Phase 17.4: full-screen OCR -> cautious, typed bilingual cards.
No hard-coded screen ROIs or inferred scene-to-choice mappings.
"""
from __future__ import annotations
import re
import unicodedata
from difflib import SequenceMatcher
from collections import defaultdict

NAME_FIELD = {'item': 'name', 'choice': 'title', 'scene': 'title'}
TAGS = re.compile(r'<@[^>]+>|</>')


def plain(value):
    return TAGS.sub('', str(value or '')).strip()


def norm(value):
    s = unicodedata.normalize('NFKC', plain(value)).lower()
    return re.sub(r'[\s「」『』“”"\'・･。、，:：!！?？\-—･]+', '', s)


def make_lines(raw):
    lines = []
    for item in raw:
        if not isinstance(item, dict) or not item.get('text'):
            continue
        box = item.get('bbox')
        if not isinstance(box, (list, tuple)) or len(box) != 4:
            continue
        try:
            x1, y1, x2, y2 = [float(v) for v in box]
            conf = float(item.get('confidence') or 0)
        except (ValueError, TypeError):
            continue
        if x2 <= x1 or y2 <= y1:
            continue
        lines.append({'text': str(item['text']), 'confidence': conf,
                      'bbox': [x1,y1,x2,y2], 'cx': (x1+x2)/2, 'cy': (y1+y2)/2,
                      'height': y2-y1, 'width':x2-x1})
    return sorted(lines, key=lambda z: (z['cy'], z['cx']))


def _typed_candidates(index, text, topic, min_score=.86, max_results=15):
    key = norm(text)
    if len(key) < 3:
        return []
    result = []
    for row in index:
        if topic and row.get('topic_id') != topic:
            continue
        cat = row.get('category')
        if cat not in NAME_FIELD:
            continue
        jp = (row.get('fields') or {}).get(NAME_FIELD[cat], {}).get('jp', '')
        candidate = norm(jp)
        if not candidate:
            continue
        # Resist short substring matches from story descriptions.
        sim = SequenceMatcher(None, key, candidate).ratio()
        if sim >= min_score:
            result.append((sim, row))
    result.sort(key=lambda t: t[0], reverse=True)
    return result[:max_results]


def _meaning(row):
    category = row['category']
    fields = row.get('fields') or {}
    return (category, tuple((k, plain(fields.get(k, {}).get('tw'))) for k in (
        ('name','usage','shortUsage') if category == 'item' else
        ('title','description','lockedCoverDesc') if category == 'choice' else
        ('title','description'))))


def _details(row):
    fields = row.get('fields') or {}
    cat = row['category']
    head = NAME_FIELD[cat]
    title = plain(fields.get(head, {}).get('tw'))
    if cat == 'item':
        desc = plain(fields.get('usage', {}).get('tw') or fields.get('shortUsage', {}).get('tw') or fields.get('description', {}).get('tw'))
    else:
        desc = plain(fields.get('description', {}).get('tw'))
    lock = plain(fields.get('lockedCoverDesc', {}).get('tw')) if cat == 'choice' else ''
    flavor = plain(fields.get('description', {}).get('tw')) if cat=='item' else ''
    return title, desc, lock, flavor


def _horizontal_relation(a,b):
    ax1,_,ax2,_ = a['bbox']; bx1,_,bx2,_ = b['bbox']
    overlap = max(0, min(ax2,bx2)-max(ax1,bx1))
    return overlap / max(1, min(ax2-ax1,bx2-bx1))


def _associate(lines, anchor_idx, used_anchors):
    """Loose spatial context for UI, NOT a claim about source game linkage."""
    anchor = lines[anchor_idx]
    near = []
    for i, line in enumerate(lines):
        if i == anchor_idx or i in used_anchors:
            continue
        dy = line['cy'] - anchor['cy']
        scale = max(20, anchor['height'], line['height'])
        # only subsequent nearby lines, don't join across unrelated column
        if -0.3 * scale <= dy <= 4.8 * scale:
            center_dist = abs(line['cx'] - anchor['cx'])
            if _horizontal_relation(anchor, line) >= .25 or center_dist < max(anchor['width'], line['width']) * .42:
                near.append((dy, i, line))
    near.sort(key=lambda z: (z[0], z[2]['cx']))
    return [line['text'] for _,_,line in near[:3]]


def is_hud_noise(line):
    """Reject only high-confidence UI chrome, not large swaths of the screen."""
    t=norm(line['text'])
    x1,y1,x2,y2=line['bbox']
    # HUD fragments are often short; don't exclude event titles, item names or choices.
    if t in {'耐久値','最大耐久値','希望','資金残高','指揮lv','lv','残り4歩',
             '価格','退出','編成','隊員','秘宝','思考負荷','探索'}:
        return True
    if len(t)<=2 and (t.isdigit() or t in {'lv','hp'}):
        return True
    return False


def analyze(raw_lines, index, topic=None, threshold=.88, suppress_hud=True):
    """Return structured result. Never resolve equal JP with divergent TW effects."""
    lines = make_lines(raw_lines)
    if suppress_hud:
        lines = [line for line in lines if not is_hud_noise(line)]
    anchors = []
    for idx,line in enumerate(lines):
        candidates = _typed_candidates(index, line['text'], topic, min_score=threshold)
        if not candidates:
            continue
        top = candidates[0][0]
        peers = [(score,row) for score,row in candidates if top-score < .025]
        variants = {_meaning(row) for _,row in peers}
        # If one OCR text maps to different categories or TW effects, refuse it.
        status = 'matched' if len(variants)==1 and line['confidence'] >= .62 else 'ambiguous'
        anchors.append({'i':idx,'status':status,'score':round(top*line['confidence'],4),
                        'peers':peers, 'text':line['text']})
    # Multiple OCR lines can resolve to the same record; prefer strongest.
    dedup = {}
    for a in anchors:
        row = a['peers'][0][1]
        key = (row.get('topic_id'),row.get('category'),row.get('record_id'))
        if a['status'] == 'ambiguous':
            key = ('ambiguous', a['i'])
        if key not in dedup or a['score'] > dedup[key]['score']:
            dedup[key] = a
    anchors = list(dedup.values())
    anchor_ids = {a['i'] for a in anchors}
    cards=[]
    for a in anchors:
        row=a['peers'][0][1]
        title, desc, lock, flavor = _details(row)
        cards.append({'status':a['status'],'category':row['category'],
                      'topic_id':row['topic_id'], 'record_id':row['record_id'],
                      'ocr_text':a['text'],'score':a['score'],
                      'bbox':lines[a['i']]['bbox'],
                      'title_tw':title if a['status']=='matched' else '',
                      'description_tw':desc if a['status']=='matched' else '',
                      'locked_tw':lock if a['status']=='matched' else '',
                      'flavor_tw':flavor if a['status']=='matched' else '',
                      'nearby_ocr':_associate(lines,a['i'],anchor_ids),
                      'alternatives': [{'topic_id':r['topic_id'],'category':r['category'],
                                        'record_id':r['record_id'], 'title_tw':_details(r)[0]}
                                       for _,r in a['peers'][:8]] if a['status']=='ambiguous' else []})
    cards.sort(key=lambda a:(a['bbox'][1],a['bbox'][0]))
    return {'cards':cards,'ocr_count':len(lines),
            'unmatched_ocr':[l['text'] for i,l in enumerate(lines) if i not in anchor_ids],
            'notes': ['Nearby OCR is visual context only, not proven to be the same in-game choice.',
                      'No scene-to-choice link is inferred from coordinates.']}
