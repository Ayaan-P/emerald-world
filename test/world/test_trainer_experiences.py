"""Real callback wire -> public history -> independently authored native opportunity."""
import importlib.util,json,os,subprocess,tempfile,unittest
from pathlib import Path
import test_canonical_world_actions as fixture
from world import trainer_experiences as experience,canonical_world_actions as actions,character_reactions as reactions
from world.runtime_gm import IntentQueue
from world.build_catalog import catalog_maps

class TrainerExperienceTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.WorldActionTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.peer=self.f.f.peer();self.peer['core_active_run']='a'*32
  self.key=next(k for k,v in experience.catalog().items() if v['symbol']=='TRAINER_WALLY_VR_1')
  self.place=next(p for p,m in catalog_maps().items() if m['name']=='LittlerootTown')
 def send(self,serial=1,outcome=2,run=None):
  return self.s.core_story.handle(self.peer,['CORE',run or 'a'*32,'BATTLE',self.key,f'{outcome}:{self.place[0]}:{self.place[1]}:{serial}'])
 def test_loss_can_prompt_real_actor_action_without_granting_player_progress(self):
  a=self.f.f.action();self.f.f.apply(a)
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    reactions.configure(q,self.s.inspect(),'canon_rydel','React to actual voluntarily shared results, without inferring identity or training.')
    self.assertEqual(reactions.observe(q,self.s.inspect(),self.f.f.fetch),[])
    seq=self.send()['evidence'];event=next(e for e in self.s.memory.history()['events'] if e['seq']==seq)
    self.assertEqual(event['outcome'],'lost');self.assertTrue(experience.relevant(event,['native:LittlerootTown']))
    self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.f.f.fetch)),1)
    item=q.claim();ctx=self.f.f.context();ctx['runtime'].update(kind='character',observed_event=json.loads(item['result']))
    a=self.f.actor(version=1,evidence=seq)
    reactions.check_response(dict(canonical_actions=[a],tests='assert True'),reactions.prepare(ctx,self.f.f.fetch));self.f.f.apply(a)
    self.assertEqual(actions.step(self.s,now=10)['status'],'completed')
    self.assertEqual(self.s.opportunities.offers('Alice','LittlerootTown')[0]['scenes'][0]['id'],'solo')
    self.assertEqual(self.s.db.execute('SELECT count(*) FROM core_story_progress').fetchone()[0],0)
    self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_players').fetchone()[0],0)
    self.assertEqual(self.send()['evidence'],seq)
    with self.assertRaises(ValueError):self.send(outcome=1)
    with self.assertRaises(ValueError):self.send(run='b'*32)
    for secret in ('Alice','Bob','a'*32,'b'*32):self.assertNotIn(secret,json.dumps(event))
   finally:q.close()
 def test_actual_native_packet_dispatch_and_catalogue_match(self):
  root=Path(os.environ.get('EW_NATIVE_SOURCE','../native-battle-experiences')).resolve()
  test=root/'tests/test_trainer_experiences.py'
  if not test.exists():self.skipTest('paired native source required')
  spec=importlib.util.spec_from_file_location('native_trainer_fixture',test);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  code=module.controller_code()
  with tempfile.TemporaryDirectory() as tmp:
   src=Path(tmp)/'test.c';src.write_text(code);exe=Path(tmp)/'test'
   subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(src),'-o',str(exe)],check=True,capture_output=True)
   packet=subprocess.run([str(exe)],check=True,capture_output=True,text=True).stdout.strip().split()
  self.peer['out'].clear();self.s._line(self.peer,' '.join(packet).encode())
  self.assertIn(' OK',self.peer['out'].decode())
  event=next(e for e in self.s.memory.history()['events'] if e['event']=='canonical_trainer_result');
  self.assertTrue(experience.relevant(event,[],'canon_wally'))
  self.assertFalse(experience.relevant(event,[],'canon_briney'))
  self.assertEqual(event['opponent_preset'],'TRAINER_WALLY_VR_1')
  import hashlib
  meta=json.loads(Path(experience.__file__).with_name('trainer_experience_catalog.json').read_text())
  self.assertEqual(hashlib.sha256((root/'src/data/trainers.party').read_bytes()).hexdigest(),meta['source_sha256'])
 def test_invalid_input_and_unshared_results_never_enter_history(self):
  before=self.s.memory.history()['through']
  with self.assertRaises(ValueError):self.send(outcome=3)
  self.peer['state_time']-=10
  with self.assertRaises(ValueError):self.send()
  self.assertEqual(self.s.memory.history()['through'],before)

 def test_shared_receipt_survives_restart_without_becoming_another_save_progress(self):
  seq=self.send()['evidence'];world=self.s.memory.world_id
  self.s.close();case=self.f.f.f.case;case.server=case.open();self.s=case.server
  self.f.s=self.s;self.f.f.s=self.s;self.f.f.f.server=self.s
  self.assertEqual(self.s.memory.world_id,world)
  self.assertTrue(any(e['seq']==seq and e['event']=='canonical_trainer_result' for e in self.s.memory.history()['events']))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM core_story_progress').fetchone()[0],0)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM trainer_experience_receipts').fetchone()[0],1)
