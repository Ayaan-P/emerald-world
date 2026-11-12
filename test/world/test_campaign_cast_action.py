"""Actual campaign receipt -> independent authored intention -> committed terrain.

No live model, native actor travel, or player construction work is implied.
"""
from copy import deepcopy
import json,tempfile,unittest
import test_canonical_construction as construction_fixture
from world import canonical_cast as cast,canonical_construction as construction,character_reactions as reactions
from world.runtime_gm import IntentQueue

class CampaignActionTests(unittest.TestCase):
 def setUp(self):
  self.f=construction_fixture.CastConstructionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.s=self.f.s;self.author=self.f.f
  # Start with no pending building task. The later campaign result does not
  # merely release a hardcoded outcome or preselected plot branch.
  before=deepcopy(self.f.action);before['expected_version']=1
  before['changes'].update(places=['native:LittlerootTown','native:MauvilleCity_Gym'],intentions=[],worksite=None)
  self.author.apply(before)
  self.peer=self.author.peer()
 def send(self,key,guard='private'):
  return self.s.core_story.handle(self.peer,['CORE','a'*32,'MILE',key,guard])
 def test_real_result_can_drive_actual_autonomous_action_without_player_errand(self):
  original=self.s.shared_cave.identity
  self.assertIsNone(construction.step(self.s,now=1))
  with tempfile.TemporaryDirectory() as tmp:
   queue=IntentQueue(tmp)
   try:
    reactions.configure(queue,self.s.inspect(),'canon_briney','Consider a supported useful project from public campaign results; do not claim travel or personal victories.')
    self.assertEqual(reactions.observe(queue,self.s.inspect(),self.author.fetch),[])
    self.send('0');self.send('on','confirm');self.send('4')
    self.assertEqual(self.s.shared_cave.identity,original) # A badge never automatically edits the map.
    self.assertEqual(len(reactions.observe(queue,self.s.inspect(),self.author.fetch)),1)
    item=queue.claim();ctx=self.author.context();ctx['runtime'].update(kind='character',observed_event=json.loads(item['result']))
    reaction=reactions.prepare(ctx,self.author.fetch)
    observed=next(e for e in self.s.memory.history()['events'] if e['event']=='canonical_campaign_milestone')
    # Inspect actual archived geometry before authoring a plan. This is the
    # supported operator inspection API, not invented field knowledge.
    geometry=self.s.memory.inspect_saved_place(self.s,original)
    self.assertEqual((geometry['revision'],geometry['template_version'],geometry['side']),(original,16,127))
    self.assertEqual(geometry['rows'][23][18],'#')
    chosen=deepcopy(self.f.action);chosen['expected_version']=2
    chosen['changes'].update(places=['native:MauvilleCity_Gym'],evidence=[observed['seq']],
      goal='Make a resting place available while trainers pursue their own journeys',
      reason='Reconsider useful support from the shared badge report and inspected empty frontier')
    reactions.check_response(dict(canonical_actions=[chosen],tests='assert True'),reaction)
    self.author.apply(chosen);queue.finish(item['id'],'succeeded',dict(ok=True))
    self.assertEqual(self.s.shared_cave.identity,original) # Authored intention is not success.
    self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_construction_receipts').fetchone()[0],0)
    # Busy area postpones execution, rather than writing success or pushing players out.
    self.s.peers['Observer']=dict(id='Observer',closing=False,in_generated_cave=True,state=None,out=bytearray())
    self.assertEqual(construction.step(self.s,now=10)['status'],'waiting')
    self.assertEqual(self.s.shared_cave.identity,original)
    self.s.peers.pop('Observer')
    outcome=construction.step(self.s,now=16)
    self.assertEqual(outcome['status'],'completed');self.assertNotEqual(self.s.shared_cave.identity,original)
    self.assertTrue(self.s.shared_cave.walkable(18,23))
    result=self.s.memory.history()['events'][-1]
    self.assertEqual(result['event'],'canonical_construction_completed')
    self.assertEqual(result['based_on'],[observed['seq']])
    self.assertEqual(result['outcome'],'connected_courtyard_committed')
    self.assertEqual(len(reactions.observe(queue,self.s.inspect(),self.author.fetch)),1)
    self.assertEqual(self.s.objects,[])
    self.assertEqual(self.s.db.execute('SELECT count(*) FROM core_story_progress').fetchone()[0],0)
    self.assertEqual(self.s.db.execute('SELECT count(*) FROM survey_sessions').fetchone()[0],0)
    self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_construction_receipts').fetchone()[0],1)
    final=self.s.shared_cave.identity
   finally:queue.close()
  self.s.close();self.f.f.f.case.server=self.f.f.f.case.open();self.s=self.f.f.f.case.server
  self.assertEqual(self.s.shared_cave.identity,final)
  self.assertIsNone(construction.step(self.s,now=30))
