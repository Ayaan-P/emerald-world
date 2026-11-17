import json,tempfile,unittest
from pathlib import Path
from world.capture_attempt_worker import Ledger,response
import test_cave_links

class FakeNative:
 digest='c'*64
 def __init__(self,caught=True,fail=False):self.caught=caught;self.fail=fail;self.calls=0
 def run(self,line):
  self.calls+=1
  if self.fail:raise TimeoutError('uncertain process outcome')
  t=line.split();assert t[0]=='ENCOUNTER1' and t[-2]=='FIRST_THROW_ONLY'
  return f"ATTEMPT1 {int(self.caught)} {int(t[5])-1} 100 278 18 123 {t[3]} 5832 "+'ab'*100+'\n'

class CaptureJobsTests(unittest.TestCase):
 def setUp(self):
  f=test_cave_links.HabitatLinkTests();f.setUp();self.addCleanup(f.doCleanups)
  self.blob=f.s.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(f.habitat,)).fetchone()[0]
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'attempts.db';self.ledger=Ledger(self.path);self.addCleanup(lambda:self.ledger.close())
  self.source=dict(size=100,species=278,level=18,personality=12,owner=99,exp=5832,blob='cd'*100)
  self.ledger.supply('researcher',1,3)
 def queue(self):return self.ledger.queue('researcher',self.source,self.blob,99,'Wally',1,FakeNative.digest)
 def test_default_disabled_real_receipt_path_and_restart_no_replay(self):
  job=self.queue();engine=FakeNative()
  with self.assertRaisesRegex(ValueError,'QA'):self.ledger.execute(job,engine)
  self.assertEqual(engine.calls,0)
  result=self.ledger.execute(job,engine,validated_native=True)
  self.assertTrue(result['caught']);self.assertFalse(result['world_imported']);self.assertEqual(result['balls_used'],1)
  self.ledger.close();self.ledger=Ledger(self.path)
  with self.assertRaises(ValueError):self.ledger.execute(job,engine,validated_native=True)
  self.assertEqual(engine.calls,1);self.assertEqual(self.ledger.db.execute('SELECT quantity FROM capture_stock').fetchone()[0],2)
  self.assertEqual(self.ledger.db.execute('SELECT count(*) FROM capture_results').fetchone()[0],1)
 def test_failed_throw_is_unresolved_not_capture_or_escape(self):
  result=self.ledger.execute(self.queue(),FakeNative(False),validated_native=True)
  self.assertEqual(result['outcome'],'not_caught_unresolved')
  self.assertEqual(self.ledger.db.execute('SELECT count(*) FROM capture_results').fetchone()[0],0)
 def test_uncertain_execution_keeps_ball_spent_and_never_retries(self):
  job=self.queue();engine=FakeNative(fail=True)
  with self.assertRaises(TimeoutError):self.ledger.execute(job,engine,validated_native=True)
  with self.assertRaises(ValueError):self.ledger.execute(job,engine,validated_native=True)
  self.assertEqual(engine.calls,1);self.assertEqual(self.ledger.db.execute('SELECT quantity FROM capture_stock').fetchone()[0],2)
 def test_no_minted_balls_parallel_jobs_or_unknown_species_results(self):
  job=self.queue()
  with self.assertRaisesRegex(ValueError,'unresolved'):self.queue()
  engine=FakeNative();original=engine.run;engine.run=lambda line:original(line).replace('100 278 18','100 999 18')
  with self.assertRaisesRegex(ValueError,'inconsistent'):self.ledger.execute(job,engine,validated_native=True)
  self.assertEqual(self.ledger.db.execute('SELECT count(*) FROM capture_results').fetchone()[0],0)

class CaptureImportTests(unittest.TestCase):
 def test_actual_ownership_import_bench_restart_and_replay(self):
  import test_companion_exchange
  from world import character_capture as capture
  from world.character_training import source,saved
  from world.character_companions import roster
  f=test_companion_exchange.ExchangeTests();f.setUp();self.addCleanup(f.doCleanups);s=f.s
  # Move through the existing authority link, rather than pretending a visit.
  f.f.plan();from world import actor_runtime
  self.assertEqual(actor_runtime.tick(s,now=10)['status'],'pending');f.f.deploy()
  self.assertEqual(actor_runtime.tick(s,now=20)['status'],'succeeded')
  current=source(s,'harbor_guide','companion')
  full=dict(size=100,species=current['species'],level=18,personality=current['personality'],owner=current['owner'],exp=5832,blob='cd'*100)
  with s.db:s.db.execute('INSERT INTO character_training VALUES(?,?,?,?,?)',('harbor_guide','companion',FakeNative.digest,18,json.dumps(full)))
  with tempfile.TemporaryDirectory() as td:
   ledger=Ledger(Path(td)/'capture.db');self.addCleanup(ledger.close);ledger.supply('harbor_guide',1,2)
   job=capture.queue(s,ledger,'harbor_guide','companion',FakeNative.digest,1,'Guide')
   ledger.execute(job,FakeNative(),validated_native=True)
   imported=capture.reconcile(s,ledger,job);key=imported['individual']
   mon=next(m for m in roster(s,'harbor_guide') if m['individual']==key)
   self.assertFalse(mon['on_team']);self.assertEqual(mon['personality'],123)
   self.assertEqual(saved(s.db,'harbor_guide',key)['state']['blob'],'ab'*100)
   self.assertEqual(capture.reconcile(s,ledger,job),imported)
   s.close();f.fx.f.server=f.fx.f.open();s=f.fx.f.server;f.s=s;f.fx.server=s
   self.assertEqual(capture.reconcile(s,ledger,job),imported)
   self.assertIn(key,[m['individual'] for m in roster(s,'harbor_guide')])
