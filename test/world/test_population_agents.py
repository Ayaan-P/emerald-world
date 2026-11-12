from copy import deepcopy
import json
import unittest
from world import actor_runtime as runtime,character_reactions as reactions,population_agents as lifecycle
from world.runtime_gm import IntentQueue
from world.character_actions import compile_actions
from world.author_backends import request
from world.gm import _prompt
from world.mechanics import Candidate
import hashlib
import test_actor_population as fixture

class PopulationAgentTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.PopulationTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.q=IntentQueue(self.s.root);self.addCleanup(lambda:self.q.close())
 def fetch(self,query):return dict(ok=True,world_id=self.s.memory.world_id,**self.s.memory.history(**{k:v for k,v in query.items() if k!='command'}))
 def birth(self,enabled=True,kind='character'):
  self.f.plan(self.f.define(kind=kind));reactions.configure(self.q,self.s.inspect(),'harbor_guide','Create freely, using actual results.')
  if enabled:lifecycle.configure(self.q,self.s.inspect(),True)
  runtime.tick(self.s,now=10);runtime.tick(self.s,now=16)
  self.assertNotIn('researcher',reactions.actors(self.s.module_state))
  self.f.admit();runtime.tick(self.s,now=22)
  reactions.observe(self.q,self.s.inspect(),self.fetch)
 def claim_child(self):
  item=self.q.claim()
  while item and item['player']!='researcher':self.q.finish(item['id'],'succeeded',dict(wait=True));item=self.q.claim()
  return item
 def author(self,item,plan,provider):
  from test_author_backends import anthropic,openai
  ctx=self.s.inspect();ctx['runtime']=dict(kind='character',observed_event=json.loads(item['result']),previous_source=self.s.candidate.source)
  ctx['recalled_history']=dict(events=self.s.memory.history()['events'])
  reaction=reactions.prepare(ctx,self.fetch)
  action=dict(id='researcher',expected_version=reaction['expected_version'],evidence=[reaction['evidence']],reason='Choose from real local observations.',changes=dict(plan=plan),object=next(o for o in self.s.objects if o['id']=='researcher'))
  wrap=anthropic if provider=='anthropic-messages' else openai
  reply=request('explicit-model',_prompt(item['text'],ctx),30,provider=provider,transport=lambda p,t:wrap(dict(character_actions=[action],tests='def test_safe(): assert True')))
  reactions.check_response(reply,reaction);source=compile_actions(reply['character_actions'],ctx);ns={};exec(source,ns)
  self.f.f.f.f.f.f.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
  self.f.f.f.f.f.f.f.commit(ns['update'](self.s._context(),deepcopy(self.s.module_state)))
  self.assertIsNone(self.s.module_error);self.q.finish(item['id'],'succeeded',dict(ok=True))
 def exercise(self,provider):
  self.birth();item=self.claim_child();self.assertIsNotNone(item)
  self.author(item,dict(id='look_around',purpose='Learn what is actually nearby.',steps=[dict(id='look',tool='world.observe',args=dict(radius=2),after=[])]),provider)
  receipt=runtime.tick(self.s,now=28);self.assertEqual(receipt['status'],'succeeded');self.assertEqual(receipt['actor'],'researcher')
  reactions.observe(self.q,self.s.inspect(),self.fetch);next_item=self.claim_child();self.assertEqual(json.loads(next_item['result'])['evidence'],receipt['seq'])
  self.author(next_item,None,provider)
  self.assertIsNone(self.s.module_state['world_characters']['researcher']['plan'])
 def test_independent_claude_creation_observation_reconsideration(self):self.exercise('anthropic-messages')
 def test_independent_openai_creation_observation_reconsideration(self):self.exercise('openai-responses')
 def test_default_off_never_enrolls(self):
  self.birth(False);self.assertIsNone(self.q.db.execute("SELECT 1 FROM character_reactions WHERE id='researcher'").fetchone())
 def test_restart_no_duplicate_and_disable_cancels_future_turns(self):
  self.birth();count=self.q.db.execute("SELECT count(*) FROM requests WHERE player='researcher'").fetchone()[0]
  self.q.close();self.q=IntentQueue(self.s.root)
  reactions.observe(self.q,self.s.inspect(),self.fetch)
  self.assertEqual(self.q.db.execute("SELECT count(*) FROM requests WHERE player='researcher'").fetchone()[0],count)
  lifecycle.configure(self.q,self.s.inspect(),False)
  self.assertIsNone(self.q.db.execute("SELECT 1 FROM character_reactions WHERE id='researcher'").fetchone())
  self.assertEqual(self.q.db.execute("SELECT status FROM requests WHERE player='researcher'").fetchone()[0],'interrupted')
 def test_recurring_budget_waits_survives_restart_and_does_not_starve_others(self):
  from unittest.mock import patch
  self.birth();item=self.claim_child();self.q.finish(item['id'],'failed',dict(error='No success'))
  lifecycle.configure(self.q,self.s.inspect(),True,turn_limit=1,period_hours=1)
  start=self.q.db.execute("SELECT started FROM population_agents WHERE id='researcher'").fetchone()[0]
  with self.q.db:
   self.q.db.execute("DELETE FROM requests WHERE player!='researcher'")
   self.q.db.execute("UPDATE requests SET status='queued' WHERE id=?",(item['id'],))
  with patch('world.population_agents.time.time',return_value=start+3599):self.assertIsNone(self.q.claim())
  self.q.submit('Host','Another request','other-host-request')
  with patch('world.population_agents.time.time',return_value=start+3599):
   other=self.q.claim();self.assertEqual(other['player'],'Host');self.q.finish(other['id'],'succeeded',{})
  self.q.close();self.q=IntentQueue(self.s.root)
  with patch('world.population_agents.time.time',return_value=start+3600):
   resumed=self.q.claim();self.assertEqual(resumed['id'],item['id'])
  self.assertEqual(self.q.db.execute("SELECT attempts FROM population_agents WHERE id='researcher'").fetchone()[0],1)
  with patch('world.population_agents.time.time',return_value=start-10):self.assertIsNone(self.q.claim())

 def test_props_are_not_model_actors(self):
  self.birth(kind='prop')
  self.assertEqual(self.q.db.execute('SELECT count(*) FROM population_agents').fetchone()[0],0)
 def test_old_lifetime_pause_migrates_but_explicit_stop_does_not(self):
  from unittest.mock import patch
  self.birth();lifecycle.configure(self.q,self.s.inspect(),True,turn_limit=2,period_hours=1)
  start=self.q.db.execute("SELECT started FROM population_agents WHERE id='researcher'").fetchone()[0]
  with self.q.db:
   self.q.db.execute("UPDATE population_agents SET status='budget_reached' WHERE id='researcher'")
   self.q.db.execute("DELETE FROM character_reactions WHERE id='researcher'")
   self.q.db.execute("UPDATE requests SET status='interrupted' WHERE player='researcher'")
  with patch('world.population_agents.time.time',return_value=start+3600):reactions.observe(self.q,self.s.inspect(),self.fetch)
  self.assertEqual(self.q.db.execute("SELECT status FROM population_agents WHERE id='researcher'").fetchone()[0],'active')
  lifecycle.configure(self.q,self.s.inspect(),False)
  with patch('world.population_agents.time.time',return_value=start+7200):reactions.observe(self.q,self.s.inspect(),self.fetch)
  self.assertEqual(self.q.db.execute("SELECT status FROM population_agents WHERE id='researcher'").fetchone()[0],'stopped')
