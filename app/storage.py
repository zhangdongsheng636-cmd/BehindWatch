import json
import queue
import sqlite3
import threading
import time
import uuid
import cv2
from contextlib import closing
from .paths import data_dir

class Store:
    def __init__(self):
        self.directory = data_dir()
        DATA = self.directory
        DATA.mkdir(parents=True, exist_ok=True)
        self.db = DATA / 'events.sqlite3'
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute('CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, ts REAL, kind TEXT, details TEXT, image TEXT)')
        self.queue = queue.Queue(maxsize=64)
        self.error = ''
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def submit(self, kind, details, frame=None, cfg=None):
        try:
            self.queue.put_nowait((kind, details, frame, cfg))
        except queue.Full:
            self.error = '日志队列已满，部分事件未能保存'

    def run(self):
        last_clean = 0
        while True:
            item = self.queue.get()
            try:
                if item is None:
                    return
                kind, details, frame, cfg = item
                ts, event_id, image = time.time(), uuid.uuid4().hex, ''
                if frame is not None and cfg and cfg.screenshots:
                    try:
                        folder = self.directory / 'snapshots'
                        folder.mkdir(exist_ok=True)
                        h, w = frame.shape[:2]
                        x1, y1, x2, y2 = cfg.roi
                        crop = frame[int(y1*h):max(int(y1*h)+1, int(y2*h)), int(x1*w):max(int(x1*w)+1, int(x2*w))]
                        ok, data = cv2.imencode('.jpg', crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        if not ok:
                            raise OSError('encode')
                        path = folder / (event_id + '.jpg')
                        path.write_bytes(data.tobytes())
                        image = str(path)
                    except Exception:
                        self.error = '截图保存失败；监测仍在继续'
                with closing(sqlite3.connect(self.db)) as c, c:
                    c.execute('INSERT INTO events VALUES(?,?,?,?,?)', (event_id, ts, kind, json.dumps(details, ensure_ascii=False), image))
                    if cfg and ts-last_clean > 60:
                        c.execute('DELETE FROM events WHERE ts < ?', (ts-cfg.retention*86400,))
                        c.execute('DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY ts DESC LIMIT 10000)')
                        last_clean = ts
                if cfg:
                    self.cleanup(cfg)
            except Exception as e:
                self.error = f'日志保存失败（{type(e).__name__}）；请检查本地空间'
            finally:
                self.queue.task_done()

    def cleanup(self, cfg):
        files = sorted((self.directory/'snapshots').glob('*.jpg'), key=lambda p: p.stat().st_mtime)
        total = sum(p.stat().st_size for p in files)
        for p in files:
            st = p.stat()
            if st.st_mtime < time.time()-cfg.retention*86400 or total > cfg.max_mb*1024**2:
                total -= st.st_size
                p.unlink(missing_ok=True)

    def rows(self):
        with closing(sqlite3.connect(self.db, timeout=.3)) as c:
            return c.execute('SELECT ts,kind,details,image FROM events ORDER BY ts DESC LIMIT 300').fetchall()

    def close(self):
        if not self.thread.is_alive():
            return True
        self.queue.put(None, timeout=2)
        self.thread.join(3)
        return not self.thread.is_alive()
