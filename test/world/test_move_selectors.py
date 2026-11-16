import json,unittest
from world import move_selectors,overworld_moves,object_choices
from world.guilds import GuildError
import test_overworld_moves,test_actor_object_programs
class Selectors(unittest.TestCase):
 def test_static_traits_and_invalid_rules(self):
  r=move_selectors.resolve({'types':['water'],'categories':['special'],'exclude':[55]})
  self.assertIn(56,r);self.assertNotIn(55,r);self.assertNotIn(52,r);self.assertNotIn(240,r)
  for value in ({'types':['fake']},{'types':[]},{'types':['water'],'unknown':1},{'exclude':[55]},[True],{'categories':['special'],'exclude':[True]}):
   with self.assertRaises(ValueError):move_selectors.resolve(value)
 def test_extractor_does_not_guess_configured_types(self):
  from scripts.build_move_traits import extract
  constants='enum __attribute__((packed)) Move {MOVE_NONE=0,MOVE_A=1,MOVE_B=2,};'
  info='    [MOVE_A] =\n {.type = TYPE_WATER, .category = DAMAGE_CATEGORY_SPECIAL,},\n    [MOVE_B] =\n {.type = CONFIG ? TYPE_FIRE : TYPE_NORMAL, .category = DAMAGE_CATEGORY_PHYSICAL,},'
  traits,excluded=extract(constants,info,{'1':'a','2':'b'})
  self.assertEqual(traits,{'1':{'type':'water','category':'special'}});self.assertEqual(excluded,['2'])
 def test_catalog_scope(self):
  from pathlib import Path
  data=json.loads(Path(move_selectors.__file__).with_name('move_traits.json').read_text())
  self.assertEqual(len(data['traits']),819);self.assertEqual(len(data['excluded']),21)
  self.assertNotIn('2',data['traits']);self.assertIn('2',data['excluded']) # configurable Karate Chop type
class Gameplay(test_overworld_moves.MoveEffects):
 def setUp(self):
  self.f=test_actor_object_programs.ProgramTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  for phase,action,kind in [('first','turn','water'),('second','reset','fire')]:
   self.f.program['states'][phase].update(use='',choices=[action],moves={action:{'types':[kind],'categories':['special']}})
  self.f.install();self.peer=self.f.f.connect('User',True)
  send=lambda line:self.f.f.f.f.send(self.peer,line)
  send('CAVE GET');send('CAVE ACK '+self.s.shared_cave.identity)
  self.f.f.f.f.state(self.peer,*self.s.wilds_map,72,69);self.peer['state'][4]=1
 # Only the inherited real fixture helpers, not its exact-ID assumptions.
 def test_family_responses_real_admission_restart(self):
  with self.assertRaises(GuildError):self.act('turn',52)
  self.act('turn',55);self.admit(1);self.assertEqual(self.s.objects[-1]['text'],'Second face.')
  self.act('reset',52);self.admit(3);self.act('turn',56);self.admit(5)
  self.assertEqual(self.s.objects[-1]['text'],'Second face.')
  self.s.close();base=self.f.f.f.f.f;base.server=base.open();self.s=base.server
  self.assertEqual(self.s.objects[-1]['text'],'Second face.')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM world_move_intents WHERE seq IS NOT NULL').fetchone()[0],3)
 def test_selector_offer_is_concise_and_default_cannot_bypass(self):
  lines=object_choices.command(self.s,self.peer,['moves']);self.assertEqual(len(lines),4)
  self.assertIn('water special learned moves',lines[-1]);self.assertTrue(all(len(x)<=120 for x in lines))
  with self.assertRaises(ValueError):overworld_moves.validate_node(dict(on={'wet':'next'},use='wet',moves={'wet':{'types':['water']}}))
# Inherited test methods encode the previous exact-ID program, so don't collect them.
for name in list(test_overworld_moves.MoveEffects.__dict__):
 if name.startswith('test_') and name not in Gameplay.__dict__:setattr(Gameplay,name,None)
class LinkedResponses(unittest.TestCase):
 def test_family_moves_drive_real_linked_position_change(self):
  import test_object_networks
  from world import actor_objects
  f=test_object_networks.NetworkTests();f.setUp();self.addCleanup(f.doCleanups);server=f.s
  for phase,action,kind in [('off','activate','water'),('on','reset','fire')]:
   node=f.definition['program']['states'][phase];node['use']={};node['choices']={'fixture':[action]};node['moves']={'fixture':{action:{'types':[kind],'categories':['special']}}}
  f.install();peer=f.f.f.connect('User',True);send=lambda line:f.f.f.f.f.send(peer,line)
  send('CAVE GET');send('CAVE ACK '+server.shared_cave.identity);f.f.f.f.f.state(peer,*server.wilds_map,72,69);peer['state'][4]=1
  object_choices.command(server,peer,['moves']);token=peer['object_moves']['token'];object_choices.command(server,peer,['move',token,'activate','56'])
  f.f.f.f.advance(1,True);actor_objects.poll_player(server)
  self.assertEqual(next(o for o in server.objects if o['id']=='panel')['y'],72)
  self.assertEqual(server.module_state['world_object_network_state']['mechanism']['phase'],'on')
class Discovery(unittest.TestCase):
 def test_registered_catalog_pages_and_static_provenance(self):
  from world.actor_runtime import CAPABILITIES
  tool=CAPABILITIES['world.inspect_move_rules'];args={'selector':json.dumps({'types':['water']}),'after':0}
  result=tool.execute(None,None,None,args);self.assertLessEqual(len(result['moves']),24)
  self.assertIn('not owned',result['limits']);self.assertGreater(result['next_after'],0)
  args['after']=result['next_after'];second=tool.execute(None,None,None,args)
  self.assertTrue(all(x['id']>args['after'] for x in second['moves']))
