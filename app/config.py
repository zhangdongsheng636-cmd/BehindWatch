from dataclasses import dataclass, asdict, field, fields
from pathlib import Path
import json
import os
import sys
from .paths import data_dir

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
DATA = data_dir()  # Initial-path compatibility for diagnostic scripts.

@dataclass
class Config:
    camera_path: str = ''
    camera_name: str = ''
    backend: int = 700
    width: int = 640
    height: int = 480
    rotate: bool = False
    mirror: bool = False
    roi: list = field(default_factory=lambda: [0., 0., 1., 1.])
    exclusions: list = field(default_factory=list)
    fps: int = 5
    confidence: float = .45
    min_height: float = .15
    dwell: float = .6
    lost: float = .8
    repeat: int = 30
    popup: bool = True
    taskbar: bool = False
    notification: bool = False
    sound: bool = False
    border: bool = False
    volume: int = 25
    dnd: bool = False
    screenshots: bool = False
    retention: int = 7
    max_mb: int = 100
    corner: str = '右下'
    screen: str = ''

    def save(self):
        DATA = data_dir()
        DATA.mkdir(parents=True, exist_ok=True)
        tmp = DATA / 'settings.tmp'
        tmp.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(DATA / 'settings.json')

    @classmethod
    def load(cls):
        try:
            DATA = data_dir()
            obj = json.loads((DATA / 'settings.json').read_text(encoding='utf-8'))
            c = cls(**{k: v for k, v in obj.items() if k in {f.name for f in fields(cls)}})
            for key, lo, hi in [('fps', 2, 10), ('confidence', .1, .95), ('min_height', 0., .8), ('dwell', .2, 3.), ('lost', .2, 2.), ('repeat', 0, 300), ('volume', 0, 100), ('retention', 1, 90), ('max_mb', 10, 2000)]:
                setattr(c, key, max(lo, min(hi, getattr(c, key))))
            if len(c.roi) != 4 or not (0 <= c.roi[0] < c.roi[2] <= 1 and 0 <= c.roi[1] < c.roi[3] <= 1):
                c.roi = [0., 0., 1., 1.]
            c.exclusions = [r for r in c.exclusions if len(r) == 4 and 0 <= r[0] < r[2] <= 1 and 0 <= r[1] < r[3] <= 1]
            return c
        except (OSError, ValueError, TypeError, AttributeError):
            return cls()
