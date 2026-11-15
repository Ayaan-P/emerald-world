"""Shared canonical choices use actual authenticated peers, not leader decisions."""
import json,tempfile,unittest
from copy import deepcopy
import test_canonical_cast as fixture
from world import canonical_cast as cast,character_reactions as reactions
from world.runtime_gm import IntentQueue
from world.guilds import GuildError

class CouncilTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.action=self.f.action();self.action['changes']['council']=dict(
    question='What should I consider while planning my next riding advice?',
    options=dict(explore='Independent exploration',together='Travelling together'))
  self.f.apply(self.action);self.a=self.f.peer();self.b=self.f.peer('Bob')
  for p in (self.a,self.b):cast.response(self.s,p,'a'*32 if p is self.a else 'b'*32,'rydel')
 def command(self,peer,*args):return cast.guild_command(self.s,peer,['rydel',*args])
 def events(self):return [e for e in self.s.memory.history()['events'] if e['event']=='canonical_council_agreed']
 def test_independent_answers_unanimous_result_and_actor_response(self):
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    reactions.configure(q,self.s.inspect(),'canon_rydel','Consider an actual shared preference while retaining your own priorities.')
    self.assertEqual(reactions.observe(q,self.s.inspect(),self.f.fetch),[])
    self.assertTrue(any('Unanimous' in s for s in self.command(self.a,'council')))
    self.command(self.a,'decide','1','explore')
    self.assertEqual(self.events(),[]);self.assertEqual(reactions.observe(q,self.s.inspect(),self.f.fetch),[])
    self.command(self.b,'decide','1','together');self.assertEqual(self.events(),[])
    # Neither the leader nor the last voter wins. Players may reconsider.
    self.command(self.b,'decide','1','explore');self.assertEqual(len(self.events()),1)
    event=self.events()[0];self.assertEqual((event['choice'],event['participants']),('explore',2))
    for private in ('Alice','Bob','a'*32,'b'*32):self.assertNotIn(private,json.dumps(event))
    self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.f.fetch)),1)
    item=q.claim();ctx=self.f.context();ctx['runtime'].update(kind='character',observed_event=json.loads(item['result']))
    response=self.f.action(1,'I will think about advice for independent riders without choosing their routes.')
    response['changes'].update(goal='Consider flexible riding advice while leaving each trainer independent',evidence=[event['seq']])
    reactions.check_response(dict(canonical_actions=[response],tests='assert True'),reactions.prepare(ctx,self.f.fetch));self.f.apply(response)
    self.assertEqual(cast.response(self.s,self.b,'b'*32,'rydel')['briefing'],response['changes']['dialogue'])
    self.assertEqual(self.s.objects,[]);self.assertEqual(self.s.db.execute('SELECT count(*) FROM core_story_progress').fetchone()[0],0)
   finally:q.close()
 def test_withdraw_membership_and_restart_do_not_inherit_votes(self):
  self.command(self.a,'decide','1','explore');self.command(self.a,'decide','1','withdraw')
  self.command(self.b,'decide','1','explore');self.assertEqual(self.events(),[])
  guild=self.s.guilds._require('Bob')[0]
  with self.s.db:
   self.s.db.execute('DELETE FROM guild_members WHERE trainer=?',('Bob',))
   self.s.db.execute('INSERT INTO guild_members VALUES(?,?)',('Bob',guild))
  self.command(self.a,'decide','1','explore');self.assertEqual(self.events(),[])
  self.s.close();self.f.f.case.server=self.f.f.case.open();self.s=self.f.f.case.server;self.f.s=self.s;self.f.f.server=self.s
  self.b=self.f.peer('Bob');cast.response(self.s,self.b,'b'*32,'rydel')
  self.command(self.b,'decide','1','explore');self.assertEqual(len(self.events()),1)
  self.command(self.b,'decide','1','together');self.assertEqual(len(self.events()),1)
 def test_requires_current_question_location_and_all_current_members(self):
  with self.assertRaises(GuildError):self.command(self.a,'decide','0','explore')
  with self.assertRaises(GuildError):self.command(self.a,'decide','1','invented')
  self.a['state'][6]=0
  with self.assertRaises(GuildError):self.command(self.a,'decide','1','explore')
  self.a['state'][6]=1
  guild=self.s.guilds._require('Alice')[0]
  with self.s.db:
   for name in ('Carol','Dave'):self.s.db.execute('INSERT INTO guild_members VALUES(?,?)',(name,guild))
  self.command(self.a,'decide','1','explore');self.command(self.b,'decide','1','explore')
  self.assertEqual(self.events(),[])
  for name in ('Carol','Dave'):
   peer=self.f.peer(name);cast.response(self.s,peer,'c'*32,'rydel');self.command(peer,'decide','1','explore')
  self.assertEqual(self.events()[0]['participants'],4)
