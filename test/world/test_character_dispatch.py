import hashlib,json,unittest
from copy import deepcopy
from world.character_actions import compile_actions
from world.mechanics import Candidate
import test_actor_cave_travel

class DispatcherTests(unittest.TestCase):
 def setUp(self):
  self.f=test_actor_cave_travel.ActorTravelTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.s=self.f.s;self.fx=self.f.fx
 def apply(self,index):
  actor=self.s.module_state['world_characters']['harbor_guide']
  obj=next(o for o in self.s.objects if o['id']=='harbor_guide')
  action=dict(id='harbor_guide',expected_version=actor['version'],evidence=actor['evidence'],
      reason='Revise my own goal from retained evidence.',changes=dict(goals=['Study '+str(index)]),object=deepcopy(obj))
  context=self.s.inspect();context['runtime']=dict(previous_source=self.fx.candidate.source)
  context['recalled_history']=dict(events=[dict(json.loads(self.s.db.execute("SELECT data FROM events WHERE seq=? AND kind='world_memory'",(seq,)).fetchone()[0]),seq=seq) for seq in actor['evidence']])
  source=compile_actions([action],context);self.fx.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
  ns={};exec(source,ns);result=ns['update'](self.s._context(),deepcopy(self.s.module_state))
  self.fx.commit(result);self.assertIsNone(self.s.module_error)
  return source,ns
 def test_forty_commits_bounded_source_durable_history_restart_and_no_replay(self):
  lengths=[]
  for i in range(40):
   source,ns=self.apply(i);lengths.append(len(source))
   self.assertEqual(len(self.s.module_state['world_character_current_receipt']),1)
   if i==19:
    self.s.close();self.fx.f.server=self.fx.f.open();self.s=self.fx.f.server;self.fx.server=self.s;self.fx.candidate=self.s.candidate
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM character_action_archive').fetchone()[0],40)
  self.assertLess(max(lengths[2:])-min(lengths[2:]),200)
  self.assertEqual(source.count('def _ew_character_dispatch_v1('),1)
  version=self.s.module_state['world_characters']['harbor_guide']['version']
  self.fx.commit(ns['update'](self.s._context(),deepcopy(self.s.module_state)))
  self.assertEqual(self.s.module_state['world_characters']['harbor_guide']['version'],version)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM character_action_archive').fetchone()[0],40)
 def test_existing_full_legacy_receipts_are_preserved_not_cleared(self):
  state=deepcopy(self.s.module_state);legacy=[hashlib.sha256(str(i).encode()).hexdigest() for i in range(32)]
  state['world_character_action_receipts']=legacy
  self.fx.commit(dict(state=state,tiles=[],objects=self.s.objects))
  self.apply(40)
  self.assertEqual(self.s.module_state['world_character_action_receipts'],legacy)
  self.assertEqual(len(self.s.module_state['world_character_current_receipt']),1)
 def test_modified_dispatcher_is_not_rewritten(self):
  source,_=self.apply(1)
  corrupted=source.replace('receipts.clear()','receipts.clear(); print("changed")')
  self.fx.candidate=Candidate(corrupted,hashlib.sha256(corrupted.encode()).hexdigest());self.s.candidate=self.fx.candidate
  with self.assertRaisesRegex(ValueError,'dispatcher changed'):self.apply(2)
