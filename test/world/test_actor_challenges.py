from copy import deepcopy
import json,hashlib,unittest
import test_character_companions as fixture
from world import actor_runtime as runtime
from world.character_companions import roster
from world.mechanics import Candidate

class ChallengeTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CompanionIdentityTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
 def plan(self,ids):
  c=deepcopy(self.s.module_state['world_characters']['may']);c['version']+=1
  c['plan']=dict(id='prepare_'+str(c['version']),purpose='Choose an owned lineup.',steps=[dict(id='prepare',tool='world.prepare_challenge',args=dict(lineup=json.dumps(ids),text='Care for a friendly battle?'),after=[])])
  self.assertIsNone(self.f.f.commit({'may':c},self.f.f.npc))
  from concurrent.futures import Future
  source='def update(context,state):\n return dict(state=state,tiles=[],objects='+repr(self.s.objects)+')\n'
  future=Future();future.set_result((Candidate(source,hashlib.sha256(source.encode()).hexdigest()),dict(state=self.s.module_state,tiles=[],objects=self.s.objects)))
  self.s.job=(future,'deploy',None,self.s.interaction_cursor);self.s._poll_mechanics()
 def admit(self):
  _,path,_=self.s.deployment;self.s.deployment=None;source=path.read_text();ns={};exec(source,ns)
  from concurrent.futures import Future
  future=Future();future.set_result((Candidate(source,hashlib.sha256(source.encode()).hexdigest()),ns['update'](self.s._context(),deepcopy(self.s.module_state))))
  self.s.job=(future,'deploy',None,self.s.interaction_cursor);self.s._poll_mechanics();self.assertIsNone(self.s.module_error)
 def test_owned_lineup_native_choice_frozen_snapshot_and_bench_return(self):
  before=roster(self.s,'may');self.plan(['coastal_partner'])
  self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending');self.admit()
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded')
  self.assertEqual(len(roster(self.s,'may')),2)
  self.s.close();self.f.f.server=self.f.f.open();self.s=self.f.f.server;self.f.s=self.s
  self.assertFalse(next(m for m in roster(self.s,'may') if m['individual']=='cedar_partner')['on_team'])
  peer=self.f.f.peer(role='SOCIALCHAR1CHARPK1')
  version=self.s.module_state['world_characters']['may']['version']
  wire=self.f.f.send(peer,f'CHARACTER_CHALLENGE 1 may {version}')
  values=self.f.values(wire);self.assertEqual(len(values),1);self.assertEqual(values[0][0],278)
  frozen=deepcopy(peer['character_pending'])
  self.plan(['cedar_partner','coastal_partner']);runtime.tick(self.s,now=22);self.admit();runtime.tick(self.s,now=28)
  self.assertEqual(peer['character_pending'],frozen)
  self.assertEqual([(m['individual'],m['personality'],m['owner']) for m in roster(self.s,'may')],[(m['individual'],m['personality'],m['owner']) for m in before])
  self.f.f.send(peer,f'CHARACTER_RESULT 1 may {version} 1')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM character_training').fetchone()[0],0)
 def test_unknown_companion_never_mints_or_stages(self):
  self.plan(['invented_capture']);self.assertEqual(runtime.tick(self.s,now=10)['status'],'blocked');self.assertIsNone(self.s.deployment)
 def test_new_population_gets_stable_baseline_identity(self):
  import test_actor_population as population
  f=population.PopulationTests();f.setUp();self.addCleanup(f.doCleanups)
  f.plan();runtime.tick(f.s,now=10);runtime.tick(f.s,now=16);f.admit();runtime.tick(f.s,now=22)
  rows=roster(f.s,'researcher');self.assertEqual(rows[0]['individual'],'partner_1');self.assertEqual(rows[0]['level'],8);self.assertFalse(rows[0]['trained'])
 def test_preparation_preserves_reconciled_full_native_state(self):
  import os,subprocess
  if not os.environ.get('EW_NATIVE_SOURCE'):self.skipTest('requires paired native component fixture')
  from types import SimpleNamespace
  from test_character_training import TrainingIntegrationTests
  from world.cast_practice_worker import step
  f=TrainingIntegrationTests();f.setUp();self.addCleanup(f.doCleanups)
  trained=step(f.ledger,f.engine,f.request,validated_native=True,steps=1024,cap=20)
  self.assertEqual(trained['status'],'reconciled_to_world_companion')
  full=f.ledger.get('may','partner')['state']
  helper=ChallengeTests();helper.s=f.s;helper.f=SimpleNamespace(f=f.f)
  helper.plan(['partner']);self.assertEqual(runtime.tick(f.s,now=10)['status'],'pending');helper.admit();runtime.tick(f.s,now=16)
  version=f.s.module_state['world_characters']['may']['version'];peer=f.f.peer(role='SOCIALCHAR1CHARPK1CHARPK2')
  wire=f.f.send(peer,f'CHARACTER_CHALLENGE 1 may {version}');self.assertTrue(wire.startswith('CHARACTER_BATTLE_V3'));self.assertEqual(wire.split()[-1],full['blob'])
  from pathlib import Path
  # Fixture pending request must match the actual newly prepared character version.
  path=Path(f.tmp.name)/'worker.c';path.write_text(path.read_text().replace('sWorld.character.version=1;',f'sWorld.character.version={version};'))
  binary=Path(f.tmp.name)/'battle_revision';subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(path),'-o',str(binary)],check=True)
  native=subprocess.run([str(binary),'--fixture-battle'],input=wire,text=True,capture_output=True)
  self.assertEqual(native.returncode,0,native.stderr);self.assertEqual(native.stdout.strip(),full['blob'])
