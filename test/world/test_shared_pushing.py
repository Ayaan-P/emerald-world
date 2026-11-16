from copy import deepcopy
import unittest
import test_actor_object_programs as fixture
from world import actor_runtime as runtime,actor_objects
from world.actor_observation import observe

class PushTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.ProgramTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
 def install(self):
  entry=next(e for e in observe(self.s,'harbor_guide',{},dict(radius=4))['entities'] if e['id']=='fixture')
  state=deepcopy(self.s.module_state);c=state['world_characters']['harbor_guide'];c['version']+=1
  c['plan']=dict(id='enable_push',purpose='Allow cooperative movement.',steps=[dict(id='install',tool='world.enable_pushing',args=dict(object='fixture',revision=entry['program_revision']),after=[])])
  self.f.f.f.f.commit(dict(state=state,objects=self.s.objects,tiles=[]));self.assertIsNone(self.s.module_error)
  self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending');self.f.f.f.advance(0,True)
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded')
 def peer(self,name,x,y,facing=1,ready=1):
  p=self.f.f.connect(name,True);self.send(p,'CAVE GET');self.send(p,'CAVE ACK '+self.s.shared_cave.identity)
  self.f.f.f.f.state(p,*self.s.wilds_map,x,y);p['state'][4]=facing;p['state'][6]=ready;return p
 def send(self,p,line):return self.f.f.f.f.send(p,line)
 def push(self,p,tick=1):
  p['last_interaction']=-1
  self.send(p,'INTERACT_REGION %s fixture %s'%(p['seq']+1,self.s.shared_cave.identity))
  if self.s.deployment:self.f.f.f.advance(tick,True);actor_objects.poll_player(self.s)
 def obj(self):return next(o for o in self.s.objects if o['id']=='fixture')
 def test_actual_player_directions_persist_and_broadcast(self):
  self.install();a=self.peer('North',72,69);b=self.peer('East',73,71,3)
  self.push(a);self.assertEqual((self.obj()['x'],self.obj()['y']),(72,71))
  self.push(b,2);self.assertEqual((self.obj()['x'],self.obj()['y']),(71,71))
  self.f.f.f.advance(3);self.assertEqual((self.obj()['x'],self.obj()['y']),(71,71))
  self.assertIn('fixture',self.s._snapshot(a));self.assertIn('fixture',self.s._snapshot(b))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM object_transition_archive').fetchone()[0],2)
  self.s.close();base=self.f.f.f.f.f;base.server=base.open();self.s=base.server
  self.assertEqual((self.obj()['x'],self.obj()['y']),(71,71))
 def test_agent_push_uses_real_side_and_existing_dispatcher(self):
  self.install();offer=actor_objects.offers(self.s,self.obj());state=deepcopy(self.s.module_state)
  c=state['world_characters']['harbor_guide'];c['version']+=1;c['plan']=dict(id='push_it',purpose='Move the shared object.',steps=[dict(id='push',tool='world.use_object',args=dict(object='fixture',action='push',object_revision=offer['object_revision']),after=[])])
  self.f.f.f.f.commit(dict(state=state,objects=self.s.objects,tiles=[]));self.assertEqual(runtime.tick(self.s,now=22)['status'],'pending')
  self.f.f.f.advance(1,True);self.assertEqual(runtime.tick(self.s,now=28)['status'],'succeeded')
  self.assertEqual((self.obj()['x'],self.obj()['y']),(73,70))
 def test_menu_player_at_destination_blocks_without_source_change(self):
  self.install();a=self.peer('Pusher',72,69);self.peer('MenuUser',72,71,ready=0)
  sha=self.s.candidate.sha256;self.push(a)
  self.assertEqual((self.obj()['x'],self.obj()['y']),(72,70));self.assertIsNone(self.s.deployment);self.assertEqual(self.s.candidate.sha256,sha)
 def test_wrong_facing_and_concurrent_use_do_not_duplicate(self):
  self.install();a=self.peer('Pusher',72,69,facing=2);self.push(a);self.assertEqual(self.obj()['y'],70)
  a['state'][4]=1;a['last_interaction']=-1
  self.send(a,'INTERACT_REGION %s fixture %s'%(a['seq']+1,self.s.shared_cave.identity));pending=self.s.deployment
  self.assertIsNotNone(pending);a['last_interaction']=-1;self.send(a,'INTERACT_REGION %s fixture %s'%(a['seq']+1,self.s.shared_cave.identity));self.assertIs(self.s.deployment,pending)
  self.f.f.f.advance(1,True);actor_objects.poll_player(self.s);self.assertEqual(self.obj()['y'],71)
 def test_failed_admission_never_moves_or_reports_completion(self):
  self.install();a=self.peer('Pusher',72,69);a['last_interaction']=-1
  self.send(a,'INTERACT_REGION %s fixture %s'%(a['seq']+1,self.s.shared_cave.identity));self.s.deployment=None;actor_objects.poll_player(self.s)
  self.assertEqual(self.obj()['y'],70);self.assertIsNone(self.s.module_state.get('world_object_controls',{}).get('fixture'))
 def test_late_menu_occupant_rejects_at_admission(self):
  self.install();a=self.peer('Pusher',72,69);a['last_interaction']=-1
  self.send(a,'INTERACT_REGION %s fixture %s'%(a['seq']+1,self.s.shared_cave.identity));self.assertIsNotNone(self.s.deployment)
  self.peer('LateMenu',72,71,ready=0)
  import hashlib
  from world.mechanics import Candidate
  _,path,_=self.s.deployment;self.s.deployment=None;source=path.read_text();ns={};exec(source,ns)
  self.f.f.f.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
  self.f.f.f.f.commit(ns['update'](self.s._context(),deepcopy(self.s.module_state)))
  self.assertIn('overlaps a player',self.s.module_error);actor_objects.poll_player(self.s);self.assertEqual(self.obj()['y'],70)
 def test_more_than_32_pushes_reuse_dispatch_and_preserve_history(self):
  self.install();p=self.peer('Mover',72,69);self.push(p,1)
  for n in range(36):
   x,y,face=((72,70,1),(71,72,4),(73,73,2),(74,71,3))[n%4]
   self.f.f.f.f.state(p,*self.s.wilds_map,x,y);p['state'][4]=face
   self.push(p,n+2)
  self.assertEqual((self.obj()['x'],self.obj()['y']),(72,71))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM object_transition_archive').fetchone()[0],37)
  self.assertEqual(len(self.s.module_state['world_object_current_receipt']),1)
  self.assertEqual(self.s.candidate.source.count('def _ew_object_dispatch_v1('),1)
 def test_npc_occupant_blocks_directional_push(self):
  self.install();p=self.peer('Pusher',73,70,3);self.push(p)
  self.assertEqual((self.obj()['x'],self.obj()['y']),(72,70));self.assertIsNone(self.s.deployment)

 def test_install_projection_refuses_a_changed_object(self):
  from world.shared_pushing import projection
  from world.actor_objects import digest
  obj=deepcopy(self.obj());definition=dict(object=obj,digest=digest(obj))
  changed=deepcopy(self.s.objects);next(o for o in changed if o['id']=='fixture')['text']='Changed by prior mechanic'
  with self.assertRaisesRegex(ValueError,'changed before'):
   projection(dict(state=deepcopy(self.s.module_state),objects=changed,tiles=[]),definition)
