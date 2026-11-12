import json,tempfile,unittest
from copy import deepcopy
from unittest.mock import patch
import test_npc_conversations as fixture
from world import npc_goal_reviews as reviews,character_reactions as reactions
from world.runtime_gm import IntentQueue
class GoalReviews(unittest.TestCase):
 def setUp(self):
  self.f=fixture.ConversationTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.c=deepcopy(self.f.f.character);self.c['version']=2;self.c['goal_review']=dict(id='consider',goal=self.c['goals'][0],after_seconds=60)
  self.assertIsNone(self.f.f.commit({'may':self.c},self.f.f.npc))
 def observe(self,q,now):
  with patch.object(reviews.time,'time',return_value=now):return reactions.observe(q,self.s.inspect(),self.f.fetch)
 def test_one_shot_review_actual_visible_action_no_fake_time_event(self):
  from world.character_actions import compile_actions
  from world.mechanics import Candidate
  import hashlib
  with tempfile.TemporaryDirectory() as td:
   q=IntentQueue(td);self.addCleanup(q.close);reactions.configure(q,self.s.inspect(),'may','Independently reconsider useful plans.')
   before=self.s.memory.history();self.assertEqual(self.observe(q,100),[]);self.assertEqual(self.observe(q,159),[])
   self.assertEqual(len(self.observe(q,160)),1);self.assertEqual(self.s.memory.history(),before)
   item=q.claim();packet=json.loads(item['result'])
   baseline='def update(context,state):\n return dict(state=state,objects='+repr(self.s.objects)+',tiles=[])\n'
   self.s.candidate=Candidate(baseline,hashlib.sha256(baseline.encode()).hexdigest())
   context=self.s.inspect();context['runtime']=dict(kind='character',observed_event=packet,previous_source=baseline)
   response=reactions.prepare(context,self.f.fetch);self.assertIn('goal_review_limits',context)
   obj=dict(self.f.f.npc,text='Shall we explore together?')
   action=dict(id='may',expected_version=2,evidence=self.c['evidence'],reason='Reconsider the existing exploration goal without inventing progress.',changes=dict(goals=['Offer to explore with visitors'],goal_review=None),object=obj)
   reactions.check_response(dict(character_actions=[action],tests='assert True'),response)
   code=compile_actions([action],context);ns={};exec(code,ns)
   self.s.candidate=Candidate(code,hashlib.sha256(code.encode()).hexdigest())
   result=ns['update'](self.s._context(),deepcopy(self.s.module_state))
   self.assertIsNone(self.f.f.commit(result['state']['world_characters'],obj))
   self.assertEqual(self.s.objects[0]['text'],'Shall we explore together?')
   q.finish(item['id'],'succeeded',dict(ok=True));self.assertEqual(self.observe(q,10000),[])
 def test_restart_no_catchup_replay_and_clock_rollback(self):
  with tempfile.TemporaryDirectory() as td:
   q=IntentQueue(td);reactions.configure(q,self.s.inspect(),'may','Consider own goals.');self.observe(q,100);q.close();q=IntentQueue(td)
   try:
    self.assertEqual(self.observe(q,80),[]);self.assertEqual(self.observe(q,139),[]);self.assertEqual(len(self.observe(q,10000)),1)
    item=q.claim();q.finish(item['id'],'succeeded',dict(ok=True));self.assertEqual(self.observe(q,20000),[])
    q.close();q=IntentQueue(td);self.assertEqual(self.observe(q,30000),[])
   finally:q.close()
 def test_pending_and_unstarted_plans_defer_and_stale_packet_fails(self):
  with tempfile.TemporaryDirectory() as td:
   q=IntentQueue(td);self.addCleanup(q.close);reactions.configure(q,self.s.inspect(),'may','Consider own goals.')
   self.observe(q,100)
   c=deepcopy(self.c);c['plan']=dict(id='pending',purpose='Wait for real work.',steps=[dict(id='inspect',tool='world.observe',args={},after=[])])
   self.assertTrue(reviews.unfinished({},'may',c))
   data=dict(actor_runtime=dict(plans=[dict(actor='may',plan=c['plan'],expanded_method=None,receipts=[dict(step='inspect',status='pending')])]))
   self.assertTrue(reviews.unfinished(data,'may',c));data['actor_runtime']['plans'][0]['receipts'][0]['status']='blocked';self.assertFalse(reviews.unfinished(data,'may',c))
   self.observe(q,160);item=q.claim();packet=json.loads(item['result'])
   changed=deepcopy(self.c);changed['version']=3;changed['goal_review']=None;self.f.f.commit({'may':changed},self.f.f.npc)
   context=self.s.inspect();context['runtime']=dict(kind='character',observed_event=packet)
   with self.assertRaises(ValueError):reactions.prepare(context,self.f.fetch)
 def test_budget_bounds_and_no_enrollment(self):
  with tempfile.TemporaryDirectory() as td:
   q=IntentQueue(td);self.addCleanup(q.close);reactions.setup(q);self.assertEqual(self.observe(q,10000),[])
   sub=dict(world=self.s.memory.world_id,id='may',purpose='Choose a goal.');c=deepcopy(self.c)
   with q.db:
    for i in range(9):
     c['goal_review']['id']='review'+str(i)
     with patch.object(reviews.time,'time',return_value=100+i*100):self.assertIsNone(reviews.enqueue(q,sub,c,{}))
     with patch.object(reviews.time,'time',return_value=160+i*100):self.assertEqual(bool(reviews.enqueue(q,sub,c,{})),i<8)
    with patch.object(reviews.time,'time',return_value=86401):self.assertIsNotNone(reviews.enqueue(q,sub,c,{}))
  for r in [dict(id='x',goal='missing',after_seconds=60),dict(id='x',goal=self.c['goals'][0],after_seconds=True)]:
   with self.assertRaises(ValueError):reviews.validate(r,self.c['goals'])
