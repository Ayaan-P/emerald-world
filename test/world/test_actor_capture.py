import json,tempfile,time,unittest
from pathlib import Path
from world import actor_capture as capture,actor_runtime
from world.capture_attempt_worker import Ledger
from world.character_training import source
from world.character_companions import roster
from test_capture_attempt_worker import FakeNative
import test_companion_exchange

class CaptureServiceTests(unittest.TestCase):
 def setUp(self):
  f=test_companion_exchange.ExchangeTests();f.setUp();self.addCleanup(f.doCleanups);self.f=f;self.s=f.s
  f.f.plan();actor_runtime.tick(self.s,now=10);f.f.deploy();actor_runtime.tick(self.s,now=20)
  current=source(self.s,'harbor_guide','companion')
  full=dict(size=100,species=current['species'],level=18,personality=current['personality'],owner=current['owner'],exp=5832,blob='cd'*100)
  with self.s.db:self.s.db.execute('INSERT INTO character_training VALUES(?,?,?,?,?)',('harbor_guide','companion',FakeNative.digest,18,json.dumps(full)))
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'capture.db'
  ledger=Ledger(self.path);ledger.supply('harbor_guide',1,2);ledger.close()
 def start(self,engine):
  self.s.capture_service=capture.Service(self.path,engine,validated_native=True)
  self.addCleanup(self.s.capture_service.close)
  self.s.actor_tool_execution=('harbor_guide',{},dict(id='catch'),dict(id='throw'))
  with self.s.db:
   pending=capture.request(self.s,'harbor_guide',{},dict(individual='companion',ball=1))
   self.s.db.execute('INSERT INTO actor_tool_receipts VALUES(?,?,?,?,?,NULL)',('harbor_guide','catch','throw','pending',json.dumps(pending.data,sort_keys=True)))
  self.s.actor_tool_execution=None
  return pending
 def run_result(self,pending):
  for _ in range(100):
   self.s.capture_service.tick(self.s)
   result=capture.poll(self.s,'harbor_guide',{},pending.data)
   if result:return result
   time.sleep(.01)
  self.fail('worker did not finish')
 def test_real_request_worker_import_and_optional_lineup_identity(self):
  engine=FakeNative();pending=self.start(engine);result=self.run_result(pending)
  self.assertEqual(result['outcome'],'captured_companion_imported')
  mon=next(m for m in roster(self.s,'harbor_guide') if m['individual']==result['individual'])
  self.assertFalse(mon['on_team']);self.assertEqual(mon['personality'],123)
  self.s.capture_service.tick(self.s);self.assertEqual(engine.calls,1)
  ledger=Ledger(self.path);self.assertEqual(ledger.db.execute('SELECT quantity FROM capture_stock').fetchone()[0],1);ledger.close()
  self.assertIn('world.attempt_capture',actor_runtime.inspect_runtime(self.s)['capabilities'])
 def test_uncertain_attempt_is_terminal_and_never_mints_or_retries(self):
  engine=FakeNative(fail=True);pending=self.start(engine);result=self.run_result(pending)
  self.assertEqual(result['outcome'],'capture_not_imported')
  for _ in range(3):self.s.capture_service.tick(self.s)
  self.assertEqual(engine.calls,1)
 def test_disabled_and_interrupted_dispatch(self):
  with self.assertRaisesRegex(ValueError,'disabled'):capture.request(self.s,'harbor_guide',{},dict(individual='companion',ball=1))
  engine=FakeNative();pending=self.start(engine)
  with self.s.db:self.s.db.execute("UPDATE actor_capture_requests SET status='dispatching'")
  self.assertEqual(self.run_result(pending)['outcome'],'capture_not_imported');self.assertEqual(engine.calls,0)
 def test_failed_throw_remains_unresolved(self):
  pending=self.start(FakeNative(False))
  self.assertEqual(self.run_result(pending)['outcome'],'not_caught_unresolved')
 def test_completed_native_job_recovers_after_service_restart(self):
  from world import character_capture
  engine=FakeNative();pending=self.start(engine)
  ledger=Ledger(self.path)
  job=character_capture.queue(self.s,ledger,'harbor_guide','companion',engine.digest,1,'Trainer')
  with self.s.db:self.s.db.execute("UPDATE actor_capture_requests SET status='queued',job=?",(job,))
  ledger.execute(job,engine,validated_native=True);ledger.close()
  self.s.capture_service.close()
  self.s.capture_service=capture.Service(self.path,engine,validated_native=True)
  self.addCleanup(self.s.capture_service.close)
  self.assertEqual(self.run_result(pending)['outcome'],'captured_companion_imported')
  self.assertEqual(engine.calls,1)
