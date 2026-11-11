import copy,json,tempfile,time,unittest
from unittest.mock import patch
import test_cooperative_moves as fixture
from world import place_conversations as places,npc_conversations as speech,character_reactions
from world.guilds import GuildError

class PlaceConversations(unittest.TestCase):
 def setUp(self):
  self.f=fixture.Cooperative();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
 def changed(self):
  a=self.s.peers.get('UserOne') or self.f.peer('UserOne');b=self.f.peer('UserTwo')
  self.f.f.f.f.f.f.state(a,*self.s.wilds_map,72,69);a['state'][4]=1
  self.f.act(a,'charge');self.f.admit(1);self.f.act(b,'charge');self.f.admit(2);self.f.act(a,'release');self.f.admit(3)
  p=self.s.peers['UserOne'];self.f.f.f.f.f.f.state(p,*self.s.wilds_map,71,70);return p
 def confirm(self,p):
  speech.command(self.s,p,['show-place','harbor_guide','mechanism'])
  return speech.command(self.s,p,['show-place','harbor_guide','mechanism',p['place_conversation_offer']['token']])
 def test_committed_shared_change_then_independent_visible_response(self):
  p=self.changed();before=copy.deepcopy(self.s.objects)
  with tempfile.TemporaryDirectory() as root:
   from world.runtime_gm import IntentQueue
   q=IntentQueue(root);self.addCleanup(q.close)
   character_reactions.configure(q,self.s.inspect(),'harbor_guide','Decide what this changed place means for my own goals.')
   self.confirm(p)
   event=json.loads(self.s.db.execute("SELECT data FROM events WHERE kind='world_memory' ORDER BY seq DESC LIMIT 1").fetchone()[0]);event['seq']=self.s.db.execute("SELECT max(seq) FROM events WHERE kind='world_memory'").fetchone()[0];facts=event['place_evidence'];self.assertEqual(facts['phase'],'on')
   self.assertEqual(event['event'],'player_addressed_character');self.assertEqual(self.s.objects,before)
   self.assertNotIn('UserOne',json.dumps(event));self.assertNotIn('UserTwo',json.dumps(event));self.assertNotIn('cooperators',json.dumps(facts))
   self.assertTrue(self.s.db.execute('SELECT 1 FROM object_transition_archive WHERE seq=?',(facts['transition_receipt'],)).fetchone())
   fetch=lambda query:dict(ok=True,world_id=self.s.memory.world_id,**self.s.memory.history(**{k:v for k,v in query.items() if k!='command'}))
   jobs=character_reactions.observe(q,self.s.inspect(),fetch);self.assertEqual(len(jobs),1)
   packet=json.loads(q.db.execute('SELECT result FROM requests WHERE id=?',(jobs[0],)).fetchone()[0]);self.assertEqual(packet['evidence'],event['seq'])
   # Explicit fixture decision through the real capability executor, not an LLM playtest.
   from world import actor_runtime
   state=copy.deepcopy(self.s.module_state);actor=state['world_characters']['harbor_guide'];actor['version']+=1
   actor['plan']=dict(id='place_reply',purpose='Acknowledge the demonstrated current mechanism.',steps=[dict(id='reply',tool='world.reply_player',args=dict(speech=event['seq'],text='The panel has changed. I will inspect it before deciding.'),after=[])])
   base=self.f.f.f.f.f.f;base.commit(dict(state=state,objects=self.s.objects,tiles=[]));self.assertIsNone(self.s.module_error)
   self.assertEqual(actor_runtime.tick(self.s,now=500)['status'],'succeeded')
   speech.flush(self.s)
   self.assertTrue(any('The panel has changed.' in bytes.fromhex(m[3]).decode() for m in p['chat_history']))
   self.assertEqual(character_reactions.observe(q,self.s.inspect(),fetch),[])
 def test_uncommitted_phase_and_stale_confirmation_rejected(self):
  p=self.f.peer('UserOne');self.f.f.f.f.f.f.state(p,*self.s.wilds_map,71,70)
  with self.assertRaises(GuildError):speech.command(self.s,p,['show-place','harbor_guide','mechanism'])
  p=self.changed();speech.command(self.s,p,['show-place','harbor_guide','mechanism']);token=p['place_conversation_offer']['token']
  self.s.module_state['world_characters']['harbor_guide']['version']+=1
  with self.assertRaises(GuildError):speech.command(self.s,p,['show-place','harbor_guide','mechanism',token])
 def test_foreign_expired_and_repeated_confirmation_fail(self):
  p=self.changed();speech.command(self.s,p,['show-place','harbor_guide','mechanism']);token=p['place_conversation_offer']['token']
  other=self.s.peers['UserTwo'];self.f.f.f.f.f.f.state(other,*self.s.wilds_map,71,70)
  with self.assertRaises(GuildError):speech.command(self.s,other,['show-place','harbor_guide','mechanism',token])
  p['place_conversation_offer']['expires']=0
  with self.assertRaises(GuildError):speech.command(self.s,p,['show-place','harbor_guide','mechanism',token])
  self.confirm(p)
  with self.assertRaises(GuildError):speech.command(self.s,p,['show-place','harbor_guide','mechanism',token])
 def test_no_personal_memory_link_even_when_already_enrolled(self):
  p=self.changed()
  with patch('world.player_npc_memory.speech',side_effect=AssertionError('must not link')):self.confirm(p)
 def test_restart_retains_real_change_but_not_confirmation_or_live_audience(self):
  p=self.changed();self.confirm(p)
  self.s.close();base=self.f.f.f.f.f.f.f;base.server=base.open();self.s=base.server
  saved=self.s.db.execute('SELECT seq,actor FROM npc_public_speech ORDER BY seq DESC LIMIT 1').fetchone()
  with self.s.db:speech.reply(self.s,saved[1],{},dict(speech=saved[0],text='I can still inspect the changed panel.'))
  speech.flush(self.s)
  self.assertEqual(self.s.db.execute('SELECT delivery FROM npc_public_speech WHERE seq=?',(saved[0],)).fetchone()[0],'not_nearby')
  self.assertEqual(self.s.module_state['world_object_network_state']['mechanism']['phase'],'on')
 def test_local_discovery_and_preview_show_actual_objects(self):
  p=self.changed();rows=speech.command(self.s,p,['show-place','harbor_guide'])
  self.assertTrue(any('mechanism' in r for r in rows))
  rows=speech.command(self.s,p,['show-place','harbor_guide','mechanism'])
  for identity in ('fixture','panel'):
   obj=next(o for o in self.s.objects if o['id']==identity)
   self.assertTrue(any(obj['text'] in r for r in rows))
 def test_range_and_different_region_fail(self):
  p=self.changed();p['state'][2]=90
  with self.assertRaises(GuildError):self.confirm(p)
 def inspect_args(self):
  from world.campaign_mechanisms import definition,fingerprint
  return dict(network='mechanism',definition=fingerprint(self.s,definition(self.s,'mechanism')))
 def test_receipt_first_reference_change_then_optional_service_and_challenge(self):
  from world import actor_runtime,actor_tutors
  from world.battle_campaigns import publish,command,active
  # Players act before any resident plan or campaign exists. No witness enrollment.
  p=self.changed();self.assertIsNone(active(self.s,p));before=copy.deepcopy(self.s.objects)
  args=self.inspect_args()
  state=copy.deepcopy(self.s.module_state);actor=state['world_characters']['harbor_guide'];actor['version']+=1
  actor['plan']=dict(id='consider_changed_place',purpose='Consider offering visitors a useful training opportunity.',steps=[
   dict(id='look',tool='world.inspect_place_change',args=args,after=[]),
   dict(id='offer',tool='world.offer_tutoring',args=dict(move=164),after=['look'],when=dict(step='look',path='/phase',equals='on'))])
  base=self.f.f.f.f.f.f;base.commit(dict(state=state,objects=self.s.objects,tiles=[]));self.assertIsNone(self.s.module_error)
  self.assertEqual(actor_runtime.tick(self.s,now=500)['step'],'look')
  result=json.loads(self.s.db.execute("SELECT result FROM actor_tool_receipts WHERE plan='consider_changed_place' AND step='look'").fetchone()[0])
  self.assertTrue(result['committed']);self.assertNotIn('UserOne',json.dumps(result));self.assertNotIn('cooperators',json.dumps(result))
  # Restart between independently authored inspection and service decision.
  self.s.close();root=self.f.f.f.f.f.f.f;root.server=root.open();self.s=root.server
  self.assertEqual(actor_runtime.tick(self.s,now=510)['step'],'offer')
  self.assertIsNone(actor_runtime.tick(self.s,now=520))
  self.assertEqual(actor_tutors.catalog(self.s)['offers']['harbor_guide']['move'],164)
  self.assertIn('164',actor_tutors.line(self.s,dict(character_tutor_capable=True),'harbor_guide',actor['version']))
  self.assertIsNone(actor_tutors.line(self.s,{},'harbor_guide',actor['version']))
  self.assertEqual(self.s.objects,before)
  # An optional challenge alongside the freely usable place, not the tutor's prerequisite.
  doc=dict(id='optional_practice',title='Optional practice',entry='try',nodes={'try':dict(opponent='harbor_guide',win=[],loss=[],decline=[])})
  with self.s.db:publish(self.s,'harbor_guide',{},dict(campaign=json.dumps(doc)))
  visitor=dict(id='ReturningVisitor',campaign_run='a'*32)
  command(self.s,visitor,['start','optional_practice']);command(self.s,visitor,['decline-challenge'])
  self.assertNotIn('outcome',active(self.s,visitor)[1]['history'][0])
  self.assertEqual(actor_tutors.catalog(self.s)['offers']['harbor_guide']['move'],164)
 def test_uncommitted_place_does_not_open_conditional_service(self):
  from world import actor_runtime,actor_tutors
  state=copy.deepcopy(self.s.module_state);actor=state['world_characters']['harbor_guide'];actor['version']+=1
  actor['plan']=dict(id='inspect_initial',purpose='Do not assume initial scenery was changed.',steps=[
   dict(id='look',tool='world.inspect_place_change',args=self.inspect_args(),after=[]),
   dict(id='offer',tool='world.offer_tutoring',args=dict(move=164),after=['look'],when=dict(step='look',path='/committed',equals=True))])
  self.f.f.f.f.f.f.commit(dict(state=state,objects=self.s.objects,tiles=[]))
  self.assertEqual(actor_runtime.tick(self.s,now=500)['status'],'succeeded')
  actor_runtime.tick(self.s,now=510)
  self.assertNotIn('harbor_guide',actor_tutors.catalog(self.s)['offers'])
 def test_receipt_reconciliation_rejects_declared_stale_or_remote_state(self):
  args=self.inspect_args();actor=self.s.module_state['world_characters']['harbor_guide']
  self.assertFalse(places.inspect_change(self.s,'harbor_guide',actor,args)['committed'])
  self.changed();self.assertTrue(places.inspect_change(self.s,'harbor_guide',actor,args)['committed'])
  with self.assertRaises(ValueError):places.inspect_change(self.s,'harbor_guide',actor,dict(args,definition='wrong'))
  # A newer unreceipted control mutation is not historical proof of the present.
  self.s.module_state['world_object_controls']['fixture']['state']['uncommitted']=True
  self.assertFalse(places.inspect_change(self.s,'harbor_guide',actor,args)['committed'])
  obj=next(o for o in self.s.objects if o['id']=='harbor_guide');obj['x']+=20
  with self.assertRaises(ValueError):places.inspect_change(self.s,'harbor_guide',actor,args)
if __name__=='__main__':unittest.main()
