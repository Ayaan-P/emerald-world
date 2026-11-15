import unittest,json,sqlite3
import test_contest_guests as fixture
from world import npc_tactics as tactics,actor_runtime
class Tactics(unittest.TestCase):
 def setUp(self):
  self.f=fixture.ContestGuests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
 def test_plan_discovery_and_wire(self):
  c=self.f.c;self.f.c=dict(c,version=3,plan=dict(id='tactics',purpose='Use current moves differently.',steps=[dict(id='configure',tool='world.set_tactics',args=dict(flags='["hp_aware","reserve_ace"]'),after=[])]));self.f.commit()
  self.assertEqual(actor_runtime.tick(self.s,now=10)['status'],'succeeded')
  self.assertIn('world.set_tactics',actor_runtime.inspect_runtime(self.s)['capabilities'])
  self.assertIn('A ENTRY harbor_guide 3 33024',tactics.wire(self.s,{},b'A GET 1'))
  self.assertIn('hp_aware',str(tactics.command(self.s,{},[])))
 def test_no_omniscience_or_arbitrary_mask(self):
  for value in ['["omniscient"]','[65536]','["risky","risky"]','{}']:
   with self.assertRaises(ValueError):tactics.configure(self.s,'harbor_guide',{},dict(flags=value))
  with self.assertRaises(ValueError):tactics.configure(self.s,'steven',{},dict(flags='[]'))
 def test_restart_and_reset(self):
  before=json.dumps(self.s.module_state,sort_keys=True)
  with self.s.db:tactics.configure(self.s,'harbor_guide',{},dict(flags='["risky"]'))
  db=sqlite3.connect(':memory:');self.s.db.backup(db);old=self.s.db;self.s.db=db
  try:
   self.assertEqual(tactics.catalog(self.s)[0]['flags'],['risky'])
   with db:tactics.configure(self.s,'harbor_guide',{},dict(flags='[]'))
   self.assertEqual(tactics.catalog(self.s)[0]['flags'],[])
  finally:self.s.db=old;db.close()
  self.assertEqual(before,json.dumps(self.s.module_state,sort_keys=True))
