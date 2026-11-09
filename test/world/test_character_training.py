"""Authority -> real compiled component subprocess -> full state -> native party.
Engine Pokemon storage/stat/move APIs are fixtures; no rendered battle claim.
"""
from copy import deepcopy
import hashlib,importlib.util,json,os,subprocess,tempfile,unittest
from pathlib import Path
import test_characters as fixtures
from world.companion_practice import Ledger,Engine
from world.cast_practice_worker import step
from world import character_reactions as reactions
from world.runtime_gm import IntentQueue

@unittest.skipUnless(os.environ.get('EW_NATIVE_SOURCE'),'requires actual native component sources')
class TrainingIntegrationTests(unittest.TestCase):
 def setUp(self):
  self.f=fixtures.CharacterLifecycleTests();self.f.setUp();self.addCleanup(self.f.tearDown);self.s=self.f.server
  c=deepcopy(self.f.character);c['team']=[dict(species=277,level=5,individual='partner')]
  c['intentions']=[dict(id='first_practice',kind='practice',target='partner',reason='Try a bounded practice session.')]
  self.c=c;self.assertIsNone(self.f.commit({'may':c},self.f.npc))
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  spec=importlib.util.spec_from_file_location('fixture',Path(os.environ['EW_NATIVE_SOURCE'])/'tests/character_worker_fixture.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  self.binary=module.build(self.tmp.name,battle=True);self.engine=Engine(self.binary,hashlib.sha256(self.binary.read_bytes()).hexdigest())
  self.ledger=Ledger(Path(self.tmp.name)/'npc-only.db');self.addCleanup(self.ledger.close)
 def request(self,body):
  conn=dict(out=bytearray());self.s._admin_line(conn,json.dumps(body).encode());return json.loads(conn['out'])
 def test_intention_receipt_native_battle_full_state_restart_and_next_author_turn(self):
  queue=IntentQueue(Path(self.tmp.name)/'queue');self.addCleanup(queue.close)
  reactions.configure(queue,self.s.inspect(),'may','Choose a next goal based on real practice results.')
  result=step(self.ledger,self.engine,self.request,validated_native=True,steps=1024,cap=20)
  self.assertEqual(result['status'],'reconciled_to_world_companion')
  full=self.ledger.get('may','partner')['state'];self.assertGreater(full['level'],5)
  peer=self.f.peer(role='SOCIALCHAR1CHARPK1CHARPK2');wire=self.f.send(peer,'CHARACTER_CHALLENGE 1 may 1')
  self.assertTrue(wire.startswith('CHARACTER_BATTLE_V3'),wire);self.assertEqual(wire.split()[-1],full['blob'])
  native=subprocess.run([str(self.binary),'--fixture-battle'],input=wire,text=True,capture_output=True)
  self.assertEqual(native.returncode,0,native.stderr);self.assertEqual(native.stdout.strip(),full['blob'])
  self.f.send(peer,'CHARACTER_RESULT 1 may 1 1') # Client report adds no training/reward.
  self.assertEqual(self.ledger.get('may','partner')['state'],full)
  self.s.peers.pop(peer['id'],None)
  old=self.f.peer(role='SOCIALCHAR1CHARPK1');self.assertIn('CHARACTER_REJECT',self.f.send(old,'CHARACTER_CHALLENGE 1 may 1'))
  payload=result['receipt']['authority_payload'];self.assertTrue(self.request(payload)['already_applied'])
  tampered=deepcopy(payload);tampered['after']['exp']+=1;self.assertFalse(self.request(tampered)['ok'])
  def fetch(query):return dict(ok=True,world_id=self.s.memory.world_id,**self.s.memory.history(**{k:v for k,v in query.items() if k!='command'}))
  self.assertEqual(len(reactions.observe(queue,self.s.inspect(),fetch)),1)
  turn=queue.claim();context=self.s.inspect();context['runtime']=dict(kind='character',observed_event=json.loads(turn['result']))
  prepared=reactions.prepare(context,fetch);self.assertEqual(prepared['id'],'may')
  changed=deepcopy(self.c);changed.update(version=2,goals=['Consider a different exercise after the recorded practice'],evidence=[result['receipt']['world_receipt']],reason='The actual isolated practice result informs this goal')
  changed['intentions']=[];self.assertIsNone(self.f.commit({'may':changed},self.f.npc))
  self.s.close();self.f.server=self.f.open();self.s=self.f.server
  peer=self.f.peer(role='SOCIALCHAR1CHARPK1CHARPK2');self.assertEqual(self.f.send(peer,'CHARACTER_CHALLENGE 1 may 2').split()[-1],full['blob'])
 def test_stale_source_and_authored_level_reset_cannot_replace_earned_state(self):
  result=step(self.ledger,self.engine,self.request,validated_native=True,steps=1024,cap=20)
  self.assertEqual(result['status'],'reconciled_to_world_companion')
  bad=deepcopy(self.c);bad['version']=2;bad['team'][0]['level']=1
  self.assertIsNotNone(self.f.commit({'may':bad},self.f.npc))
  payload=deepcopy(result['receipt']['authority_payload']);payload['job']='f'*32
  self.assertFalse(self.request(payload)['ok'])
