"""Real retained cast authoring/authority -> isolated host job, no live growth claim."""
from copy import deepcopy
import json,tempfile,unittest
from pathlib import Path
import test_canonical_cast as fixture
from test_companion_practice import FakeEngine
from world.companion_practice import Ledger
from world.cast_practice_worker import step
from world import canonical_cast as cast

class CastPracticeTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.ledger=Ledger(Path(self.tmp.name)/'npc-only.db');self.addCleanup(self.ledger.close)
  self.engine=FakeEngine();self.action=self.f.action()
  self.action['changes']['intentions']=[dict(id='patient_practice',kind='practice',target='partner',reason='Try a short practice with my registered companion.')]
  self.f.apply(self.action)
 def request(self,body):
  conn=dict(out=bytearray());self.f.s._admin_line(conn,json.dumps(body).encode());return json.loads(conn['out'])
 def register(self):self.ledger.initialize('canon_rydel','partner',277,5,123,456,self.engine)
 def run_step(self,**kw):return step(self.ledger,self.engine,self.request,validated_native=True,steps=100,cap=10,**kw)
 def test_actual_retained_intention_requires_verified_host_and_registered_companion(self):
  with self.assertRaises(ValueError):step(self.ledger,self.engine,self.request)
  result=self.run_step();self.assertEqual(result['status'],'blocked');self.assertIn('Unknown companion',result['reason'])
  self.assertEqual(self.ledger.db.execute('SELECT count(*) FROM jobs').fetchone()[0],0)
  response=self.request({'command':'cast_practice_intentions'});self.assertEqual(set(response),{'ok','world_id','actors'})
  self.assertNotIn('players',response);self.assertNotIn('state',response)
 def test_one_shot_completion_receipt_does_not_invent_live_world_or_story_growth(self):
  self.register();public=deepcopy(self.f.s.memory.history());state=deepcopy(self.f.s.module_state)
  result=self.run_step();self.assertEqual(result['status'],'completed_in_host_ledger')
  receipt=result['receipt'];self.assertEqual(receipt['exp_added'],100);self.assertEqual(receipt['individual'],'partner')
  self.assertEqual(receipt['publication'],'local_host_ledger_only')
  self.assertEqual(self.f.s.memory.history(),public);self.assertEqual(self.f.s.module_state,state)
  self.assertEqual(self.run_step()['status'],'idle')
  self.ledger.close();self.ledger=Ledger(Path(self.tmp.name)/'npc-only.db');self.addCleanup(self.ledger.close)
  self.assertEqual(self.run_step()['status'],'idle');self.assertEqual(self.ledger.get('canon_rydel','partner')['revision'],2)
  # An agent cannot promote a queued/local practice into a public fulfillment.
  finished=deepcopy(self.action);finished['expected_version']=1
  finished['changes'].update(intentions=[],fulfill='patient_practice')
  with self.assertRaises(ValueError):cast.compile_actions([finished],self.f.context())
 def test_intention_withdrawal_during_native_work_discards_result(self):
  self.register();before=self.ledger.get('canon_rydel','partner');old=self.engine.run
  def run(line):
   out=old(line);changed=deepcopy(self.action);changed['expected_version']=1;changed['changes']['intentions']=[];self.f.apply(changed);return out
  self.engine.run=run
  self.assertEqual(self.run_step()['status'],'failed');self.assertEqual(self.ledger.get('canon_rydel','partner'),before)
 def test_invalid_target_and_budget_fail_closed(self):
  bad=deepcopy(self.action);bad['expected_version']=1;bad['changes']['intentions'][0]['target']='../../player.sav'
  with self.assertRaises(ValueError):cast.compile_actions([bad],self.f.context())
  with self.assertRaises(ValueError):step(self.ledger,self.engine,self.request,validated_native=True,steps=100000)
