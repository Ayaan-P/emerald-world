"""Original-actor invitation admits one native request, never reports victory."""
import time,unittest
from copy import deepcopy
import test_canonical_cast as fixture
from world import canonical_cast as cast
from world.build_catalog import catalog_maps
class StevenCompanionTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.a=self.f.action();self.a['id']='canon_steven';self.a['changes'].update(companion='steven_wild_once',dialogue='I can lend my battle experience for one wild encounter if you would like.')
  self.f.apply(self.a);self.c=self.f.peer()
  self.c['state'][:2]=next(p for p,m in catalog_maps().items() if m['name']=='MossdeepCity_StevensHouse')
 def request(self,run='a'*32):return self.s.core_story.handle(self.c,['CORE',run,'ALLY','steven','confirm'])
 def test_exact_original_conversation_admits_without_world_or_party_effect(self):
  with self.assertRaises(ValueError):self.request()
  response=cast.response(self.s,self.c,'a'*32,'steven');self.assertIn('companion',response['objective'].lower())
  history=deepcopy(self.s.memory.history());state=deepcopy(self.s.module_state)
  self.assertTrue(self.request()['ok'])
  self.assertEqual(self.s.memory.history(),history);self.assertEqual(self.s.module_state,state)
  self.assertTrue(any('/history companion' in line for line in cast.guild_command(self.s,self.c,['steven'])))
  # Actual authenticated dispatch uses optional CORE reply, never public CHAT.
  self.c['out'].clear();self.s._line(self.c,('CORE '+'a'*32+' ALLY steven confirm 44').encode())
  self.assertIn('CORE REPLY 44 '+'a'*32+' ALLY steven OK',self.c['out'].decode())
  self.assertNotIn('CHAT',self.c['out'].decode())
 def test_no_other_actor_stale_context_withdrawal_or_other_save_admission(self):
  wrong=deepcopy(self.a);wrong['id']='canon_rydel'
  with self.assertRaisesRegex(ValueError,'Only Steven'):cast.compile_actions([wrong],self.f.context())
  cast.response(self.s,self.c,'a'*32,'steven')
  with self.assertRaises(ValueError):self.request('b'*32)
  self.c['state'][6]=0
  with self.assertRaises(ValueError):self.request()
  self.c['state'][6]=1;self.c['canonical_location']['expires']=0
  with self.assertRaises(ValueError):self.request()
  cast.response(self.s,self.c,'a'*32,'steven')
  withdrawn=deepcopy(self.a);withdrawn['expected_version']=1;withdrawn['changes'].pop('companion');self.f.apply(withdrawn)
  with self.assertRaises(ValueError):self.request()
