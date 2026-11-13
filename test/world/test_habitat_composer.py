import json
import unittest
from copy import deepcopy
import test_actor_habitats as fixture
from world import actor_runtime as runtime
from world.habitat_composer import compose,traits,inspect_species
from world.shared_cave import SharedCave
from world.species_cohort import catalogue


def criteria(**extra):
 return json.dumps(dict(types=['water','ice'],generations=list(range(1,10)),bst=[200,550],levels=[8,18],seed=42,**extra)) if not extra else json.dumps(dict(json.loads(criteria()),**extra))

class ComposerTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.HabitatTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
 def plan(self,query=None,actor='harbor_guide'):
  self.f.plan();state=deepcopy(self.s.module_state);c=state['world_characters'][actor];c['version']+=1
  bp=dict(rooms=[[3,3,7,7],[18,18,8,8]],links=[[0,1]],entrance_room=0,exit_room=1)
  c['plan']=dict(id='compose',purpose='Author a diverse type-themed habitat.',steps=[dict(id='create',tool='world.compose_habitat',args=dict(label='Frozen Hollow',blueprint=json.dumps(bp),profile='ice',rate=25,criteria=query or criteria()),after=[])])
  # Remove the other actor's unused plan when exercising the second actor.
  if actor!='harbor_guide':
   state['world_characters']['harbor_guide'].pop('plan',None);state['world_characters']['harbor_guide']['version']+=1
  self.f.f.f.f.f.f.f.commit(dict(state=state,objects=self.s.objects,tiles=[]));self.assertIsNone(self.s.module_error)
 def test_real_creation_transfer_population_and_restart(self):
  self.plan();self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded');r=self.f.f.result()
  blob=self.s.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(r['revision'],)).fetchone()[0];cave=SharedCave(blob)
  expected=compose(criteria());ids=catalogue('expansion-native');self.assertEqual(cave.version,10);self.assertEqual(cave.profile,2)
  self.assertEqual(len({s[0] for s in expected['slots']}),12)
  for i,(name,level) in enumerate(expected['slots']):
   self.assertEqual(int.from_bytes(cave.wildlife[1+3*i:3+3*i],'little'),ids[name]);self.assertEqual(cave.wildlife[3+3*i],level)
  peer=self.f.connect('Visitor','SOCIALCAVE10REGION1');self.assertIn('REGION SELECTED',self.f.send(peer,'REGION SELECT '+r['place_id']))
  self.assertIn('CAVE WILD '+r['revision'],self.f.send(peer,'CAVE GET'));self.assertIn('CAVE OK',self.f.send(peer,'CAVE ACK '+r['revision']))
  self.s.close();base=self.f.f.f.f.f.f.f.f;base.server=base.open();self.s=base.server
  self.assertEqual(self.s.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(r['revision'],)).fetchone()[0],blob)
 def test_filters_seed_diversity_and_higher_slot_levels(self):
  a=compose(criteria());self.assertEqual(a,compose(criteria()));b=compose(criteria(seed=43));self.assertNotEqual(a['slots'],b['slots'])
  self.assertTrue(all(set(r['types'])&{'water','ice'} and not r['special'] and 200<=r['bst']<=550 for r in a['traits']))
  self.assertEqual([r['bst'] for r in a['traits']],sorted(r['bst'] for r in a['traits']))
  self.assertEqual(a['slots'][0][1],8);self.assertEqual(a['slots'][-1][1],18)
 def test_sourced_stats_and_special_species_exclusion(self):
  rows={r['name']:r for r in traits()};self.assertEqual(rows['BULBASAUR']['bst'],318)
  self.assertEqual(rows['PIKACHU']['bst'],320)
  for name in ('MEWTWO','MEW','ARTICUNO','NIHILEGO','GREAT_TUSK'):self.assertTrue(rows[name]['special'])
  self.assertGreater(len(rows),900)
  for name,generation in [('ANNIHILAPE',9),('CROBAT',2),('SYLVEON',6),('KINGAMBIT',9),('SIRFETCHD',8)]:self.assertEqual(rows[name]['generation'],generation)
 def test_bounded_complete_metadata_pages(self):
  page=0;seen=[]
  while True:
   r=inspect_species(self.s,'harbor_guide',{},dict(criteria=criteria(),page=page));self.assertLess(len(json.dumps(r)),5000);seen.extend(r['species'])
   if r['next_page'] is None:break
   page=r['next_page']
  self.assertEqual(len(seen),r['total']);self.assertEqual(len({x['species'] for x in seen}),len(seen))
 def test_impossible_query_cannot_publish(self):
  before=self.s.db.execute('SELECT count(*) FROM generated_area_archive').fetchone()[0]
  self.plan(criteria(types=['ice'],generations=[1],bst=[150,200]));self.assertEqual(runtime.tick(self.s,now=10)['status'],'blocked')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM generated_area_archive').fetchone()[0],before)
 def test_second_actor_can_choose_a_different_population(self):
  self.plan(criteria(types=['grass','bug'],seed=17),actor='second');self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded')
  r=self.f.f.result();self.assertEqual(len(r['population']['slots']),12)
 def test_invalid_criteria_rejected(self):
  for patch in (dict(seed=True),dict(types=['unknown']),dict(generations=[0]),dict(levels=[15,8]),dict(bst=[0,900])):
   with self.assertRaises(ValueError):compose(criteria(**patch))
 def test_changed_native_pin_fails_closed(self):
  from unittest.mock import patch
  from pathlib import Path
  original=Path.read_text
  def read(path,*args,**kwargs):
   text=original(path,*args,**kwargs)
   if path.name=='living-cast-candidate.json':
    data=json.loads(text);data['native_revision']='0'*40;return json.dumps(data)
   return text
  traits.cache_clear()
  try:
   with patch.object(Path,'read_text',read):
    with self.assertRaisesRegex(ValueError,'Regenerate'):compose(criteria())
  finally:traits.cache_clear()
 def test_receipt_failure_rolls_back_created_habitat(self):
  from unittest.mock import patch
  self.plan();count=self.s.db.execute('SELECT count(*) FROM generated_area_archive').fetchone()[0];original=runtime._receipt
  def fail(server,actor,row,plan,step,status,result):
   if status=='succeeded':raise ValueError('injected receipt failure')
   return original(server,actor,row,plan,step,status,result)
  with patch.object(runtime,'_receipt',side_effect=fail):self.assertEqual(runtime.tick(self.s,now=10)['status'],'blocked')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM generated_area_archive').fetchone()[0],count)
