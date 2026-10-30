"""Render fictional corridor graphics; never opens a camera or reads user images."""
import os
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ['BEHINDWATCH_DATA']=tempfile.mkdtemp(prefix='behindwatch-public-demo-')
os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['QT_MEDIA_BACKEND']='windows'
import cv2
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase,QFont
from app.ui import MainWindow

app=QApplication([])
for path in ('C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/msyhbd.ttc','C:/Windows/Fonts/segoeui.ttf'):
    if Path(path).exists():
        QFontDatabase.addApplicationFont(path)
app.setFont(QFont('Microsoft YaHei',10))
w=MainWindow(demo=True)
w.resize(980,780)
w.cameras.addItem('演示摄像头（模拟画面）')
w.start_button.setText('停止监测')
w.preview_button.setText('检测画面')
w.preview_button.setEnabled(False)
w.on_status('检测到 1 人 · 以下为模拟画面','alert')
frame=np.full((480,640,3),(209,220,218),np.uint8)
cv2.fillConvexPoly(frame,np.array([[0,480],[240,180],[400,180],[640,480]]),(175,192,186))
cv2.fillConvexPoly(frame,np.array([[0,0],[240,180],[400,180],[640,0]]),(233,239,236))
cv2.rectangle(frame,(248,105),(392,235),(153,176,166),-1)
for x in (80,170,470,560):
    cv2.line(frame,(x,0),(240 if x<320 else 400,180),(185,204,197),2)
for y in (265,355,450):
    cv2.line(frame,(0,y),(640,y),(154,177,168),1)
# Two abstract silhouettes, deliberately not photographs.
cv2.ellipse(frame,(172,458),(98,150),0,0,360,(78,112,106),-1)
cv2.circle(frame,(172,300),47,(98,137,127),-1)
cv2.rectangle(frame,(442,265),(487,369),(47,95,84),-1)
cv2.circle(frame,(464,241),23,(71,118,104),-1)
cv2.line(frame,(449,360),(439,415),(47,95,84),13)
cv2.line(frame,(480,360),(490,415),(47,95,84),13)
cv2.line(frame,(442,279),(419,327),(47,95,84),10)
cv2.line(frame,(486,279),(507,325),(47,95,84),10)
w.cfg.roi=[.04,.08,.97,.96]
w.cfg.exclusions=[[.10,.50,.43,.99]]
w.preview.set_frame(frame,[((.11,.50,.43,.99),.94),((.64,.44,.81,.90),.91)],w.cfg)
w.metrics.setText('640×480 · 本地处理 · 每秒检测 5 次')
w.show()
app.processEvents()
(ROOT/'docs').mkdir(exist_ok=True)
w.grab().save(str(ROOT/'docs/demo.png'))
w.finish_quit()
print('Rendered fictional interface demo')
