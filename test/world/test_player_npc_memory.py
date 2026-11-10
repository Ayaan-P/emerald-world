import copy,json,time,unittest,tempfile
from unittest.mock import patch
import test_npc_conversations as fixture
from world import player_npc_memory as memory,npc_conversations as speech,actor_runtime,character_reactions
from world.guilds import GuildError

class MemoryTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.ConversationTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s;self.p=self.f.peer
 def consent(self,p=None,actor='may'):
  p=p or self.p
  lines=speech.command(self.s,p,['remember-public',actor]);self.assertTrue(any('PUBLIC' in x for x in lines))
  self.assertIsNone(memory.current(self.s,p['id'],actor))
  speech.command(self.s,p,['remember-public',actor,p['npc_memory_offer']['token'],'yes'])
  return memory.current(self.s,p['id'],actor)['handle']
 def say(self,p=None,actor='may'):
  p=p or self.p;p['npc_speech_time']=-100
  speech.command(self.s,p,['say-public',actor,'Shall we train together?'])
  return self.s.db.execute('SELECT seq FROM player_npc_evidence ORDER BY seq DESC LIMIT 1').fetchone()[0]
 def appraisal(self,h,seq,battle='invite',actor='may'):
  with self.s.db:return memory.appraise(self.s,actor,{},dict(visitor=h,evidence=seq,text='I would like to try a friendly match.',battle=battle,greeting='A friendly match today?'))
 def challenge(self,p=None):
  p=p or self.p;p['state_time']=time.monotonic();v=self.s.module_state['world_characters']['may']['version']
  return self.f.f.send(p,'CHARACTER_CHALLENGE %s may %s'%(p['seq']+1,v))
 def events(self):return self.s.memory.history(limit=64)['events']
 def result(self,p=None):
  p=p or self.p;f=p['character_pending'];return self.f.f.send(p,'CHARACTER_RESULT %s may %s 1'%(f['seq'],f['version']))
 def test_consent_no_retroactive_link_and_personal_native_interaction(self):
  self.f.say();old=self.s.db.execute('SELECT seq FROM npc_public_speech').fetchone()[0]
  h=self.consent();self.assertFalse(memory.catalog(self.s)[0]['evidence'])
  with self.assertRaises(ValueError):self.appraisal(h,old)
  seq=self.say();self.appraisal(h,seq,'decline')
  bob=self.f.f.peer('Bob',role='SOCIALCHATCHAR1')
  self.assertIn('A friendly match today?'.encode().hex(),self.s._snapshot(self.p))
  self.assertNotIn('A friendly match today?'.encode().hex(),self.s._snapshot(bob))
  self.assertIn('CHARACTER_REJECT',self.challenge())
  self.assertIn('CHARACTER_BATTLE_V1',self.challenge(bob))
  self.appraisal(h,seq,'invite');self.assertIn('CHARACTER_BATTLE_V1',self.challenge())
  self.assertEqual(self.p['character_pending']['team'],self.f.f.character['team'])
  self.assertIn('CHARACTER_RESULT_ACK',self.result())
  report=next(e for e in self.events() if e['event']=='remembered_character_battle_report')
  self.assertEqual(report['visitor'],h);self.assertEqual(report['provenance'],'authenticated_client_report_not_verified_outcome')
  public=json.dumps([e for e in self.events() if e.get('basis')==memory.BASIS]);self.assertNotIn('Alice',public);self.assertNotIn('Bob',public)
 def test_revocation_inflight_and_new_consent_never_link_old_battle(self):
  h=self.consent();seq=self.say();self.appraisal(h,seq);self.assertIn('CHARACTER_BATTLE_V1',self.challenge())
  frozen=copy.deepcopy(self.p['character_pending'])
  speech.command(self.s,self.p,['stop-remembering','may']);self.assertEqual(self.p['character_pending'],frozen)
  with self.assertRaises(ValueError):self.appraisal(h,seq)
  with self.assertRaises(GuildError):self.consent() # Cannot grant while a battle is pending.
  self.assertIn('CHARACTER_RESULT_ACK',self.result())
  fresh=self.consent();self.assertNotEqual(fresh,h)
  self.assertFalse(any(e['event']=='remembered_character_battle_report' for e in self.events()))
  self.assertFalse(memory.catalog(self.s)[0]['evidence'])
  self.assertEqual(self.s.objects[0]['text'],self.f.f.npc['text'])
 def test_current_policy_beats_cached_menu_but_not_frozen_battle(self):
  h=self.consent();seq=self.say();self.appraisal(h,seq)
  cached=self.s._snapshot(self.p);self.assertIn('CHARACTER may',cached)
  self.appraisal(h,seq,'decline');self.assertIn('CHARACTER_REJECT',self.challenge())
  self.appraisal(h,seq,'invite');self.assertIn('CHARACTER_BATTLE_V1',self.challenge())
  frozen=copy.deepcopy(self.p['character_pending']);self.appraisal(h,seq,'decline')
  self.assertEqual(self.p['character_pending'],frozen);self.assertIn('CHARACTER_RESULT_ACK',self.result())
  self.assertIn('CHARACTER_REJECT',self.challenge())
 def test_scoped_receipts_expired_consent_and_restart(self):
  with self.assertRaises(GuildError):speech.command(self.s,self.p,['remember-public','may','invented','yes'])
  speech.command(self.s,self.p,['remember-public','may']);self.p['npc_memory_offer']['until']=0
  with self.assertRaises(GuildError):speech.command(self.s,self.p,['remember-public','may',self.p['npc_memory_offer']['token'],'yes'])
  h=self.consent();seq=self.say();self.appraisal(h,seq)
  bob=self.f.f.peer('Bob',role='SOCIALCHATCHAR1');other=self.consent(bob)
  with self.assertRaises(ValueError):self.appraisal(other,seq)
  with self.assertRaises(ValueError):self.appraisal(h,seq,actor='other')
  self.s.close();self.f.f.server=self.f.f.open();self.s=self.f.f.server;self.f.s=self.s
  self.assertEqual(memory.current(self.s,'Alice','may')['handle'],h)
  self.assertEqual(memory.current(self.s,'Bob','may')['appraisal'],'')
 def test_existing_anonymous_speech_and_battles_remain_unlinked(self):
  self.f.say();self.assertEqual(memory.catalog(self.s),[])
  self.assertIn('CHARACTER_BATTLE_V1',self.challenge());self.assertIn('CHARACTER_RESULT_ACK',self.result())
  self.assertFalse(any(e.get('basis')==memory.BASIS for e in self.events()))
 def test_author_queue_and_real_appraisal_capability(self):
  from world.runtime_gm import IntentQueue
  h=self.consent()
  with tempfile.TemporaryDirectory() as root:
   q=IntentQueue(root);self.addCleanup(q.close);character_reactions.configure(q,self.s.inspect(),'may','Choose how I respond to visitors.')
   seq=self.say();queued=character_reactions.observe(q,self.s.inspect(),self.f.fetch);self.assertTrue(queued)
   # Both anonymous speech and its consented linkage are real sources; the
   # normal bounded author queue may coalesce them. The appraiser must cite
   # the exact linked receipt, never the unlinked anonymous source.
   event=next(e for e in self.events() if e['seq']==seq);self.assertTrue(character_reactions.dynamic_result(event,'may',{}))
   c=copy.deepcopy(self.f.f.character);c['version']=2;c['evidence']=[seq]
   c['plan']=dict(id='appraise',purpose='Choose an optional interaction from the actual visitor message.',steps=[dict(id='decide',tool='world.appraise_player',args=dict(visitor=h,evidence=seq,text='I am interested in a friendly battle.',battle='invite',greeting='Care for a friendly match?'),after=[])])
   self.assertIsNone(self.f.f.commit({'may':c},self.f.f.npc))
   self.assertEqual(actor_runtime.tick(self.s,now=10)['status'],'succeeded')
   self.assertIn('Care for a friendly match?'.encode().hex(),self.s._snapshot(self.p));self.assertIn('CHARACTER_BATTLE_V1',self.challenge())

 def test_existing_campaign_binding_is_not_changed_by_social_decline(self):
  h=self.consent();seq=self.say();self.appraisal(h,seq,'decline')
  def campaign_bind(server,conn,frozen):frozen['campaign_binding']=['existing','run','node',0]
  with patch('world.battle_campaigns.bind',side_effect=campaign_bind):self.assertIn('CHARACTER_BATTLE_V1',self.challenge())
  self.assertNotIn('memory_binding',self.p['character_pending'])
 def test_revoked_appraisal_plan_fails_without_new_public_claim(self):
  h=self.consent();seq=self.say()
  c=copy.deepcopy(self.f.f.character);c['version']=2;c['evidence']=[seq]
  c['plan']=dict(id='late',purpose='An old queued reaction must not override revocation.',steps=[dict(id='decide',tool='world.appraise_player',args=dict(visitor=h,evidence=seq,text='A stale interpretation.',battle='decline',greeting='Not today.'),after=[])])
  self.assertIsNone(self.f.f.commit({'may':c},self.f.f.npc))
  speech.command(self.s,self.p,['stop-remembering','may'])
  self.assertEqual(actor_runtime.tick(self.s,now=10)['status'],'blocked')
  self.assertFalse(any(e['event']=='character_player_appraisal' for e in self.events()))
  self.assertEqual(self.s.db.execute('SELECT trainer FROM player_npc_memory WHERE handle=?',(h,)).fetchone()[0],'')

 def test_actual_chat_disclosure_and_confirmation_fit_native_messages(self):
  self.s.guild_chat.handle(self.p,'/guild npc remember-public may')
  lines=[bytes.fromhex(r[3]).decode() for r in self.p['chat_history']]
  self.assertTrue(any('PUBLIC to world' in x for x in lines))
  command=next(x[7:] for x in lines if x.startswith('Guild: /guild npc remember-public'))
  self.assertTrue(all(len(x)<=120 for x in lines))
  self.s.guild_chat.handle(self.p,command)
  self.assertIsNotNone(memory.current(self.s,'Alice','may'))
  self.s.guild_chat.handle(self.p,'/guild npc stop-remembering may')
  self.assertIsNone(memory.current(self.s,'Alice','may'))
 def test_appraisal_and_public_receipt_rollback_together(self):
  h=self.consent();seq=self.say();before=memory.current(self.s,'Alice','may');head=self.s.memory.history()['through']
  with self.assertRaises(RuntimeError):
   with self.s.db:
    memory.appraise(self.s,'may',{},dict(visitor=h,evidence=seq,text='An uncommitted interpretation.',battle='decline',greeting='Not today.'))
    raise RuntimeError('fixture transaction interrupted')
  self.assertEqual(memory.current(self.s,'Alice','may'),before)
  self.assertEqual(self.s.memory.history()['through'],head)
