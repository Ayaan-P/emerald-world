from copy import deepcopy
import hashlib,unittest
import test_actor_objects as fixture
from world import actor_objects,actor_runtime
from world.mechanics import Candidate

class PlayerObjectTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.ObjectTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  state=deepcopy(self.s.module_state);state['world_object_player_use']={'fixture':'move'}
  source=self.s.candidate.source.replace('x=72,y=71,gfx=1','x=72,y=70,gfx=1')
  self.f.f.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
  self.f.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
  self.peer=self.f.connect('User',True);self.send('CAVE GET');self.send('CAVE ACK '+self.s.shared_cave.identity)
  self.f.f.f.state(self.peer,*self.s.wilds_map,72,69);self.peer['state'][4]=1
 def send(self,line):return self.f.f.f.send(self.peer,line)
 def use(self):return self.send('INTERACT_REGION %s fixture %s'%(self.peer['seq']+1,self.s.shared_cave.identity))
 def admit(self):self.f.f.advance(0,True);actor_objects.poll_player(self.s)
 def test_native_A_wire_and_agent_execute_same_durable_handler(self):
  original=self.s.objects[-1]['text'];self.use();self.assertIsNotNone(self.s.deployment)
  self.assertEqual(self.s.objects[-1]['text'],original);self.admit()
  self.assertEqual(self.s.module_state['world_object_controls']['fixture']['state'],{'uses':1})
  self.assertEqual(self.s.objects[-1]['text'],'Moved.')
  self.assertTrue(any(e['event']=='object_action_applied' for e in self.s.memory.history()['events']))
  self.f.plan();self.assertEqual(actor_runtime.tick(self.s,now=10)['status'],'pending')
  self.f.f.advance(1,True);self.assertEqual(actor_runtime.tick(self.s,now=16)['status'],'succeeded')
  self.assertEqual(self.s.module_state['world_object_controls']['fixture']['state'],{'uses':2})
  self.s.close();base=self.f.f.f.f;base.server=base.open();self.s=base.server
  self.assertEqual(self.s.module_state['world_object_controls']['fixture']['state'],{'uses':2})
 def test_text_only_prop_and_busy_use_do_not_run_handler(self):
  self.s.module_state['world_object_player_use']={};self.use();self.assertIsNone(self.s.deployment)
  self.s.module_state['world_object_player_use']={'fixture':'move'};self.peer['last_interaction']=-1
  self.use();first=self.s.deployment;self.peer['last_interaction']=-1;self.use()
  self.assertIs(self.s.deployment,first);self.admit()
  self.assertEqual(self.s.module_state['world_object_controls']['fixture']['state'],{'uses':1})
 def test_unadmitted_action_does_not_claim_success(self):
  self.use();self.s.deployment=None;actor_objects.poll_player(self.s)
  self.assertNotIn('world_object_controls',self.s.module_state)
  self.assertFalse(any(e['event']=='object_action_applied' for e in self.s.memory.history()['events']))
 def test_wrong_facing_or_region_does_not_dispatch(self):
  self.peer['state'][4]=2;self.use();self.assertIsNone(self.s.deployment)
  self.peer['state'][4]=1;self.send('INTERACT_REGION %s fixture %s'%(self.peer['seq']+1,'f'*64));self.assertIsNone(self.s.deployment)
