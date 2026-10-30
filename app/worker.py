import copy
import threading
import time
import uuid
import cv2
from PySide6.QtCore import QObject, Signal
from cv2_enumerate_cameras import enumerate_cameras
from .detector import Detector
from .engine import Engine

def devices():
    result = []
    for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF):
        try:
            for c in enumerate_cameras(backend):
                result.append({'name': c.name, 'path': c.path or f'{c.name}:{c.index}', 'index': c.index, 'backend': c.backend})
        except Exception:
            continue
    return result

class Bus(QObject):
    status = Signal(str, str)
    event = Signal(object)
    enumerated = Signal(object)

class Worker:
    def __init__(self, cfg, bus, monitoring=True):
        self.bus = bus
        self.cfg = copy.deepcopy(cfg)
        self.monitoring = monitoring
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.raw = None
        self.result = None
        self.seq = 0
        self.epoch = 0
        self.last_status = None
        self.session = uuid.uuid4().hex[:8]
        self.capture = threading.Thread(target=self.capture_loop, daemon=True)
        self.processing = threading.Thread(target=self.process_loop, daemon=True)

    def start(self):
        self.capture.start()
        self.processing.start()

    def update(self, cfg, monitoring):
        with self.lock:
            self.cfg = copy.deepcopy(cfg)
            self.monitoring = monitoring
            self.epoch += 1
            self.result = None

    def stop(self):
        self.stop_event.set()

    def alive(self):
        return self.capture.is_alive() or self.processing.is_alive()

    def status(self, text, kind):
        if self.last_status != (text, kind) and not self.stop_event.is_set():
            self.last_status = (text, kind)
            self.bus.status.emit(text, kind)

    def capture_loop(self):
        cv2.setNumThreads(1)
        failed_backend = None
        while not self.stop_event.is_set():
            cap = None
            try:
                self.status('正在连接摄像头…', 'busy')
                available = devices()
                selected = next((d for d in available if d['path'] == self.cfg.camera_path and d['backend'] == self.cfg.backend), None)
                if selected is None:
                    raise RuntimeError('所选摄像头已断开，请刷新设备')
                # Match the physical USB path, not a backend-specific index or name.
                physical = selected['path'].split('#{')[0].lower()
                alternate = next((d for d in available if d['backend'] != selected['backend'] and d['path'].split('#{')[0].lower() == physical), None)
                if failed_backend == selected['backend'] and alternate:
                    selected = alternate
                cap = cv2.VideoCapture(selected['index'], selected['backend'])
                if not cap.isOpened():
                    raise RuntimeError('摄像头不可用：检查权限或关闭占用相机的软件')
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg.height)
                cap.set(cv2.CAP_PROP_FPS, 10)
                while not self.stop_event.is_set():
                    began = time.monotonic()
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        raise RuntimeError('摄像头无画面，正在重试')
                    h, w = frame.shape[:2]
                    scale = min(1., 640/w, 480/h)
                    if scale < 1:
                        frame = cv2.resize(frame, (round(w*scale), round(h*scale)))
                    with self.lock:
                        self.seq += 1
                        self.raw = (self.seq, time.monotonic(), frame, (w, h))
                    self.stop_event.wait(max(0., .1-(time.monotonic()-began)))
            except Exception as e:
                if 'selected' in locals() and selected:
                    failed_backend = selected['backend']
                with self.lock:
                    self.raw = self.result = None
                    self.epoch += 1
                self.status(str(e) if isinstance(e, RuntimeError) else '摄像头异常，请检查连接', 'error')
            finally:
                if cap is not None:
                    cap.release()
            self.stop_event.wait(3)

    def process_loop(self):
        detector, engine, previous_epoch, previous_seq = None, None, -1, -1
        next_tick = 0.
        while not self.stop_event.wait(.02):
            with self.lock:
                raw, epoch = self.raw, self.epoch
                cfg, monitoring = copy.deepcopy(self.cfg), self.monitoring
            if raw is None:
                continue
            seq, captured, frame, actual = raw
            now = time.monotonic()
            if now-captured > 1.5:
                with self.lock:
                    self.result = None
                self.status('摄像头画面已停滞，请停止后重新连接', 'error')
                engine = None
                continue
            if seq == previous_seq or now < next_tick:
                continue
            if epoch != previous_epoch or engine is None:
                engine = Engine(cfg)
                previous_epoch = epoch
            previous_seq = seq
            start = now
            if cfg.rotate:
                frame = cv2.rotate(frame, cv2.ROTATE_180)
            if cfg.mirror:
                frame = cv2.flip(frame, 1)
            try:
                events, active, detections = [], [], []
                if monitoring:
                    if detector is None:
                        self.status('正在加载本地检测模型…', 'busy')
                        detector = Detector()
                    detections = detector.detect(frame, cfg.confidence)
                    events, active = engine.update(detections, captured)
                elapsed = (time.monotonic()-start)*1000
                with self.lock:
                    if self.stop_event.is_set() or epoch != self.epoch:
                        continue
                    self.result = (seq, frame, detections, actual, elapsed, captured)
                if events:
                    self.bus.event.emit({'events': events, 'frame': frame.copy() if cfg.screenshots else None, 'cfg': cfg, 'session': self.session, 'epoch': epoch})
                self.status(f'检测到 {len(active)} 人' if active else ('监测中 · 暂无确认目标' if monitoring else '预览中 · 尚未开始监测'), 'alert' if active else ('on' if monitoring else 'preview'))
            except Exception as e:
                self.status(f'模型不可用：{e}', 'error')
                with self.lock:
                    self.result = None
                self.stop_event.wait(3)
            next_tick = time.monotonic() + max(0., 1/(cfg.fps if monitoring else 10) - (time.monotonic()-start))
