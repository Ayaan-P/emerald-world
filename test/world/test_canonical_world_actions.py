"""Independent actor decisions change real shared opportunities, not player records."""
import copy,json,tempfile,unittest
from unittest.mock import patch
import test_canonical_cast as fixture
from world import canonical_cast as cast,canonical_world_actions as actions,character_reactions as reactions
from world.runtime_gm import IntentQueue


def pack():
 return dict(id='workshop',title='Community workshop',qualities=dict(stage=dict(scope='place',initial=0,max=2)),scenes=dict(
  organize=dict(place='LittlerootTown',text='Choose whether to organize a public discussion.',requires=dict(stage=[0,0]),once='world',actors=['canon_rydel'],choices=dict(open=dict(text='Open the discussion',requires={},effects=dict(stage=1),result='The public discussion is now available.'))),
  contribute=dict(place='LittlerootTown',text='Choose whether to add a second perspective.',requires=dict(stage=[1,1]),once='world',actors=['canon_wally'],choices=dict(join=dict(text='Contribute a perspective',requires={},effects=dict(stage=1),result='Two perspectives are available for discussion.'))),
  solo=dict(place='LittlerootTown',text='Rydel has opened a public discussion.',requires=dict(stage=[1,1]),once='player',choices=dict(read=dict(text='Read the cycling perspective',requires={},effects=dict(stage=1),result='The discussion has moved forward.'))),
  shared=dict(place='LittlerootTown',text='Rydel and Wally have both contributed to this discussion.',requires=dict(stage=[2,2]),once='player',choices=dict(consider=dict(text='Consider the two perspectives',requires={},effects=dict(stage=-1),result='You considered the public perspectives.')))))

class WorldActionTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.s.opportunities.publish(pack())
 def actor(self,identity='canon_rydel',version=0,revision=0,scene='organize',choice='open',evidence=None):
  a=self.f.action(version);a['id']=identity
  a['changes'].update(world_action=dict(pack='workshop',scene=scene,choice=choice,place='LittlerootTown',revision=revision),
     intentions=[dict(id='discussion',kind='world_action',target='workshop',reason='Make a public discussion available without a player errand.')])
  if evidence:a['changes']['evidence']=[evidence]
  return a
 def test_two_independent_actions_change_player_opportunities_and_survive_restart(self):
  self.f.apply(self.actor());w=self.f.action();w['id']='canon_wally';self.f.apply(w)
  self.assertEqual(self.s.opportunities.offers('Alice','LittlerootTown'),[])
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_players').fetchone()[0],0)
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    reactions.configure(q,self.s.inspect(),'canon_wally','Consider whether to contribute independently.')
    self.assertEqual(reactions.observe(q,self.s.inspect(),self.f.fetch),[])
    first=actions.step(self.s,now=10);self.assertEqual(first['status'],'completed')
    self.assertEqual(self.s.opportunities.offers('Alice','LittlerootTown')[0]['scenes'][0]['id'],'solo')
    self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.f.fetch)),1)
    item=q.claim();ctx=self.f.context();ctx['runtime'].update(kind='character',observed_event=json.loads(item['result']))
    next_action=self.actor('canon_wally',1,1,'contribute','join',first['seq'])
    reactions.check_response(dict(canonical_actions=[next_action],tests='assert True'),reactions.prepare(ctx,self.f.fetch));self.f.apply(next_action)
    self.assertEqual(actions.step(self.s,now=16)['actor'],'canon_wally')
    for name in ('Alice','Bob'):
     available=self.s.opportunities.offers(name,'LittlerootTown')[0]
     self.assertEqual([s['id'] for s in available['scenes']],['shared'])
    peer=self.f.peer();from world.build_catalog import catalog_maps
    peer['state'][:2]=next(pair for pair,m in catalog_maps().items() if m['name']=='LittlerootTown')
    peer['chat_credit']=4
    self.s._line(peer,('CHAT 1 * '+('/story workshop'.encode().hex())).encode())
    visible=[bytes.fromhex(line[3]).decode() for line in peer['chat_history']]
    self.assertTrue(any('Rydel and Wally' in line for line in visible))
    self.assertTrue(any('/story pick workshop shared consider' in line for line in visible))
    from world.world_journal import describe
    self.assertIn('Wally changed',describe(self.s.memory.history()['events'][-1])['title'])
    self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_players').fetchone()[0],0)
    self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_receipts').fetchone()[0],0)
    self.assertEqual(self.s.objects,[]) # No duplicate or alleged physical cast travel.
   finally:q.close()
  self.s.close();self.f.f.case.server=self.f.f.case.open();self.s=self.f.f.case.server;self.f.s=self.s
  self.assertIsNone(actions.step(self.s,now=30))
  self.assertEqual(self.s.opportunities.offers('Bob','LittlerootTown')[0]['scenes'][0]['id'],'shared')
 def test_player_turns_private_qualities_and_false_completion_are_not_available(self):
  p=pack();p['qualities']['secret']=dict(scope='player',initial=0,max=2)
  p['scenes']['organize']['choices']['open']['effects']['secret']=1
  with self.assertRaisesRegex(ValueError,'player qualities'):self.s.opportunities.publish(p)
  # Real players cannot consume the actor's turn, even by guessing its identifiers.
  with self.assertRaises(ValueError):self.s.opportunities.choose('Alice','LittlerootTown','workshop','organize','open',0,'try')
  bad=self.actor();bad['changes']['world_action']['scene']='solo';bad['changes']['world_action']['choice']='read';self.f.apply(bad)
  self.assertEqual(actions.step(self.s,now=10)['status'],'waiting')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_consequences').fetchone()[0],0)
  fake=copy.deepcopy(bad);fake['expected_version']=1;fake['changes'].update(intentions=[],fulfill='discussion')
  with self.assertRaisesRegex(ValueError,'authority state commit'):cast.compile_actions([fake],self.f.context())
 def test_stale_or_withdrawn_action_and_receipt_failure_leave_world_unchanged(self):
  a=self.actor();a['changes']['world_action']['revision']=99;self.f.apply(a)
  self.assertEqual(actions.step(self.s,now=10)['status'],'waiting')
  a=self.actor(version=1);self.f.apply(a)
  with patch.object(self.s.memory,'append',side_effect=ValueError('receipt refused')):
   self.assertEqual(actions.step(self.s,now=16)['status'],'waiting')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_places').fetchone()[0],0)
  a=self.f.action(2);self.f.apply(a)
  self.assertIsNone(actions.step(self.s,now=22))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_intent_receipts').fetchone()[0],0)

 def test_authority_loop_dispatch_and_actor_scope(self):
  import inspect
  source=inspect.getsource(type(self.s)._loop)
  self.assertLess(source.index('self._poll_mechanics()'),source.index('step_cast_world_action(self)'))
  self.assertEqual(self.s.inspect()['cast_world_actions'][0]['actors'],['canon_rydel'])
  action=self.actor('canon_briney');self.f.apply(action)
  self.assertEqual(actions.step(self.s,now=10)['status'],'waiting')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_places').fetchone()[0],0)

 def test_obstruction_drives_independent_replanning_and_real_shared_result(self):
  # Wally commits a plan before Rydel changes the shared discussion. No player
  # performs either actor's action or advances a save flag.
  self.f.apply(self.actor('canon_wally',scene='contribute',choice='join'))
  self.f.apply(self.actor())
  self.assertEqual(actions.step(self.s,now=10)['actor'],'canon_rydel')
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    reactions.configure(q,self.s.inspect(),'canon_wally','Reconsider your own plans when circumstances change.')
    self.assertEqual(reactions.observe(q,self.s.inspect(),self.f.fetch),[])
    blocked=actions.step(self.s,now=16)
    self.assertEqual(blocked['status'],'waiting')
    event=self.s.memory.history()['events'][-1]
    self.assertEqual(event['event'],'canonical_action_obstructed')
    self.assertEqual(event['character_id'],'canon_wally')
    self.assertFalse(actions.obstruction_relevant(event,'canon_briney'))
    self.assertEqual(self.s.opportunities.offers('Alice','LittlerootTown')[0]['scenes'][0]['id'],'solo')
    self.assertIsNone(self.s.db.execute("SELECT 1 FROM canonical_intent_receipts WHERE actor='canon_wally'").fetchone())
    before=self.s.memory.history()['through']
    self.assertEqual(actions.step(self.s,now=22)['seq'],blocked['seq'])
    self.assertEqual(self.s.memory.history()['through'],before)
    self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.f.fetch)),1)
    item=q.claim();ctx=self.f.context();ctx['runtime'].update(kind='character',observed_event=json.loads(item['result']))
    repair=self.actor('canon_wally',1,1,'contribute','join',blocked['seq'])
    reactions.check_response(dict(canonical_actions=[repair],tests='assert True'),reactions.prepare(ctx,self.f.fetch))
    self.f.apply(repair)
    result=actions.step(self.s,now=28)
    self.assertEqual(result['status'],'completed')
    self.assertEqual(result['actor'],'canon_wally')
    self.assertEqual(self.s.opportunities.offers('Bob','LittlerootTown')[0]['scenes'][0]['id'],'shared')
    self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_players').fetchone()[0],0)
    self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_receipts').fetchone()[0],0)
   finally:q.close()
  self.s.close();self.f.f.case.server=self.f.f.case.open();self.s=self.f.f.case.server;self.f.s=self.s
  self.assertIsNone(actions.step(self.s,now=40))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_action_obstructions').fetchone()[0],1)

 def test_unavailable_request_deduplicates_across_restart_and_unrelated_revision(self):
  self.f.apply(self.actor(revision=99))
  first=actions.step(self.s,now=10)
  self.s.close();self.f.f.case.server=self.f.f.case.open();self.s=self.f.f.case.server;self.f.s=self.s
  self.assertEqual(actions.step(self.s,now=20)['seq'],first['seq'])
  self.f.apply(self.actor(version=1,revision=99,evidence=first['seq']))
  self.assertEqual(actions.step(self.s,now=30)['seq'],first['seq'])
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_action_obstructions').fetchone()[0],1)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_places').fetchone()[0],0)

 def test_failed_observation_persistence_does_not_invent_history(self):
  self.f.apply(self.actor(revision=99))
  before=self.s.memory.history()['through']
  with patch.object(self.s.memory,'append',side_effect=ValueError('receipt refused')):
   self.assertEqual(actions.step(self.s,now=10)['status'],'waiting')
  self.assertEqual(self.s.memory.history()['through'],before)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_action_obstructions').fetchone()[0],0)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_places').fetchone()[0],0)
  self.assertIn('seq',actions.step(self.s,now=16))
