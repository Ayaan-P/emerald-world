from copy import deepcopy
import json,tempfile,unittest
import test_actor_social
from world import actor_runtime as runtime,character_reactions as reactions
from world.runtime_gm import IntentQueue
from world.actor_knowledge import share,recall,inbox

class KnowledgeTests(unittest.TestCase):
 def setUp(self):
  self.f=test_actor_social.SocialTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
 def plan(self,actor,steps):
  state=deepcopy(self.s.module_state);a=state['world_characters'][actor];a['version']+=1
  a['plan']=dict(id='plan_'+str(a['version']),purpose='Decide what to investigate from actual reports.',steps=steps)
  self.f.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
 def deliver(self):
  self.plan('harbor_guide',[
   dict(id='look',tool='world.observe',args=dict(radius=4),after=[]),
   dict(id='approach',tool='world.approach',args=dict(target='second',expected_version=1),after=['look']),
   dict(id='tell',tool='world.share_observation',args=dict(target='second',expected_version=1,observation=dict(result='look',key='tool_receipt')),after=['look','approach'])])
  self.assertEqual(runtime.tick(self.s,now=1)['status'],'succeeded')
  self.f.arrive()
  self.assertEqual(runtime.tick(self.s,now=36)['status'],'succeeded')
  return inbox(self.s)['second'][0]['delivered']
 def test_actual_handoff_independent_reaction_recall_navigation_and_restart(self):
  with tempfile.TemporaryDirectory() as td:
   q=IntentQueue(td);self.addCleanup(q.close)
   reactions.configure(q,self.s.inspect(),'second','Independently investigate useful reports.')
   delivery=self.deliver()
   self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.f.fetch)),1)
   job=q.claim();context=self.s.inspect();context['runtime']=dict(kind='character',observed_event=json.loads(job['result']),previous_source=self.f.f.f.candidate.source)
   self.assertEqual(reactions.prepare(context,self.f.fetch)['id'],'second')
   report=recall(self.s,'second',{},dict(delivery=delivery))
   self.assertNotIn('cells',report) # Never usable as recipient first-hand observation.
   self.plan('second',[
    dict(id='remember',tool='world.recall_report',args=dict(delivery=delivery),after=[]),
    dict(id='investigate',tool='world.navigate',args={k:dict(result='remember',key='report_'+k) for k in ('revision','x','y')},after=['remember']),
    dict(id='look',tool='world.observe',args=dict(radius=2),after=['investigate'])])
   self.assertEqual(runtime.tick(self.s,now=42)['status'],'succeeded')
   self.assertEqual(runtime.tick(self.s,now=48)['status'],'pending')
   self.f.f.advance(20,True)
   for n in range(21,40):self.f.f.advance(n)
   self.assertEqual(runtime.tick(self.s,now=80)['status'],'succeeded')
   self.assertEqual(runtime.tick(self.s,now=86)['status'],'succeeded')
   self.s.close();self.f.f.f.f.server=self.f.f.f.f.open();self.s=self.f.f.f.f.server
   self.assertEqual(recall(self.s,'second',{},dict(delivery=delivery)),report)
 def test_remote_forged_receipt_and_wrong_recipient_refused(self):
  with self.assertRaises(ValueError):share(self.s,'harbor_guide',{},dict(target='second',expected_version=1,observation=1))
  delivery=self.deliver()
  with self.assertRaises(ValueError):recall(self.s,'harbor_guide',{},dict(delivery=delivery))
  seq=self.s.db.execute("SELECT seq FROM actor_tool_receipts WHERE step='tell'").fetchone()[0]
  with self.assertRaisesRegex(ValueError,'Only actual'):share(self.s,'harbor_guide',{},dict(target='second',expected_version=1,observation=seq))
  row=inbox(self.s)['second'][0]
  duplicate=share(self.s,'harbor_guide',{},dict(target='second',expected_version=1,observation=row['observation']))
  self.assertEqual(duplicate['outcome'],'already_shared');self.assertEqual(len(inbox(self.s)['second']),1)
