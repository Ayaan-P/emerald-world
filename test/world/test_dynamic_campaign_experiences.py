"""Consented reports -> real author queue -> chosen supported world action.
Author output is a deterministic fixture, not a live model claim.
"""
from copy import deepcopy
import hashlib,json,tempfile,unittest
import test_shared_outbreaks as fixture
from world import character_reactions as reactions,trainer_experiences as reports,actor_runtime
from world.character_actions import compile_actions,action_step
from world.mechanics import Candidate
from world.runtime_gm import IntentQueue

class DynamicCampaignTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.OutbreakTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.c=deepcopy(self.f.f.character);self.c['campaign_interests']=['native:Route102'];self.c['version']=2
  self.f.f.commit(dict(state={'world_characters':{'harbor_guide':self.c}},tiles=[],objects=[self.f.f.obj]))
  self.assertIsNone(self.s.module_error)
  self.peer=self.f.peer();self.peer['core_active_run']='a'*32
  self.key=next(iter(reports.catalog()));self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.q=IntentQueue(self.tmp.name);self.addCleanup(self.q.close)
  reactions.configure(self.q,self.s.inspect(),'harbor_guide','Choose freely how public campaign reports affect your goals. Reports are anonymous claims, not earned growth.')
 def fetch(self,query):return dict(ok=True,world_id=self.s.memory.world_id,**self.s.memory.history(**{k:v for k,v in query.items() if k!='command'}))
 def report(self,serial=1):
  group,num=self.peer['state'][:2]
  return reports.handle(self.s,self.peer,'a'*32,self.key,f'2:{group}:{num}:{serial}',automatic=True)
 def test_consented_report_author_choice_actual_world_snapshot_without_growth(self):
  with self.assertRaises(ValueError):self.report()
  self.assertEqual(reactions.observe(self.q,self.s.inspect(),self.fetch),[])
  reports.participation(self.s,self.peer,'a'*32,'on','confirm');seq=self.report()['evidence']
  self.assertEqual(len(reactions.observe(self.q,self.s.inspect(),self.fetch)),1)
  item=self.q.claim();context=self.s.inspect();context['runtime']=dict(kind='character',observed_event=json.loads(item['result']),previous_source=self.f.f.source)
  reaction=reactions.prepare(context,self.fetch)
  action=dict(id='harbor_guide',expected_version=2,evidence=[seq],reason='Consider a habitat opportunity after a public report; no victory or training inferred.',changes=dict(goals=['Offer a different local habitat opportunity'],plan=dict(id='respond',purpose='Change a supported world encounter opportunity.',steps=[dict(id='habitat',tool='world.configure_outbreak',args=self.f.args,after=[])])),object=deepcopy(self.f.f.obj))
  reactions.check_response(dict(character_actions=[action],tests='assert True'),reaction)
  code=compile_actions([action],context);definition=hashlib.sha256(json.dumps([action],sort_keys=True).encode()).hexdigest()
  self.f.f.candidate=Candidate(code,hashlib.sha256(code.encode()).hexdigest())
  self.f.f.commit(action_step([action],definition,dict(state=self.s.module_state,tiles=[],objects=self.s.objects)))
  self.assertIsNone(self.s.module_error);self.assertEqual(actor_runtime.tick(self.s,now=10)['status'],'succeeded')
  self.assertIn('WILD_OUTBREAK',self.s._snapshot(self.peer))
  self.assertEqual(self.s.module_state['world_characters']['harbor_guide']['team'],self.c['team'])
  event=next(e for e in self.s.memory.history()['events'] if e['seq']==seq)
  self.assertIn('client attestation',event['limits'])
  for private in ('Alice','a'*32):self.assertNotIn(private,json.dumps(event))
 def test_interest_withdrawal_and_no_interest_prevent_reaction(self):
  reports.participation(self.s,self.peer,'a'*32,'on','confirm');self.report()
  self.c['campaign_interests']=[];self.c['version']=3
  self.f.f.commit(dict(state={'world_characters':{'harbor_guide':self.c}},tiles=[],objects=[self.f.f.obj]))
  self.assertEqual(reactions.observe(self.q,self.s.inspect(),self.fetch),[])
 def test_other_save_and_revoked_mode_cannot_feed_future_events(self):
  reports.participation(self.s,self.peer,'a'*32,'on','confirm');seq=self.report()['evidence']
  self.peer['core_active_run']='b'*32
  with self.assertRaises(ValueError):self.report(2)
  self.peer['core_active_run']='a'*32;reports.participation(self.s,self.peer,'a'*32,'off','confirm')
  with self.assertRaises(ValueError):self.report(3)
  self.assertEqual(self.s.memory.history()['through'],seq)
