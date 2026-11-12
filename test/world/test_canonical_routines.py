"""Quiet-world self-direction reaches actual supported authority work."""
from copy import deepcopy
import json,tempfile,unittest
from unittest.mock import patch
import test_canonical_cast as fixture
from test_frontier_outposts import base,plan
from world import canonical_cast as cast,canonical_construction as build,character_reactions as reactions
from world.runtime_gm import IntentQueue

class RoutineTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.action=self.f.action();self.action['id']='canon_rydel'
  self.action['changes'].update(goal='Consider what useful work to pursue next',
      routine=dict(interval_seconds=60))
  self.f.apply(self.action)
 def observe(self,q,now):
  with patch('world.canonical_routines.time.time',return_value=now):
   return reactions.observe(q,self.s.inspect(),self.f.fetch)
 def test_quiet_decision_without_new_event_produces_real_independent_activity(self):
  revision=self.s._replace_cave(base(),label='Quiet Frontier')
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    reactions.configure(q,self.s.inspect(),'canon_rydel','Choose your own supported priorities rather than waiting for players.')
    before=self.s.memory.history()
    self.assertEqual(self.observe(q,100),[]);self.assertEqual(self.observe(q,159),[])
    keys=self.observe(q,160);self.assertEqual(len(keys),1)
    self.assertEqual(self.s.memory.history(),before) # Time passage is not a world outcome.
    item=q.claim();packet=json.loads(item['result']);self.assertIn('routine',packet)
    ctx=self.f.context();ctx['runtime'].update(kind='character',observed_event=packet)
    with patch('world.canonical_routines.time.time',return_value=160):
     reaction=reactions.prepare(ctx,self.f.fetch)
    next_action=deepcopy(self.action);next_action['expected_version']=1
    next_action['changes'].update(goal='Prepare a small connected courtyard for future plans',
       worksite=dict(revision=revision,label='Rydel Courtyard',plan=plan()),
       intentions=[dict(id='courtyard',kind='construction',target=revision,reason='Commit useful shared space without asking players to do the work.')])
    reactions.check_response(dict(canonical_actions=[next_action],tests='assert True'),reaction)
    self.f.apply(next_action);q.finish(item['id'],'succeeded',dict(ok=True))
    # A real authority action, not a clock-driven claim of construction.
    self.assertEqual(build.step(self.s,now=10)['status'],'completed')
    self.assertTrue(self.s.shared_cave.walkable(18,23))
    self.assertEqual(self.s.memory.history()['events'][-1]['event'],'canonical_construction_completed')
    self.assertEqual(self.s.objects,[])
   finally:q.close()
 def test_restart_no_catchup_and_daily_budget_survives_removal(self):
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   reactions.configure(q,self.s.inspect(),'canon_rydel','Consider a next action or wait.')
   self.assertEqual(self.observe(q,100),[]);q.close();q=IntentQueue(tmp)
   try:
    self.assertEqual(len(self.observe(q,10000)),1)
    self.assertEqual(self.observe(q,10000),[]) # Existing pending request, no burst.
    item=q.claim();q.finish(item['id'],'succeeded',dict(ok=True))
    for i in range(1,8):
     self.assertEqual(len(self.observe(q,10000+i*60)),1)
     item=q.claim();q.finish(item['id'],'succeeded',dict(ok=True))
    self.assertEqual(self.observe(q,11000),[])
    q.close();q=IntentQueue(tmp)
    self.assertEqual(self.observe(q,12000),[])
    removed=deepcopy(self.action);removed['expected_version']=1;removed['changes']['routine']=None;self.f.apply(removed)
    self.assertEqual(self.observe(q,12001),[])
    restored=deepcopy(self.action);restored['expected_version']=2;self.f.apply(restored)
    self.assertEqual(self.observe(q,12002),[]);self.assertEqual(self.observe(q,12100),[])
    self.assertEqual(len(self.observe(q,86401)),1)
   finally:q.close()
 def test_withdrawn_or_changed_routine_cannot_run_stale_turn(self):
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    reactions.configure(q,self.s.inspect(),'canon_rydel','Consider a next action.')
    self.observe(q,100);self.observe(q,160);item=q.claim();packet=json.loads(item['result'])
    changed=deepcopy(self.action);changed['expected_version']=1;changed['changes']['routine']=None;self.f.apply(changed)
    ctx=self.f.context();ctx['runtime'].update(kind='character',observed_event=packet)
    with self.assertRaises(ValueError):reactions.prepare(ctx,self.f.fetch)
    q.finish(item['id'],'failed',dict(ok=False))
    self.assertEqual(self.observe(q,200),[])
   finally:q.close()
 def test_no_hidden_startup_and_bounds(self):
  from world.canonical_routines import validate
  for value in [dict(interval_seconds=0),dict(interval_seconds=True),dict(interval_seconds=86401),dict(interval_seconds=60,run='model')]:
   with self.assertRaises(ValueError):validate(value)
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    reactions.setup(q)
    self.assertEqual(self.observe(q,100000),[]) # No host enrollment, no work.
   finally:q.close()
