"""Real cast request -> independent response -> shared project consequence."""
import copy,json,tempfile,unittest
from unittest.mock import patch
import test_canonical_initiatives as fixture
from world import canonical_cast as cast,canonical_project_requests as requests,canonical_world_actions as actions,character_reactions as reactions
from world.runtime_gm import IntentQueue

class ProjectRequestTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.InitiativeTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.s=self.f.s;self.c=self.f.f
  self.c.apply(self.f.author());self.done=actions.step(self.s,now=10)
 def invite(self):
  a=self.c.action(1);a['changes'].update(evidence=[self.done['seq']],initiative=self.f.author()['changes']['initiative'],project_request=dict(id='second_view',to='canon_wally',action=dict(pack='workshop',scene='contribute',choice='join',place='LittlerootTown',revision=1),message='Would you add your own perspective to the discussion?'))
  self.c.apply(a)
  self.event=next(e for e in reversed(self.s.memory.history()['events']) if e['event']=='canonical_project_requested')
 def reply(self,decision='accept'):
  a=self.c.action(1);a['id']='canon_wally';a['changes'].update(evidence=[self.event['seq']],project_reply=dict(sender='canon_rydel',id='second_view',decision=decision,message='I can contribute a different perspective.' if decision=='accept' else 'I want to focus on my own preparation for now.'))
  return a
 def test_independent_recipient_acceptance_executes_role_and_informs_sender(self):
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    reactions.configure(q,self.s.inspect(),'canon_wally','Choose whether this project fits your priorities.')
    self.invite();self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.c.fetch)),1)
    item=q.claim();packet=json.loads(item['result']);self.assertEqual(packet['evidence'],self.event['seq'])
    ctx=self.c.context();ctx['runtime'].update(kind='character',observed_event=packet)
    reactions.check_response(dict(canonical_actions=[self.reply()],tests='assert True'),reactions.prepare(ctx,self.c.fetch))
    self.assertEqual(self.s.opportunities.offers('Alice','LittlerootTown')[0]['scenes'][0]['id'],'solo')
    self.c.apply(self.reply())
    self.assertEqual(self.s.opportunities.offers('Bob','LittlerootTown')[0]['scenes'][0]['id'],'shared')
    response=self.s.memory.history()['events'][-1];self.assertEqual(response['decision'],'accept');self.assertIsInstance(response['action_receipt'],int)
    self.assertEqual(requests.view(self.s)[0]['decision'],'accept')
    # A directional response to Wally's actual choice, not assumed reciprocity.
    a=self.c.action(2);a['changes'].update(evidence=[response['seq']],relationships=dict(canon_wally=dict(stance='respectful',motivation='Wally chose to contribute his perspective.',evidence=[response['seq']])))
    self.c.apply(a)
    self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_players').fetchone()[0],0)
    self.assertEqual(self.s.objects,[])
   finally:q.close()
  self.s.close();self.c.f.case.server=self.c.f.case.open();self.s=self.c.f.case.server
  self.assertEqual(requests.view(self.s)[0]['decision'],'accept')
  self.assertEqual(self.s.opportunities.offers('Alice','LittlerootTown')[0]['scenes'][0]['id'],'shared')
 def test_decline_changes_no_project_state_and_fake_recipient_rejected(self):
  self.invite();a=self.reply('decline');self.c.apply(a)
  response=self.s.memory.history()['events'][-1];self.assertIsNone(response['action_receipt'])
  self.assertEqual(self.s.opportunities.offers('Alice','LittlerootTown')[0]['scenes'][0]['id'],'solo')
  bad=self.c.action(2);bad['changes'].update(evidence=[self.event['seq']],project_reply=a['changes']['project_reply'])
  with self.assertRaises(ValueError):cast.compile_actions([bad],self.c.context())
 def test_withdrawal_and_receipt_failure_cannot_partially_execute(self):
  self.invite();before=self.s.inspect()['cast_initiatives']
  append=self.s.memory.append
  def fail(kind,data):
   if kind=='canonical_project_responded':raise ValueError('receipt unavailable')
   return append(kind,data)
  with patch.object(self.s.memory,'append',side_effect=fail),self.assertRaises(AssertionError):self.c.apply(self.reply())
  self.assertEqual(self.s.inspect()['cast_initiatives'],before);self.assertIsNone(requests.view(self.s)[0]['decision'])
  self.c.source=self.s.candidate.source
  a=self.c.action(2);a['changes']['evidence']=[self.event['seq']];self.c.apply(a) # withdraw request
  with self.assertRaises(AssertionError):self.c.apply(self.reply())
  self.assertEqual(self.s.inspect()['cast_initiatives'],before)
  self.assertIsNone(requests.view(self.s)[0]['decision'])
