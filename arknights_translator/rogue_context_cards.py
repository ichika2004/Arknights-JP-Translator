"""Add starting/monthly squad pins and safe repeated-event title fallback."""
from __future__ import annotations
import json
from pathlib import Path
from difflib import SequenceMatcher
from collections import defaultdict
from arknights_translator.rogue_layout_engine import norm, make_lines


def load_squads(root=None):
    root = Path(root) if root else Path(__file__).resolve().parents[1] / 'data' / 'generated'
    groups = []
    for filename, kind in [('rogue_starting_squads.json','starting_squad'), ('rogue_monthly_squads.json','monthly_squad')]:
        p=root/filename
        if not p.is_file():
            print('[Phase22.3] Squad index missing:',p,flush=True)
            continue
        obj=json.loads(p.read_text(encoding='utf-8-sig'))
        for value in (obj.values() if isinstance(obj,dict) else obj):
            if isinstance(value,dict) and value.get('name_jp') and value.get('name_tw'):
                groups.append(dict(value, _kind=kind))
    return groups


def context_cards(raw_lines, squads, records, topic=None):
    """No guessed effects. For duplicate names, show a title-only pin when necessary."""
    lines=make_lines(raw_lines)
    cards=[]
    for line in lines:
        q=norm(line['text'])
        if len(q)<3 or line['confidence']<.62:continue
        choices=[]
        for s in squads:
            if topic and s.get('topic_id') != topic:continue
            name=norm(s.get('name_jp'))
            if not name:continue
            ratio=SequenceMatcher(None,q,name).ratio()
            if ratio >= .89:choices.append((ratio,s))
        if not choices:continue
        choices.sort(key=lambda t:t[0],reverse=True)
        best=choices[0][0]
        winner_name=norm(choices[0][1]['name_jp'])
        if any(score>=best-.05 and norm(s['name_jp'])!=winner_name for score,s in choices):continue
        winners=[s for score,s in choices if norm(s['name_jp'])==winner_name and score>=best-.025]
        titles={s.get('name_tw','') for s in winners}
        if len(titles)!=1:continue
        title=next(iter(titles))
        effects={s.get('effect_tw') or s.get('description_tw') or '' for s in winners}
        desc=next(iter(effects)) if len(effects)==1 else ''
        # Extra OCR context may distinguish variant, but only via very strong textual agreement.
        if len(effects)>1:
            scored=[]
            neighboring=[n for n in lines if n is not line and abs(n['cy']-line['cy'])<=max(170,line['height']*9)]
            for s in winners:
                effect=norm(s.get('effect_jp') or s.get('description_jp'))
                if len(effect)<8:continue
                score=max((SequenceMatcher(None,norm(n['text']),effect).ratio() for n in neighboring if len(norm(n['text']))>=8),default=0.)
                scored.append((score,s))
            scored.sort(key=lambda x:x[0],reverse=True)
            if scored and scored[0][0]>=.88 and (len(scored)==1 or scored[0][0]-scored[1][0]>=.10):
                desc=scored[0][1].get('effect_tw') or scored[0][1].get('description_tw') or ''
        if not desc and len(effects)>1:
            desc='同名分隊有多個效果版本；目前只確認名稱，請以遊戲畫面中的效果為準。'
        category=winners[0]['_kind']
        cards.append(dict(status='matched',category=category,topic_id=topic or winners[0]['topic_id'],
                          record_id='squad:'+winner_name+':'+str(topic or 'all'),
                          bbox=line['bbox'],score=round(best*line['confidence'],4),
                          title_tw=title,description_tw=desc,locked_tw=''))
    # Event title fallback: title only when all identical-JP scene records agree on TW title.
    scene_rows=[]
    iterable=records.values() if isinstance(records,dict) else records
    for r in iterable:
        if not isinstance(r,dict) or r.get('category')!='scene':continue
        if topic and r.get('topic_id')!=topic:continue
        fields=r.get('fields') or {}
        jp=norm((fields.get('title') or {}).get('jp'))
        tw=(fields.get('title') or {}).get('tw','')
        if jp and tw:scene_rows.append((jp,tw,r))
    grouped=defaultdict(list)
    for jp,tw,r in scene_rows:grouped[jp].append((tw,r))
    for line in lines:
        q=norm(line['text'])
        if len(q)<4 or line['confidence']<.70:continue
        similar=[(SequenceMatcher(None,q,name).ratio(),name) for name in grouped]
        if not similar:continue
        similar.sort(reverse=True)
        score,name=similar[0]
        if score<.94 or (len(similar)>1 and similar[1][0]>=score-.05):continue
        variants=grouped[name]
        titles={tw for tw,_ in variants}
        if len(titles)!=1 or len(variants)<2:continue
        same_desc={((r.get('fields') or {}).get('description') or {}).get('tw','') for _,r in variants}
        desc=next(iter(same_desc)) if len(same_desc)==1 else '此事件存在不同敘述／階段；已確認標題翻譯，詳細內容需配合當前事件選項判斷。'
        cards.append(dict(status='matched',category='scene',topic_id=topic or variants[0][1].get('topic_id'),
                          record_id='repeated_scene:'+name+':'+str(topic or 'all'),
                          bbox=line['bbox'],score=round(score*line['confidence'],4),title_tw=next(iter(titles)),
                          description_tw=desc,locked_tw=''))
    return cards


def merge_cards(report, additions):
    """Prefer original unambiguous card and replace original ambiguous same bbox."""
    original=list(report.get('cards',[]))
    def overlap(a,b):
        aa=a['bbox'];bb=b['bbox']
        return max(abs(aa[i]-bb[i]) for i in range(4))<26
    for new in additions:
        conflicts=[c for c in original if overlap(c,new)]
        if any(c.get('status')=='matched' and c.get('title_tw') for c in conflicts):continue
        original=[c for c in original if not (overlap(c,new) and c.get('status')!='matched')]
        original.append(new)
    return dict(report,cards=original)
