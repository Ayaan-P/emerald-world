"""Independent cast project decisions unlock an actual existing native activity."""
import copy,unittest
import test_canonical_cast as fixture
from test_canonical_world_actions import pack
from world import canonical_cast as cast,canonical_world_actions as actions
from world.canonical_activity_projects import available
from world.build_catalog import catalog_maps

class ActivityProjectTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  w=self.f.action();w['id']='canon_wally';self.f.apply(w)
  self.p=pack();self.p['scenes']['organize']['actors']=['canon_steven']
  self.a=self.f.action();self.a['id']='canon_steven'
  self.a['changes'].update(initiative=self.p,companion='steven_wild_once',
   activity_projects=dict(companion=dict(scene='contribute',requires=dict(stage=[2,2]))),
   world_action=dict(pack='workshop',scene='organize',choice='open',place='LittlerootTown',revision=0),
   intentions=[dict(id='prepare',kind='world_action',target='workshop',reason='Offer a shared perspective before a partner invitation.')])
  self.f.apply(self.a);self.c=self.f.peer()
  self.c['state'][:2]=next(k for k,v in catalog_maps().items() if v['name']=='MossdeepCity_StevensHouse')
 def reply(self):return cast.response(self.s,self.c,'a'*32,'steven')
 def accept(self):return self.s.core_story.handle(self.c,['CORE','a'*32,'ALLY','steven','confirm'])
 def contribute(self):
  first=actions.step(self.s,now=10)
  a=self.f.action(1);a['id']='canon_wally'
  a['changes'].update(evidence=[first['seq']],world_action=dict(pack='workshop',scene='contribute',choice='join',place='LittlerootTown',revision=1),
   intentions=[dict(id='contribute',kind='world_action',target='workshop',reason='Independently add a different perspective.')])
  self.f.apply(a);return actions.step(self.s,now=16)
 def test_independent_cooperation_changes_actual_partner_admission_and_survives_restart(self):
  self.assertNotIn('Companion',self.reply()['objective'])
  with self.assertRaises(ValueError):self.accept()
  outcome=self.contribute();self.assertEqual(outcome['actor'],'canon_wally')
  self.assertIn('Companion',self.reply()['objective']);self.assertTrue(self.accept()['ok'])
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_players').fetchone()[0],0)
  self.assertEqual(self.s.objects,[])
  self.assertEqual(cast.records(self.s.module_state)['canon_steven']['version'],1) # No extra author turn required.
  self.s.close();self.f.f.case.server=self.f.f.case.open();self.s=self.f.f.case.server;self.f.s=self.s
  self.c=self.f.peer();self.c['state'][:2]=next(k for k,v in catalog_maps().items() if v['name']=='MossdeepCity_StevensHouse')
  self.assertIn('Companion',self.reply()['objective']);self.assertTrue(self.accept()['ok'])
  # A real subsequent shared choice changes project state. No fabricated withdrawal.
  self.s.opportunities.choose('Alice','LittlerootTown','workshop','shared','consider',2,'actual_choice')
  with self.assertRaises(ValueError):self.accept()
  self.assertNotIn('Companion',self.reply()['objective'])
 def test_invalid_bindings_and_fake_initial_state_do_not_unlock(self):
  row=cast.records(self.s.module_state)['canon_steven']
  self.assertFalse(available(self.s,'canon_steven',row,'companion'))
  for mutation in ('private','player_scene','unknown','unsupported','missing'):
   a=copy.deepcopy(self.a);a['expected_version']=1
   rules=a['changes']['activity_projects']
   if mutation=='private':a['changes']['initiative']['qualities']['stage']['scope']='player'
   elif mutation=='player_scene':rules['companion']['scene']='shared'
   elif mutation=='unknown':rules['companion']['requires']={'invented':[1,2]}
   elif mutation=='unsupported':rules['money']=rules.pop('companion')
   else:a['changes'].pop('initiative')
   with self.subTest(mutation=mutation),self.assertRaises(ValueError):cast.compile_actions([a],self.f.context())
  self.contribute()
  self.assertFalse(available(self.s,'canon_wally',row,'companion')) # Cannot borrow another owner's project.
 def test_shared_scene_checks_actual_project_before_offer_and_before_join(self):
  from test_canonical_scenes import CanonicalSceneTests
  f=CanonicalSceneTests();f.setUp();self.addCleanup(f.doCleanups)
  a=f.f.action(1);p=pack();p['scenes']['contribute']['actors']=['canon_rydel']
  a['changes'].update(initiative=p,scene='rydel_step',activity_projects=dict(scene=dict(scene='organize',requires=dict(stage=[1,1]))),
   world_action=dict(pack='workshop',scene='organize',choice='open',place='LittlerootTown',revision=0),
   intentions=[dict(id='prepare',kind='world_action',target='workshop',reason='Open a discussion before a demonstration.')])
  f.f.apply(a);f.f.query(f.a)
  self.assertIn('CORE SCENE REFUSED',f.send(f.a,'CORE SCENE ASK '+f.run+' rydel'))
  actions.step(f.s,now=10);f.f.query(f.a);token=f.offer()
  # Another actual shared choice changes the conditions before anyone joins.
  f.s.opportunities.choose('Alice','LittlerootTown','workshop','solo','read',1,'change')
  f.send(f.a,'CORE SCENE JOIN '+token)
  self.assertIn('CORE SCENE REFUSED',f.send(f.b,'CORE SCENE JOIN '+token))
  self.assertIsNone(f.s.cast_scenes.live)
