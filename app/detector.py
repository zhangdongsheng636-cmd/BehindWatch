from pathlib import Path
import hashlib
import json
import cv2
import numpy as np
import onnxruntime as ort
from .config import ROOT

class Detector:
    def __init__(self):
        ort.disable_telemetry_events()
        model = ROOT / 'models/yolox_nano.onnx'
        manifest = json.loads((ROOT / 'models/manifest.json').read_text(encoding='utf-8'))
        if hashlib.sha256(model.read_bytes()).hexdigest() != manifest['sha256']:
            raise ValueError('模型校验失败，请重新解压完整软件包')
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        opts.add_session_config_entry('session.intra_op.allow_spinning', '0')
        opts.add_session_config_entry('session.inter_op.allow_spinning', '0')
        opts.log_severity_level = 3
        self.session = ort.InferenceSession(str(model), opts, providers=['CPUExecutionProvider'])
        self.name = self.session.get_inputs()[0].name
        self.h, self.w = self.session.get_inputs()[0].shape[2:]
        grids, strides = [], []
        for s in (8, 16, 32):
            y, x = np.meshgrid(np.arange(self.h//s), np.arange(self.w//s), indexing='ij')
            grids.append(np.stack((x, y), axis=-1).reshape(-1, 2))
            strides.append(np.full((x.size, 1), s))
        self.grid = np.concatenate(grids)
        self.strides = np.concatenate(strides)

    def detect(self, frame, threshold=.45):
        fh, fw = frame.shape[:2]
        ratio = min(self.h/fh, self.w/fw)
        resized = cv2.resize(frame, (int(fw*ratio), int(fh*ratio)))
        padded = np.full((self.h, self.w, 3), 114, dtype=np.uint8)
        padded[:resized.shape[0], :resized.shape[1]] = resized
        tensor = np.ascontiguousarray(padded.transpose(2, 0, 1), dtype=np.float32)[None]
        pred = self.session.run(None, {self.name: tensor})[0][0]
        scores = pred[:, 4] * pred[:, 5]  # COCO person, class 0
        mask = scores >= threshold
        p, scores = pred[mask], scores[mask]
        if not len(p):
            return []
        xy = (p[:, :2] + self.grid[mask]) * self.strides[mask]
        wh = np.exp(np.clip(p[:, 2:4], -20, 20)) * self.strides[mask]
        boxes = np.concatenate((xy-wh/2, xy+wh/2), axis=1) / ratio
        boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]], 0, fw)
        boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]], 0, fh)
        xywh = boxes.copy()
        xywh[:, 2:] -= xywh[:, :2]
        indices = cv2.dnn.NMSBoxes(xywh.tolist(), scores.tolist(), threshold, .45)
        return [(tuple((boxes[int(i)] / [fw, fh, fw, fh]).tolist()), float(scores[int(i)])) for i in np.asarray(indices).flatten()]
