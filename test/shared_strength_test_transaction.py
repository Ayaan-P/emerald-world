import importlib.util,pathlib,sys,unittest
p=pathlib.Path(__file__).resolve().parents[1]/'world/strength_transaction.py'
s=importlib.util.spec_from_file_location('strength_transaction',p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
class Transaction(unittest.TestCase):
 def room(self):return m.StrengthRoom(('a','b'),8,{'a':1,'b':2},m.INITIAL)
 def propose(self,r):return r.propose('a',8,1,0,2,(10,15),(11,15),0)
 def test_complete(self):
  r=self.room();self.propose(r)
  self.assertIsNone(r.ready('a',8,1,1,m.INITIAL,1))
  self.assertEqual(r.ready('b',8,2,1,m.INITIAL,1)['phase'],'commit')
  updated=r.pending['updated'];self.assertIsNone(r.applied('a',8,1,1,updated,2))
  self.assertEqual(r.revision,0);self.assertFalse(r.history)
  self.assertEqual(r.applied('b',8,2,1,updated,2)['phase'],'completed');self.assertEqual(r.revision,1)
 def test_stale_and_competing(self):
  r=self.room();self.propose(r)
  for call in [lambda:r.ready('a',8,2,1,m.INITIAL,1),lambda:r.ready('x',8,1,1,m.INITIAL,1),lambda:r.ready('b',8,2,2,m.INITIAL,1),lambda:self.propose(r),lambda:r.applied('a',8,1,1,m.INITIAL,1)]:
   with self.assertRaises(ValueError):call()
 def test_no_false_completion_on_disconnect(self):
  r=self.room();self.propose(r);r.ready('a',8,1,1,m.INITIAL,1);r.ready('b',8,2,1,m.INITIAL,1)
  r.applied('a',8,1,1,r.pending['updated'],2)
  self.assertTrue(r.close('disconnect')['partial']);self.assertEqual(r.positions,m.INITIAL);self.assertFalse(r.history)
  with self.assertRaises(ValueError):r.ready('b',8,2,1,m.INITIAL,3)
 def test_timeout_and_mismatched_layout(self):
  r=self.room();self.propose(r)
  changed=list(m.INITIAL);changed[0]=(2,9,15)
  with self.assertRaises(ValueError):r.ready('b',8,2,1,changed,1)
  self.assertEqual(r.tick(11)['reason'],'timeout');self.assertFalse(r.history)
if __name__=='__main__':unittest.main()
