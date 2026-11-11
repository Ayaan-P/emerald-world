"""Fixture agent decisions exercise seed -> plan -> authority action -> native panel.
No model is called; no physical construction/travel or battle is simulated.
"""
import copy,json,tempfile,unittest
import test_canonical_cast as fixture
from world import canonical_seeds as seeds,canonical_cast as cast,character_reactions as reactions
from world import canonical_self_direction as direction,canonical_world_actions as actions
from world.canonical_project_panel import panel
from world.runtime_gm import IntentQueue

class SelfDirectionTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.q=IntentQueue(self.tmp.name);self.addCleanup(lambda:self.q.close())
 def observe(self):return reactions.observe(self.q,self.s.inspect(),self.f.fetch)
 def goal(self):
  seeds.initialize(self.q,self.s);self.observe()
  item=self.q.claim()
  while item['player']!='canon_rydel':
   self.q.finish(item['id'],'succeeded',dict(ok=True,wait=True));item=self.q.claim()
  event=json.loads(item['result'])
  a=dict(id='canon_rydel',expected_version=0,changes=dict(goal='Make cycling advice easier to use',dialogue='I am considering how to make cycling advice more useful.',places=['native:MauvilleCity_BikeShop'],evidence=[event['evidence']],reason='Initial identity-based goal, not a claimed achievement'))
  self.f.apply(a);self.q.finish(item['id'],'succeeded',dict(ok=True))
  # Remaining initialized actors may wait. No test-authored arc is deployed for them.
  while (item:=self.q.claim()):self.q.finish(item['id'],'succeeded',dict(ok=True,wait=True))
  return a
 def test_goal_plans_and_executes_visible_project_then_reconsiders(self):
  a=self.goal();self.assertEqual(len(self.observe()),1)
  item=self.q.claim();packet=json.loads(item['result']);self.assertTrue(packet['self_direction'])
  ctx=self.f.context();ctx['runtime'].update(kind='character',observed_event=packet)
  reactions.prepare(ctx,self.f.fetch);self.assertIn('intention evidence only',ctx['character_planning'])
  a['expected_version']=1;a['changes']['evidence']=[packet['evidence']]
  a['changes'].update(initiative=dict(id='cycling_advice',title='Rydel cycling advice',qualities=dict(ready=dict(scope='place',initial=0,max=1),questions=dict(scope='place',initial=0,max=4)),scenes=dict(
   prepare=dict(place='MauvilleCity_BikeShop',text='Decide whether to open your cycling discussion.',actors=['canon_rydel'],requires=dict(ready=[0,0]),once='world',choices=dict(open=dict(text='Open discussion',requires={},effects=dict(ready=1),result='The cycling discussion is now open.'))),
   discuss=dict(place='MauvilleCity_BikeShop',text='Rydel has opened a cycling discussion.',requires=dict(ready=[1,1]),once='player',choices=dict(ask=dict(text='Discuss bike handling',requires={},effects=dict(questions=1),result='Rydel suggests considering the terrain before choosing a bike.'))))),
   world_action=dict(pack='cycling_advice',scene='prepare',choice='open',place='MauvilleCity_BikeShop',revision=0),intentions=[dict(id='open_advice',kind='world_action',target='cycling_advice',reason='Make the discussion available independently.')])
  reactions.check_response(dict(canonical_actions=[a],tests='assert True'),packet);self.f.apply(a)
  self.q.finish(item['id'],'succeeded',dict(ok=True))
  self.assertEqual(self.s.opportunities.offers('Alice','MauvilleCity_BikeShop'),[])
  done=actions.step(self.s,now=10);self.assertEqual(done['status'],'completed')
  peer=self.f.peer();self.f.query(peer)
  ui=panel(self.s,peer,'a'*32,'rydel','view')
  self.assertEqual(ui['role'],4);self.assertIn('opened a cycling discussion',ui['question'])
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_players').fetchone()[0],0)
  self.assertEqual(self.s.objects,[])
  # Real committed action, not a player errand, supports the next chosen goal.
  after=copy.deepcopy(a);after['expected_version']=2
  after['changes'].update(goal='Consider a second perspective on bike handling',evidence=[done['seq']],intentions=[])
  after['changes'].pop('world_action');self.f.apply(after)
  self.assertTrue(direction.relevant(next(e for e in reversed(self.s.memory.history()['events']) if e['event']=='canonical_actor_changed'),'canon_rydel',cast.records(self.s.module_state)['canon_rydel']))
  self.s.close();self.f.f.case.server=self.f.f.case.open();self.s=self.f.f.case.server
  self.assertIsNone(actions.step(self.s,now=30))
  self.assertEqual(self.s.opportunities.offers('Bob','MauvilleCity_BikeShop')[0]['scenes'][0]['id'],'discuss')
 def test_budget_and_exact_current_goal_not_achievement_evidence(self):
  self.goal()
  with self.q.db:
   for _ in range(8):self.assertTrue(direction.reserve(self.q,self.s.memory.world_id,'canon_rydel'))
  self.assertEqual(self.observe(),[])
  self.q.close();self.q=IntentQueue(self.tmp.name)
  with self.q.db:self.assertFalse(direction.reserve(self.q,self.s.memory.world_id,'canon_rydel'))
  e=next(e for e in reversed(self.s.memory.history()['events']) if e['event']=='canonical_actor_changed')
  row=cast.records(self.s.module_state)['canon_rydel'];self.assertTrue(direction.relevant(e,'canon_rydel',row))
  self.assertFalse(direction.relevant(e,'canon_wally',row));self.assertFalse(direction.relevant(e,'canon_rydel',dict(row,version=2)))
  self.assertFalse(direction.evidence(e,'canon_rydel',dict(row,version=3)))
  changed=copy.deepcopy(e);changed['before']=changed['after'];self.assertFalse(direction.goal_event(changed,'canon_rydel'))
  # No other character's feelings or participation follow from your own goal.
  with self.assertRaises(ValueError):cast.validate_relationship_evidence(dict(relationships=dict(canon_wally=dict(evidence=[e['seq']])),places=row['places']),lambda n:e,'canon_rydel')
