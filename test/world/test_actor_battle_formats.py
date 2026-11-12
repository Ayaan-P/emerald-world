import unittest,copy
import test_character_companions as fixture
from world import actor_runtime,actor_battle_formats as formats
class FormatTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CompanionIdentityTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
 def configure(self):
  c=copy.deepcopy(self.s.module_state['world_characters']['may']);c['version']+=1
  c['plan']=dict(id='double_battle',purpose='Try a coordinated optional battle with our actual partners.',steps=[dict(id='format',tool='world.set_battle_format',args=dict(format='doubles'),after=[])])
  self.assertIsNone(self.f.f.commit({'may':c},self.f.f.npc))
  self.assertEqual(actor_runtime.tick(self.s,now=10)['status'],'succeeded')
  return c['version'],formats.current(self.s,'may')[0]
 def test_real_author_format_freeze_native_descriptor_and_restart(self):
  version,revision=self.configure();p=self.f.f.peer(role='SOCIALCHAR1CHARPK1CHARFORM1')
  self.assertIn(f'CHARACTER_FORMAT may {version} {revision} 1',self.s._snapshot(p))
  wire=self.f.f.send(p,f'CHARACTER_CHALLENGE 1 may {version} {revision}')
  self.assertTrue(wire.startswith(f'CHARACTER_BATTLE_V4 1 may {version} 2 {revision} 1 1 '),wire)
  frozen=copy.deepcopy(p['character_pending'])
  with self.s.db:formats.configure(self.s,'may',{},dict(format='singles'))
  self.assertEqual(p['character_pending'],frozen)
  self.s.close();self.f.f.server=self.f.f.open();self.s=self.f.f.server
  self.assertEqual(formats.current(self.s,'may')[1],0)
  self.assertIsNone(actor_runtime.tick(self.s,now=20))
 def test_legacy_and_stale_consent_refuse_double_without_downgrade(self):
  version,revision=self.configure();old=self.f.f.peer(role='SOCIALCHAR1CHARPK1')
  self.assertIn('CHARACTER_REJECT',self.f.f.send(old,f'CHARACTER_CHALLENGE 1 may {version}'))
  p=self.f.f.peer('Bob',role='SOCIALCHAR1CHARPK1CHARFORM1')
  self.assertIn('CHARACTER_REJECT',self.f.f.send(p,f'CHARACTER_CHALLENGE 1 may {version} {revision-1}'))
  self.assertNotIn('character_pending',p)
 def test_identity_and_format_are_frozen_in_one_descriptor(self):
  version,revision=self.configure()
  p=self.f.f.peer(role='SOCIALCHAR1CHARPK1CHARIDENT1CHARIDENT2CHARFORM1')
  self.assertTrue(p.get('character_identity2_capable'))
  wire=self.f.f.send(p,f'CHARACTER_CHALLENGE 1 may {version} {revision}')
  fields=wire.split()
  self.assertEqual(fields[0],'CHARACTER_BATTLE_V5',wire)
  self.assertEqual(fields[7:10],['2',str(revision),'1'])
  self.assertEqual(p['character_pending']['battle_format'],1)
  self.assertEqual(p['character_pending']['format_revision'],revision)
 def test_unowned_and_small_team_cannot_offer_doubles(self):
  c=copy.deepcopy(self.s.module_state['world_characters']['may']);c['version']+=1;c['team']=c['team'][:1]
  self.assertIsNone(self.f.f.commit({'may':c},self.f.f.npc))
  with self.assertRaises(ValueError):formats.configure(self.s,'may',{},dict(format='doubles'))
  with self.assertRaises(ValueError):formats.configure(self.s,'may',{},dict(format='arbitrary_flags'))
 def test_paired_native_parser_and_launch(self):
  import os,pathlib,importlib.util,subprocess,tempfile
  path=pathlib.Path(os.environ.get('EW_FORMAT_NATIVE_SOURCE','../native-battle-formats')).resolve()
  if not (path/'tests/test_formats.py').exists():self.skipTest('paired source unavailable')
  version,revision=self.configure();p=self.f.f.peer(role='SOCIALCHAR1CHARPK1CHARFORM1')
  wire=self.f.f.send(p,f'CHARACTER_CHALLENGE 1 may {version} {revision}')
  spec=importlib.util.spec_from_file_location('native_formats',path/'tests/test_formats.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  snapshot=next(line for line in self.s._snapshot(p).splitlines() if line.startswith('CHARACTER_FORMAT '))
  with tempfile.TemporaryDirectory() as d:subprocess.run([str(m.build(d,wire,snapshot))],check=True,capture_output=True)
