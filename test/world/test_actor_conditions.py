import unittest,json
from copy import deepcopy
import test_actor_weather as fixture
from world import actor_runtime as runtime,actor_weather
from world.actor_conditions import validate,matches

class ConditionTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.WeatherTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s;self.revision=self.f.revision
  self.peer=self.f.peer()
 def plan(self):
  return dict(id='respond_weather',purpose='Choose an environment action from the actual observation.',steps=[
   dict(id='see',tool='world.observe',args=dict(radius=1),after=[]),
   dict(id='rain',tool='world.set_weather',args=dict(revision=self.revision,mode='rain'),after=['see'],when=dict(step='see',path='/weather/mode',equals='default')),
   dict(id='clear',tool='world.set_weather',args=dict(revision=self.revision,mode='clear'),after=['see'],when=dict(step='see',path='/weather/mode',equals='rain'))])
 def apply(self,plan=None):
  c=dict(self.f.f.character,version=3,evidence=[self.s.memory.history()['events'][-1]['seq']],reason='Choose supported actual actions.',plan=plan or self.plan())
  self.f.f.commit(dict(state={'world_characters':{'harbor_guide':c}},tiles=[],objects=[self.f.f.obj]))
  self.assertIsNone(self.s.module_error)
 def test_observation_selects_one_real_native_weather_effect(self):
  self.apply();self.assertEqual(runtime.tick(self.s,now=10)['step'],'see')
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded')
  self.assertEqual(runtime.tick(self.s,now=22)['status'],'skipped')
  self.assertEqual(actor_weather.current(self.s,self.revision)['mode'],'rain')
  self.assertIn('OUTDOOR_WEATHER '+self.revision,self.s._snapshot(self.peer))
  events=[e for e in self.s.memory.history()['events'] if e['event']=='outdoor_weather_changed'];self.assertEqual(len(events),1)
  receipt=self.s.db.execute("SELECT result FROM actor_tool_receipts WHERE step='clear'").fetchone()[0]
  self.assertFalse(json.loads(receipt)['executed']);self.assertIsNone(runtime.tick(self.s,now=28))
 def test_different_actual_initial_state_selects_other_branch_and_restart(self):
  with self.s.db:actor_weather.configure(self.s,'harbor_guide',{},dict(revision=self.revision,mode='rain'))
  self.apply();runtime.tick(self.s,now=10)
  self.s.close();self.f.f.f.server=self.f.f.f.open();self.s=self.f.f.f.server;self.f.f.server=self.s
  self.assertEqual(runtime.tick(self.s,now=20)['status'],'skipped')
  self.assertEqual(runtime.tick(self.s,now=26)['status'],'succeeded')
  self.assertEqual(actor_weather.current(self.s,self.revision)['mode'],'clear')
  self.assertIsNone(runtime.tick(self.s,now=32))
 def test_skipped_descendants_do_not_run_and_guard_failure_still_halts(self):
  p=self.plan();p['steps'][1]['when']['equals']='snow'
  p['steps'][2]['after']=['rain'];p['steps'][2].pop('when');self.apply(p)
  self.assertEqual([runtime.tick(self.s,now=n)['status'] for n in (10,16,22)],['succeeded','skipped','skipped'])
  self.assertEqual(actor_weather.current(self.s,self.revision)['mode'],'default')
 def test_literal_conditions_missing_null_types_and_invalid_references(self):
  receipts={'s':('succeeded',{'n':None,'b':True,'list':[3]})}
  self.assertTrue(matches(dict(step='s',path='/n',equals=None),receipts))
  self.assertFalse(matches(dict(step='s',path='/absent',equals=None),receipts))
  self.assertFalse(matches(dict(step='s',path='/b',equals=1),receipts))
  self.assertTrue(matches(dict(step='s',path='/list/0',equals=3),receipts))
  for condition in [dict(step='other',path='/n',equals=None),dict(step='s',path='/bad~2',equals=1),dict(step='s',path='/n',equals={})]:
   with self.assertRaises(ValueError):validate(condition,['s'])
 def test_hard_failure_cannot_be_conditionally_bypassed(self):
  p=self.plan();p['steps'][0]['args']['radius']=99;self.apply(p)
  self.assertEqual(runtime.tick(self.s,now=10)['status'],'blocked');self.assertIsNone(runtime.tick(self.s,now=16))
  self.assertEqual(actor_weather.current(self.s,self.revision)['mode'],'default')
 def test_both_fake_provider_transports_preserve_conditional_plan(self):
  from world import author_backends
  from test_author_backends import openai,anthropic
  plan=self.plan();prompt=json.dumps(self.s.inspect()['actor_runtime'])
  self.assertIn('conditional_steps',prompt)
  for provider,wrap in [('openai-responses',openai),('anthropic-messages',anthropic)]:
   def transport(payload,timeout):
    self.assertEqual(payload['tools'],[])
    return wrap(dict(character_actions=[dict(id='harbor_guide',changes=dict(plan=plan))],tests=''))
   response=author_backends.request('explicit-model',prompt,30,provider=provider,transport=transport)
   returned=response['character_actions'][0]['changes']['plan'];runtime.validate(returned)
   self.assertEqual(returned,plan)
