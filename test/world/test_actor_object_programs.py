from copy import deepcopy
import json,unittest
import test_actor_objects as fixture
from world import actor_runtime as runtime,actor_objects
from world.actor_observation import observe

class ProgramTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.ObjectTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  state=deepcopy(self.s.module_state);state['world_object_actions']={}
  self.f.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
  self.program=dict(initial='first',states=dict(first=dict(text='First face.',gfx=0,on={'turn':'second'},use='turn'),second=dict(text='Second face.',gfx=1,on={'reset':'first'},use='reset')))
 def plan(self,program=None):
  entry=next(e for e in observe(self.s,'harbor_guide',{},dict(radius=4))['entities'] if e['id']=='fixture')
  state=deepcopy(self.s.module_state);c=state['world_characters']['harbor_guide'];c['version']+=1
  c['plan']=dict(id='program',purpose='Create an interactive object.',steps=[dict(id='install',tool='world.program_object',args=dict(object='fixture',revision=entry['program_revision'],program=json.dumps(program or self.program,separators=(',',':'))),after=[])])
  self.f.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
 def install(self):
  self.plan();self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending');self.f.f.advance(0,True);self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded')
 def test_native_player_and_agent_share_authored_program_restart(self):
  self.install();self.assertEqual(self.s.objects[-1]['text'],'First face.')
  peer=self.f.connect('User',True);send=lambda line:self.f.f.f.send(peer,line)
  send('CAVE GET');send('CAVE ACK '+self.s.shared_cave.identity);self.f.f.f.state(peer,*self.s.wilds_map,72,69);peer['state'][4]=1
  send('INTERACT_REGION %s fixture %s'%(peer['seq']+1,self.s.shared_cave.identity));self.assertIsNotNone(self.s.deployment)
  self.f.f.advance(1,True);actor_objects.poll_player(self.s);self.f.f.advance(2)
  self.assertEqual(self.s.objects[-1]['text'],'Second face.');self.assertEqual(self.s.module_state['world_object_controls']['fixture']['state'],{'phase':'second'})
  offer=actor_objects.offers(self.s,self.s.objects[-1]);self.assertEqual(set(offer['actions']),{'reset'})
  state=deepcopy(self.s.module_state);c=state['world_characters']['harbor_guide'];c['version']+=1;c['plan']=dict(id='use_program',purpose='Use the current transition.',steps=[dict(id='use',tool='world.use_object',args=dict(object='fixture',action='reset',object_revision=offer['object_revision']),after=[])])
  self.f.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects))
  self.assertEqual(runtime.tick(self.s,now=22)['status'],'pending');self.f.f.advance(3,True);self.assertEqual(runtime.tick(self.s,now=28)['status'],'succeeded');self.f.f.advance(4)
  self.assertEqual(self.s.objects[-1]['text'],'First face.')
  self.s.close();base=self.f.f.f.f;base.server=base.open();self.s=base.server
  self.assertEqual(self.s.module_state['world_object_controls']['fixture']['state'],{'phase':'first'})
 def test_bad_transition_rejected_and_failed_admission_not_success(self):
  bad=deepcopy(self.program);bad['states']['first']['on']['turn']='missing';self.plan(bad)
  self.assertEqual(runtime.tick(self.s,now=10)['status'],'blocked');self.assertIsNone(self.s.deployment)
 def test_existing_handler_never_overwritten(self):
  self.s.module_state['world_object_actions']={'fixture':{'move':'Existing custom action'}};self.plan()
  self.assertEqual(runtime.tick(self.s,now=10)['status'],'blocked')
