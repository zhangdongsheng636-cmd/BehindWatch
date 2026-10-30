import unittest
from app.config import Config
from app.engine import Engine, eligible

A=((.2,.2,.4,.8),.9)
B=((.65,.2,.85,.8),.9)

class EngineTests(unittest.TestCase):
    def make(self,**kwargs):
        return Engine(Config(**kwargs))
    def test_confirmation_and_repeat(self):
        e=self.make(dwell=.6,repeat=5)
        for t in [0,.2,.4]:
            self.assertEqual(e.update([A],t)[0],[])
        self.assertEqual(len(e.update([A],.6)[0]),1)
        for n in range(4,28):
            self.assertEqual(e.update([A],n*.2)[0],[])
        self.assertEqual(len(e.update([A],5.6)[0]),1)
    def test_fast_flash_no_alert(self):
        e=self.make()
        for t,ds in [(0,[A]),(.2,[A]),(.4,[]),(.6,[])]:
            self.assertFalse(e.update(ds,t)[0])
    def test_people_cannot_share_timer(self):
        e=self.make()
        for t,ds in [(0,[A]),(.2,[A]),(.4,[B]),(.6,[B])]:
            self.assertFalse(e.update(ds,t)[0])
    def test_newcomer_during_cooldown(self):
        e=self.make(dwell=.4)
        for t in [0,.2,.4]:
            e.update([A],t)
        self.assertFalse(e.update([A,B],.6)[0])
        self.assertFalse(e.update([A,B],.8)[0])
        event=e.update([A,B],1.)[0]
        self.assertEqual(len(event),1)
        self.assertEqual(event[0]['track'],2)
    def test_gap_not_presence(self):
        e=self.make()
        e.update([A],0)
        e.update([A],.2)
        self.assertFalse(e.update([A],3)[0])
    def test_lost_track_not_repeated(self):
        e=self.make(dwell=.2,repeat=1,lost=2.)
        e.update([A],0)
        self.assertTrue(e.update([A],.2)[0])
        self.assertFalse(e.update([],1.5)[0])
    def test_once_and_short_occlusion(self):
        e=self.make(dwell=.2,repeat=0)
        e.update([A],0)
        e.update([A],.2)
        e.update([],.4)
        self.assertFalse(e.update([A],.6)[0])
        for n in range(4,40):
            self.assertFalse(e.update([A],n*.2)[0])
    def test_roi_size_exclusion(self):
        c=Config(roi=[.1,.1,.5,.9])
        self.assertTrue(eligible(A[0],c))
        self.assertFalse(eligible(B[0],c))
        self.assertFalse(eligible((.2,.2,.23,.25),c))
        c.exclusions=[.1,.1,.5,.9],
        self.assertFalse(eligible(A[0],c))
    def test_multiple_tracks_unique(self):
        e=self.make(dwell=.2)
        e.update([A,B],0)
        events,_=e.update([B,A],.2)
        self.assertEqual({x['track'] for x in events},{1,2})

if __name__=='__main__':
    unittest.main()
