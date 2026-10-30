"""Build-time assets only. The application never imports this downloader."""
from pathlib import Path
import hashlib
import json
import math
import struct
import urllib.request
import wave

ROOT=Path(__file__).resolve().parents[1]
URL='https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_nano.onnx'
model=ROOT/'models/yolox_nano.onnx'
model.parent.mkdir(exist_ok=True)
if not model.exists():
    urllib.request.urlretrieve(URL,model)
if model.stat().st_size < 1000000:
    raise RuntimeError('Invalid model download')
(ROOT/'models/manifest.json').write_text(json.dumps({'source':URL,'sha256':hashlib.sha256(model.read_bytes()).hexdigest(),'model':'YOLOX-Nano COCO 416x416 FP32','license':'Apache-2.0; see licenses/YOLOX.txt'},indent=2),encoding='utf-8')
(ROOT/'assets').mkdir(exist_ok=True)
with wave.open(str(ROOT/'assets/chime.wav'),'wb') as w:
    w.setparams((1,2,22050,0,'NONE','not compressed'))
    data=[]
    for i in range(int(.24*22050)):
        t=i/22050
        envelope=min(t/.015,1)*math.exp(-t*16)
        sample=.22*envelope*(math.sin(2*math.pi*660*t)+.3*math.sin(2*math.pi*990*t))
        data.append(struct.pack('<h',int(sample*32767)))
    w.writeframes(b''.join(data))
licenses={
    'YOLOX':'https://raw.githubusercontent.com/Megvii-BaseDetection/YOLOX/main/LICENSE',
    'ONNXRuntime':'https://raw.githubusercontent.com/microsoft/onnxruntime/v1.20.1/LICENSE',
    'CameraEnumerator':'https://raw.githubusercontent.com/lukehugh/cv2_enumerate_cameras/main/LICENSE',
    'LGPL-3.0':'https://www.gnu.org/licenses/lgpl-3.0.txt',
    'GPL-3.0':'https://raw.githubusercontent.com/qt/qtbase/v6.8.3/LICENSES/GPL-3.0-only.txt',
}
(ROOT/'licenses').mkdir(exist_ok=True)
for name,url in licenses.items():
    p=ROOT/'licenses'/f'{name}.txt'
    if not p.exists():
        urllib.request.urlretrieve(url,p)
print('Model and assets prepared:',model.stat().st_size,'bytes')
