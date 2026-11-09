"""Optional listeners advise; the actual speaker decides, including against advice."""
import json,tempfile,time,unittest
from copy import deepcopy
import test_canonical_cast as fixture
from world import canonical_cast as cast,character_reactions as reactions
from world.guilds import GuildError
from world.runtime_gm import IntentQueue

class SharedDialogueTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  action=self.f.action();action['changes'].update(
    council=dict(mode='speaker',question='What should I consider for my next advice?',options=dict(independent='Independent journeys',together='Travelling together')),
    conversation=dict(private=dict(label='My personal choice',reply='My private response is not shared.')))
  self.f.apply(action);self.a=self.f.peer();self.b=self.f.peer('Bob')
  for p in (self.a,self.b):cast.response(self.s,p,'a'*32 if p is self.a else 'b'*32,'rydel')
  self.command(self.a,'talk','1','private')
 def command(self,peer,*args):return cast.guild_command(self.s,peer,['rydel',*args])
 def open(self):
  self.command(self.b,'converse') # Bob is not the guild leader.
  return self.s.db.execute('SELECT id FROM canonical_dialogues').fetchone()[0]
 def events(self):return [e for e in self.s.memory.history()['events'] if e['event']=='canonical_speaker_decided']
 def test_listener_advice_speaker_choice_actor_response_and_restart(self):
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    reactions.configure(q,self.s.inspect(),'canon_rydel','Consider the speakers actual choice without inventing consensus.')
    self.assertEqual(reactions.observe(q,self.s.inspect(),self.f.fetch),[])
    identifier=self.open()
    with self.assertRaises(GuildError):self.command(self.a,'advise',identifier,'together')
    shared=self.command(self.a,'listen',identifier)
    self.assertNotIn('My private response',str(shared));self.assertTrue(any('public world history' in line for line in shared))
    self.command(self.a,'advise',identifier,'together');self.assertEqual(self.events(),[])
    self.assertEqual(reactions.observe(q,self.s.inspect(),self.f.fetch),[])
    with self.assertRaises(GuildError):self.command(self.a,'choose',identifier,'together') # Leader cannot override speaker.
    self.assertTrue(any('1 suggestions' in line for line in self.command(self.b,'conversation',identifier)))
    self.command(self.b,'choose',identifier,'independent') # Allowed against advice.
    event=self.events()[0];self.assertEqual(event['choice'],'independent');self.assertEqual(event['advice']['together'],1)
    for private in ('Alice','Bob','a'*32,'b'*32,'My private response'):self.assertNotIn(private,json.dumps(event))
    self.assertEqual(self.s.db.execute("SELECT choice FROM canonical_conversations WHERE trainer='Alice'").fetchone()[0],'private')
    self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_encounters').fetchone()[0],0)
    self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.f.fetch)),1)
    item=q.claim();ctx=self.f.context();ctx['runtime'].update(kind='character',observed_event=json.loads(item['result']))
    response=self.f.action(1,'I heard the speaker. I will consider flexible advice without assuming everyone agrees.')
    response['changes'].update(evidence=[event['seq']],goal='Consider independent riders while respecting the different suggestion')
    reactions.check_response(dict(canonical_actions=[response],tests='assert True'),reactions.prepare(ctx,self.f.fetch));self.f.apply(response)
    transcript=self.command(self.a,'conversation',identifier)
    self.assertIn(response['changes']['dialogue'],transcript)
    self.assertTrue(any('not group consensus' in line for line in transcript))
   finally:q.close()
  self.s.close();self.f.f.case.server=self.f.f.case.open();self.s=self.f.f.case.server;self.f.s=self.s;self.f.f.server=self.s
  self.a=self.f.peer();self.assertIn(response['changes']['dialogue'],self.command(self.a,'conversation',identifier))
  self.assertEqual(len(self.events()),1)
 def test_leave_expiry_and_actor_change_do_not_force_choices(self):
  identifier=self.open();self.command(self.a,'listen',identifier);self.command(self.a,'advise',identifier,'together')
  self.command(self.a,'leave',identifier)
  self.assertTrue(any('0 suggestions' in line for line in self.command(self.b,'conversation',identifier)))
  self.command(self.b,'leave',identifier);self.assertEqual(self.events(),[])
  with self.assertRaises(GuildError):self.command(self.b,'choose',identifier,'independent')
  identifier=self.open()
  with self.s.db:self.s.db.execute('UPDATE canonical_dialogues SET expires=?',(time.time()-1,))
  with self.assertRaises(GuildError):self.command(self.b,'choose',identifier,'independent')
  identifier=self.open();changed=self.f.action(1);self.f.apply(changed)
  with self.assertRaises(GuildError):self.command(self.b,'choose',identifier,'independent')
  self.assertEqual(self.events(),[])
 def test_unanimity_separate_opt_in_capacity_and_membership(self):
  with self.assertRaises(GuildError):self.command(self.b,'decide','1','independent')
  identifier=self.open();guild=self.s.guilds._require('Alice')[0]
  for name in ('Carol','Dave','Eve'):
   with self.s.db:self.s.db.execute('INSERT INTO guild_members VALUES(?,?)',(name,guild))
  self.command(self.a,'listen',identifier)
  for name in ('Carol','Dave'):
   peer=self.f.peer(name);cast.response(self.s,peer,'c'*32,'rydel');self.command(peer,'listen',identifier)
  outsider=self.f.peer('Eve');cast.response(self.s,outsider,'c'*32,'rydel')
  with self.assertRaises(GuildError):self.command(outsider,'listen',identifier)
  with self.s.db:self.s.db.execute("DELETE FROM guild_members WHERE trainer='Alice'")
  with self.assertRaises(GuildError):self.command(self.b,'choose',identifier,'independent')
  self.assertEqual(self.events(),[])
 def test_native_panel_uses_bound_cast_context_without_weakening_chat_ready(self):
  # Original native conversation scripts hold controls, so FIELD ready is zero.
  for peer in (self.a,self.b):peer['state'][6]=0
  with self.assertRaises(GuildError):self.command(self.b,'converse')
  def panel(peer,guard):return self.s.core_story.handle(peer,['CORE','a'*32 if peer is self.a else 'b'*32,'DIALOG','rydel',guard])
  view=panel(self.b,'view');self.assertEqual((view['role'],view['session'],len(view['options'])),(0,'-',2))
  opened=panel(self.b,'open:1');self.assertEqual(opened['role'],1);identifier=opened['session']
  joined=panel(self.a,'join:'+identifier+':1');self.assertEqual(joined['role'],2)
  panel(self.a,'pick:'+identifier+':1:2')
  chosen=panel(self.b,'pick:'+identifier+':1:1');self.assertEqual(chosen['role'],3)
  self.assertIn('Speaker chose Independent journeys',chosen['question'])
  self.assertEqual(self.events()[0]['choice'],'independent');self.assertEqual(self.events()[0]['advice']['together'],1)
  self.assertEqual(self.a['state'][6],0);self.assertEqual(self.b['state'][6],0)
  # A native operation cannot reuse another save, expired CAST or moved location.
  with self.assertRaises(ValueError):self.s.core_story.handle(self.a,['CORE','f'*32,'DIALOG','rydel','view'])
  self.a['canonical_location']['expires']=0
  with self.assertRaises(ValueError):panel(self.a,'view')
