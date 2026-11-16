import json,unittest
from unittest.mock import patch
import test_characters
from world import actor_bulletins as bulletins,actor_runtime

class BulletinTests(unittest.TestCase):
 def setUp(self):
  self.f=test_characters.CharacterLifecycleTests();self.f.setUp();self.addCleanup(self.f.tearDown);self.s=self.f.server
  self.assertIsNone(self.f.commit({'may':self.f.character},self.f.npc))
  self.args=dict(pages=json.dumps(['The route is open.','Come see for yourself.']),evidence=json.dumps([self.s.revision]),hours=2)
 def test_actual_plan_negotiated_snapshot_restart_and_withdraw(self):
  c=dict(self.f.character,version=2,reason='Share my public report.',evidence=[self.s.revision],plan=dict(id='report',purpose='Publish my interpretation.',steps=[dict(id='publish',tool='world.publish_bulletin',args=self.args,after=[])]))
  self.assertIsNone(self.f.commit({'may':c},self.f.npc));self.assertEqual(actor_runtime.tick(self.s,now=10)['status'],'succeeded')
  peer=self.f.peer(role='SOCIALCHAR1WORLDTV1');wire=self.s._snapshot(peer)
  line=next(l for l in wire.splitlines() if l.startswith('WORLD_BULLETIN '));self.assertEqual(len(line.split()),5)
  self.assertEqual(bytes.fromhex(line.split()[3]).decode(),'The route is open.')
  old=self.f.peer('Old',role='SOCIALCHAR1');self.assertNotIn('WORLD_BULLETIN',self.s._snapshot(old))
  self.s.close();self.f.server=self.f.open();self.s=self.f.server
  self.assertEqual(bulletins.line(self.s,dict(world_bulletin_capable=True)),line)
  with self.s.db:bulletins.withdraw(self.s,'may',{}, {})
  self.assertIsNone(bulletins.line(self.s,dict(world_bulletin_capable=True)))
  self.assertTrue(any(e['event']=='character_bulletin_published' for e in self.s.memory.history()['events']))
 def test_expiry_invalid_glyphs_and_nonpublic_evidence(self):
  with patch.object(bulletins.time,'time',return_value=100):
   with self.s.db:bulletins.publish(self.s,'may',{},self.args)
  with patch.object(bulletins.time,'time',return_value=8000):self.assertIsNone(bulletins.line(self.s,dict(world_bulletin_capable=True)))
  for changed in [dict(pages='["Bad$", "No"]'),dict(evidence='[999999]'),dict(hours=0)]:
   with self.assertRaises(ValueError):bulletins.publish(self.s,'may',{},dict(self.args,**changed))
 def test_history_failure_leaves_no_published_report(self):
  with patch.object(self.s.memory,'append',side_effect=RuntimeError('fixture')):
   with self.assertRaises(RuntimeError):
    with self.s.db:bulletins.publish(self.s,'may',{},self.args)
  self.assertIsNone(bulletins.line(self.s,dict(world_bulletin_capable=True)))
