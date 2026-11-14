"""Actual authority/plan/session-worker wiring, explicitly fake engine storage."""
from copy import deepcopy
import json,tempfile,unittest
from pathlib import Path
import test_characters as fixture
from world import actor_runtime as runtime
from world.character_training import source
from world.companion_practice import Ledger
from world.cast_practice_worker import step

class MovesIntegration(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CharacterLifecycleTests();self.f.setUp();self.addCleanup(self.f.tearDown);self.s=self.f.server
  self.c=deepcopy(self.f.character);self.c['team']=[dict(species=277,level=5,individual='partner')]
  self.assertIsNone(self.f.commit({'may':self.c},self.f.npc))
  identity=source(self.s,'may','partner')
  self.before=dict(size=100,species=277,level=5,personality=identity['personality'],owner=identity['owner'],exp=125,blob='00'*100)
  with self.s.db:self.s.db.execute('INSERT INTO character_training VALUES(?,?,?,?,?)',('may','partner','a'*64,5,json.dumps(self.before,sort_keys=True)))
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.ledger=Ledger(Path(self.tmp.name)/'jobs');self.addCleanup(self.ledger.close)
  before=self.before
  class Fake:
   digest='a'*64
   def exchange(self,line):return 'MOVES1 1 7 2 0 0 1' if line.endswith('01'*100) else 'MOVES1 1 1 2 0 0 7'
   def run(self,line):return dict(before,blob='01'*100)
  self.engine=Fake()
 def request(self,body):
  conn=dict(out=bytearray());self.s._admin_line(conn,json.dumps(body).encode());return json.loads(conn['out'])
 def plan(self,args,version):
  self.c.update(version=version,plan=dict(id='moves'+str(version),purpose='Consider actual available moves.',steps=[dict(id='learn',tool='world.learn_move' if 'move' in args else 'world.inspect_moves',args=args,after=[])]))
  self.assertIsNone(self.f.commit({'may':self.c},self.f.npc))
 def run_worker(self,**kw):return step(self.ledger,self.engine,self.request,validated_native=True,**kw)
 def test_inspect_choose_reconcile_battle_and_restart(self):
  self.plan(dict(individual='partner'),2);self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending')
  with self.assertRaises(ValueError):step(self.ledger,self.engine,self.request)
  result=self.run_worker();self.assertEqual(result['result']['result']['moves'],[7]);self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded')
  self.plan(dict(individual='partner',move=7,slot=0),3);self.assertEqual(runtime.tick(self.s,now=22)['status'],'pending')
  self.assertEqual(self.run_worker()['status'],'native_moves_completed');self.assertEqual(runtime.tick(self.s,now=28)['status'],'succeeded')
  saved=source(self.s,'may','partner')['trained']['state'];self.assertEqual(saved['blob'],'01'*100);self.assertEqual(saved['exp'],125)
  peer=self.f.peer(role='SOCIALCHAR1CHARPK1CHARPK2');self.assertEqual(self.f.send(peer,'CHARACTER_CHALLENGE 1 may 3').split()[-1],saved['blob'])
  self.s.close();self.f.server=self.f.open();self.s=self.f.server
  self.assertEqual(source(self.s,'may','partner')['trained']['state'],saved)
  self.assertEqual(self.run_worker()['status'],'idle')
 def test_durable_application_retry_does_not_repeat_engine(self):
  self.plan(dict(individual='partner',move=7,slot=0),2);runtime.tick(self.s,now=10)
  def failed(body):return dict(ok=False) if body['command']=='character_moves_finish' else self.request(body)
  self.assertEqual(step(self.ledger,self.engine,failed,validated_native=True)['status'],'blocked')
  self.engine.run=lambda line:(_ for _ in ()).throw(AssertionError('must not reexecute'))
  self.assertEqual(self.run_worker()['status'],'move_reconciled')
  self.assertEqual(source(self.s,'may','partner')['trained']['state']['blob'],'01'*100)
 def test_withdrawal_during_native_work_never_changes_world(self):
  self.plan(dict(individual='partner',move=7,slot=0),2);runtime.tick(self.s,now=10);old=self.engine.run
  def withdraw(line):
   self.c['version']=3;self.c.pop('plan');self.assertIsNone(self.f.commit({'may':self.c},self.f.npc));return old(line)
  self.engine.run=withdraw
  self.assertEqual(self.run_worker()['status'],'blocked');self.assertEqual(source(self.s,'may','partner')['trained']['state'],self.before)

 def test_unavailable_move_yields_actual_failure_not_infinite_pending(self):
  self.plan(dict(individual='partner',move=99,slot=0),2);runtime.tick(self.s,now=10)
  self.assertEqual(self.run_worker()['status'],'blocked')
  result=self.s.db.execute('SELECT result FROM actor_move_requests').fetchone()[0]
  self.assertEqual(json.loads(result)['outcome'],'native_move_failed')
  self.assertEqual(source(self.s,'may','partner')['trained']['state'],self.before)
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded')
