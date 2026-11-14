import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from world.contest_completion import ContestCompletion
class Completion(unittest.TestCase):
 def setUp(self):self.c=ContestCompletion(42,{'a':'ac','b':'bc'},2,30)
 def report(self,w,standings=(0,1,2,3)):
  return self.c.report(owner=w,connection=w+'c',session=42,category=2,standings=standings,contestants_digest='a'*80,now=10)
 def test_both_native_results_before_save(self):
  self.assertEqual(self.report('a')['state'],'waiting')
  with self.assertRaises(ValueError):self.c.save_ack(owner='a',connection='ac',session=42,success=True)
  self.assertEqual(self.report('b')['state'],'agreed')
  self.assertEqual(self.c.save_ack(owner='a',connection='ac',session=42,success=True)['saved'],('a',))
  self.assertEqual(self.c.save_ack(owner='b',connection='bc',session=42,success=False)['state'],'local_save_failed')
  self.assertEqual(self.c.disconnect('b','bc')['saved'],('a',))
 def test_disagreement_cannot_award(self):
  self.report('a');self.assertEqual(self.report('b',(1,0,2,3))['state'],'aborted')
 def test_disconnect_before_results_aborts(self):
  self.report('a');self.c.disconnect('b','bc')
  with self.assertRaises(ValueError):self.report('b')
 def test_replay_is_idempotent(self):
  self.report('a');self.report('b')
  for _ in range(2):self.c.save_ack(owner='a',connection='ac',session=42,success=True)
  self.assertEqual(self.c.saved,{'a'})
if __name__=='__main__':unittest.main()
