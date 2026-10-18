"""Fast cached Japanese squad / repeated scene OCR matching for Phase 22.4."""
from __future__ import annotations
from collections import defaultdict
from difflib import SequenceMatcher
from functools import lru_cache
from arknights_translator.rogue_layout_engine import make_lines, norm
from arknights_translator.rogue_context_cards import load_squads, merge_cards


def similarity(a,b):
    if not a or not b: return 0.0
    if a == b: return 1.0
    if abs(len(a)-len(b))>max(4,len(b)//2): return 0.0
    return SequenceMatcher(None,a,b,autojunk=False).ratio()


class CachedContextMatcher:
    def __init__(self, squads=None):
        self.squads = load_squads() if squads is None else squads
        self.squad_names=defaultdict(list)
        for s in self.squads:
            k=(s.get('topic_id'),norm(s.get('name_jp')))
            if k[1]: self.squad_names[k].append(s)
        self.squad_keys=tuple(self.squad_names)
        self._scene_source=None
        self.scenes={}
        self.scene_keys=()

    def prepare_scenes(self,records):
        if records is self._scene_source:return
        self._scene_source=records
        groups=defaultdict(list)
        iterable=records.values() if isinstance(records,dict) else records
        for r in iterable:
            if not isinstance(r,dict) or r.get('category')!='scene':continue
            fields=r.get('fields') or {}
            t=fields.get('title') or {}
            jp=norm(t.get('jp'))
            tw=t.get('tw') or ''
            if jp and tw: groups[(r.get('topic_id'),jp)].append((tw,r))
        self.scenes=groups
        self.scene_keys=tuple(groups)

    @staticmethod
    def candidate(query, keys, topic, min_score):
        # Exact match first, only fuzzy-search if OCR differs.
        exact=[k for k in ((topic,query),(None,query)) if k in keys]
        if exact:return exact[0],1.0
        candidates=[]
        for key in keys:
            if topic and key[0]!=topic:continue
            name=key[1]
            if abs(len(query)-len(name)) > max(3,len(name)//3): continue
            score=similarity(query,name)
            if score>=min_score:candidates.append((score,key))
        if not candidates:return None,0.0
        candidates.sort(reverse=True)
        if len(candidates)>1 and candidates[0][0]-candidates[1][0]<.07:return None,0.0
        return candidates[0][1],candidates[0][0]

    @staticmethod
    def effect_agreement(effect, other_lines):
        normalized=norm(effect)
        if len(normalized)<6:return 0.0
        texts=[norm(x['text']) for x in other_lines if len(norm(x['text']))>=5]
        if not texts:return 0.0
        # Effect text in UI is often line-wrapped: compare a nearby combined text too.
        combined=''.join(texts[:8])
        values=[similarity(text,normalized) for text in texts]
        if normalized in combined:return 1.0
        values.append(similarity(combined,normalized))
        # Partial substantial overlap still useful, but cannot uniquely select a variant.
        return max(values,default=0.0)

    def match(self, raw_lines, records, topic=None):
        self.prepare_scenes(records)
        lines=make_lines(raw_lines)
        results=[]
        for line in lines:
            q=norm(line['text'])
            confidence=line.get('confidence',0)
            if len(q)<3 or confidence<.62:continue
            key,score=self.candidate(q,self.squad_names,topic,.87)
            if key:
                group=self.squad_names[key]
                title_set={s.get('name_tw','') for s in group}
                if len(title_set)==1 and next(iter(title_set)):
                    title=next(iter(title_set))
                    effects={s.get('effect_tw') or s.get('description_tw') or '' for s in group}
                    desc=next(iter(effects)) if len(effects)==1 else ''
                    if len(effects)>1:
                        near=sorted((n for n in lines if n is not line and abs(n['cy']-line['cy'])<=max(190,line['height']*10)),key=lambda n:abs(n['cy']-line['cy']))[:12]
                        scored=sorted(((self.effect_agreement(s.get('effect_jp') or s.get('description_jp'),near),s) for s in group),key=lambda x:x[0],reverse=True)
                        if scored and scored[0][0]>=.82 and (len(scored)==1 or scored[0][0]-scored[1][0]>=.09):
                            desc=scored[0][1].get('effect_tw') or scored[0][1].get('description_tw') or ''
                        else:
                            # Show meaningful, source-grounded options rather than a name-only dead end.
                            distinct=list(dict.fromkeys(x for x in (s.get('effect_tw') or s.get('description_tw') or '' for s in group) if x))
                            if len(distinct)<=5:
                                desc='此分隊有不同版本，畫面尚無法確定效果：\n'+ '\n'.join(f'• {x}' for x in distinct)
                            else:
                                desc=f'此分隊存在 {len(distinct)} 種不同效果，請依遊戲畫面核對。目前不顯示不確定的版本效果。'
                    results.append(dict(status='matched',category=group[0].get('_kind','starting_squad'),topic_id=key[0],record_id=f'squad:{key[0]}:{key[1]}',bbox=line['bbox'],score=round(score*confidence,4),title_tw=title,description_tw=desc,locked_tw=''))
            if len(q)<4 or confidence<.7:continue
            skey,sscore=self.candidate(q,self.scenes,topic,.93)
            if skey:
                variants=self.scenes[skey]
                if len(variants)<2:continue
                titles={tw for tw,_ in variants}
                if len(titles)!=1:continue
                descriptions={((r.get('fields') or {}).get('description') or {}).get('tw','') for _,r in variants}
                desc=next(iter(descriptions)) if len(descriptions)==1 else '此事件有不同敘述或階段；已確認標題，完整內容需依事件選項判斷。'
                results.append(dict(status='matched',category='scene',topic_id=skey[0],record_id=f'repeated_scene:{skey[0]}:{skey[1]}',bbox=line['bbox'],score=round(sscore*confidence,4),title_tw=next(iter(titles)),description_tw=desc,locked_tw=''))
        return results
