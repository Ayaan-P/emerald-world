"""Registered native calls supplement existing speech without becoming field visits."""
import json,unittest
from copy import deepcopy
import test_canonical_cast as fixture
from world import canonical_cast as cast
class MatchCallTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  a=self.f.action();a['id']='canon_wally';a['changes'].update(dialogue='I am considering the field teams news.',conversation=dict(slow=dict(label='Take time',reply='I remember you preferred taking time.')))
  self.f.apply(a);self.a=self.f.peer();self.b=self.f.peer('Bob')
  # Real private SYNC establishes each save; no visit to Wally occurs.
  for peer,run in ((self.a,'a'*32),(self.b,'b'*32)):
   self.s.core_story.handle(peer,['CORE',run,'SYNC','0','private'])
  with self.s.db:self.s.db.execute('INSERT INTO canonical_conversations VALUES(?,?,?,?)',('Alice','canon_wally',1,'slow'))
 def call(self,peer,run):return self.s.core_story.handle(peer,['CORE',run,'CALL','wally','registered'])
 def test_remote_call_is_personal_and_does_not_forge_contact_or_progress(self):
  history=deepcopy(self.s.memory.history());state=deepcopy(self.s.module_state)
  self.assertIn('preferred',self.call(self.a,'a'*32)['briefing'])
  self.assertNotIn('preferred',self.call(self.b,'b'*32)['briefing'])
  self.assertEqual(self.s.memory.history(),history);self.assertEqual(self.s.module_state,state)
  self.assertNotIn('canonical_location',self.a);self.assertNotIn('cast_seen_pending',self.a)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_encounters').fetchone()[0],0)
  self.a['out'].clear();self.s._line(self.a,('CORE '+'a'*32+' CALL wally registered 22').encode())
  line=self.a['out'].decode().strip().split();self.assertEqual(line[:6],['CORE','REPLY','22','a'*32,'CALL','wally'])
  self.assertEqual(bytes.fromhex(line[8]).decode(),'I remember you preferred taking time.')
 def test_wrong_run_unavailable_contact_and_revision_fallback(self):
  with self.assertRaises(ValueError):self.call(self.a,'b'*32)
  for key in ('rydel','briney','unknown','steven'):
   with self.assertRaises(ValueError):self.s.core_story.handle(self.a,['CORE','a'*32,'CALL',key,'registered'])
  a=self.f.action(1);a['id']='canon_wally';a['changes']['dialogue']='The real news has changed my current plan.';self.f.apply(a)
  self.assertEqual(self.call(self.a,'a'*32)['briefing'],a['changes']['dialogue'])
  self.s.close();self.f.f.case.server=self.f.f.case.open();self.s=self.f.f.case.server;self.f.s=self.s;self.f.f.server=self.s
  self.a=self.f.peer();self.s.core_story.handle(self.a,['CORE','a'*32,'SYNC','0','private'])
  self.assertEqual(self.call(self.a,'a'*32)['briefing'],a['changes']['dialogue'])
