"""Explicit, bounded camera test: statistics only, no saved images."""
import sys
import time
import json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
import psutil
from app.worker import devices
from app.detector import Detector

def check():
    cv2.setNumThreads(1)
    cams=devices()
    if not cams:
        return {'camera_open':False,'reason':'No camera enumerated'}
    d=cams[0]
    cap=cv2.VideoCapture(d['index'],d['backend'])
    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
        cap.set(cv2.CAP_PROP_FPS,10)
        ok,frame=cap.read()
        if not ok:
            return {'camera_open':False,'name':d['name'],'reason':'No frame; possibly busy or permission disabled'}
        model=Detector()
        model.detect(frame)
        proc=psutil.Process()
        t0=time.monotonic()
        cpu0=sum(proc.cpu_times()[:2])
        costs,counts=[],[]
        while time.monotonic()-t0<15:
            t=time.monotonic()
            ok,frame=cap.read()
            if not ok:
                break
            begin=time.monotonic()
            results=model.detect(frame)
            costs.append((time.monotonic()-begin)*1000)
            counts.append(len(results))
            time.sleep(max(0,.2-(time.monotonic()-t)))
        elapsed=time.monotonic()-t0
        return {'camera_open':True,'name':d['name'],'backend':d['backend'],'actual_size':[frame.shape[1],frame.shape[0]],
            'samples':len(costs),'duration_seconds':elapsed,'inference_ms_median':float(np.median(costs)),
            'inference_ms_p95':float(np.percentile(costs,95)),'process_cpu_taskmanager_percent':100*(sum(proc.cpu_times()[:2])-cpu0)/elapsed/psutil.cpu_count(),
            'process_working_set_mb':proc.memory_info().rss/1024**2,'logical_cpus':psutil.cpu_count(),
            'frames_with_person':sum(n>0 for n in counts),'max_person_count':max(counts,default=0),'frames_saved':0}
    finally:
        cap.release()

if __name__=='__main__':
    r=check()
    out=Path(__file__).resolve().parents[2]/'验证结果/camera.json'
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(r,ensure_ascii=False))
