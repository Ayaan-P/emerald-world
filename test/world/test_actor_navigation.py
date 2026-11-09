from concurrent.futures import Future
from copy import deepcopy
import hashlib,unittest
import test_region_characters as fixture
from world.mechanics import Candidate
from world import actor_runtime as runtime,actor_navigation as navigation

class NavigationTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.RegionCharacterTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.s=self.f.server;self.revision=self.f.enable_shared_xl();self.peer=self.f.connect_shared_xl(walking=True)
  state=deepcopy(self.s.module_state);a=state['world_characters']['harbor_guide'];a.update(version=3,evidence=[self.s.memory.history()['events'][-1]['seq']])
  b=deepcopy(a);b.update(version=1,name='Second Researcher',object_id='second',offer=None)
  state['world_characters']['second']=b
  objects=[deepcopy(self.f.obj),dict(self.f.obj,id='second',x=74,y=70)]
  self.base_objects=objects
  source="def update(context,state):\n return dict(state=state,tiles=[],objects="+repr(objects)+")\n"
  self.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());self.f.commit(dict(state=state,tiles=[],objects=objects));self.assertIsNone(self.s.module_error)
 def plan(self,actor,x,y):
  state=deepcopy(self.s.module_state);c=state['world_characters'][actor];c['version']+=1
  c['plan']=dict(id='travel',purpose='Select a destination without prescribing a path.',steps=[dict(id='go',tool='world.navigate',args=dict(revision=self.revision,x=x,y=y),after=[])])
  self.f.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
 def advance(self,n,deploy=False):
  self.s.tick=n
  if deploy:
   _,path,_=self.s.deployment;source=path.read_text();self.s.deployment=None
   self.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
  ns={};exec(self.f.candidate.source,ns)
  result=ns['update'](self.s._context(),deepcopy(self.s.module_state))
  self.f.commit(result);self.assertIsNone(self.s.module_error)
 def test_destination_route_avoids_obstacle_uses_executor_and_reports_actual_arrival(self):
  self.plan('harbor_guide',78,70)
  pending=runtime.tick(self.s,now=10);self.assertEqual(pending['status'],'pending')
  self.assertEqual(self.s.objects[0]['x'],71)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM character_journey_receipts').fetchone()[0],0)
  self.advance(0,True)
  route=self.s.module_state['world_character_controls']['harbor_guide']['journey']['path']
  self.assertNotIn([74,70],route);self.assertEqual(route[-1],[78,70])
  self.assertIsNone(runtime.tick(self.s,now=16))
  for tick in range(1,4):self.advance(tick)
  # Restart mid-route, preserving pending tool and existing reducer state.
  self.s.close();self.f.f.server=self.f.f.open();self.s=self.f.f.server;self.f.server=self.s;self.f.candidate=self.s.candidate
  for tick in range(4,24):self.advance(tick)
  complete=runtime.tick(self.s,now=40);self.assertEqual(complete['status'],'succeeded')
  result=self.s.inspect()['actor_runtime']['plans'][0]['receipts'][0]['result']
  self.assertEqual((result['x'],result['y']),(78,70));self.assertIn('arrival_receipt',result)
  self.assertIsNone(runtime.tick(self.s,now=46))
 def test_second_actor_and_new_destination_with_live_occupancy_pause(self):
  self.plan('second',77,72);self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending');self.advance(0,True)
  control=self.s.module_state['world_character_controls']['second'];next_point=control['walk']['path'][1]
  self.f.state(self.peer,*self.s.wilds_map,*next_point);self.advance(1)
  self.assertEqual(self.s.module_state['world_character_controls']['second']['walk']['index'],0)
  self.assertIsNone(runtime.tick(self.s,now=16))
  self.f.state(self.peer,*self.s.wilds_map,70,70)
  for tick in range(2,20):self.advance(tick)
  self.assertEqual(runtime.tick(self.s,now=30)['status'],'succeeded')
 def test_unreachable_destination_and_unadmitted_or_interrupted_job_never_arrive(self):
  self.plan('harbor_guide',0,0);self.assertEqual(runtime.tick(self.s,now=10)['status'],'blocked')
  self.assertIsNone(self.s.deployment);self.assertEqual(self.s.db.execute('SELECT count(*) FROM character_journey_receipts').fetchone()[0],0)
  # Another actor has a valid request, but interrupted staging is not success.
  self.plan('second',75,72);self.assertEqual(runtime.tick(self.s,now=16)['status'],'pending')
  self.s.deployment=None
  self.assertEqual(runtime.tick(self.s,now=22)['status'],'blocked')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM character_journey_receipts').fetchone()[0],0)
 def test_new_archived_wall_geometry_is_routed_without_a_predefined_path(self):
  rows=['#'*127]+['#'+'.'*125+'#']*125+['#'*127]
  for y in range(68,73):rows[y]=rows[y][:74]+'#'+rows[y][75:]
  self.f.state(self.peer,0,9,8,8)
  self.revision=self.s._replace_cave(b'EWGMAP0A'+''.join(rows).encode(),label='Unseen wall layout')
  objects=[dict(self.s.objects[0],region_revision=self.revision),dict(self.s.objects[1],region_revision=self.revision,x=83,y=75)]
  state=deepcopy(self.s.module_state)
  for c in state['world_characters'].values():c['version']+=1;c['evidence']=[self.s.memory.history()['events'][-1]['seq']]
  source="def update(context,state):\n return dict(state=state,tiles=[],objects="+repr(objects)+")\n"
  self.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());self.f.commit(dict(state=state,tiles=[],objects=objects));self.assertIsNone(self.s.module_error)
  self.plan('harbor_guide',78,70);self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending');self.advance(0,True)
  path=self.s.module_state['world_character_controls']['harbor_guide']['journey']['path']
  self.assertTrue(any(y<68 or y>72 for x,y in path));self.assertFalse(any(x==74 and 68<=y<=72 for x,y in path))
  for tick in range(1,35):self.advance(tick)
  self.assertEqual(runtime.tick(self.s,now=40)['status'],'succeeded')
 def test_versioned_interruption_stops_existing_movement_without_false_arrival(self):
  from world.character_actions import compile_actions
  self.plan('harbor_guide',80,70);runtime.tick(self.s,now=10);self.advance(0,True);self.advance(1)
  actor=self.s.module_state['world_characters']['harbor_guide'];obj=next(o for o in self.s.objects if o['id']=='harbor_guide')
  action=dict(id='harbor_guide',expected_version=actor['version'],evidence=actor['evidence'],reason='Stop this actor navigation.',changes=dict(plan=None),object=obj)
  context=self.s.inspect();context['runtime']=dict(previous_source=self.f.candidate.source)
  import json
  context['recalled_history']=dict(events=[dict(json.loads(self.s.db.execute("SELECT data FROM events WHERE seq=? AND kind='world_memory'",(seq,)).fetchone()[0]),seq=seq) for seq in actor['evidence']])
  source=compile_actions([action],context);self.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());self.advance(2)
  self.assertNotIn('journey',self.s.module_state['world_character_controls']['harbor_guide'])
  self.assertEqual(runtime.tick(self.s,now=20)['status'],'blocked')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM character_journey_receipts').fetchone()[0],0)
