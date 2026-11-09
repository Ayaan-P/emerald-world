"""Host lifecycle with fake native responses, not linked engine verification."""
import tempfile,unittest
from pathlib import Path
from world.companion_practice import Ledger
from world.companion_moves import MoveJobs,choices

class Fake:
 digest='a'*64
 def run(self,line):
  return dict(size=2,species=277,level=5,personality=123,owner=456,exp=125,blob='0100' if line.startswith('LEARN1') else '0000')
 def exchange(self,line):return 'MOVES1 1 7 2 0 0 1' if line.endswith('0100') else 'MOVES1 1 1 2 0 0 7'

class MoveTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'ledger';self.ledger=Ledger(self.path);self.engine=Fake()
  self.ledger.initialize('a','one',277,5,123,456,self.engine);self.jobs=MoveJobs(self.ledger)
 def tearDown(self):self.ledger.close();self.tmp.cleanup()
 def test_legal_choice_full_state_restart_and_no_replay(self):
  self.assertEqual(self.jobs.inspect('a','one',self.engine)['moves'],[7])
  job=self.jobs.queue('a','one',1,7,0)
  self.ledger.close();self.ledger=Ledger(self.path);self.jobs=MoveJobs(self.ledger)
  after=self.jobs.execute(job,self.engine);self.assertEqual(after['state']['blob'],'0100');self.assertEqual(after['revision'],2)
  with self.assertRaises(ValueError):self.jobs.execute(job,self.engine)
  self.ledger.close();self.ledger=Ledger(self.path);self.assertEqual(self.ledger.get('a','one'),after)
 def test_no_eligibility_or_growth_fabrication(self):
  original=self.ledger.get('a','one');job=self.jobs.queue('a','one',1,8,0)
  with self.assertRaises(ValueError):self.jobs.execute(job,self.engine)
  self.assertEqual(self.ledger.get('a','one'),original)
  job=self.jobs.queue('a','one',1,7,0);old=self.engine.run;self.engine.run=lambda line:dict(old(line),exp=200)
  with self.assertRaises(ValueError):self.jobs.execute(job,self.engine)
  self.assertEqual(self.ledger.get('a','one'),original)
 def test_queued_work_exclusion_and_stale_choice(self):
  job=self.jobs.queue('a','one',1,7,0)
  with self.assertRaises(ValueError):self.ledger.queue('a','one',2,10)
  with self.ledger.db:self.ledger.db.execute("UPDATE companion_move_jobs SET status='failed'")
  self.ledger.queue('a','one',2,10)
  with self.assertRaises(ValueError):self.jobs.queue('a','one',1,7,0)
  with self.assertRaises(ValueError):self.jobs.queue('a','one',0,7,0)
 def test_interrupted_claim_is_not_replayed(self):
  job=self.jobs.queue('a','one',1,7,0)
  with self.ledger.db:self.ledger.db.execute("UPDATE companion_move_jobs SET status='running'")
  self.ledger.close();self.ledger=Ledger(self.path);self.jobs=MoveJobs(self.ledger)
  with self.assertRaises(ValueError):self.jobs.execute(job,self.engine)
 def test_protocol_bounds(self):
  for line in ('MOVES1 2 1 2 0 0 7','MOVES1 1 1 2 0 0 1','MOVES1 1 1 2 0 0 0','MOVES1 2 1 2 0 0 7 7'):
   with self.assertRaises(ValueError):choices(line)
