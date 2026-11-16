import json,unittest
from copy import deepcopy
from unittest.mock import patch
import test_companion_exchange as fixture
from world import actor_runtime as runtime, companion_barter as barter, character_reactions
from world.character_companions import roster,descriptor

class BarterTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.ExchangeTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  state=deepcopy(self.s.module_state);c=state['world_characters']['visitor'];c['version']+=1
  c['team'].append(dict(individual='other_reserve',species=277,level=9));self.f.commit(state)
  state=deepcopy(self.s.module_state);state['world_characters']['visitor']['version']+=1;state['world_characters']['visitor']['team']=state['world_characters']['visitor']['team'][:1];self.f.commit(state)
 def propose(self,**changes):
  args=dict(target='visitor',give='reserve',receive='other_reserve',sender_alias='received_here',recipient_alias='received_there');args.update(changes)
  self.f.plan('harbor_guide','world.propose_exchange',args)
  self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded')
  return barter.offers(self.s)[0]['id']
 def accept(self,key,decision='accept',actor='visitor',now=20):
  self.f.plan(actor,'world.resolve_exchange',dict(offer=key,decision=decision));return runtime.tick(self.s,now=now)
 def test_independent_choice_both_identities_restart_and_real_lineup(self):
  before={a:roster(self.s,a) for a in ('harbor_guide','visitor')}
  key=self.propose()
  event=next(e for e in self.s.memory.history()['events'] if e['event']=='companion_barter_offered')
  self.assertTrue(character_reactions.dynamic_result(event,'visitor',{}))
  self.assertFalse(character_reactions.dynamic_result(event,'unrelated',{}))
  self.assertEqual({a:roster(self.s,a) for a in before},before)
  self.s.close();self.f.fx.f.server=self.f.fx.f.open();self.s=self.f.fx.f.server;self.f.s=self.s;self.f.fx.server=self.s
  self.assertEqual(self.accept(key)['status'],'succeeded')
  for actor,alias,previous_actor,old_alias in [('harbor_guide','received_here','visitor','other_reserve'),('visitor','received_there','harbor_guide','reserve')]:
   old=next(m for m in before[previous_actor] if m['individual']==old_alias)
   new=next(m for m in roster(self.s,actor) if m['individual']==alias)
   self.assertFalse(new['on_team'])
   self.assertEqual([new[k] for k in ('species','personality','owner','level')],[old[k] for k in ('species','personality','owner','level')])
   self.assertNotIn(old_alias,[m['individual'] for m in roster(self.s,previous_actor)])
  self.assertEqual(barter.offers(self.s),[])
  # Received individual enters the existing real team preparation/descriptor.
  self.f.plan('visitor','world.prepare_challenge',dict(lineup='["received_there"]',text='A friendly battle?'))
  self.assertEqual(runtime.tick(self.s,now=30)['status'],'pending')
  _,path,_=self.s.deployment;self.s.deployment=None;source=path.read_text();ns={};exec(source,ns)
  from world.mechanics import Candidate
  import hashlib
  self.f.fx.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
  self.f.fx.commit(ns['update'](self.s._context(),deepcopy(self.s.module_state)));self.assertIsNone(self.s.module_error)
  self.assertEqual(runtime.tick(self.s,now=40)['status'],'succeeded')
  old=next(m for m in before['harbor_guide'] if m['individual']=='reserve')
  self.assertEqual(descriptor(self.s,'visitor',self.s.module_state['world_characters']['visitor']['team']),[old['species'],old['level'],old['personality'],old['owner']])
 def test_failed_second_leg_rolls_back_first(self):
  key=self.propose(sender_alias='companion') # existing different on-team Pokemon
  before={a:roster(self.s,a) for a in ('harbor_guide','visitor')}
  self.assertEqual(self.accept(key)['status'],'blocked')
  self.assertEqual({a:roster(self.s,a) for a in before},before)
  self.assertEqual(barter.offers(self.s)[0]['status'],'offered')
 def test_final_receipt_failure_rolls_back_both_transfers(self):
  key=self.propose();before={a:roster(self.s,a) for a in ('harbor_guide','visitor')};original=runtime._receipt
  def fail(server,actor,row,plan,step,status,result):
   if actor=='visitor' and status=='succeeded':raise ValueError('injected receipt failure')
   return original(server,actor,row,plan,step,status,result)
  with patch.object(runtime,'_receipt',side_effect=fail):self.assertEqual(self.accept(key)['status'],'blocked')
  self.assertEqual({a:roster(self.s,a) for a in before},before)
  self.assertEqual(len(barter.offers(self.s)),1)
  self.assertFalse(any(e['event']=='companion_barter_resolved' for e in self.s.memory.history()['events']))
 def test_decline_withdraw_and_no_forced_acceptance(self):
  key=self.propose();self.assertEqual(self.accept(key,actor='harbor_guide')['status'],'blocked')
  self.assertEqual(self.accept(key,decision='decline',now=30)['status'],'succeeded')
  self.assertIn('reserve',[m['individual'] for m in roster(self.s,'harbor_guide')])
  self.assertEqual(self.accept(key,now=40)['status'],'blocked')
 def test_changed_team_or_recipient_location_blocks(self):
  key=self.propose();state=deepcopy(self.s.module_state);c=state['world_characters']['visitor'];c['version']+=1
  c['team'].append(dict(individual='other_reserve',species=277,level=9));self.f.commit(state)
  self.assertEqual(self.accept(key)['status'],'blocked')
 def test_two_full_states_preserved_exactly_without_exposing_bytes_in_inbox(self):
  states={}
  for actor,individual,level in [('harbor_guide','reserve',16),('visitor','other_reserve',9)]:
   mon=next(m for m in roster(self.s,actor) if m['individual']==individual)
   full=dict(size=100,species=mon['species'],level=level,personality=mon['personality'],owner=mon['owner'],exp=level**3,blob=('ab' if actor=='visitor' else 'cd')*100)
   states[actor]=full
   with self.s.db:self.s.db.execute('INSERT INTO character_training VALUES(?,?,?,?,?)',(actor,individual,'c'*64,level,json.dumps(full,sort_keys=True)))
  key=self.propose();self.assertNotIn('blob',json.dumps(barter.offers(self.s)))
  self.assertEqual(self.accept(key)['status'],'succeeded')
  from world.character_training import saved
  self.assertEqual(saved(self.s.db,'visitor','received_there')['state'],states['harbor_guide'])
  self.assertEqual(saved(self.s.db,'harbor_guide','received_here')['state'],states['visitor'])
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM character_training_receipts').fetchone()[0],0)
 def test_return_exchange_reuses_existing_aliases_without_duplication(self):
  before={a:roster(self.s,a) for a in ('harbor_guide','visitor')};key=self.propose()
  self.assertEqual(self.accept(key)['status'],'succeeded')
  self.f.plan('visitor','world.propose_exchange',dict(target='harbor_guide',give='received_there',receive='received_here',sender_alias='other_reserve',recipient_alias='reserve'))
  self.assertEqual(runtime.tick(self.s,now=30)['status'],'succeeded');key=barter.offers(self.s)[0]['id']
  self.assertEqual(self.accept(key,actor='harbor_guide',now=40)['status'],'succeeded')
  self.assertEqual({a:roster(self.s,a) for a in before},before)
 def test_actual_recipient_author_queue_receives_offer_not_forced_action(self):
  import tempfile
  from world.runtime_gm import IntentQueue
  with tempfile.TemporaryDirectory() as d:
   queue=IntentQueue(d)
   try:
    character_reactions.configure(queue,self.s.inspect(),'visitor','Choose freely whether a proposed exchange serves your goals.')
    key=self.propose()
    def fetch(query):return dict(ok=True,world_id=self.s.memory.world_id,**self.s.memory.history(**{k:v for k,v in query.items() if k!='command'}))
    queued=character_reactions.observe(queue,self.s.inspect(),fetch)
    self.assertEqual(len(queued),1)
    request=queue.claim();self.assertEqual(request['player'],'visitor')
    packet=json.loads(request['result']);event=next(e for e in self.s.memory.history()['events'] if e['seq']==packet['evidence'])
    self.assertEqual(event['offer'],key)
    context=self.s.inspect();context['runtime']=dict(kind='character',observed_event=packet)
    prepared=character_reactions.prepare(context,fetch);self.assertEqual(prepared['id'],'visitor')
    self.assertIn('reserve',[m['individual'] for m in roster(self.s,'harbor_guide')])
   finally:queue.close()
 def test_sender_can_withdraw_and_no_second_unresolved_pair(self):
  key=self.propose()
  self.f.plan('visitor','world.propose_exchange',dict(target='harbor_guide',give='other_reserve',receive='reserve',sender_alias='next',recipient_alias='next'))
  self.assertEqual(runtime.tick(self.s,now=20)['status'],'blocked')
  self.assertEqual(self.accept(key,decision='withdraw',actor='harbor_guide',now=30)['status'],'succeeded')
  self.assertEqual(barter.offers(self.s),[])
  self.assertIn('reserve',[m['individual'] for m in roster(self.s,'harbor_guide')])
