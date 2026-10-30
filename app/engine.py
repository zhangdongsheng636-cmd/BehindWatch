"""Pure, clock-injected short-term tracking and alert decisions. No identity data."""
from dataclasses import dataclass
import math

def area(b):
    return max(0., b[2]-b[0]) * max(0., b[3]-b[1])

def overlap(a, b):
    return area((max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])))

def iou(a, b):
    x = overlap(a, b)
    return x / max(1e-9, area(a)+area(b)-x)

def center(b):
    return ((b[0]+b[2])/2, (b[1]+b[3])/2)

def contains(r, p):
    return r[0] <= p[0] <= r[2] and r[1] <= p[1] <= r[3]

def eligible(box, cfg):
    p = center(box)
    return (box[3]-box[1] >= cfg.min_height and contains(cfg.roi, p)
            and overlap(box, cfg.roi) / max(area(box), 1e-9) >= .35
            and not any(contains(r, p) for r in cfg.exclusions))

@dataclass
class Track:
    id: int
    box: tuple
    first: float
    seen: float
    evidence: float = 0.
    samples: int = 1
    alerted: float | None = None
    score: float = 0.

class Engine:
    def __init__(self, cfg):
        self.cfg = cfg
        self.tracks = {}
        self.next_id = 1
        self.last_sample = None

    def update(self, detections, now):
        # Missing samples never count as continuous presence.
        gap_limit = max(.6, 1.8 / self.cfg.fps)
        if self.last_sample is not None and now-self.last_sample > gap_limit:
            for t in self.tracks.values():
                if t.alerted is None:
                    t.evidence = 0.
                    t.samples = 0
        self.last_sample = now
        self.tracks = {i: t for i, t in self.tracks.items() if now-t.seen <= self.cfg.lost}
        valid = [(tuple(b), score) for b, score in detections if score >= self.cfg.confidence and eligible(b, self.cfg)]
        pairs = []
        for j, (b, _) in enumerate(valid):
            for i, t in self.tracks.items():
                ov = iou(b, t.box)
                d = math.dist(center(b), center(t.box))
                scale = max(.03, math.hypot(t.box[2]-t.box[0], t.box[3]-t.box[1]))
                if ov >= .12 or d < min(.12, scale*.35):
                    pairs.append((ov-d, i, j))
        matched, used = {}, set()
        for _, i, j in sorted(pairs, reverse=True):
            if i not in used and j not in matched:
                matched[j] = i
                used.add(i)
        events, active = [], []
        for j, (b, score) in enumerate(valid):
            if j in matched:
                t = self.tracks[matched[j]]
                dt = now-t.seen
                if dt <= gap_limit:
                    t.evidence += min(dt, 1.5/self.cfg.fps)
                elif t.alerted is None:
                    t.evidence = 0.
                t.samples += 1
                t.seen, t.box, t.score = now, b, score
            else:
                t = Track(self.next_id, b, now, now, score=score)
                self.tracks[t.id] = t
                self.next_id += 1
            confirmed = t.evidence + 1e-8 >= self.cfg.dwell and t.samples >= 2
            if confirmed:
                active.append(t.id)
                if t.alerted is None or (self.cfg.repeat > 0 and now-t.alerted >= self.cfg.repeat):
                    events.append({'track': t.id, 'box': b, 'score': score, 'duration': now-t.first, 'kind': '首次' if t.alerted is None else '重复'})
                    t.alerted = now
        return events, active
