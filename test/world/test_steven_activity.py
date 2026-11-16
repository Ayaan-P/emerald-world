"""Real public goal -> original Steven -> authenticated expedition -> next intent.

The author response is a deterministic fixture, not a live model inference.
"""
from copy import deepcopy
import json,tempfile,time,unittest
import test_canonical_cast as fixture
from world import canonical_cast as cast,character_reactions as reactions
from world.build_catalog import catalog_maps
from world.guilds import GuildError
from world.runtime_gm import IntentQueue

class StevenActivityTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  a=self.f.action();a['id']='canon_steven'
  a['changes'].update(goal='Compare field observations before proposing further exploration',
      dialogue='I would like to compare the field teams observations before choosing another route.',
      offer=dict(map='LittlerootTown',count=2))
  self.f.apply(a);self.c=self.f.peer();self.f.f.connections['Alice']=self.c
 def place(self,name='MossdeepCity_StevensHouse'):
  self.c['state'][:2]=next(p for p,m in catalog_maps().items() if m['name']==name)
  self.c['state_time']=time.monotonic()
 def talk(self):
  return self.s.core_story.handle(self.c,['CORE','a'*32,'CAST','steven','safe'])
 def test_original_steven_goal_real_completion_and_retained_social_response(self):
  self.place()
  with self.assertRaises(GuildError):cast.guild_command(self.s,self.c,['steven'])
  self.assertEqual(self.talk()['actor'],'canon_steven')
  self.assertIn('Public guild expedition',cast.guild_command(self.s,self.c,['steven'])[1])
  self.f.f.command('chronicle off')
  with self.assertRaises(GuildError):cast.guild_command(self.s,self.c,['steven','1'])
  self.f.f.command('chronicle on')
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    reactions.configure(q,self.s.inspect(),'canon_steven','Choose a new exploration priority from actual field results.')
    self.assertEqual(reactions.observe(q,self.s.inspect(),self.f.fetch),[])
    self.f.f.command('cast steven 1')
    # Accepting is not a visit, expedition completion, or Steven's own travel.
    self.assertEqual(self.f.f.stats()[0],10)
    self.f.f.state('Alice');self.f.f.state('Bob')
    event=self.f.f.events()[-1]
    self.assertEqual(event['character_id'],'canon_steven');self.assertEqual(self.f.f.stats()[0],20)
    self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.f.fetch)),1)
    item=q.claim();self.assertEqual(item['player'],'canon_steven')
    # A second established actor must exist before an intention can name him.
    b=self.f.action();b['id']='canon_briney';self.f.apply(b)
    a=self.f.action(1);a['id']='canon_steven'
    a['changes'].update(goal='Ask Briney which observations warrant coastal exploration',
       dialogue='Those field visits give us a starting point. I want Brineys perspective.',
       evidence=[event['seq']],offer=None,
       intentions=[dict(id='consult_briney',kind='letter',target='canon_briney',reason='Seek a different perspective on the actual field results.')])
    ctx=self.f.context();ctx['runtime'].update(kind='character',observed_event=json.loads(item['result']))
    reactions.check_response(dict(canonical_actions=[a],tests='assert True'),reactions.prepare(ctx,self.f.fetch))
    self.f.apply(a);q.finish(item['id'],'succeeded',dict(ok=True))
    # Retained initiative uses the existing queue, not a fabricated meeting.
    self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.f.fetch)),1)
    intention=q.claim();self.assertEqual(json.loads(intention['result'])['intention']['id'],'consult_briney')
    done=deepcopy(a);done['expected_version']=2
    done['changes'].update(intentions=[],fulfill='consult_briney',
       letter=dict(to='canon_briney',text='Briney, which coastal route would help us compare these field observations?'))
    self.f.apply(done)
    letters=[e for e in self.s.memory.history()['events'] if e['event']=='canonical_letter_delivered']
    self.assertEqual((letters[-1]['sender'],letters[-1]['recipient']),('canon_steven','canon_briney'))
    self.assertEqual(self.s.objects,[])
    self.place();self.assertIn('Brineys perspective',self.talk()['briefing'])
   finally:q.close()
  self.s.close();self.f.f.case.server=self.f.f.case.open();self.s=self.f.f.case.server
  self.assertEqual(cast.records(self.s.module_state)['canon_steven']['goal'],a['changes']['goal'])
  self.assertEqual(self.s.db.execute("SELECT count(*) FROM canonical_intent_receipts WHERE actor='canon_steven'").fetchone()[0],1)
 def test_location_and_private_player_boundaries(self):
  self.place();self.talk();other=self.f.peer('Bob');other['state']=self.c['state'][:];other['state_time']=time.monotonic()
  with self.assertRaises(GuildError):cast.guild_command(self.s,other,['steven'])
  self.place('LittlerootTown')
  with self.assertRaises(ValueError):self.talk()
  with self.assertRaises(GuildError):cast.guild_command(self.s,self.c,['steven'])
