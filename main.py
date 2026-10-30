import os
import sys
os.environ.setdefault('QT_LOGGING_RULES', 'qt.multimedia.*=false')
os.environ.setdefault('QT_MEDIA_BACKEND', 'windows')
from PySide6.QtCore import QLockFile, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox
from app.config import DATA
from app.paths import data_dir, CONTROL

def main():
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('BehindWatch.Desktop.1')
    app=QApplication(sys.argv)
    app.setApplicationName('BehindWatch')
    app.setQuitOnLastWindowClosed(False)
    DATA.mkdir(parents=True,exist_ok=True)
    CONTROL.mkdir(parents=True,exist_ok=True)
    lock=QLockFile(str(CONTROL/'app.lock'))
    lock.setStaleLockTime(30000)
    if not lock.tryLock(100):
        QMessageBox.information(None,'BehindWatch 已运行','请在系统托盘找到 BehindWatch，双击打开窗口。')
        return 0
    from app.ui import MainWindow
    w=MainWindow(demo='--smoke-test' in sys.argv)
    w.show()
    if '--camera-smoke-test' in sys.argv:
        import json
        import time
        started=time.monotonic()
        result={'started':False,'detection_result':False,'frames_saved':0}
        w.cfg.dnd=True
        w.cfg.screenshots=False
        def probe():
            if not result['started'] and w.cameras.count():
                w.launch(True)
                result['started']=True
            if w.worker and w.worker.result:
                result['detection_result']=True
            if time.monotonic()-started>12:
                probe_timer.stop()
                result['last_status']=w.status.text()
                w.quit()
        def finished():
            result['camera_released']=w.worker is None
            (DATA/'camera-smoke.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
        app.aboutToQuit.connect(finished)
        probe_timer=QTimer(w)
        probe_timer.timeout.connect(probe)
        probe_timer.start(250)
    if '--smoke-test' in sys.argv:
        from app.detector import Detector
        import numpy as np
        import json
        result={'model_loaded':True,'blank_detections':len(Detector().detect(np.zeros((480,640,3),dtype=np.uint8)))}
        (DATA/'smoke-result.json').write_text(json.dumps(result),encoding='utf-8')
        QTimer.singleShot(1800,w.finish_quit)
    code=app.exec()
    lock.unlock()
    return code

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception:
        import traceback
        current_data = data_dir()
        current_data.mkdir(parents=True,exist_ok=True)
        (current_data/'startup-error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        if QApplication.instance():
            QMessageBox.critical(None,'启动失败',f'错误信息保存在：\n{current_data / "startup-error.txt"}')
        raise
