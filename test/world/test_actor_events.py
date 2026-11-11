import copy,json,unittest
import test_actor_runtime as fixture
from world import actor_runtime as runtime

class EventWaitTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.ActorRuntimeTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
 def plan(self,kind='canonical_letter_delivered',filters=None):
  return dict(id='react',purpose='Act on a real committed event.',steps=[
   dict(id='wait',tool='world.await_event',args=dict(event=kind,where=json.dumps(filters or {})),after=[]),
   dict(id='act',tool='world.act',args=dict(pack='workshop',scene='organize',choice='open',place='LittlerootTown',revision=0),after=['wait'])])
 def test_actual_other_actor_event_restart_then_authority_effect(self):
  p=self.plan(filters={'recipient':'canon_rydel'});p['steps'].append(dict(id='tell',tool='actor.message',args=dict(to='canon_wally',text=dict(result='wait',key='event_text')),after=['wait','act']))
  self.f.apply(p);self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending')
  self.assertIsNone(runtime.tick(self.s,now=16));self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_consequences').fetchone()[0],0)
  reply=dict(id='speak',purpose='Independently contact another actor.',steps=[dict(id='send',tool='actor.message',args=dict(to='canon_rydel',text='We can discuss our plans.'),after=[])])
  self.f.apply(reply,1,actor='canon_wally');self.assertEqual(runtime.tick(self.s,now=22)['actor'],'canon_wally')
  self.s.close();case=self.f.f.f.f.case;case.server=case.open();self.s=case.server
  self.assertEqual(runtime.tick(self.s,now=28)['step'],'wait')
  self.assertEqual(runtime.tick(self.s,now=34)['step'],'act');self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_consequences').fetchone()[0],1)
  self.assertEqual(runtime.tick(self.s,now=40)['step'],'tell')
  self.assertIsNone(runtime.tick(self.s,now=46))
 def test_backlog_paging_private_kinds_and_old_events(self):
  with self.s.db:self.s.memory.append('test_signal',dict(value=2))
  self.f.apply(self.plan('test_signal',{'value':2}));runtime.tick(self.s,now=10)
  with self.s.db:
   self.s.db.execute('INSERT INTO events(kind,data) VALUES(?,?)',('private_test',json.dumps(dict(event='test_signal',value=2))))
   for i in range(130):self.s.memory.append('unrelated_fixture',dict(index=i))
   seq=self.s.memory.append('test_signal',dict(value=2))
  self.assertIsNone(runtime.tick(self.s,now=16));self.assertIsNone(runtime.tick(self.s,now=22))
  self.assertEqual(runtime.tick(self.s,now=28)['status'],'succeeded')
  payload=json.loads(self.s.db.execute("SELECT result FROM actor_tool_receipts WHERE step='wait'").fetchone()[0]);self.assertEqual(payload['event_seq'],seq);self.assertEqual(payload['event_value'],2)
 def test_invalid_filter_does_not_subscribe(self):
  p=self.plan();p['steps'][0]['args']['where']='{"value":[]}'
  self.f.apply(p);self.assertEqual(runtime.tick(self.s,now=10)['status'],'blocked')
