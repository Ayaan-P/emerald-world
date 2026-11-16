import unittest
import test_characters
from world import actor_tutors as tutors,actor_runtime
class TutorTests(unittest.TestCase):
 def setUp(self):
  self.f=test_characters.CharacterLifecycleTests();self.f.setUp();self.addCleanup(self.f.tearDown);self.s=self.f.server
  self.assertIsNone(self.f.commit({'may':self.f.character},self.f.npc))
 def test_actual_author_plan_optional_offer_and_restart(self):
  peer=self.f.peer(role='SOCIALCHAR1CHARTUTOR1')
  c=dict(self.f.character,version=2,reason='Offer an optional training opportunity.',evidence=[self.s.memory.history()['events'][-1]['seq']],
   plan=dict(id='tutor',purpose='Let visitors choose eligible move training.',steps=[dict(id='offer',tool='world.offer_tutoring',args=dict(move=164),after=[])]))
  self.assertIsNone(self.f.commit({'may':c},self.f.npc))
  self.assertEqual(actor_runtime.tick(self.s,now=10)['status'],'succeeded')
  self.assertIn('CHARACTER_TUTOR may 2',self.s._snapshot(peer))
  old=self.f.peer('Old',role='SOCIALCHAR1');self.assertNotIn('CHARACTER_TUTOR',self.s._snapshot(old))
  self.s.close();self.f.server=self.f.open();self.s=self.f.server
  self.assertEqual(tutors.catalog(self.s)['offers']['may']['move'],164)
  with self.s.db:tutors.configure(self.s,'may',{},dict(move=0))
  self.assertIsNone(tutors.line(self.s,dict(character_tutor_capable=True),'may',2))
 def test_unknown_moves_and_party_parameters_rejected(self):
  for args in (dict(move=9999),dict(move=True),dict(move=164,party=0)):
   with self.assertRaises(ValueError):tutors.configure(self.s,'may',{},args)
 def test_actual_snapshot_through_native_tutor_choice(self):
  import importlib.util,pathlib,tempfile,subprocess,os
  path=pathlib.Path(os.environ.get('EW_TUTOR_NATIVE_SOURCE','../native-npc-tutoring')).resolve()
  if not (path/'tests/test_tutoring.py').exists():self.skipTest('Exact native tutoring source unavailable')
  peer=self.f.peer(role='SOCIALCHAR1CHARTUTOR1')
  with self.s.db:tutors.configure(self.s,'may',{},dict(move=164))
  wire=next(x for x in self.s._snapshot(peer).splitlines() if x.startswith('CHARACTER_TUTOR '))
  spec=importlib.util.spec_from_file_location('tutor_native',path/'tests/test_tutoring.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  with tempfile.TemporaryDirectory() as d:subprocess.run([str(module.build(d,wire))],check=True,capture_output=True)
  header=(path/'include/constants/moves.h').read_text()
  for move in tutors.MOVES:self.assertRegex(header,r'MOVE_[A-Z_]+ = '+str(move)+r',')
