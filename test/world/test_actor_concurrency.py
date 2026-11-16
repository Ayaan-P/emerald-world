"""Real authority/chat/receipt execution; no model or rendered-game claims."""
import copy,json,unittest
import test_npc_conversations as conversations
import test_actor_runtime as canonical
from world import actor_runtime as runtime,npc_conversations as speech

class ConcurrentActivityTests(unittest.TestCase):
 def setUp(self):
  self.f=conversations.ConversationTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
 def install(self,steps):
  c=copy.deepcopy(self.f.f.character);c.update(version=2,plan=dict(id='independent',purpose='Stay available while awaiting a real outcome.',steps=steps))
  self.assertIsNone(self.f.f.commit({'may':c},self.f.f.npc))
 def wait(self,key,event):return dict(id=key,tool='world.await_event',args=dict(event=event,where='{}'),after=[])
 def status(self,key):return self.s.db.execute('SELECT status FROM actor_tool_receipts WHERE actor=? AND plan=? AND step=?',('may','independent',key)).fetchone()[0]
 def test_two_real_waits_reply_to_player_and_original_completion(self):
  self.install([self.wait('project','project_result'),self.wait('visitor','player_addressed_character'),
   dict(id='answer',tool='world.reply_player',args=dict(speech=dict(result='visitor',key='event_seq'),text='I can talk while I wait.'),after=['visitor'])])
  self.assertEqual(runtime.tick(self.s,now=10)['step'],'project')
  self.assertEqual(runtime.tick(self.s,now=16)['step'],'visitor')
  seq=self.f.say();self.assertEqual(runtime.tick(self.s,now=22)['step'],'visitor')
  self.assertEqual(runtime.tick(self.s,now=28)['step'],'answer');speech.flush(self.s)
  self.assertEqual(self.status('project'),'pending')
  self.assertTrue(any('talk while I wait' in bytes.fromhex(v[3]).decode() for v in self.f.peer['chat_history']))
  with self.s.db:self.s.memory.append('project_result',dict(result='real test event'))
  self.assertEqual(runtime.tick(self.s,now=34)['step'],'project')
  self.assertEqual(self.status('project'),'succeeded')
  self.assertIsNone(runtime.tick(self.s,now=40))
 def test_restart_preserves_waits_and_does_not_replay_reply(self):
  self.install([self.wait('project','project_result'),dict(id='search',tool='world.search_history',args=dict(query='{}',after=0,through=0),after=[])])
  runtime.tick(self.s,now=10);runtime.tick(self.s,now=16)
  before=self.s.db.execute('SELECT count(*) FROM actor_tool_receipts').fetchone()[0]
  self.s.close();self.f.f.server=self.f.f.open();self.s=self.f.f.server
  self.assertIsNone(runtime.tick(self.s,now=22));self.assertEqual(self.status('project'),'pending')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM actor_tool_receipts').fetchone()[0],before)
  with self.s.db:self.s.memory.append('project_result',dict(done=True))
  self.assertEqual(runtime.tick(self.s,now=28)['step'],'project')
 def test_failed_social_step_does_not_orphan_admitted_wait(self):
  self.install([self.wait('project','project_result'),dict(id='invalid',tool='world.reply_player',args=dict(speech=999999,text='Hello'),after=[])])
  runtime.tick(self.s,now=10);self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked')
  with self.s.db:self.s.memory.append('project_result',dict(done=True))
  self.assertEqual(runtime.tick(self.s,now=22)['status'],'succeeded')
  self.assertIsNone(runtime.tick(self.s,now=28))
 def test_default_exclusive_action_and_dependency_do_not_run_early(self):
  self.install([self.wait('project','project_result'),dict(id='move',tool='world.navigate',args=dict(revision='not-a-revision',x=3,y=3),after=[]),
   dict(id='dependent',tool='world.search_history',args=dict(query='{}',after=0,through=0),after=['project'])])
  runtime.tick(self.s,now=10);self.assertIsNone(runtime.tick(self.s,now=16))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM actor_tool_receipts').fetchone()[0],1)
  caps=runtime.inspect_runtime(self.s)['capabilities']
  self.assertTrue(caps['world.reply_player']['during_activity']);self.assertFalse(caps['world.navigate']['during_activity'])

class ActorFairnessTests(unittest.TestCase):
 def test_two_actors_alternate_and_cursor_survives_restart(self):
  f=canonical.ActorRuntimeTests();f.setUp();self.addCleanup(f.doCleanups);s=f.s
  def plan(name):return dict(id=name,purpose='Inspect public history independently.',steps=[dict(id='read'+str(i),tool='world.search_history',args=dict(query='{}',after=0,through=0),after=[]) for i in range(3)])
  f.apply(plan('a'));f.apply(plan('b'),1,'canon_wally')
  self.assertEqual(runtime.tick(s,now=10)['actor'],'canon_rydel')
  s.close();case=f.f.f.f.case;case.server=case.open();s=case.server
  self.assertEqual(runtime.tick(s,now=16)['actor'],'canon_wally')
  self.assertEqual(runtime.tick(s,now=22)['actor'],'canon_rydel')
