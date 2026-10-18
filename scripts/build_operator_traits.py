"""Build original (non-module) operator trait/talent captions from TW character table.
Official TW data; never infer modified trait from a module stage.
"""
from __future__ import annotations
import json
from pathlib import Path
from build_module_index import source
ROOT=Path(__file__).resolve().parents[1]

def first_description(value):
    if not isinstance(value,dict):return ''
    candidates=value.get('candidates') or []
    if isinstance(candidates,dict):candidates=list(candidates.values())
    if not isinstance(candidates,list):candidates=[]
    for candidate in candidates:
        if not isinstance(candidate,dict):continue
        for name in ('overrideDescripton','overrideDescription','description'):
            text=candidate.get(name)
            if isinstance(text,str) and text.strip():return text.strip()
    for name in ('description','overrideDescripton','overrideDescription'):
        text=value.get(name)
        if isinstance(text,str) and text.strip():return text.strip()
    return ''

def build():
    characters=source('tw','character_table.json')
    result={}
    for cid,info in characters.items():
        if not isinstance(info,dict):continue
        trait=first_description(info.get('trait'))
        talents=[]
        for talent in info.get('talents') or []:
            desc=first_description(talent)
            if desc and desc not in talents:talents.append(desc)
        if trait or talents:
            result[cid]={'trait_tw':trait,'talents_tw':talents}
    target=ROOT/'data'/'generated'/'operator_traits.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Saved {target}: {len(result)} operators')

if __name__=='__main__':build()
