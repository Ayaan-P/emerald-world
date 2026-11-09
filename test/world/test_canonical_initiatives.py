"""Executable actor-authored projects, not a live model or rendered native test."""
import copy,json,tempfile,unittest
from unittest.mock import patch
import test_canonical_cast as fixture
from test_canonical_world_actions import pack
from world import canonical_cast as cast, canonical_initiatives as initiatives
from world import canonical_world_actions as actions, character_reactions as reactions
from world.runtime_gm import IntentQueue

class InitiativeTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  a=self.f.action();a['id']='canon_wally';self.f.apply(a)
 def author(self):
  a=self.f.action();a['changes']['initiative']=pack()
  a['changes'].update(world_action=dict(pack='workshop',scene='organize',choice='open',place='LittlerootTown',revision=0),
     intentions=[dict(id='open_workshop',kind='world_action',target='workshop',reason='Open a shared discussion independently.')])
  return a
 def test_author_creates_executable_project_other_actor_chooses_and_relationship_grows(self):
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_packs').fetchone()[0],0)
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    reactions.configure(q,self.s.inspect(),'canon_wally','Independently consider public projects.')
    self.assertEqual(reactions.observe(q,self.s.inspect(),self.f.fetch),[])
    self.f.apply(self.author())
    state=self.s.inspect()['cast_initiatives'][0]
    self.assertEqual((state['owner'],state['places'][0]['revision']),('canon_rydel',0))
    self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.f.fetch)),1)
    self.assertTrue(initiatives.relevant(self.s.memory.history()['events'][-1],'canon_wally',cast.records(self.s.module_state)['canon_wally']))
    first=actions.step(self.s,now=10)
    self.assertEqual(first['status'],'completed')
    self.assertEqual(self.s.opportunities.offers('Alice','LittlerootTown')[0]['scenes'][0]['id'],'solo')
    # A distinct authored turn chooses participation; publication never does it.
    w=self.f.action(1);w['id']='canon_wally'
    w['changes'].update(evidence=[first['seq']],world_action=dict(pack='workshop',scene='contribute',choice='join',place='LittlerootTown',revision=1),
       intentions=[dict(id='add_perspective',kind='world_action',target='workshop',reason='Contribute a different perspective.')],
       relationships=dict(canon_rydel=dict(stance='encouraged',motivation='Rydel made room for a public discussion.',evidence=[first['seq']])))
    self.f.apply(w);second=actions.step(self.s,now=16)
    self.assertEqual(second['actor'],'canon_wally')
    r=self.f.action(1);r['changes'].update(initiative=pack(),evidence=[second['seq']],
       relationships=dict(canon_wally=dict(stance='respectful',motivation='Wally chose to add another perspective.',evidence=[second['seq']])))
    self.f.apply(r)
    for trainer in ('Alice','Bob'):
     self.assertEqual(self.s.opportunities.offers(trainer,'LittlerootTown')[0]['scenes'][0]['id'],'shared')
    self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_players').fetchone()[0],0)
    self.assertEqual(self.s.objects,[])
    peer=self.f.peer();self.assertTrue(any('/story workshop' in line for line in cast.guild_command(self.s,peer,['rydel','initiatives'])))
    self.assertIn('initiatives',bytes.fromhex(self.f.query(peer).split()[-1]).decode())
    self.assertEqual(self.s.inspect()['cast_initiatives'][0]['places'][0]['completed_scenes'],['organize','contribute'])
   finally:q.close()
  self.s.close();self.f.f.case.server=self.f.f.case.open();self.s=self.f.f.case.server
  self.assertEqual(self.s.inspect()['cast_initiatives'][0]['places'][0]['revision'],2)
  self.assertIsNone(actions.step(self.s,now=30))
  self.assertEqual(cast.records(self.s.module_state)['canon_rydel']['relationships']['canon_wally']['stance'],'respectful')
 def test_no_claimed_participation_or_private_data_and_immutable_ownership(self):
  for change in ('private','unknown','owner','mystery','player'):
   a=self.author();p=a['changes']['initiative']
   if change=='private':p['qualities']['stage']['scope']='player'
   elif change=='unknown':p['scenes']['contribute']['actors']=['canon_steven']
   elif change=='owner':p['scenes']['organize']['actors']=['canon_wally']
   elif change=='mystery':p['scenes']['solo']['mystery']='private'
   else:p['scenes']={k:v for k,v in p['scenes'].items() if 'actors' in v}
   with self.subTest(change=change),self.assertRaises(ValueError):cast.compile_actions([a],self.f.context())
  self.f.apply(self.author())
  published=self.s.memory.history()['events'][-1]['seq']
  a=self.f.action(1);a['id']='canon_wally'
  a['changes'].update(evidence=[published],relationships=dict(canon_rydel=dict(stance='respectful',motivation='A claimed contribution.',evidence=[published])))
  with self.assertRaisesRegex(ValueError,'relationship'):cast.compile_actions([a],self.f.context())
  # Even actual authority admission cannot replace content or seize ownership.
  c=dict(character_id='canon_wally',after=dict(initiative=pack(),evidence=[published],places=['native:LittlerootTown']))
  with self.assertRaisesRegex(ValueError,'owner'):initiatives.publish(self.s,c)
  c['character_id']='canon_rydel';c['after']['initiative']['title']='Replaced'
  with self.assertRaisesRegex(ValueError,'immutable'):initiatives.publish(self.s,c)
 def test_atomic_module_installation_and_no_repeat_publication(self):
  before=self.s.module_state.copy()
  original=self.s.memory.append
  def fail(kind,data):
   if kind=='canonical_initiative_published':raise ValueError('receipt unavailable')
   return original(kind,data)
  a=self.author();source=cast.compile_actions([a],self.f.context());ns={};exec(source,ns)
  result=ns['update'](self.s._context(),copy.deepcopy(self.s.module_state))
  with patch.object(self.s.memory,'append',side_effect=fail):
   with self.assertRaises(AssertionError):self.f.commit(source,result)
  self.assertEqual(self.s.module_state,before)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_packs').fetchone()[0],0)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_initiatives').fetchone()[0],0)
  # Use verified active source after the deliberately rejected candidate.
  self.f.source=self.s.candidate.source;self.f.apply(a)
  next_action=self.author();next_action['expected_version']=1
  self.f.apply(next_action)
  events=[e for e in self.s.memory.history()['events'] if e['event']=='canonical_initiative_published']
  self.assertEqual(len(events),1)
  from world.world_journal import describe
  self.assertEqual(describe(events[0])['title'],'Rydel opened a shared project')
