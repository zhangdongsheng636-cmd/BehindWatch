"""Local integration check. Never records a real camera image."""
import os
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ['BEHINDWATCH_DATA']=tempfile.mkdtemp(prefix='behindwatch-check-')
os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['QT_MEDIA_BACKEND']='windows'
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtGui import QFontDatabase, QFont
import numpy as np
from app.ui import MainWindow, Settings
from app.detector import Detector
from app.config import Config, DATA
import json
import time

app=QApplication([])
for font in ['C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/msyhbd.ttc','C:/Windows/Fonts/segoeui.ttf']:
    QFontDatabase.addApplicationFont(font)
app.setFont(QFont('Microsoft YaHei',10))
w=MainWindow(demo=True)
w.show()
app.processEvents()
model=Detector()
blank=np.zeros((480,640,3),np.uint8)
assert not model.detect(blank)
costs=[]
for _ in range(20):
    t=time.perf_counter()
    model.detect(blank)
    costs.append((time.perf_counter()-t)*1000)
# Synthetic preview makes UI reproducible without persisting private imagery.
frame=np.full((480,640,3),(55,75,74),np.uint8)
frame[:180]=[100,115,111]
frame[180:]=[58,74,72]
w.cfg.roi=[.48,.08,.96,.95]
w.preview.set_frame(frame,[((.6,.25,.78,.88),.91)],w.cfg)
w.on_status('监测中 · 界面验证画面','on')
app.processEvents()
out=ROOT.parent/'验证结果'
out.mkdir(exist_ok=True)
w.grab().save(str(out/'主窗口.png'))
dialog=Settings(w.cfg,w)
dialog.show()
app.processEvents()
dialog.grab().save(str(out/'设置.png'))
dialog.close()
# Selecting on a letterboxed preview must give normalized coordinates.
hits=[]
w.preview.selected.connect(lambda b,e:hits.append((b,e)))
r=w.preview.target()
w.preview.mode='roi'
a=QPointF(r.x()+r.width()*.2,r.y()+r.height()*.3)
b=QPointF(r.x()+r.width()*.8,r.y()+r.height()*.9)
for typ,p in [(QMouseEvent.Type.MouseButtonPress,a),(QMouseEvent.Type.MouseButtonRelease,b)]:
    event=QMouseEvent(typ,p,p,Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
    app.sendEvent(w.preview,event)
assert hits and np.allclose(hits[0][0],[.2,.3,.8,.9])
w.cfg.popup=w.cfg.border=w.cfg.sound=w.cfg.notification=True
w.cfg.dnd=True
w.alerts.notify(w.cfg,test=True)
assert not w.alerts.popup.isVisible() and not w.alerts.border.isVisible() and not w.alerts.sound.isPlaying()
w.cfg.dnd=False
w.alerts.notify(w.cfg,test=True)
assert w.alerts.popup.isVisible()
w.alerts.silence()
w.show_mini()
app.processEvents()
w.mini.grab().save(str(out/'迷你窗口.png'))
w.mini.fold()
assert not w.mini.preview.isVisible()
w.restore()
# Storage defaults never write images; optional snapshot is bounded to ROI.
w.store.submit('测试',{'ok':True},None,Config())
w.store.queue.join()
assert not list((DATA/'snapshots').glob('*.jpg'))
w.store.submit('测试截图',{'ok':True},frame,Config(screenshots=True,roi=[.5,.0,1.,1.]))
w.store.queue.join()
import cv2
pics=list((DATA/'snapshots').glob('*.jpg'))
assert len(pics)==1
assert cv2.imdecode(np.frombuffer(pics[0].read_bytes(),np.uint8),cv2.IMREAD_COLOR).shape[:2]==(480,320)
w.cfg.save()
assert Config.load().roi==w.cfg.roi
result={'python':sys.version,'blank_detections':0,'inference_ms_median':float(np.median(costs)),'inference_ms_p95':float(np.percentile(costs,95)),'roi_mapping':True,'dnd':True,'popup':True,'mini':True,'default_no_snapshot':True,'snapshot_crop':True,'config_roundtrip':True}
(out/'integration.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
w.finish_quit()
print(json.dumps(result,ensure_ascii=False))
