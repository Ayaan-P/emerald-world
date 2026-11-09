import copy,json,tempfile,unittest
from unittest.mock import patch
import test_canonical_world_actions as fixture
from world import actor_runtime as runtime,character_reactions as reactions
from world.runtime_gm import IntentQueue

class ActorRuntimeTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.WorldActionTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  a=self.f.f.action();a['id']='canon_wally';self.f.f.apply(a)
 def plan(self,identity='work',revision=0):
  return dict(id=identity,purpose='Choose a supported action and communicate its actual result.',steps=[
   dict(id='act',tool='world.act',args=dict(pack='workshop',scene='organize',choice='open',place='LittlerootTown',revision=revision),after=[]),
   dict(id='tell',tool='actor.message',args=dict(to='canon_wally',text=dict(result='act',key='text')),after=['act'])])
 def apply(self,plan,version=0,actor='canon_rydel',evidence=None):
  a=self.f.f.action(version);a['id']=actor;a['changes']['plan']=plan
  if evidence:a['changes']['evidence']=[evidence]
  self.f.f.apply(a)
 def test_real_composition_result_reference_restart_and_independent_recipient(self):
  self.apply(self.plan());catalog=self.s.inspect()['actor_runtime']
  self.assertEqual(set(catalog['capabilities']),{'world.inspect_habitat','world.revise_habitat','world.accompany_player','world.request_cooperation','world.respond_cooperation','world.deliver_cooperation','world.propose_exchange','world.resolve_exchange','world.inspect_environment','world.reshape_environment','world.act','actor.message','world.navigate','world.observe','world.open_ground','world.approach','world.address','world.use_object','world.take_prop','world.place_prop','world.extend_space','world.create_place','world.create_habitat','world.populate','world.create_landscape','world.await_entity','world.link_caves','world.traverse_link','world.publish_bulletin','world.withdraw_bulletin','world.navigate_places','world.offer_companion','world.respond_companion','world.program_object','world.await_event','world.practice','world.offer_tutoring','world.set_weather','world.configure_shop','world.attempt_capture','world.prepare_challenge','world.share_observation','world.recall_report','world.program_network','world.reply_player'})
  first=runtime.tick(self.s,now=10);self.assertEqual(first['status'],'succeeded')
  self.assertEqual(self.s.opportunities.offers('Alice','LittlerootTown')[0]['scenes'][0]['id'],'solo')
  # Restart before dependent tool; committed state is not replayed.
  self.s.close();case=self.f.f.f.case;case.server=case.open();self.s=case.server
  self.f.s=self.s;self.f.f.s=self.s;self.f.f.f.server=self.s
  second=runtime.tick(self.s,now=20);self.assertEqual(second['step'],'tell')
  self.assertIsNone(runtime.tick(self.s,now=26))
  letters=[e for e in self.s.memory.history()['events'] if e['event']=='canonical_letter_delivered']
  self.assertEqual(len(letters),1);self.assertEqual(letters[0]['text'],'The public discussion is now available.')
  self.assertEqual(letters[0]['recipient'],'canon_wally')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_consequences').fetchone()[0],1)
  # Recipient decides independently; same capability works without a role-specific runner.
  other=dict(id='respond',purpose='Contribute independently.',steps=[dict(id='act',tool='world.act',args=dict(pack='workshop',scene='contribute',choice='join',place='LittlerootTown',revision=1),after=[])])
  self.apply(other,1,'canon_wally',letters[0]['seq'])
  self.assertEqual(runtime.tick(self.s,now=32)['actor'],'canon_wally')
  self.assertEqual(self.s.opportunities.offers('Bob','LittlerootTown')[0]['scenes'][0]['id'],'shared')
  self.assertEqual(self.s.objects,[])
 def test_blocked_action_observed_replanned_and_no_blind_retry(self):
  self.apply(self.plan(revision=99));first=runtime.tick(self.s,now=10)
  self.assertEqual(first['status'],'blocked');self.assertIsNone(runtime.tick(self.s,now=16))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_consequences').fetchone()[0],0)
  event=next(e for e in self.s.memory.history()['events'] if e['seq']==first['seq'])
  self.assertTrue(runtime.relevant(event,'canon_rydel'))
  # Actual blocked evidence permits a new authored plan, not invented success.
  self.apply(self.plan('reconsidered'),1,evidence=first['seq'])
  self.assertEqual(runtime.tick(self.s,now=22)['status'],'succeeded')
 def test_atomic_receipt_failure_rolls_back_effect_and_stop_removes_future_work(self):
  self.apply(self.plan())
  original=self.s.memory.append
  def append(kind,payload):
   if kind=='actor_tool_result' and payload['status']=='succeeded':raise ValueError('receipt store refused')
   return original(kind,payload)
  with patch.object(self.s.memory,'append',side_effect=append):self.assertEqual(runtime.tick(self.s,now=10)['status'],'blocked')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_consequences').fetchone()[0],0)
  action=self.f.f.action(1);self.f.f.apply(action)
  self.assertIsNone(runtime.tick(self.s,now=16))
 def test_invalid_dependencies_unknown_tools_and_identity_reuse_fail(self):
  for modify in (lambda p:p['steps'][0].update(tool='native.arbitrary'),lambda p:p['steps'][0].update(after=['tell']),lambda p:p['steps'][1]['args'].update(text=dict(result='act',key='text'))):
   p=self.plan();modify(p)
   if p['steps'][0]['tool']=='world.act' and not p['steps'][0]['after']:p['steps'][1]['after']=[]
   with self.assertRaises(ValueError):runtime.validate(p)
  self.apply(self.plan());runtime.tick(self.s,now=10)
  changed=self.plan();changed['purpose']='Changed under the same identity.'
  with self.assertRaises(ValueError):self.apply(changed,1)

 def test_actual_tool_receipt_drives_next_model_turn_with_capability_context(self):
  self.apply(self.plan(revision=99))
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    reactions.configure(q,self.s.inspect(),'canon_rydel','Choose freely among supported tools.')
    self.assertEqual(reactions.observe(q,self.s.inspect(),self.f.f.fetch),[])
    result=runtime.tick(self.s,now=10)
    self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.f.f.fetch)),1)
    job=q.claim();ctx=self.f.f.context();ctx['runtime'].update(kind='character',observed_event=json.loads(job['result']))
    observed=reactions.prepare(ctx,self.f.f.fetch)
    self.assertIn('actor_runtime',ctx);self.assertIn('world.act',ctx['actor_runtime']['capabilities'])
    a=self.f.f.action(1);a['changes'].update(plan=self.plan('new_approach'),evidence=[result['seq']])
    reactions.check_response(dict(canonical_actions=[a],tests='assert True'),observed)
    self.f.f.apply(a);self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded')
   finally:q.close()
