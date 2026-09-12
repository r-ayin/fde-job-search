# -*- coding: utf-8 -*-
import time, sys
t0 = time.time()
from rapidocr import RapidOCR
print(f"[init] import+load {time.time()-t0:.2f}s", flush=True)

engine = RapidOCR()
t1 = time.time()
res = engine("test_card.png")
print(f"[run ] ocr {time.time()-t1:.2f}s", flush=True)
print("type:", type(res).__name__)
print("attrs:", [a for a in dir(res) if not a.startswith('_')][:20])

txts = getattr(res, "txts", None)
boxes = getattr(res, "boxes", None)
scores = getattr(res, "scores", None)
if txts is None:
    print("raw:", str(res)[:1000]); sys.exit()
print(f"\n识别到 {len(txts)} 个文本块：")
for i,(t,s) in enumerate(zip(txts, scores)):
    b = boxes[i]
    xs=[p[0] for p in b]; ys=[p[1] for p in b]
    x0,y0,x1,y1 = min(xs),min(ys),max(xs),max(ys)
    print(f"  [{i:2d}] conf={float(s):.3f} box=({x0:.0f},{y0:.0f},{x1:.0f},{y1:.0f})  {t}")
