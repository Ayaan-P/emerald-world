"""Real authority catalogue snapshots and future-only anonymous projection."""
import unittest,time,json,tempfile
from copy import deepcopy
import test_core_story as fixture
import test_canonical_cast as cast_fixture
from world.campaign_milestones import MILESTONES,relevant
from world import canonical_cast as cast,character_reactions as reactions
from world.runtime_gm import IntentQueue

class MilestoneTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CoreStoryTests();self.f.setUp();self.addCleanup(self.f.tearDown);self.s=self.f.s
  self.f.place(self.f.a,'MauvilleCity');self.f.place(self.f.b,'MauvilleCity')
 def request(self,key,guard='private',conn=None,run=None):return self.f.request(conn or self.f.a,'MILE',key,guard,run=run)
 def events(self):return [e for e in self.s.memory.history()['events'] if e['event']=='canonical_campaign_milestone']
 def test_baseline_optin_rewind_restart_off_and_saves(self):
  self.assertTrue(self.request('3')['ok']);self.assertEqual(self.events(),[])
  self.assertTrue(self.request('on','confirm')['sharing']);self.assertEqual(self.events(),[])
  self.request('7');self.assertEqual([e['milestone'] for e in self.events()],['badge_3'])
  self.request('3');self.request('7');self.assertEqual(len(self.events()),1)
  self.request('511',conn=self.f.b);self.assertEqual(len(self.events()),1)
  self.request('511',run='b'*32);self.assertEqual(len(self.events()),1)
  self.s.close();self.f.s=self.f.open();self.s=self.f.s;self.f.a=self.f.connect('Alice');self.f.place(self.f.a,'MauvilleCity')
  self.request('15');self.assertEqual([e['milestone'] for e in self.events()],['badge_3','badge_4'])
  self.request('off','confirm');self.request('31');self.assertEqual(len(self.events()),2)
  self.request('on','confirm');self.request('63');self.assertEqual(self.events()[-1]['milestone'],'badge_6')
  text=json.dumps(self.events())
  for private in ('Alice','Bob','a'*32,'b'*32,'party','token'):self.assertNotIn(private,text)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM core_story_progress').fetchone()[0],0)
 def test_rejects_unbounded_stale_and_unnegotiated_input(self):
  self.assertIsNone(self.request('on','confirm'))
  for key in ('512','-1','0000','1.0','badge_1'):self.assertIsNone(self.request(key))
  self.f.a['state_time']-=10;self.assertIsNone(self.request('1'))
  peer=self.f.connect('Legacy',False);self.f.place(peer,'MauvilleCity');self.assertIsNone(self.request('1',conn=peer))
 def test_catalogue_uses_real_native_places_and_fixed_claims(self):
  from world.build_catalog import catalog_maps
  names={'native:'+m['name'] for m in catalog_maps().values()}
  self.assertTrue(all(m['place'] in names for m in MILESTONES))
  self.request('0');self.request('on','confirm');self.request('511')
  self.assertEqual(len(self.events()),9)
  for event in self.events():
   self.assertTrue(relevant(event,event['places']))
   self.assertFalse(relevant(dict(event,summary='The actor won a battle'),event['places']))

class CastMilestoneTests(unittest.TestCase):
 def test_real_badge_snapshot_prompts_existing_rydel_without_a_new_quest(self):
  f=cast_fixture.CanonicalCastTests();f.setUp();self.addCleanup(f.doCleanups);s=f.s
  action=f.action();action['changes']['places']=['native:LittlerootTown','native:MauvilleCity_Gym'];f.apply(action)
  peer=f.peer()
  def send(key,guard='private'):return s.core_story.handle(peer,['CORE','a'*32,'MILE',key,guard])
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    reactions.configure(q,s.inspect(),'canon_rydel','Consider real shared campaign events while preserving the bike service.')
    self.assertEqual(reactions.observe(q,s.inspect(),f.fetch),[])
    send('0');send('on','confirm');send('4')
    self.assertEqual(len(reactions.observe(q,s.inspect(),f.fetch)),1)
    item=q.claim();ctx=f.context();ctx['runtime'].update(kind='character',observed_event=json.loads(item['result']))
    event=next(e for e in s.memory.history()['events'] if e['event']=='canonical_campaign_milestone')
    action=f.action(1,'More trainers are progressing. I am reconsidering my riding advice.')
    action['changes'].update(places=['native:MauvilleCity_Gym'],evidence=[event['seq']],goal='Offer useful riding advice without assuming any particular trainers progress')
    reactions.check_response(dict(canonical_actions=[action],tests='assert True'),reactions.prepare(ctx,f.fetch));f.apply(action)
    self.assertEqual(cast.response(s,peer,'a'*32,'rydel')['briefing'],action['changes']['dialogue'])
    self.assertEqual(s.objects,[])
   finally:q.close()
