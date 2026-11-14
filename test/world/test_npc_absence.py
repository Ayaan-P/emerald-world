import json,time,unittest
from copy import deepcopy
from unittest.mock import patch
import test_actor_navigation as fixture
from world import actor_runtime,npc_absence
class Absence(unittest.TestCase):
 def setUp(self):
  self.f=fixture.NavigationTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
 def plan(self):
  state=deepcopy(self.s.module_state);c=state['world_characters']['harbor_guide'];c['version']+=1;c.pop('offer',None)
  c['plan']=dict(id='absence',purpose='Choose a period of unavailability, not fictional travel.',steps=[dict(id='leave',tool='world.take_leave',args=dict(seconds=60),after=[])])
  self.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
  return deepcopy(c)
 def tick(self,t):
  with patch.object(npc_absence.time,'time',return_value=t):return actor_runtime.tick(self.s,now=t)
 def test_actual_removal_wait_occupied_tile_restart_return_identity(self):
  original=self.plan();obj=deepcopy(next(o for o in self.s.objects if o['id']=='harbor_guide'))
  self.assertEqual(self.tick(10)['status'],'pending');self.assertTrue(npc_absence.guarded(self.s,'harbor_guide'))
  self.f.advance(0,True);self.assertFalse(any(o['id']=='harbor_guide' for o in self.s.objects));self.assertEqual(self.s.module_state['world_characters']['harbor_guide']['status'],'away')
  self.assertIsNone(self.tick(20));self.assertIsNone(self.tick(75));self.assertIsNone(self.s.deployment)
  self.f.f.state(self.f.peer,*self.s.wilds_map,obj['x'],obj['y']);self.assertIsNone(self.tick(81));self.assertIsNone(self.s.deployment)
  self.s.close();self.f.f.f.server=self.f.f.f.open();self.s=self.f.f.f.server;self.f.s=self.s;self.f.f.server=self.s;self.f.f.candidate=self.s.candidate
  self.assertIsNone(self.tick(90));self.assertIsNotNone(self.s.deployment)
  self.f.advance(1,True);self.assertEqual(self.tick(96)['status'],'succeeded')
  current=self.s.module_state['world_characters']['harbor_guide'];self.assertEqual(current['status'],'active')
  for field in ('name','goals','relationships','team','plan','evidence'):self.assertEqual(current[field],original[field])
  self.assertEqual(next(o for o in self.s.objects if o['id']=='harbor_guide'),obj)
  self.assertFalse(npc_absence.guarded(self.s,'harbor_guide'))
 def test_frozen_battle_refuses_departure_and_plan_membership_retention(self):
  self.plan();self.f.peer['character_pending']={'id':'harbor_guide'}
  self.assertEqual(self.tick(10)['status'],'blocked');self.assertIsNone(self.s.deployment)
  self.assertFalse(npc_absence.retained(self.s.inspect(),'harbor_guide'))
 def test_pending_absence_is_retained_and_unadmitted_departure_not_success(self):
  self.plan();self.assertEqual(self.tick(10)['status'],'pending');self.assertTrue(npc_absence.retained(self.s.inspect(),'harbor_guide'))
  self.s.deployment=None;self.assertEqual(self.tick(20)['status'],'blocked');self.assertFalse(npc_absence.guarded(self.s,'harbor_guide'))
  self.assertEqual(self.s.module_state['world_characters']['harbor_guide']['status'],'active')
 def test_rollback_does_not_shorten_absence(self):
  self.plan();self.tick(10);self.f.advance(0,True);self.tick(20)
  # Runtime monotonic dispatch is independent of the patched wall clock.
  with patch.object(npc_absence.time,'time',return_value=5):self.assertIsNone(actor_runtime.tick(self.s,now=30))
  with patch.object(npc_absence.time,'time',return_value=64):self.assertIsNone(actor_runtime.tick(self.s,now=40))
  self.assertIsNone(self.s.deployment)

 def test_enrollment_retained_only_pending_absence_and_host_stop_wins(self):
  from world import character_reactions as reactions,population_agents as agents
  from world.runtime_gm import IntentQueue
  import tempfile
  with tempfile.TemporaryDirectory() as root:
   q=IntentQueue(root);self.addCleanup(q.close)
   reactions.configure(q,self.s.inspect(),'harbor_guide','Choose availability independently.')
   agents.configure(q,self.s.inspect(),True)
   with q.db:q.db.execute('INSERT INTO population_agents VALUES(?,?,?,?,?,?)',('harbor_guide',self.s.memory.world_id,1,100,'active',0))
   fetch=lambda request:dict(ok=True,world_id=self.s.memory.world_id,**self.s.memory.history(**{k:v for k,v in request.items() if k!='command'}))
   self.plan();self.tick(10);self.f.advance(0,True);self.tick(20)
   agents.observe(q,self.s.inspect(),fetch)
   self.assertEqual(q.db.execute('SELECT status FROM population_agents').fetchone()[0],'active')
   self.assertEqual(len(reactions.subscriptions(q)),1)
   reactions.unfollow(q,'harbor_guide');agents.observe(q,self.s.inspect(),fetch)
   self.assertEqual(q.db.execute('SELECT status FROM population_agents').fetchone()[0],'stopped')
   self.assertEqual(reactions.subscriptions(q),[])
 def test_return_checks_revision_and_menu_occupancy_at_admission(self):
  self.plan();self.tick(10);self.f.advance(0,True);self.tick(20)
  with patch.object(npc_absence,'available',return_value=False):self.assertIsNone(self.tick(81))
  self.assertIsNone(self.s.deployment);self.assertIn('revision',npc_absence.catalog(self.s)[0]['reason'])
  self.tick(87);self.assertIsNotNone(self.s.deployment)
  # A player enters after staging, even in a menu. The admission guard fails.
  obj=json.loads(self.s.db.execute('SELECT data FROM npc_absence').fetchone()[0])['object']
  self.f.f.state(self.f.peer,*self.s.wilds_map,obj['x'],obj['y']);self.f.peer['state'][6]=0
  state=deepcopy(self.s.module_state);state['world_characters']['harbor_guide']['status']='active'
  with self.assertRaises(ValueError):npc_absence.validate_objects(self.s,self.s.objects+[obj],state)
