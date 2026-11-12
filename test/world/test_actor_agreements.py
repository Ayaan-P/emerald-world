import json,sqlite3,unittest
from copy import deepcopy
from unittest.mock import patch
import test_shared_outbreaks as fixture
from world import actor_agreements as agreements,actor_runtime as runtime,shared_outbreaks

class AgreementTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.OutbreakTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s;self.peer=self.f.peer();self.now=10
  state=deepcopy(self.s.module_state);other=deepcopy(self.f.f.character);other.update(name='Other Researcher',object_id='other')
  state['world_characters']['other']=other;obj=dict(self.f.f.obj,id='other',x=4)
  self.f.f.commit(dict(state=state,tiles=[],objects=[self.f.f.obj,obj]));self.assertIsNone(self.s.module_error)
 def run_tool(self,actor,tool,args,plan):
  state=deepcopy(self.s.module_state)
  c=state['world_characters'][actor];c['version']+=1;c['plan']=dict(id=plan,purpose='Choose an independent shared action.',steps=[dict(id='act',tool=tool,args=args,after=[])])
  self.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
  self.now+=6;return runtime.tick(self.s,now=self.now)
 def propose(self):
  r=self.run_tool('harbor_guide','world.propose_agreement',dict(participants='["other"]',purpose='Collaborate on a temporary population.',tool='world.configure_outbreak',args=json.dumps(self.f.args),hours=1),'offer')
  self.assertEqual(r['status'],'succeeded');return self.s.db.execute('SELECT id FROM actor_agreements').fetchone()[0]
 def accept(self,key):return self.run_tool('other','world.decide_agreement',dict(agreement=key,decision='accept'),'accept')
 def test_independent_choices_real_native_effect_and_idempotency(self):
  key=self.propose();self.assertIsNone(shared_outbreaks.line(self.s,self.peer))
  self.assertEqual(self.accept(key)['status'],'succeeded');self.assertIsNone(shared_outbreaks.line(self.s,self.peer))
  self.assertEqual(self.run_tool('harbor_guide','world.commit_agreement',dict(agreement=key),'commit')['status'],'succeeded')
  wire=next(line for line in self.s._snapshot(self.peer).splitlines() if line.startswith('WILD_OUTBREAK'))
  import pathlib,importlib.util,tempfile,subprocess
  path=pathlib.Path('../native-shared-outbreaks/tests/test_outbreak.py').resolve()
  if path.exists():
   spec=importlib.util.spec_from_file_location('agreed_outbreak_native',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
   with tempfile.TemporaryDirectory() as d:subprocess.run([str(module.build(d,wire))],check=True,capture_output=True)
  events=[e for e in self.s.memory.history()['events'] if e['event']=='shared_outbreak_configured'];self.assertEqual(len(events),1)
  self.run_tool('harbor_guide','world.commit_agreement',dict(agreement=key),'again')
  self.assertEqual(len([e for e in self.s.memory.history()['events'] if e['event']=='shared_outbreak_configured']),1)
  event=next(e for e in self.s.memory.history()['events'] if e['event']=='actor_agreement_applied')
  self.assertEqual(event['result']['outcome'],'shared_outbreak_configured')
 def test_no_unilateral_execution_decline_and_expiry(self):
  key=self.propose();self.assertEqual(self.run_tool('harbor_guide','world.commit_agreement',dict(agreement=key),'early')['status'],'blocked')
  self.assertEqual(self.run_tool('other','world.decide_agreement',dict(agreement=key,decision='decline'),'decline')['status'],'succeeded')
  self.assertEqual(self.run_tool('harbor_guide','world.commit_agreement',dict(agreement=key),'late')['status'],'blocked')
  self.assertIsNone(shared_outbreaks.line(self.s,self.peer))
 def test_native_operation_guard_retained_no_partial_commit(self):
  key=self.propose();self.accept(key)
  with self.s.db:shared_outbreaks.configure(self.s,'other',{},self.f.args)
  before=self.s.db.execute('SELECT * FROM shared_outbreaks').fetchall()
  self.assertEqual(self.run_tool('harbor_guide','world.commit_agreement',dict(agreement=key),'collision')['status'],'blocked')
  self.assertEqual(self.s.db.execute('SELECT * FROM shared_outbreaks').fetchall(),before)
  self.assertEqual(agreements.load(self.s,key)[3],'open')
  self.assertFalse(any(e['event']=='actor_agreement_applied' for e in self.s.memory.history()['events']))
 def test_restart_retains_acceptances_and_expiry_blocks(self):
  key=self.propose();self.accept(key)
  db=sqlite3.connect(':memory:');self.s.db.backup(db);old=self.s.db;self.s.db=db
  try:
   agreements.setup(db);self.assertEqual(agreements.load(self.s,key)[2],{'harbor_guide':'accept','other':'accept'})
   with patch('world.actor_agreements.time.time',return_value=agreements.load(self.s,key)[4]+1):
    with self.assertRaises(ValueError):agreements.commit(self.s,'harbor_guide',{},dict(agreement=key))
   self.assertEqual(agreements.discover(self.s)['open'][0]['id'],key)
  finally:self.s.db=old;db.close()
 def test_reaction_routes_and_nonparticipants_cannot_decide(self):
  from world.character_reactions import dynamic_result
  from world.canonical_cast import reaction_activity
  key=self.propose();event=next(e for e in self.s.memory.history()['events'] if e['event']=='actor_agreement_proposed')
  self.assertTrue(dynamic_result(event,'other',{}));self.assertTrue(reaction_activity(event,'other',{}))
  self.assertFalse(agreements.relevant(event,'outsider'))
  with self.assertRaises(ValueError):agreements.decide(self.s,'outsider',{},dict(agreement=key,decision='accept'))
