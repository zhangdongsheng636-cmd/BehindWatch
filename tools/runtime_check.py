"""Exercise the full app on the real camera, no image output."""
import os
import sys
import tempfile
import json
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['BEHINDWATCH_DATA']=tempfile.mkdtemp(prefix='behindwatch-runtime-')
os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['QT_MEDIA_BACKEND']='windows'
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from app.ui import MainWindow
import psutil
app=QApplication([])
w=MainWindow()
w.cfg.dnd=True
proc=psutil.Process()
state={'started':False,'statuses':[],'frames_saved':0}
start=time.monotonic()
cpu0=None
wall0=None
maxrss=0
def step():
    global cpu0,wall0,maxrss
    elapsed=time.monotonic()-start
    maxrss=max(maxrss,proc.memory_info().rss/1024**2)
    if not state['started'] and w.cameras.count():
        w.launch(True)
        state['started']=True
    if elapsed>5 and cpu0 is None:
        cpu0=sum(proc.cpu_times()[:2]); wall0=time.monotonic()
    if w.worker and w.worker.result:
        state['has_detection_result']=True
    if elapsed>20:
        state['background_taskmanager_cpu_percent']=100*(sum(proc.cpu_times()[:2])-cpu0)/(time.monotonic()-wall0)/psutil.cpu_count() if cpu0 is not None else None
        state['peak_working_set_mb']=maxrss
        state['duration_seconds']=elapsed
        state['logical_cpu_count']=psutil.cpu_count()
        state['last_status']=w.status.text()
        timer.stop()
        w.quit()
        QTimer.singleShot(8000,app.quit)
w.bus.status.connect(lambda text,kind:state['statuses'].append([text,kind]))
timer=QTimer()
timer.timeout.connect(step)
timer.start(500)
app.exec()
state['worker_stopped']=w.worker is None
out=Path(__file__).resolve().parents[2]/'验证结果/runtime.json'
out.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(state,ensure_ascii=False))
