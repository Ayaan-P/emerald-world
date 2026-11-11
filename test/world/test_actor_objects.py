from copy import deepcopy
import hashlib,json,unittest
import test_actor_navigation as fixture
from world import actor_runtime as runtime
from world.actor_observation import observe
from world.mechanics import Candidate

class ObjectTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.NavigationTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.f.f.state(self.f.peer,0,9,8,8)
  objects=deepcopy(self.s.objects)+[dict(self.s.objects[0],id='fixture',kind='prop',gfx=0,x=72,y=70,text='Closed.')]
  state=deepcopy(self.s.module_state);state['world_object_actions']={'fixture':{'move':'Move this fixture one cell.'}}
  source='def update(context,state):\n return dict(state=state,tiles=[],objects='+repr(objects)+')\n'
  source+="def actor_interact(object_id,action,state):\n assert object_id=='fixture' and action=='move'\n return dict(state={'uses':state.get('uses',0)+1},x=72,y=71,gfx=1,text='Moved.')\n"
  self.f.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());self.f.f.commit(dict(state=state,tiles=[],objects=objects));self.assertIsNone(self.s.module_error)
 def plan(self,actor='harbor_guide',revision=None):
  snapshot=observe(self.s,actor,{},dict(radius=4));offer=next(o for o in snapshot['entities'] if o['id']=='fixture')
  state=deepcopy(self.s.module_state);c=state['world_characters'][actor];c['version']+=1
  c['plan']=dict(id='use',purpose='Use an observed supported object action.',steps=[dict(id='use',tool='world.use_object',args=dict(object='fixture',action='move',object_revision=revision or offer['object_revision']),after=[])])
  self.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
 def test_observed_object_handler_changes_actual_object_and_restart_preserves_it(self):
  self.plan();self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending')
  self.assertEqual(self.s.objects[-1]['y'],70)
  self.f.advance(0,True);self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded')
  self.assertEqual(self.s.objects[-1]['y'],71);self.assertEqual(self.s.objects[-1]['text'],'Moved.')
  self.assertEqual(self.s.module_state['world_object_controls']['fixture']['state'],{'uses':1})
  self.f.advance(1);self.assertEqual(self.s.objects[-1]['y'],71)
  self.s.close();self.f.f.f.server=self.f.f.f.open();self.s=self.f.f.f.server
  self.assertEqual(self.s.objects[-1]['y'],71);self.assertIsNone(runtime.tick(self.s,now=22))
 def test_stale_observation_and_nonadjacent_second_actor_refuse(self):
  self.plan(revision='f'*64);self.assertEqual(runtime.tick(self.s,now=10)['status'],'blocked')
  self.plan('second');self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked')
  self.assertIsNone(self.s.deployment);self.assertNotIn('world_object_controls',self.s.module_state)
 def test_unadmitted_handler_does_not_claim_effect(self):
  self.plan();runtime.tick(self.s,now=10);self.s.deployment=None
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked');self.assertEqual(self.s.objects[-1]['y'],70)

 def connect(self,name,capable):
  token=self.s.create_identity(name)['token'];conn=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
  role='SOCIALCAVE16CHAR1CHARQUEST1CHARREG1'+('WORLDOBJ1' if capable else '')
  self.assertIn('WELCOME',self.f.f.send(conn,f'HELLO 1 {name} {token} {role}'));self.f.f.state(conn,0,9,8,8)
  return conn
 def test_actual_native_snapshot_and_legacy_admission_refusal(self):
  import os,subprocess,tempfile
  from test_world_props_native import parser_binary
  legacy=self.connect('Legacy',False)
  self.assertIn('CAVE NONE',self.f.f.send(legacy,'CAVE GET'))
  peer=self.connect('Capable',True)
  self.assertIn('XLWILDS',self.f.f.send(peer,'CAVE GET'))
  self.assertIn('CAVE OK',self.f.f.send(peer,'CAVE ACK '+self.s.shared_cave.identity))
  self.f.f.state(peer,*self.s.wilds_map,70,70)
  row=next(s for s in self.s._snapshot(peer).splitlines() if s.startswith('REGION_PROP '))
  self.assertNotIn('CHARACTER fixture',self.s._snapshot(peer))
  root=os.environ.get('EW_NATIVE_SOURCE')
  if root:
   with tempfile.TemporaryDirectory() as tmp:
    binary=parser_binary(root,tmp)
    self.assertEqual(subprocess.check_output([str(binary),row,self.s.shared_cave.identity,'0'],text=True).strip(),'1 1 86')
 def test_handler_cannot_move_prop_onto_ready_player(self):
  peer=self.connect('Capable',True);self.f.f.send(peer,'CAVE GET');self.f.f.send(peer,'CAVE ACK '+self.s.shared_cave.identity)
  self.f.f.state(peer,*self.s.wilds_map,72,71)
  self.plan();runtime.tick(self.s,now=10)
  _,path,_=self.s.deployment;self.s.deployment=None;source=path.read_text();ns={};exec(source,ns)
  result=ns['update'](self.s._context(),deepcopy(self.s.module_state))
  self.f.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());self.f.f.commit(result)
  self.assertIn('overlaps',self.s.module_error);self.assertEqual(self.s.objects[-1]['y'],70)
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked')
 def test_second_actor_can_use_same_advertised_object_without_ownership_spoofing(self):
  objects=deepcopy(self.s.objects);objects[1]['x']=73
  source=self.f.f.candidate.source.replace("'x': 74", "'x': 73")
  self.f.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());self.f.f.commit(dict(state=self.s.module_state,tiles=[],objects=objects));self.assertIsNone(self.s.module_error)
  self.plan('second');self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending');self.f.advance(0,True)
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded');self.assertEqual(self.s.objects[-1]['y'],71)
 def test_legacy_player_inside_prevents_new_prop_admission(self):
  objects=deepcopy(self.s.objects);state=deepcopy(self.s.module_state);original=self.f.f.candidate
  source='def update(context,state):\n return dict(state=state,tiles=[],objects='+repr(objects[:-1])+')\n'
  self.f.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());self.f.f.commit(dict(state=state,tiles=[],objects=objects[:-1]))
  peer=self.connect('Legacy',False);self.assertIn('XLWILDS',self.f.f.send(peer,'CAVE GET'))
  self.assertIn('CAVE OK',self.f.f.send(peer,'CAVE ACK '+self.s.shared_cave.identity));self.f.f.state(peer,*self.s.wilds_map,70,70)
  self.f.f.candidate=original;self.f.f.commit(dict(state=state,tiles=[],objects=objects))
  self.assertIn('Legacy player',self.s.module_error);self.assertNotIn('fixture',[o['id'] for o in self.s.objects])
