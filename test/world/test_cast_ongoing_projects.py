"""Ongoing voluntary cast decisions, not timer-generated success."""
import copy,unittest
from unittest.mock import patch
import test_canonical_cast as fixture
from world import canonical_cast as cast,canonical_world_actions as actions
from world.build_catalog import catalog_maps

HOUSE='MossdeepCity_StevensHouse'

def project():
 return dict(id='field_partners',title='A continuing field partnership',qualities=dict(
  available=dict(scope='project',initial=0,max=1),notes=dict(scope='place',initial=0,max=100)),scenes=dict(
  decide=dict(place=HOUSE,text='Decide whether to make time for field partnership.',requires={},once='actor',actors=['canon_steven'],choices=dict(
   offer=dict(text='Make time for a partner',requires=dict(available=[0,0]),effects=dict(available=1),result='The project now offers partner time.'),
   pause=dict(text='Return to other research',requires=dict(available=[1,1]),effects=dict(available=-1),result='Partner time is paused while other research takes priority.'))),
  read=dict(place=HOUSE,text='Partner time is currently available.',requires=dict(available=[1,1]),once='player',choices=dict(
   note=dict(text='Read the project notice',requires={},effects=dict(notes=1),result='You read the current notice.')))))

class OngoingProjectTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s;self.p=project()
 def decide(self,index,evidence,task=None):
  a=self.f.action(index);a['id']='canon_steven'
  a['changes'].update(places=['native:LittlerootTown','native:'+HOUSE],evidence=[evidence],initiative=self.p,
   companion='steven_wild_once',activity_projects=dict(companion=dict(scene='decide',requires=dict(available=[1,1]))),
   world_action=dict(pack=self.p['id'],scene='decide',choice='offer' if index%2==0 else 'pause',place=HOUSE,revision=index),
   intentions=[dict(id=task or 'decision_'+str(index),kind='world_action',target=self.p['id'],reason='Choose how to divide attention between current commitments.')])
  self.f.apply(a)
 def partner(self):
  c=self.f.peer();c['state'][:2]=next(k for k,v in catalog_maps().items() if v['name']==HOUSE)
  cast.response(self.s,c,'a'*32,'steven')
  return self.s.core_story.handle(c,['CORE','a'*32,'ALLY','steven','confirm'])
 def test_independent_repeated_decisions_change_actual_invitation_without_player_work(self):
  evidence=self.f.evidence
  for index in range(10):
   self.decide(index,evidence)
   with patch('world.opportunities.time.time',return_value=(100+index//8)*86400):
    result=actions.step(self.s,now=10+index*6)
   self.assertEqual(result['status'],'completed');evidence=result['seq']
   if index%2==0:self.assertTrue(self.partner()['ok'])
   else:
    with self.assertRaises(ValueError):self.partner()
   # No periodic repeat of the same retained decision.
   self.assertIsNone(actions.step(self.s,now=11+index*6))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_intent_receipts').fetchone()[0],10)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_players').fetchone()[0],0)
  self.assertEqual(self.s.objects,[])
  self.s.close();self.f.f.case.server=self.f.f.case.open();self.s=self.f.s=self.f.f.case.server
  self.assertIsNone(actions.step(self.s,now=100))
  self.assertEqual(self.s.opportunities.public_state(self.p,HOUSE)[2],['decide'])
  with self.assertRaises(ValueError):self.partner()
 def test_budget_is_durable_shared_across_paths_and_rolls_back(self):
  self.decide(0,self.f.evidence)
  with patch('world.opportunities.time.time',return_value=100*86400):
   for index in range(8):
    with self.s.db:self.s.opportunities.actor_choose('canon_steven',dict(pack=self.p['id'],scene='decide',choice='offer' if index%2==0 else 'pause',place=HOUSE,revision=index))
   with self.assertRaisesRegex(ValueError,'budget'):
    with self.s.db:self.s.opportunities.actor_choose('canon_steven',dict(pack=self.p['id'],scene='decide',choice='offer',place=HOUSE,revision=8))
  self.s.close();self.f.f.case.server=self.f.f.case.open();self.s=self.f.s=self.f.f.case.server
  with patch('world.opportunities.time.time',return_value=99*86400),self.assertRaisesRegex(ValueError,'budget'):
   with self.s.db:self.s.opportunities.actor_choose('canon_steven',dict(pack=self.p['id'],scene='decide',choice='offer',place=HOUSE,revision=8))
  with patch('world.opportunities.time.time',return_value=101*86400):
   with self.assertRaises(RuntimeError):
    with self.s.db:
     self.s.opportunities.actor_choose('canon_steven',dict(pack=self.p['id'],scene='decide',choice='offer',place=HOUSE,revision=8))
     raise RuntimeError('abort')
   self.assertEqual(self.s.opportunities.public_state(self.p,HOUSE)[0],8)
   self.assertEqual(self.s.db.execute('SELECT day,attempts FROM story_actor_budget').fetchone(),(100,8))
 def test_repeatable_scene_never_becomes_an_unassigned_player_action(self):
  from world.opportunities import validate
  p=project();p['scenes']['decide'].pop('actors')
  with self.assertRaisesRegex(ValueError,'assigned'):validate(p,{HOUSE})
