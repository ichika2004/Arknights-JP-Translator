"""Persistent text detection + recognition process. JSONL IPC, ASCII-safe output.

Worker performs full screen image OCR and returns selected character after
conservative candidate filtering. Paddle native errors cannot crash Qt parent.
"""
from __future__ import annotations
import os
os.environ.setdefault('FLAGS_use_mkldnn','0')
os.environ.setdefault('OMP_NUM_THREADS','1')
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from .phase10_core import load_names, lookup, scene_score, normalize
from difflib import SequenceMatcher

def get_bundled_model_dir(model_name: str):
    """打包版本使用 EXE 旁的模型；開發版本維持原設定。"""
    if not getattr(sys, "frozen", False):
        return None

    exe_dir = Path(sys.executable).resolve().parent
    model_dir = exe_dir / "models" / model_name

    if not model_dir.is_dir():
        raise FileNotFoundError(
            f"找不到 OCR 模型：{model_dir}"
        )

    return str(model_dir)

def emit(data):
    sys.stdout.write('OCR_JSON=' + json.dumps(data, ensure_ascii=True) + '\n')
    sys.stdout.flush()


def unwrap(result):
    data = result.json
    if isinstance(data, str):
        data = json.loads(data)
    return data.get('res',data)


def load_skill_names(path):
    """Use JP skill name, keyed by character ID and 1-based slot."""
    raw=json.loads(path.read_text(encoding='utf-8-sig'))['characters']
    result={}
    for cid,ch in raw.items():
        rows=[]
        for i,skill in enumerate(ch.get('skills') or []):
            levels=skill.get('levels') or []
            jp=next((str(level.get('name_jp')).strip() for level in reversed(levels)
                     if level.get('name_jp')), '')
            if jp:
                rows.append((int(skill.get('slot') or i+1), jp))
        result[cid]=rows
    return result


def skill_box_priority(box,w,h,scene):
    """Generous ROI: tested positions must be tuned for other resolutions/scenes."""
    x1,y1,x2,y2=box
    cx=(x1+x2)/(2*w); cy=(y1+y2)/(2*h)
    bw=(x2-x1)/w; bh=(y2-y1)/h
    if not (.035 <= bw <= .65 and .014 <= bh <= .16):
        return None
    if scene=='operator' and (.48 <= cx <= .98 and .25 <= cy <= .92):
        return 1.0 + bw*0.2
    if scene=='battle' and (.02 <= cx <= .70 and .18 <= cy <= .92):
        return 0.8 + bw*0.2
    return None


def match_skill(text, skill_names):
    key=normalize(text)
    if len(key)<3:
        return None
    scores=[]
    for slot,jp in skill_names:
        candidate=normalize(jp)
        if not candidate:
            continue
        # Do not accept substrings from full skill descriptions.
        ratio=SequenceMatcher(None,key,candidate).ratio()
        scores.append((ratio,slot,jp))
    scores.sort(reverse=True)
    if not scores:
        return None
    best=scores[0]
    runner=scores[1][0] if len(scores)>1 else 0
    if best[0] >= 0.87 and best[0]-runner >= .12:
        return {'slot':best[1], 'text':text, 'name_jp':best[2], 'similarity':round(best[0],4)}
    return None


def run_detection(detector, recognizer, image, scene, names, skill_db, max_candidates=10):
    h,w = image.shape[:2]
    t0 = time.perf_counter()
    found=[]
    all_boxes=[]
    for result in detector.predict(input=image,batch_size=1):
        data=unwrap(result)
        for i,polygon in enumerate(data.get('dt_polys', [])):
            xy=np.asarray(polygon,dtype=np.float32).reshape(-1,2)
            x1=max(0,int(np.floor(xy[:,0].min())))
            y1=max(0,int(np.floor(xy[:,1].min())))
            x2=min(w,int(np.ceil(xy[:,0].max())))
            y2=min(h,int(np.ceil(xy[:,1].max())))
            if x2-x1<16 or y2-y1<12:
                continue
            all_boxes.append([x1,y1,x2,y2])
            det_scores=data.get('dt_scores',[])
            det_conf=float(det_scores[i]) if i<len(det_scores) else None
            if det_conf is not None and det_conf<.15:
                continue
            candidates=[]
            for s in (('operator','battle') if scene=='auto' else (scene,)):
                prior=scene_score(x1,y1,x2,y2,w,h,s)
                if prior is not None:
                    candidates.append((prior,s))
            if not candidates:
                continue
            prior,s=max(candidates)
            found.append({'bbox':[x1,y1,x2,y2],'scene':s,'position_score':prior,'det_confidence':det_conf})
    found.sort(key=lambda a:a['position_score'],reverse=True)
    found=found[:max_candidates]
    detect_seconds=round(time.perf_counter()-t0,3)
    t1=time.perf_counter()
    for entry in found:
        x1,y1,x2,y2=entry['bbox']
        crop=image[y1:y2,x1:x2].copy()
        entry.update({'ocr_text':'','ocr_confidence':0,'matches':[],'character_id':None,'status':'unmatched'})
        try:
            for result in recognizer.predict(input=crop,batch_size=1):
                data=unwrap(result)
                entry['ocr_text']=str(data.get('rec_text') or '').strip()
                entry['ocr_confidence']=float(data.get('rec_score') or 0)
                break
            matches=lookup(entry['ocr_text'],names,topk=5)
            entry['matches']=matches
            best=matches[0] if matches else None
            runner=matches[1]['score'] if len(matches)>1 else 0
            if best and entry['ocr_confidence']>=.65 and best['score']>=.84 and best['score']-runner>=.08:
                entry['character_id']=best['character_id']
                entry['status']='matched'
        except Exception as exc:
            entry['status']='ocr_error'
            entry['error']=str(exc)
    valid=[r for r in found if r['character_id']]
    valid.sort(key=lambda r:(r['matches'][0]['score']*r['ocr_confidence'],r['position_score']),reverse=True)
    selected=valid[0] if valid else None
    skill_result=None
    if selected:
        cid=selected['character_id']
        scene_found=selected['scene']
        ranked=[]
        for box in all_boxes:
            if box == selected['bbox']:
                continue
            priority=skill_box_priority(box,w,h,scene_found)
            if priority is not None:
                ranked.append((priority,box))
        ranked.sort(reverse=True)
        candidates=[]
        # Bound work: no more than 12 additional OCR passes per screenshot.
        for _,box in ranked[:12]:
            x1,y1,x2,y2=box
            try:
                for output in recognizer.predict(input=image[y1:y2,x1:x2].copy(),batch_size=1):
                    info=unwrap(output)
                    text=str(info.get('rec_text') or '').strip()
                    confidence=float(info.get('rec_score') or 0)
                    matched=match_skill(text,skill_db.get(cid,[])) if confidence>=.68 else None
                    if matched:
                        matched.update({'confidence':confidence,'bbox':box})
                        candidates.append(matched)
                    break
            except Exception:
                pass
        if candidates:
            candidates.sort(key=lambda a:(a['similarity']*a['confidence']),reverse=True)
            first=candidates[0]
            second=candidates[1] if len(candidates)>1 else None
            if not second or first['slot']==second['slot'] or (first['similarity']*first['confidence'] - second['similarity']*second['confidence'] >= .12):
                skill_result=first
    return {'skill_detection':skill_result,
            'character_id': selected['character_id'] if selected else None,
            'ocr_text':selected['ocr_text'] if selected else None,
            'scene': selected['scene'] if selected else None,
            'candidates':found,
            'detection_seconds':detect_seconds,
            'recognition_seconds':round(time.perf_counter()-t1,3)}


def main():
    try:
        from paddleocr import TextDetection, TextRecognition
        root=Path(__file__).resolve().parents[1]
        names=load_names(root/'data'/'generated'/'character_names.json')
        skill_db=load_skill_names(root/'data'/'generated'/'skill_database.json')
        t=time.perf_counter()
        detector = TextDetection(
                model_name='PP-OCRv6_medium_det',
                model_dir=get_bundled_model_dir('PP-OCRv6_medium_det'),
                device='cpu',
                enable_mkldnn=False,
                cpu_threads=2
            )
        recognizer = TextRecognition(
                model_name='PP-OCRv6_medium_rec',
                model_dir=get_bundled_model_dir('PP-OCRv6_medium_rec'),
                device='cpu',
                enable_mkldnn=False,
                cpu_threads=2
            )
        emit({'ready':True,'init_seconds':round(time.perf_counter()-t,2),'indexed_names':len(names)})
    except Exception as exc:
        emit({'error':'init: '+repr(exc)})
        return 1
    for line in sys.stdin:
        req_id=None
        try:
            request=json.loads(line)
            req_id=request.get('id')
            image_path=Path(request['image_path'])
            image=cv2.imdecode(np.fromfile(str(image_path),dtype=np.uint8),cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError(f'cannot read image: {image_path}')
            result=run_detection(detector,recognizer,image,request.get('scene','operator'),names,skill_db)
            result['id']=req_id
            emit(result)
        except Exception as exc:
            emit({'id':req_id,'error':repr(exc)})
    return 0

if __name__=='__main__':
    sys.exit(main())
