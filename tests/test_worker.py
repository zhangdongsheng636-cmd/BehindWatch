import threading
import time
import unittest
import numpy as np
from app.config import Config
from app.worker import Worker

class Sink:
    def emit(self,*args):
        pass
class FakeBus:
    status=Sink()
    event=Sink()

class WorkerTests(unittest.TestCase):
    def test_rotation_mirror_preview_and_stop(self):
        cfg=Config(rotate=True,mirror=True)
        w=Worker(cfg,FakeBus(),monitoring=False)
        frame=np.arange(4*6*3,dtype=np.uint8).reshape(4,6,3)
        w.raw=(1,time.monotonic(),frame,(6,4))
        w.processing.start()
        for _ in range(50):
            if w.result:
                break
            time.sleep(.01)
        w.stop()
        w.processing.join(1)
        self.assertFalse(w.processing.is_alive())
        self.assertIsNotNone(w.result)
        np.testing.assert_array_equal(w.result[1],frame[::-1,:,:])
    def test_stale_frame_cannot_trigger(self):
        w=Worker(Config(),FakeBus())
        w.raw=(1,time.monotonic()-10,np.zeros((20,20,3),np.uint8),(20,20))
        w.processing.start()
        time.sleep(.1)
        w.stop()
        w.processing.join(1)
        self.assertIsNone(w.result)

if __name__=='__main__':
    unittest.main()
