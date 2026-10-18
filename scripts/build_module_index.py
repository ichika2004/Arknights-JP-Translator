"""Build modules from JP/TW/CN game data, keeping regional provenance.
Preserve module IDs, do not infer non-text battle modifiers as descriptions.
"""
from __future__ import annotations
import json
import argparse
import urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE='https://raw.githubusercontent.com/ArknightsAssets/ArknightsGamedata/master'

def source(server,name,refresh=False):
    target=ROOT/'data'/'raw'/'modules'/server/name
    if refresh or not target.is_file():
        target.parent.mkdir(parents=True,exist_ok=True)
        url=f'{BASE}/{server}/gamedata/excel/{name}'
        print('Downloading',url,flush=True)
        request=urllib.request.Request(url,headers={'User-Agent':'Arknights-JP-Translator/23.3'})
        with urllib.request.urlopen(request,timeout=60) as resp: content=resp.read()
        json.loads(content)
        target.write_bytes(content)
    return json.loads(target.read_text(encoding='utf-8-sig'))

def find_equip(data,mid):
    if not isinstance(data,dict):return None
    for key in ('equipDict','equips','modules','battleEquipDict'):
        group=data.get(key)
        if isinstance(group,dict) and mid in group:return group[mid]
    return data.get(mid)

def ordered_phases(entry):
    if not isinstance(entry,dict):return []
    for key in ('phases','levels','equipLevels','stages'):
        items=entry.get(key)
        if isinstance(items,list):return [(i+1,v) for i,v in enumerate(items) if isinstance(v,dict)]
        if isinstance(items,dict):
            return [(int(k) if str(k).isdigit() else i+1,v) for i,(k,v) in enumerate(items.items()) if isinstance(v,dict)]
    if all(str(i) in entry for i in range(1,4)):
        return [(i,entry[str(i)]) for i in range(1,4) if isinstance(entry[str(i)],dict)]
    return []

# Rich-text game fields; intentionally exclude internal numeric blackboards.
TEXT_KEYS={'description','desc','effect','effectdesc','effectdescription','upgradedesc','upgradedescription',
           'additionaldescription','additionaldesc','overridedescription','overridedescrip',
           'talentdesc','talentdescription','traiteffect','traitdescription','partdesc',
           'buffdesc','buffdescription','unlockdescription','unlockdesc','uniequipdesc'}

def extract_text(obj,max_depth=8):
    found=[]
    def walk(value,depth=0):
        if depth>max_depth:return
        if isinstance(value,dict):
            for key,v in value.items():
                if isinstance(v,str) and str(key).lower() in TEXT_KEYS and v.strip():
                    found.append(v.strip())
                elif isinstance(v,(dict,list)):walk(v,depth+1)
        elif isinstance(value,list):
            for v in value:walk(v,depth+1)
    walk(obj)
    return list(dict.fromkeys(found))

def text(d,*keys):
    for key in keys:
        s=d.get(key) if isinstance(d,dict) else None
        if isinstance(s,str) and s.strip():return s.strip()
    return ''

ATTRIBUTE_LABELS = {'max_hp':'生命值','atk':'攻擊力','def':'防禦力',
                    'magic_resistance':'法術抗性','attack_speed':'攻擊速度',
                    'respawn_time':'再部署時間','cost':'部署費用','block_cnt':'阻擋數'}

import re
MARKUP = re.compile(r'<[^>]+>')
PLACEHOLDER = re.compile(r'\{([A-Za-z_][A-Za-z0-9_]*)(?::([^}]+))?\}')

def readable(value, board=None):
    if not isinstance(value,str): return ''
    board=board if isinstance(board,dict) else {}
    def replace(match):
        k,fmt=match.group(1),match.group(2) or ''
        if k not in board:return match.group(0)
        v=board[k]
        if not isinstance(v,(int,float)): return match.group(0)
        if '%' in fmt:
            z=v*100
            return f'{z:g}%'
        if fmt.startswith('0.') and fmt[2:].isdigit():
            return f'{v:.{min(int(fmt[2:]),6)}f}'
        return f'{v:g}'
    value=PLACEHOLDER.sub(replace,value)
    return MARKUP.sub('',value).strip()

def blackboard_as_dict(raw):
    """Game data represents blackboards as either mappings or key/value arrays."""
    if isinstance(raw, dict):
        # A single {"key": "atk", "value": 65} entry is also valid.
        if isinstance(raw.get('key'), str) and 'value' in raw:
            return {raw['key']: raw['value']}
        return raw
    if isinstance(raw, list):
        result = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            key = item.get('key')
            if not isinstance(key, str):
                continue
            result[key] = item.get('value')
        return result
    return {}


def extract_stage(phase):
    """Use known display descriptions only. No inferred game combat mechanics."""
    if not isinstance(phase,dict):return {'attributes':{},'trait':[],'talent':[]}
    attrib=blackboard_as_dict(phase.get('attributeBlackboard'))
    attributes={ATTRIBUTE_LABELS.get(k,k):v for k,v in attrib.items()
                if isinstance(v,(int,float)) and not isinstance(v,bool) and v!=0}
    traits=[];talents=[]
    for part in phase.get('parts',[]) if isinstance(phase.get('parts'),list) else []:
        if not isinstance(part,dict):continue
        for bundle,keys,out in (
            ('overrideTraitDataBundle',('overrideDescripton','overrideDescription','additionalDescription','traitDescription'),traits),
            ('addOrOverrideTalentDataBundle',('upgradeDescription','description','talentDescription'),talents)):
            node=part.get(bundle) or {}
            candidates = node.get('candidates') if isinstance(node, dict) else None
            if isinstance(candidates, dict):
                candidates = list(candidates.values())
            elif not isinstance(candidates, list):
                candidates = []
            for candidate in candidates:
                if not isinstance(candidate,dict):continue
                board=blackboard_as_dict(candidate.get('blackboard'))
                for key in keys:
                    value=readable(candidate.get(key),board)
                    if value and value not in out:out.append(value)
    return {'attributes':attributes,'trait':traits,'talent':talents}

def build(refresh=False):
    jp=source('jp','uniequip_table.json',refresh);tw=source('tw','uniequip_table.json',refresh)
    jbe=source('jp','battle_equip_table.json',refresh);tbe=source('tw','battle_equip_table.json',refresh)
    try:
        cn=source('cn','uniequip_table.json',refresh)
        cbe=source('cn','battle_equip_table.json',refresh)
    except Exception as exc:
        print('[WARN] Simplified Chinese data unavailable:',exc,flush=True)
        cn={'equipDict':{}};cbe={}

    jdict=jp.get('equipDict',{});tdict=tw.get('equipDict',{});cdict=cn.get('equipDict',{})
    result={}; by_char={}; stage_count=0; stage_text_count=0; jp_only=[]
    for mid,j in jdict.items():
        t=tdict.get(mid)
        c=cdict.get(mid)
        if not isinstance(j,dict):continue
        localized = isinstance(t,dict)
        if not localized:
            t={}
        if not isinstance(c,dict):c={}
        if not localized and not c:jp_only.append(mid)

        cid=j.get('charId') or t.get('charId')
        if not cid or str(j.get('typeIcon','')).lower()=='original':continue
        record={'id':mid,'character_id':cid,
                'name_jp':text(j,'uniEquipName'),'name_tw':text(t,'uniEquipName'),'name_cn':text(c,'uniEquipName'),
                'translation_status':'tw_matched' if localized else ('cn_fallback' if c else 'jp_only'),
                'description_jp':text(j,'uniEquipDesc'),'description_tw':text(t,'uniEquipDesc'),'description_cn':text(c,'uniEquipDesc'),
                'story_tw':text(t,'uniEquipDesc'),'story_cn':text(c,'uniEquipDesc'),
                'type_jp':text(j,'typeName1','typeName2'),
                'type_tw':text(t,'typeName1','typeName2'),'type_cn':text(c,'typeName1','typeName2'),
                'unlock_level':t.get('unlockLevel'),
                'unlock_phase':t.get('unlockEvolvePhase'),
                'stages':[]}
        bjp=find_equip(jbe,mid);btw=find_equip(tbe,mid);bcn=find_equip(cbe,mid)
        jp_phases=dict(ordered_phases(bjp));tw_phases=dict(ordered_phases(btw));cn_phases=dict(ordered_phases(bcn))
        # Some regional tables do not expose stages at all; preserve provenance.
        for n in sorted(jp_phases.keys() | tw_phases.keys() | cn_phases.keys()):
            jphase=jp_phases.get(n, {});tphase=tw_phases.get(n, {});cphase=cn_phases.get(n, {})
            tw_strings=extract_text(tphase);jp_strings=extract_text(jphase)
            parsed_tw=extract_stage(tphase); parsed_jp=extract_stage(jphase);parsed_cn=extract_stage(cphase);
            # Avoid accidentally labeling one-time unlock text as stage effect.
            phase={'level':n,'effects_tw':tw_strings,'effects_jp':jp_strings,'effects_cn':extract_text(cphase),
                   'has_raw_battle_data':bool(jphase or tphase or cphase), 'attributes_tw':parsed_tw['attributes'],
                   'traits_tw':parsed_tw['trait'], 'talents_tw':parsed_tw['talent'],
                   'traits_jp':parsed_jp['trait'], 'talents_jp':parsed_jp['talent'],
                   'attributes_jp':parsed_jp['attributes'],
                   'attributes_cn':parsed_cn['attributes'],'traits_cn':parsed_cn['trait'],'talents_cn':parsed_cn['talent']}
            record['stages'].append(phase)
            stage_count+=1
            if tw_strings or parsed_tw['trait'] or parsed_tw['talent'] or parsed_tw['attributes']:stage_text_count+=1
        result[mid]=record
        by_char.setdefault(cid,[]).append(mid)
    target=ROOT/'data'/'generated'/'operator_modules.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps({'modules':result,'by_character':by_char,'stats':{'stages':stage_count,'stages_with_text':stage_text_count,'jp_only':len(jp_only),'cn_fallback':sum(r['translation_status']=='cn_fallback' for r in result.values())}},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Saved',target,'modules',len(result),'stages',stage_count,'stages with effect text',stage_text_count)
    print('JP-only modules without TW or CN table entry:',len(jp_only))
    print('Modules matched in CN but not TW:',sum(r['translation_status']=='cn_fallback' for r in result.values()))
    print('Stage coverage includes attribute bonuses and readable trait/talent descriptions. Some game parameters remain untranslated.')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--refresh',action='store_true',help='Download fresh JP/TW module files before rebuilding')
    args=parser.parse_args()
    build(refresh=args.refresh)
