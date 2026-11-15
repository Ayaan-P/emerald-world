"""Isolated ledger/process boundary; never a full-engine gameplay claim."""
import hashlib,importlib.util,os,sqlite3,tempfile,unittest
from pathlib import Path
from world.companion_practice import Ledger,Engine,state
class FakeEngine:
 digest='a'*64
 def run(self,line):
  return dict(size=2,species=277,level=5 if line.startswith('INIT') else 6,personality=123,owner=456,exp=125 if line.startswith('INIT') else 225,blob='0000' if line.startswith('INIT') else '0100')
class PracticeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'npc.db';self.ledger=Ledger(self.path);self.engine=FakeEngine()
  self.ledger.initialize('may','partner',277,5,123,456,self.engine)
 def tearDown(self):self.ledger.close();self.tmp.cleanup()
 def test_restart_exactly_once_full_state_and_engine_pin(self):
  job=self.ledger.queue('may','partner',100,10)
  with self.assertRaises(sqlite3.IntegrityError):self.ledger.queue('may','partner',100,10)
  self.ledger.close();self.ledger=Ledger(self.path)
  wrong=FakeEngine();wrong.digest='b'*64
  with self.assertRaises(ValueError):self.ledger.execute(job,wrong)
  result=self.ledger.execute(job,self.engine);self.assertEqual(result['revision'],2);self.assertEqual(result['state']['blob'],'0100')
  with self.assertRaises(ValueError):self.ledger.execute(job,self.engine)
  self.ledger.close();self.ledger=Ledger(self.path);self.assertEqual(self.ledger.get('may','partner'),result)
 def test_stale_cancelled_mismatched_and_interrupted_results_do_not_apply(self):
  original=self.ledger.get('may','partner')
  job=self.ledger.queue('may','partner',100,10);self.ledger.cancel(job)
  with self.assertRaises(ValueError):self.ledger.execute(job,self.engine)
  job=self.ledger.queue('may','partner',100,10)
  with self.ledger.db:self.ledger.db.execute('UPDATE companions SET revision=2')
  with self.assertRaises(ValueError):self.ledger.execute(job,self.engine)
  self.assertEqual(self.ledger.get('may','partner')['state'],original['state'])
  job=self.ledger.queue('may','partner',100,10)
  engine=FakeEngine();old=engine.run;engine.run=lambda line:dict(old(line),personality=999)
  with self.assertRaises(ValueError):self.ledger.execute(job,engine)
  self.assertEqual(self.ledger.get('may','partner')['state'],original['state'])
  job=self.ledger.queue('may','partner',100,10)
  with self.ledger.db:self.ledger.db.execute("UPDATE jobs SET status='running' WHERE id=?",(job,))
  self.ledger.close();self.ledger=Ledger(self.path)
  with self.assertRaises(ValueError):self.ledger.execute(job,self.engine)
 def test_bounds(self):
  for value in ['STATE1 1 1 5 0 0 100 0','STATE1 1 1 5 0 0 100 zz','STATE1 1 1 101 0 0 100 00']:
   with self.assertRaises(ValueError):state(value)
  with self.assertRaises(ValueError):self.ledger.queue('may','partner',1025,100)
  with self.assertRaises(ValueError):self.ledger.initialize('may','x',1,5,-1,0,self.engine)
 @unittest.skipUnless(os.environ.get('EW_NATIVE_SOURCE'),'requires native source component fixture')
 def test_actual_compiled_protocol_and_pinned_subprocess(self):
  path=Path(os.environ['EW_NATIVE_SOURCE'])/'tests/character_worker_fixture.py'
  spec=importlib.util.spec_from_file_location('worker_fixture',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  binary=module.build(self.tmp.name);engine=Engine(binary,hashlib.sha256(binary.read_bytes()).hexdigest())
  before=self.ledger.initialize('actor_fixture','partner_fixture',277,5,123,456,engine)
  job=self.ledger.queue('actor_fixture','partner_fixture',1024,20);after=self.ledger.execute(job,engine)
  self.assertGreater(after['state']['level'],before['state']['level']);self.assertEqual(after['state']['exp'],before['state']['exp']+1024)
  self.assertEqual(after['state']['personality'],123);self.assertEqual(after['state']['owner'],456)
  self.ledger.close();self.ledger=Ledger(self.path);self.assertEqual(self.ledger.get('actor_fixture','partner_fixture'),after)
  with self.assertRaises(ValueError):Engine(binary,'0'*64).run('INIT1 277 5 1 2')
