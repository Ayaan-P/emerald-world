from copy import deepcopy
import json,unittest
from unittest.mock import patch
import test_actor_observation as fixture
from world import actor_runtime as runtime

class GeometryTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.ObservationTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.f.test_unseen_wall_blocks_observation_not_just_navigation();self.s=self.f.s
 def plan(self,actor,x,y,identity="open_ground"):
  state=deepcopy(self.s.module_state);c=state['world_characters'][actor];c['version']+=1
  c['plan']=dict(id=identity,purpose='Open a locally observed obstruction.',steps=[
   dict(id='look',tool='world.observe',args=dict(radius=4),after=[]),
   dict(id='open',tool='world.open_ground',args=dict(observation=dict(result='look',key='tool_receipt'),x=x,y=y,width=1,height=1),after=['look'])])
  self.f.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
 def test_actual_geometry_receipt_rebinding_restart_and_no_replay(self):
  old=self.s.shared_cave.identity;self.plan('harbor_guide',72,70)
  self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded')
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded')
  new=self.s.shared_cave.identity;self.assertNotEqual(old,new);self.assertTrue(self.s.shared_cave.walkable(72,70))
  self.assertTrue(all(o['region_revision']==new for o in self.s.objects))
  self.assertEqual([(o['x'],o['y']) for o in self.s.objects],[(71,70),(74,70)])
  result=json.loads(self.s.db.execute("SELECT result FROM actor_tool_receipts WHERE step='open'").fetchone()[0])
  self.assertEqual(result['revision'],new);self.assertEqual(result['opened'],[[72,70]])
  self.assertEqual(self.s.memory.place(old),self.s.memory.place(new))
  self.s.close();self.f.f.f.f.server=self.f.f.f.f.open();self.s=self.f.f.f.f.server
  self.assertEqual(self.s.shared_cave.identity,new);self.assertIsNone(runtime.tick(self.s,now=22))
 def test_other_actor_opens_different_observed_point(self):
  self.plan('second',72,71);runtime.tick(self.s,now=10)
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded');self.assertTrue(self.s.shared_cave.walkable(72,71))
  self.assertFalse(self.s.shared_cave.walkable(72,70))
 def test_occupied_map_refuses_without_geometry_change(self):
  old=self.s.shared_cave.identity;self.plan('harbor_guide',72,70);runtime.tick(self.s,now=10)
  self.f.f.f.connect_shared_xl('Bob')
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked');self.assertEqual(self.s.shared_cave.identity,old)
 def test_receipt_failure_rolls_back_geometry_and_character_scope(self):
  old=self.s.shared_cave.identity;self.plan('harbor_guide',72,70);runtime.tick(self.s,now=10)
  original=runtime._receipt
  def fail(server,actor,row,plan,step,status,result):
   if step['id']=='open' and status=='succeeded':raise ValueError('Injected receipt failure')
   return original(server,actor,row,plan,step,status,result)
  with patch.object(runtime,'_receipt',side_effect=fail):self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked')
  self.assertEqual(self.s.shared_cave.identity,old);self.assertTrue(all(o['region_revision']==old for o in self.s.objects))
  self.assertFalse(self.s.shared_cave.walkable(72,70))
  from world.shared_cave import SharedCave
  self.assertEqual(SharedCave(self.s.db.execute('SELECT template FROM generated_cave').fetchone()[0]).identity,old)
 def test_unobserved_rectangle_refuses(self):
  old=self.s.shared_cave.identity;self.plan('harbor_guide',80,70);runtime.tick(self.s,now=10)
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked');self.assertEqual(self.s.shared_cave.identity,old)

 def test_map_revision_change_invalidates_observation_then_fresh_plan_can_act(self):
  self.plan('harbor_guide',72,70);runtime.tick(self.s,now=10)
  old=self.s.shared_cave.identity
  blob=bytearray(self.s.db.execute('SELECT template FROM generated_cave').fetchone()[0]);blob[8+90*127+90]=ord('#');blob=bytes(blob)
  from world.shared_cave import SharedCave
  from world.character_rebinding import prepare
  revision=SharedCave(blob).identity
  self.s._replace_cave(blob,previous_revision=old,character_continuation=prepare(self.s,old,revision))
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked');self.assertFalse(self.s.shared_cave.walkable(72,70))
  self.f.f.f.candidate=self.s.candidate
  self.plan('harbor_guide',72,70,'fresh_ground');runtime.tick(self.s,now=22)
  self.assertEqual(runtime.tick(self.s,now=28)['status'],'succeeded');self.assertTrue(self.s.shared_cave.walkable(72,70))
