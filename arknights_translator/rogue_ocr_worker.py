"""Phase 21: full-screen det + batched recognition, with conservative fallback.

OCR protocol remains compatible with existing Phase 18/20 views.
"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path
os.environ.setdefault('FLAGS_use_mkldnn', '0')
os.environ.setdefault('OMP_NUM_THREADS', '1')
import cv2
import numpy as np


def emit(payload):
    print('OCR_JSON=' + json.dumps(payload, ensure_ascii=True), flush=True)


def unpack(result):
    value = result.json
    if isinstance(value, str):
        value = json.loads(value)
    return value.get('res', value)


def model_path(name):
    if not getattr(sys, 'frozen', False):
        return None
    path = Path(sys.executable).resolve().parent / 'models' / name
    if not path.is_dir():
        raise FileNotFoundError(f'Bundled OCR model missing: {path}')
    return str(path)


def detect_boxes(det, image):
    h, w = image.shape[:2]
    unique = set()
    for result in det.predict(input=image, batch_size=1):
        info = unpack(result)
        for polygon in info.get('dt_polys', []):
            xy = np.asarray(polygon, dtype=np.float32).reshape(-1, 2)
            x1 = max(0, int(np.floor(xy[:, 0].min())))
            y1 = max(0, int(np.floor(xy[:, 1].min())))
            x2 = min(w, int(np.ceil(xy[:, 0].max())))
            y2 = min(h, int(np.ceil(xy[:, 1].max())))
            if x2-x1 >= 18 and y2-y1 >= 12:
                unique.add((x1, y1, x2, y2))
    return sorted(unique, key=lambda box: (box[1], box[0]))


def results_for(rec, crops, batch_size=8):
    """Batch recognition. On unsupported runtime/batch errors use sequential fallback."""
    if not crops:
        return [], 'none'
    try:
        results = list(rec.predict(input=crops, batch_size=batch_size))
        if len(results) != len(crops):
            raise ValueError(f'Batch result count {len(results)} != {len(crops)}')
        return [unpack(result) for result in results], 'batch'
    except Exception as exc:
        print('[Rogue OCR] batch unavailable, sequential fallback:', repr(exc), file=sys.stderr, flush=True)
        output = []
        for crop in crops:
            try:
                response = next(iter(rec.predict(input=crop, batch_size=1)))
                output.append(unpack(response))
            except Exception:
                output.append({})
        return output, 'sequential'


def recognize(det, rec, image):
    t0 = time.perf_counter()
    boxes = detect_boxes(det, image)  # Entire screen: no fixed region cutoff.
    detect_seconds = time.perf_counter()-t0
    t1 = time.perf_counter()
    rows = []
    methods = set()
    # Bound memory per batch without limiting the number of boxes examined.
    for start in range(0, len(boxes), 8):
        batch = boxes[start:start+8]
        crops = [image[y1:y2, x1:x2].copy() for x1,y1,x2,y2 in batch]
        output, method = results_for(rec, crops, batch_size=8)
        methods.add(method)
        for bbox, item in zip(batch, output):
            text = str(item.get('rec_text') or '').strip()
            score = float(item.get('rec_score') or 0)
            if text and score >= .5:
                rows.append({'text':text, 'confidence':round(score,3), 'bbox':list(bbox)})
    recognition_seconds = time.perf_counter()-t1
    return rows, {
        'detected_boxes':len(boxes),
        'detection_seconds':round(detect_seconds,3),
        'recognition_seconds':round(recognition_seconds,3),
        'recognition_method':','.join(sorted(methods)),
    }


def main():
    try:
        from paddleocr import TextDetection, TextRecognition
        started = time.perf_counter()
        det = TextDetection(model_name='PP-OCRv6_medium_det', model_dir=model_path('PP-OCRv6_medium_det'),
                            device='cpu', enable_mkldnn=False, cpu_threads=2)
        rec = TextRecognition(model_name='PP-OCRv6_medium_rec', model_dir=model_path('PP-OCRv6_medium_rec'),
                              device='cpu', enable_mkldnn=False, cpu_threads=2)
        emit({'ready':True, 'init_seconds':round(time.perf_counter()-started,2)})
    except Exception as exc:
        emit({'error':'init: '+repr(exc)})
        return 1
    for line in sys.stdin:
        rid = None
        try:
            req = json.loads(line)
            rid = req.get('id')
            image = cv2.imdecode(np.fromfile(req['image_path'],dtype=np.uint8),cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError('cannot decode screenshot')
            t = time.perf_counter()
            rows, metrics = recognize(det, rec, image)
            emit({'id':rid, 'lines':rows, 'seconds':round(time.perf_counter()-t,2), **metrics})
        except Exception as exc:
            emit({'id':rid, 'error':repr(exc)})
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
