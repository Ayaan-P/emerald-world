from copy import deepcopy
import os,unittest
from world import actor_runtime as runtime
from world.cast_practice_worker import step
import test_character_training as training

@unittest.skipUnless(os.environ.get('EW_NATIVE_SOURCE'),'requires native component fixture')
class PracticeCapabilityTests(unittest.TestCase):
 def setUp(self):
  self.f=training.TrainingIntegrationTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  c=deepcopy(self.f.c);c['version']=2;c['intentions']=[]
  c['plan']=dict(id='own_practice',purpose='Practice with my own companion.',steps=[dict(id='practice',tool='world.practice',args=dict(individual='partner'),after=[])])
  self.c=c;self.assertIsNone(self.f.f.commit({'may':c},self.f.f.npc))
 def test_actual_request_restart_runner_reconciliation_and_optional_battle(self):
  self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending')
  self.assertIsNone(runtime.tick(self.s,now=16))
  with self.assertRaises(ValueError):step(self.f.ledger,self.f.engine,self.f.request)
  self.s.close();self.f.f.server=self.f.f.open();self.s=self.f.f.server;self.f.s=self.s
  result=step(self.f.ledger,self.f.engine,self.f.request,validated_native=True,steps=256,cap=20)
  self.assertEqual(result['status'],'reconciled_to_world_companion')
  self.assertEqual(runtime.tick(self.s,now=22)['status'],'succeeded')
  self.assertEqual(step(self.f.ledger,self.f.engine,self.f.request,validated_native=True)['status'],'idle')
  full=self.f.ledger.get('may','partner')['state'];peer=self.f.f.peer(role='SOCIALCHAR1CHARPK1CHARPK2')
  self.assertEqual(self.f.f.send(peer,'CHARACTER_CHALLENGE 1 may 2').split()[-1],full['blob'])
 def test_withdrawn_plan_cannot_dispatch(self):
  runtime.tick(self.s,now=10)
  c=deepcopy(self.c);c['version']=3;c.pop('plan');self.assertIsNone(self.f.f.commit({'may':c},self.f.f.npc))
  self.assertEqual(step(self.f.ledger,self.f.engine,self.f.request,validated_native=True)['status'],'idle')
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked')
 def test_unknown_individual_blocked(self):
  self.s.module_state['world_characters']['may']['plan']['steps'][0]['args']['individual']='foreign'
  self.assertEqual(runtime.tick(self.s,now=10)['status'],'blocked')
