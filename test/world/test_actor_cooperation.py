import json,unittest,tempfile
from unittest.mock import patch
import test_companion_exchange as fixture
from world import actor_runtime as runtime,actor_cooperation as cooperation,character_reactions,actor_shops

class CooperationTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.ExchangeTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s;self.now=0
 def act(self,actor,tool,args):
  self.f.plan(actor,tool,args);self.now+=10
  return runtime.tick(self.s,now=self.now)
 def request(self,tool='world.configure_shop',where=None):
  result=self.act('harbor_guide','world.request_cooperation',dict(target='visitor',purpose='Would you help travelers prepare?',tool=tool,where=json.dumps(where or dict(outcome='retail_catalog_opened'))))
  self.assertEqual(result['status'],'succeeded');return cooperation.discover(self.s)[0]['id']
 def decision(self,key,decision='accept',actor='visitor'):
  return self.act(actor,'world.respond_cooperation',dict(request=key,decision=decision))
 def receipt(self,actor,tool):
  return next(e['seq'] for e in reversed(self.s.memory.history()['events']) if e.get('event')=='actor_tool_result' and e.get('character_id')==actor and e.get('tool')==tool and e.get('status')=='succeeded')
 def deliver(self,key,seq,actor='visitor'):
  return self.act(actor,'world.deliver_cooperation',dict(request=key,receipt=seq))
 def test_real_voluntary_service_action_and_durable_provenance(self):
  key=self.request();self.assertIsNone(actor_shops.line(self.s,{'character_shop_capable':True},'visitor',1))
  self.assertEqual(self.decision(key)['status'],'succeeded')
  self.assertEqual(self.act('visitor','world.configure_shop',dict(items='[1,28,114]'))['status'],'succeeded')
  seq=self.receipt('visitor','world.configure_shop')
  wire=actor_shops.line(self.s,{'character_shop_capable':True},'visitor',self.s.module_state['world_characters']['visitor']['version'])
  self.assertTrue(wire.endswith('3 1 28 114'))
  self.assertEqual(self.deliver(key,seq)['status'],'succeeded')
  event=next(e for e in self.s.memory.history()['events'] if e['event']=='character_cooperation_delivered')
  self.assertEqual(event['receipt'],seq);self.assertTrue(character_reactions.dynamic_result(event,'harbor_guide',{}))
  self.s.close();self.f.fx.f.server=self.f.fx.f.open();self.s=self.f.fx.f.server;self.f.s=self.s;self.f.fx.server=self.s
  self.assertEqual(cooperation.discover(self.s),[])
  self.assertTrue(actor_shops.line(self.s,{'character_shop_capable':True},'visitor',1).endswith('3 1 28 114'))
  self.assertEqual(self.deliver(key,seq)['status'],'blocked')
 def test_independent_choice_and_cancel_does_not_undo_real_action(self):
  key=self.request();self.assertEqual(self.decision(key,actor='harbor_guide')['status'],'blocked')
  self.assertEqual(self.decision(key,'decline')['status'],'succeeded')
  self.assertEqual(cooperation.discover(self.s),[])
  key=self.request();self.decision(key)
  self.act('visitor','world.configure_shop',dict(items='[1]'));seq=self.receipt('visitor','world.configure_shop')
  self.assertEqual(self.decision(key,'withdraw','harbor_guide')['status'],'succeeded')
  self.assertEqual(self.deliver(key,seq)['status'],'blocked')
  self.assertTrue(actor_shops.line(self.s,{'character_shop_capable':True},'visitor',1).endswith('1 1'))
 def test_old_other_actor_wrong_result_and_fiction_cannot_complete_work(self):
  self.act('visitor','world.configure_shop',dict(items='[1]'));old=self.receipt('visitor','world.configure_shop')
  key=self.request();self.decision(key)
  self.assertEqual(self.deliver(key,old)['status'],'blocked')
  self.act('harbor_guide','world.configure_shop',dict(items='[1]'));other=self.receipt('harbor_guide','world.configure_shop')
  self.assertEqual(self.deliver(key,other)['status'],'blocked')
  self.act('visitor','world.configure_shop',dict(items='[]'));closed=self.receipt('visitor','world.configure_shop')
  self.assertEqual(self.deliver(key,closed)['status'],'blocked')
  with self.s.db:fake=self.s.memory.append('fictional_claim',dict(character_id='visitor',tool='world.configure_shop',status='succeeded',result=dict(outcome='retail_catalog_opened')))
  self.assertEqual(self.deliver(key,fake)['status'],'blocked')
 def test_receipt_failure_rolls_back_decision_and_event(self):
  key=self.request();original=runtime._receipt
  def fail(server,actor,row,plan,step,status,result):
   if actor=='visitor' and status=='succeeded':raise ValueError('injected failure')
   return original(server,actor,row,plan,step,status,result)
  with patch.object(runtime,'_receipt',side_effect=fail):self.assertEqual(self.decision(key)['status'],'blocked')
  self.assertEqual(cooperation.discover(self.s)[0]['status'],'offered')
  self.assertFalse(any(e['event']=='character_cooperation_decided' for e in self.s.memory.history()['events']))
 def test_recipient_queue_gets_request_without_forced_plan(self):
  from world.runtime_gm import IntentQueue
  with tempfile.TemporaryDirectory() as d:
   queue=IntentQueue(d)
   try:
    character_reactions.configure(queue,self.s.inspect(),'visitor','Decide independently whether to help others.')
    key=self.request()
    def fetch(query):return dict(ok=True,world_id=self.s.memory.world_id,**self.s.memory.history(**{k:v for k,v in query.items() if k!='command'}))
    self.assertEqual(len(character_reactions.observe(queue,self.s.inspect(),fetch)),1)
    item=queue.claim();self.assertEqual(item['player'],'visitor');packet=json.loads(item['result'])
    context=self.s.inspect();context['runtime']=dict(kind='character',observed_event=packet)
    self.assertEqual(character_reactions.prepare(context,fetch)['id'],'visitor')
    self.assertEqual(cooperation.discover(self.s)[0]['status'],'offered')
    self.assertIsNone(actor_shops.line(self.s,{'character_shop_capable':True},'visitor',1))
   finally:queue.close()
 def test_single_pending_pair_no_lifetime_limit_and_no_recursive_contracts(self):
  key=self.request()
  self.assertEqual(self.act('visitor','world.request_cooperation',dict(target='harbor_guide',purpose='Other work',tool='world.configure_shop',where='{"outcome":"retail_catalog_opened"}'))['status'],'blocked')
  self.decision(key,'decline')
  for _ in range(10):key=self.request();self.decision(key,'decline')
  self.assertEqual(self.act('visitor','world.request_cooperation',dict(target='harbor_guide',purpose='Nested request',tool='world.request_cooperation',where='{"outcome":"cooperation_requested"}'))['status'],'blocked')

 def test_recipient_composes_real_action_and_delivery_in_one_plan(self):
  from copy import deepcopy
  from world import actor_tutors
  key=self.request('world.offer_tutoring',dict(outcome='tutoring_offered',move=102))
  self.decision(key)
  state=deepcopy(self.s.module_state);c=state['world_characters']['visitor'];c['version']+=1
  c['plan']=dict(id='chosen_cooperation',purpose='Choose my own supported contribution.',steps=[
   dict(id='offer',tool='world.offer_tutoring',args=dict(move=102),after=[]),
   dict(id='report',tool='world.deliver_cooperation',args=dict(request=key,receipt={'result':'offer','key':'tool_receipt'}),after=['offer'])])
  self.f.commit(state)
  self.now+=10;self.assertEqual(runtime.tick(self.s,now=self.now)['status'],'succeeded')
  self.now+=10;self.assertEqual(runtime.tick(self.s,now=self.now)['status'],'succeeded')
  self.assertEqual(cooperation.discover(self.s),[])
  self.assertTrue(actor_tutors.line(self.s,{'character_tutor_capable':True},'visitor',c['version']).endswith(' 102'))
  event=next(e for e in self.s.memory.history()['events'] if e['event']=='character_cooperation_delivered')
  self.assertEqual(event['result']['move'],102)
  self.assertFalse(any(e['event']=='pokemon_learned_move' for e in self.s.memory.history()['events']))
