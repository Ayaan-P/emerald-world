import json,unittest,tempfile
from copy import deepcopy
from world import companion_evolution as evolution
from world.character_companions import roster,validate
from world.companion_exchange import owned,identity
from world.companion_practice import Ledger
import test_companion_exchange as fixture

class EvolutionTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.ExchangeTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.actor='harbor_guide';self.key='reserve';self.job='a'*32;self.engine='e'*64
  mon=next(m for m in roster(self.s,self.actor) if m['individual']==self.key)
  self.before=dict(size=100,species=mon['species'],level=22,personality=mon['personality'],owner=mon['owner'],exp=10648,blob='11'*100)
  self.after=dict(self.before,species=278,blob='22'*100)
  with self.s.db:
   self.s.db.execute('INSERT INTO character_training VALUES(?,?,?,?,?)',(self.actor,self.key,self.engine,16,json.dumps(self.before,sort_keys=True)))
   seq=self.s.memory.append('character_practice_completed',dict(character_id=self.actor,individual=self.key,job=self.job,before_level=21,after_level=22))
   self.s.db.execute('INSERT INTO character_training_receipts VALUES(?,?,?,?,?)',(self.job,self.actor,self.key,seq,'fixture'))
 def payload(self):
  src=evolution.source(self.s,self.actor,self.key,self.job)
  return dict(command='character_evolution_apply',actor=self.actor,individual=self.key,practice=self.job,token=src['token'],engine=self.engine,after=self.after)
 def test_retained_identity_native_state_replay_restart_and_new_lineup(self):
  before=self.before
  # Former owner alias must not become a second owned copy after species change.
  with self.s.db:
   self.s.db.execute('INSERT INTO character_companions VALUES(?,?,?,?,?)',('visitor','old_alias',before['species'],before['personality'],before['owner']))
   self.s.db.execute('INSERT INTO companion_custody VALUES(?,?)',(identity((before['species'],before['personality'],before['owner'])),self.actor))
  payload=self.payload();result=evolution.apply(self.s,payload)
  self.assertTrue(result['ok']);self.assertTrue(evolution.apply(self.s,payload)['already_applied'])
  self.assertFalse(owned(self.s.db,'visitor','old_alias'))
  mon=next(m for m in roster(self.s,self.actor) if m['individual']==self.key)
  self.assertEqual((mon['species'],mon['level'],mon['personality'],mon['owner']),(278,22,before['personality'],before['owner']))
  self.assertFalse(mon['on_team'])
  self.s.close();self.f.fx.f.server=self.f.fx.f.open();self.s=self.f.fx.f.server;self.f.s=self.s;self.f.fx.server=self.s
  self.assertTrue(evolution.apply(self.s,payload)['already_applied'])
  validate(self.s.db,self.actor,dict(team=[dict(individual=self.key,species=278,level=22)]))
  with self.assertRaises(ValueError):validate(self.s.db,self.actor,dict(team=[dict(individual=self.key,species=277,level=22)]))
 def test_wrong_identity_no_level_gain_or_changed_source_refused(self):
  payload=self.payload();payload['after']=dict(self.after,owner=0)
  with self.assertRaises(ValueError):evolution.apply(self.s,payload)
  payload=self.payload()
  with self.s.db:self.s.db.execute('UPDATE character_training SET state=? WHERE actor=? AND individual=?',(json.dumps(dict(self.before,blob='33'*100)),self.actor,self.key))
  with self.assertRaises(ValueError):evolution.apply(self.s,payload)
 def test_atomic_history_failure(self):
  from unittest.mock import patch
  payload=self.payload()
  with patch.object(self.s.memory,'append',side_effect=RuntimeError('fixture')):
   with self.assertRaises(RuntimeError):evolution.apply(self.s,payload)
  self.assertEqual(next(m for m in roster(self.s,self.actor) if m['individual']==self.key)['species'],277)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM companion_evolutions').fetchone()[0],0)
 def test_host_gate_and_reconciliation_retry_never_reruns_native(self):
  with tempfile.TemporaryDirectory() as d:
   ledger=Ledger(d+'/jobs');self.addCleanup(ledger.close)
   with ledger.db:ledger.db.execute('INSERT INTO companions VALUES(?,?,?,?,?)',(self.actor,self.key,self.engine,1,json.dumps(self.before,sort_keys=True)))
   with ledger.db:ledger.db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?)',(self.job,self.actor,self.key,self.engine,1,json.dumps(dict(self.before,level=21,exp=10000)),648,22,'completed',json.dumps(self.before)))
   calls=[]
   class Engine:
    digest=self.engine
    def run(engine,line):calls.append(line);return self.after
   def request(body):
    if body['command'].endswith('_source'):return dict(ok=True,source=evolution.source(self.s,self.actor,self.key,self.job))
    return evolution.apply(self.s,body)
   with self.assertRaises(ValueError):evolution.dispatch(ledger,Engine(),request,self.actor,self.key,self.job)
   def lost(body):
    result=request(body)
    if body['command'].endswith('_apply'):raise TimeoutError('reply lost')
    return result
   with self.assertRaises(TimeoutError):evolution.dispatch(ledger,Engine(),lost,self.actor,self.key,self.job,validated_evolution=True)
   self.assertEqual(len(calls),1)
   self.assertEqual(evolution.dispatch(ledger,Engine(),request,self.actor,self.key,self.job,validated_evolution=True)['status'],'evolved')
   self.assertEqual(len(calls),1);self.assertEqual(ledger.get(self.actor,self.key)['state'],self.after)
