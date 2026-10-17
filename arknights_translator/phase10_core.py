"""Reuse Phase 10 name matching and box selection without importing its CLI."""
from __future__ import annotations
import json
import re
import unicodedata
from pathlib import Path
from difflib import SequenceMatcher

def normalize(s):
    s=unicodedata.normalize('NFKC',str(s or '')).casefold()
    return re.sub(r'[\s\u200b\u3000\u00b7・\-\'’]+','',s)

def load_names(path:Path):
    data=json.loads(path.read_text(encoding='utf-8-sig'))
    names={}
    for cid,row in data.items():
        if not cid.startswith('char_') or not isinstance(row,dict):
            continue
        for field in ('name_jp','name_en','name_zh_tw'):
            val=row.get(field)
            if isinstance(val,str) and val.strip():
                names.setdefault(normalize(val),set()).add(cid)
    if not names:
        raise ValueError('character names database is empty')
    return names

def lookup(text,names,topk=5):
    key=normalize(text)
    if not key:
        return []
    try:
        from rapidfuzz.fuzz import ratio
        metric=lambda a,b:ratio(a,b)/100
    except ImportError:
        metric=lambda a,b:SequenceMatcher(None,a,b).ratio()
    scores={}
    for name,ids in names.items():
        value=metric(key,name)
        for cid in ids:
            scores[cid]=max(value,scores.get(cid,0))
    return [{'character_id':cid,'score':round(score,4)} for cid,score in sorted(scores.items(),key=lambda x:(-x[1],x[0]))[:topk]]

def scene_score(x1,y1,x2,y2,width,height,scene):
    cx=(x1+x2)/(2*width)
    cy=(y1+y2)/(2*height)
    bw=(x2-x1)/width
    bh=(y2-y1)/height
    if scene=='operator':
        if not (0<=cx<=.40 and .57<=cy<=.89 and .08<=bw<=.40 and .025<=bh<=.16):
            return None
        return 1-abs(cy-.76)*1.8+bw*.8
    if scene=='battle':
        if not (cx<=.56 and .12<=cy<=.88 and .045<=bw<=.42 and .018<=bh<=.15):
            return None
        return .7+bw*.7
    raise ValueError(scene)
