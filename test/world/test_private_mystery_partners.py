import json,unittest
import test_character_offers as fixture
from world import private_mystery_partners as partners

class PrivatePartners(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CharacterOfferTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.server
  self.a=self.f.peer('Alice','SOCIALCHATCOMMANDS1');self.b=self.f.peer('Bob','SOCIALCHATCOMMANDS1')
  obj=next(o for o in self.s.objects if o['id']=='field_researcher');self.point=[obj['group'],obj['num'],obj['x'],obj['y']]
  self.pack=dict(id='private_pair',title='Private pair',roles=['Visitor','Researcher'],ending='Puzzle completed.',stages=[dict(title='Two observations',stations=[dict(at=self.a['state'][:4],clue='FIRST_CLUE_ONLY'),dict(at=self.point,clue='SECOND_CLUE_ONLY')],answer='AB',result='The answer matched.')])
  self.s.mysteries.publish(self.pack);self.chat(self.a,'/mystery start private_pair');self.run=self.s.mysteries._current('Alice')[0]
 def chat(self,p,message):
  p['chat_credit']=4;self.s._line(p,f"CHAT {p['seq']+1} * {message.encode().hex()}".encode())
  lines=[bytes.fromhex(x[3]).decode() for x in p['chat_history']];p['chat_history']=[];return lines
 def ready(self):
  self.assertTrue(any('role reserved' in x for x in self.chat(self.a,'/mystery npc field_researcher')))
  self.chat(self.a,'/mystery clue');self.chat(self.a,'/mystery npc-send PRIVATE_PLAYER_MESSAGE')
 def admin(self,request):
  conn=dict(out=bytearray());self.s._admin_line(conn,json.dumps(request).encode());return json.loads(conn['out'])
 def test_actual_private_solver_completes_without_public_context_or_player_leak(self):
  self.ready();seen=[]
  def fake_private_solver(context):
   seen.append(context)
   self.assertEqual(context['station_clue'],'SECOND_CLUE_ONLY');self.assertEqual(context['partner_message'],'PRIVATE_PLAYER_MESSAGE')
   encoded=json.dumps(context)
   for forbidden in ('Alice','Bob','FIRST_CLUE_ONLY','"AB"',self.run,'save','party_hash'):
    self.assertNotIn(forbidden,encoded)
   return dict(action='solve',answer='AB')
  before=self.s.memory.history()['through']
  self.assertTrue(partners.process_one(self.s,'field_researcher',self.run,fake_private_solver)['ok'])
  self.assertTrue(self.s.mysteries.completed('Alice','private_pair'));self.assertFalse(self.s.mysteries.completed('Bob','private_pair'))
  self.assertEqual(self.s.memory.history()['through'],before)
  public=json.dumps(self.s.inspect())+json.dumps(self.s.memory.history())
  for private in ('FIRST_CLUE_ONLY','SECOND_CLUE_ONLY','PRIVATE_PLAYER_MESSAGE'):self.assertNotIn(private,public)
  self.assertTrue(any('Puzzle completed' in x for x in self.chat(self.a,'/mystery npc-status')))
  self.assertFalse(self.b['chat_history']);self.assertEqual(len(seen),1)
 def test_wrong_actor_and_invalid_public_action_refused_no_retry(self):
  self.ready()
  self.assertFalse(self.admin(dict(command='private_mystery_claim',actor='other',run=self.run))['ok'])
  job=self.admin(dict(command='private_mystery_claim',actor='field_researcher',run=self.run));self.assertTrue(job['ok'])
  self.assertFalse(self.admin(dict(command='private_mystery_finish',actor='other',lease=job['lease'],decision=dict(action='solve',answer='AB')))['ok'])
  self.assertFalse(self.admin(dict(command='private_mystery_finish',actor='field_researcher',lease=job['lease'],decision=dict(action='world.set_weather',answer='')))['ok'])
  self.assertTrue(self.admin(dict(command='private_mystery_finish',actor='field_researcher',lease=job['lease'],decision=dict(action='wait',answer='')))['ok'])
  self.assertFalse(self.admin(dict(command='private_mystery_finish',actor='field_researcher',lease=job['lease'],decision=dict(action='solve',answer='AB')))['ok'])
 def test_movement_cancel_and_new_actor_version_invalidate_claim(self):
  self.ready();job=partners.claim(self.s,'field_researcher',self.run)
  self.s.module_state['world_characters']['field_researcher']['version']+=1
  self.assertEqual(partners.finish(self.s,'field_researcher',job['lease'],dict(action='solve',answer='AB'))['status'],'stale')
  self.assertFalse(self.s.mysteries.completed('Alice','private_pair'))
  self.chat(self.a,'/mystery npc-send RETRY_MESSAGE');job=partners.claim(self.s,'field_researcher',self.run)
  self.chat(self.a,'/mystery leave')
  with self.assertRaises(ValueError):partners.finish(self.s,'field_researcher',job['lease'],dict(action='solve',answer='AB'))
  row=self.s.db.execute('SELECT message,lease,fingerprint FROM private_mystery_partners').fetchone();self.assertEqual(row,('',None,None))
 def test_no_canonical_or_fake_presence_and_no_automatic_provider(self):
  self.assertTrue(any('must already stand' in x for x in self.chat(self.a,'/mystery npc canon_wally')))
  self.s.objects[0]['x']+=1
  self.assertTrue(any('must already stand' in x for x in self.chat(self.a,'/mystery npc field_researcher')))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM private_mystery_partners').fetchone()[0],0)
 def test_incomplete_solver_leaves_claim_unresolved_and_private(self):
  self.ready()
  def fail(context):raise RuntimeError('fixture failure')
  with self.assertRaises(ValueError):partners.process_one(self.s,'field_researcher',self.run,fail)
  with self.assertRaises(ValueError):partners.claim(self.s,'field_researcher',self.run)
  self.assertEqual(self.s.db.execute('SELECT status FROM private_mystery_partners').fetchone()[0],'claimed')
  self.assertFalse(self.s.mysteries.completed('Alice','private_pair'))

 def test_restart_does_not_reclaim_or_leak_an_uncertain_turn(self):
  self.ready();job=partners.claim(self.s,'field_researcher',self.run)
  self.s.close();case=self.f.fixture.case;case.server=case.open();self.s=case.server;self.f.server=self.s
  with self.assertRaises(ValueError):partners.claim(self.s,'field_researcher',self.run)
  self.assertNotIn('PRIVATE_PLAYER_MESSAGE',json.dumps(self.s.inspect()))
  # Without the original player's fresh presence, late results fail closed.
  self.assertEqual(partners.finish(self.s,'field_researcher',job['lease'],dict(action='solve',answer='AB'))['status'],'stale')
  self.assertFalse(self.s.mysteries.completed('Alice','private_pair'))
 def test_private_receipt_failure_rolls_back_puzzle_completion(self):
  import sqlite3
  self.ready();job=partners.claim(self.s,'field_researcher',self.run)
  self.s.db.execute("CREATE TRIGGER fail_partner BEFORE UPDATE ON private_mystery_partners WHEN NEW.status='finished' BEGIN SELECT RAISE(ABORT,'fixture'); END")
  with self.assertRaises(sqlite3.Error):partners.finish(self.s,'field_researcher',job['lease'],dict(action='solve',answer='AB'))
  self.assertFalse(self.s.mysteries.completed('Alice','private_pair'))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM mystery_solved').fetchone()[0],0)
  self.assertEqual(self.s.db.execute('SELECT status FROM private_mystery_partners').fetchone()[0],'claimed')
