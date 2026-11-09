from copy import deepcopy
import hashlib,json,unittest
import test_actor_navigation as fixture
from world import actor_runtime as runtime
from world.actor_observation import observe
from world.mechanics import Candidate

class ObservationTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.NavigationTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
 def test_local_actor_scope_public_entities_and_no_private_players(self):
  a=observe(self.s,'harbor_guide',{},dict(radius=4))
  b=observe(self.s,'second',{},dict(radius=1))
  self.assertEqual((a['x'],a['y']),(71,70));self.assertEqual((b['x'],b['y']),(74,70))
  self.assertEqual(a['entities'],[dict(id='second',x=74,y=70,version=1)]);self.assertEqual(b['entities'],[])
  self.assertLessEqual(len(a['cells']),41)
  self.assertNotIn('Alice',json.dumps(a));self.assertNotIn('players',a)
  other=dict(self.s.objects[1],id='elsewhere',region_revision='f'*64)
  self.s.objects.append(other)
  self.assertNotIn('elsewhere',json.dumps(observe(self.s,'harbor_guide',{},dict(radius=4))))
  for args in ({'radius':True},{'radius':5},{'radius':2,'x':74}):
   with self.assertRaises(ValueError):observe(self.s,'harbor_guide',{},args)
  with self.assertRaises(ValueError):observe(self.s,'wally',{},dict(radius=2))
 def test_navigation_then_observation_uses_arrived_position_and_persists_snapshot(self):
  self.f.plan('harbor_guide',78,70)
  state=deepcopy(self.s.module_state);c=state['world_characters']['harbor_guide'];c['version']+=1
  c['plan']['id']='travel_observe';c['plan']['steps'].append(dict(id='look',tool='world.observe',args=dict(radius=2),after=['go']))
  self.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
  self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending');self.f.advance(0,True)
  for tick in range(1,25):self.f.advance(tick)
  self.assertEqual(runtime.tick(self.s,now=40)['step'],'go')
  result=runtime.tick(self.s,now=46);self.assertEqual(result['step'],'look');self.assertEqual(result['status'],'succeeded')
  def saved(server):return json.loads(server.db.execute("SELECT result FROM actor_tool_receipts WHERE actor='harbor_guide' AND step='look'").fetchone()[0])
  snapshot=saved(self.s);self.assertEqual((snapshot['x'],snapshot['y']),(78,70))
  self.assertEqual(snapshot['revision'],self.f.revision)
  self.s.close();self.f.f.f.server=self.f.f.f.open();self.s=self.f.f.f.server
  self.assertEqual(saved(self.s),snapshot);self.assertIsNone(runtime.tick(self.s,now=52))
 def test_unseen_wall_blocks_observation_not_just_navigation(self):
  rows=['#'*127]+['#'+'.'*125+'#']*125+['#'*127]
  for y in range(67,74):rows[y]=rows[y][:72]+'#'+rows[y][73:]
  self.f.f.state(self.f.peer,0,9,8,8)
  revision=self.s._replace_cave(b'EWGMAP0A'+''.join(rows).encode(),label='Observation wall')
  objects=[dict(o,region_revision=revision) for o in self.s.objects]
  state=deepcopy(self.s.module_state)
  for c in state['world_characters'].values():c['version']+=1;c['evidence']=[self.s.memory.history()['events'][-1]['seq']]
  source='def update(context,state):\n return dict(state=state,tiles=[],objects='+repr(objects)+')\n'
  self.f.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());self.f.f.commit(dict(state=state,tiles=[],objects=objects));self.assertIsNone(self.s.module_error)
  snapshot=observe(self.s,'harbor_guide',{},dict(radius=4))
  self.assertIn(dict(x=72,y=70,walkable=False),snapshot['cells'])
  self.assertFalse(any(c['x']>72 for c in snapshot['cells']));self.assertEqual(snapshot['entities'],[])
  self.assertEqual(snapshot['revision'],revision)
