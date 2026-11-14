import copy,json,tempfile,unittest,hashlib
from unittest.mock import patch
import test_cooperative_moves as fixture
from world import move_witnesses as witness,character_reactions,overworld_moves

class WitnessTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.Cooperative();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
 def configure(self,actor='harbor_guide',radius=4):
  with self.s.db,patch.object(witness.time,'time',return_value=100):return witness.configure(self.s,actor,{},dict(mode='local',radius=radius,cooldown=30))
 def event(self,seq):return json.loads(self.s.db.execute('SELECT data FROM events WHERE seq=?',(seq,)).fetchone()[0])
 def commit_move(self,t=1):
  p=self.s.peers.get('UserOne') or self.f.peer('UserOne');self.f.act(p,'charge');self.f.admit(t)
 def test_unchanged_object_real_receipt_and_independent_response(self):
  from world.runtime_gm import IntentQueue
  self.configure();before=copy.deepcopy(self.s.objects)
  with tempfile.TemporaryDirectory() as root:
   q=IntentQueue(root);self.addCleanup(q.close)
   character_reactions.configure(q,self.s.inspect(),'harbor_guide','Choose my own response to local move actions.')
   self.commit_move();self.assertEqual(self.s.objects,before)
   self.assertEqual(witness.tick(self.s,120),[])
   seq=witness.tick(self.s,131)[0];e=self.event(seq);self.assertEqual(e['moves'][0]['move'],85)
   source=self.event(e['moves'][0]['receipt']);self.assertEqual(source['event'],'object_move_committed');self.assertEqual(e['moves'][0]['basis'],'client_reported_learned_move')
   self.assertNotIn('individual',e['moves'][0]);self.assertFalse(character_reactions.dynamic_result(e,'second',{}))
   fetch=lambda query:dict(ok=True,world_id=self.s.memory.world_id,**self.s.memory.history(**{k:v for k,v in query.items() if k!='command'}))
   queued=character_reactions.observe(q,self.s.inspect(),fetch);self.assertEqual(len(queued),1)
   packet=json.loads(q.db.execute('SELECT result FROM requests WHERE id=?',(queued[0],)).fetchone()[0]);self.assertEqual(packet['evidence'],seq)
   context=self.s.inspect();context['runtime']={'kind':'character','observed_event':packet,'previous_source':self.s.candidate.source}
   self.assertEqual(character_reactions.prepare(context,fetch)['evidence'],seq)
   # Fixture author response, not a claimed live-model result. Ordinary action
   # compiler and admission produce actual visible NPC dialogue.
   from world.character_actions import compile_actions
   from world.mechanics import Candidate
   obj=dict(next(o for o in self.s.objects if o['id']=='harbor_guide'),text='I noticed that move.')
   action=dict(id='harbor_guide',expected_version=packet['expected_version'],evidence=[seq],reason='Respond to the exact locally committed move.',changes={},object=obj)
   code=compile_actions([action],context);ns={};exec(code,ns)
   base=self.f.f.f.f.f.f;base.candidate=Candidate(code,hashlib.sha256(code.encode()).hexdigest());base.commit(ns['update'](self.s._context(),copy.deepcopy(self.s.module_state)))
   self.assertIsNone(self.s.module_error);self.assertEqual(next(o for o in self.s.objects if o['id']=='harbor_guide')['text'],'I noticed that move.')
   self.assertEqual(character_reactions.observe(q,self.s.inspect(),fetch),[])
 def test_failed_effect_no_notice_and_off_drops_pending(self):
  self.configure();p=self.f.peer('UserOne');self.f.act(p,'charge');self.s.deployment=None
  from world import actor_objects
  actor_objects.poll_player(self.s);self.assertEqual(witness.tick(self.s,131),[])
  self.commit_move(2)
  with self.s.db:witness.configure(self.s,'harbor_guide',{},dict(mode='off',radius=4,cooldown=30))
  self.assertEqual(witness.tick(self.s,200),[])
 def test_restart_preserves_pending_and_no_replay(self):
  self.configure();self.commit_move();self.s.close();base=self.f.f.f.f.f.f.f;base.server=base.open();self.s=base.server
  seq=witness.tick(self.s,131)[0];self.assertEqual(len(self.event(seq)['moves']),1)
  request=self.event(seq)['moves'][0]['request']
  with self.s.db:overworld_moves.admitted(self.s,request)
  self.assertEqual(witness.tick(self.s,200),[])
 def test_locality_at_commit_not_later_global_history(self):
  self.configure(actor='second',radius=1);self.commit_move();self.assertEqual(witness.tick(self.s,131),[])
  self.configure(actor='second',radius=4);self.commit_move(2)
  event=self.event(witness.tick(self.s,131)[0]);self.assertEqual(event['character_id'],'second')
  self.assertEqual(event['moves'][0]['observer_position'],[74,70])
 def test_bounded_batches_and_clock_rollback(self):
  self.configure()
  for n in range(10):self.commit_move(n+1)
  pending=witness.discover(self.s)[0];self.assertEqual((pending['pending'],pending['omitted']),(8,2))
  self.assertEqual(witness.tick(self.s,90),[]);self.assertEqual(witness.tick(self.s,110),[])
  e=self.event(witness.tick(self.s,121)[0]);self.assertEqual(len(e['moves']),8);self.assertEqual(e['omitted'],2)
  self.commit_move(20);self.assertEqual(len(self.event(witness.tick(self.s,152)[0])['moves']),1)

 def test_npc_actual_inspection_provenance_and_self_exclusion(self):
  self.configure();self.configure(actor='second')
  self.f.test_npc_native_inspection_contributes_without_fabricating_a_player()
  events=[self.event(seq) for seq in witness.tick(self.s,131)]
  own=next(e for e in events if e['character_id']=='harbor_guide')
  other=next(e for e in events if e['character_id']=='second')
  self.assertEqual(len(own['moves']),1)
  self.assertEqual([m['basis'] for m in other['moves']],['client_reported_learned_move','matching_native_move_inspection'])
  self.assertEqual(other['moves'][1]['character_id'],'harbor_guide')
  self.assertNotIn('individual',other['moves'][1])
 def test_real_runtime_registration_and_validation(self):
  from world import actor_runtime
  from world.mechanics import Candidate
  state=copy.deepcopy(self.s.module_state);actor=state['world_characters']['harbor_guide'];actor['version']+=1
  actor['plan']=dict(id='watch_moves',purpose='Notice actual local move effects and decide independently.',steps=[dict(id='watch',tool='world.attend_moves',args=dict(mode='local',radius=4,cooldown=30),after=[])])
  base=self.f.f.f.f.f.f;base.commit(dict(state=state,tiles=[],objects=self.s.objects))
  with patch.object(witness.time,'time',return_value=100):result=actor_runtime.tick(self.s,now=22)
  self.assertEqual(result['status'],'succeeded')
  self.assertEqual(self.s.inspect()['actor_runtime']['move_attention'][0]['actor'],'harbor_guide')
  for args in [dict(mode='local',radius=True,cooldown=30),dict(mode='local',radius=4,cooldown=0)]:
   with self.assertRaises(ValueError):witness.configure(self.s,'harbor_guide',{},args)
