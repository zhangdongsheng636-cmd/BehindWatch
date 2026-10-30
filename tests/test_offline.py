import unittest
from unittest.mock import patch
import numpy as np

class OfflineTests(unittest.TestCase):
    def test_model_load_and_inference_without_python_network(self):
        def blocked(*args,**kwargs):
            raise AssertionError('Unexpected Python network access')
        with patch('socket.socket.connect',blocked),patch('socket.getaddrinfo',blocked):
            from app.detector import Detector
            self.assertEqual(Detector().detect(np.zeros((480,640,3),np.uint8)),[])

if __name__=='__main__':
    unittest.main()
