"""Local owner UI controls real enrollment/queue, never keys or provider calls."""
import json,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,Mock
import test_canonical_cast as fixture
from world.cast_agent_ui import action
from world.runtime_gm import IntentQueue
from world.session import DesktopSession,SessionError

class AgentUITests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.f.apply(self.f.action())
  self.session=SimpleNamespace(server=self.s,state=self.s.root,engine='expansion-native',gm_thread=None,gm_error=None)
  self.session._gm_queue=lambda:IntentQueue(self.s.root)
  def status():
   q=self.session._gm_queue()
   try:return q.status()
   finally:q.close()
  self.session.gm_status=status;self.session.start_gm=Mock();self.session.stop_gm=Mock()
  self.world=self.s.root.name
 def call(self,command,**kw):return action(self.session,[dict(key=self.world)],'cast_agent_'+command,dict(world=self.world,**kw))
 def test_real_follow_unfollow_and_initialization_queue_are_scoped(self):
  info=self.call('follow',actor='canon_rydel',purpose='Consider actual shared cycling events.',confirmed=True)
  self.assertTrue(next(a for a in info['actors'] if a['id']=='canon_rydel')['followed'])
  info=self.call('unfollow',actor='canon_rydel');self.assertFalse(next(a for a in info['actors'] if a['id']=='canon_rydel')['followed'])
  self.call('initialize',actor='canon_steven',purpose='Consider actual public history.',confirmed=True)
  info=self.call('initialize',actor='canon_steven',purpose='Consider actual public history.',confirmed=True)
  self.assertEqual(info['queued'],0) # Durable enrollment; only runtime observation queues typed work.
  q=self.session._gm_queue()
  try:
   from world.character_reactions import observe,subscriptions,prepare
   self.assertEqual([s['id'] for s in subscriptions(q)],['canon_steven'])
   self.assertEqual(subscriptions(q)[0]['purpose'],'Consider actual public history.')
   self.assertEqual(len(observe(q,self.s.inspect(),self.f.fetch)),1)
   item=q.claim();self.assertEqual(item['kind'],'character');self.assertEqual(item['player'],'canon_steven')
   packet=json.loads(item['result']);self.assertTrue(packet['bootstrap']);self.assertEqual(packet['expected_version'],0)
   context=self.f.context();context['runtime'].update(kind='character',observed_event=packet)
   prepare(context,self.f.fetch);self.assertEqual(context.get('data',context)['players'],[])
   q.finish(item['id'],'failed',dict(ok=False))
  finally:q.close()
  self.call('initialize',actor='canon_steven',purpose='Changed purpose must not replay.',confirmed=True)
  q=self.session._gm_queue()
  try:
   self.assertEqual(observe(q,self.s.inspect(),self.f.fetch),[])
   self.assertEqual(len(q.status()['requests']),1)
  finally:q.close()
  events=[e for e in self.s.memory.history()['events'] if e['event']=='canonical_actor_commissioned']
  self.assertEqual([e['character_id'] for e in events],['canon_steven'])
  self.session.start_gm.assert_not_called()
  self.assertNotIn('canon_steven',self.s.module_state['canonical_cast'])
 def test_no_secret_fields_remote_control_or_automatic_start(self):
  with patch.dict('os.environ',{'ANTHROPIC_API_KEY':'synthetic-secret'},clear=True):info=self.call('read')
  self.assertNotIn('synthetic-secret',json.dumps(info));self.session.start_gm.assert_not_called()
  with self.assertRaises(SessionError):self.call('start',provider='anthropic-messages',model='model',confirmed=False)
  with self.assertRaises(SessionError):self.call('start',provider='anthropic-messages',model='model',confirmed=True,api_key='not-accepted')
  self.call('start',provider='anthropic-messages',model='explicit-model',confirmed=True)
  self.session.start_gm.assert_called_once_with(provider='anthropic-messages',model='explicit-model')
  self.call('stop');self.session.stop_gm.assert_called_once()
  self.session.server=None
  with self.assertRaises(SessionError):self.call('read')
 def test_single_cast_enrollment_preserves_original_records(self):
  info=self.call('enroll_cast',confirmed=True)
  self.assertEqual(sum(a['followed'] for a in info['actors']),4)
  self.assertEqual(info['queued'],0)
  self.assertEqual(set(self.s.module_state['canonical_cast']),{'canon_rydel'})
  self.call('enroll_cast',confirmed=True)
  self.session.start_gm.assert_not_called()
 def test_existing_session_lifecycle_passes_selected_backend_and_stops(self):
  seen=[]
  class FakeRuntime:
   def __init__(self,*args,**kw):seen.append((args,kw))
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def run(self,stop):stop.wait(2)
  with tempfile.TemporaryDirectory() as tmp:
   session=DesktopSession(Path(tmp),engine='expansion-native');session.state=Path(tmp)/'test';session.state.mkdir();session.server=SimpleNamespace()
   with patch('world.author_backends.preflight') as preflight,patch('world.runtime_gm.RuntimeGM',FakeRuntime):
    session.start_gm(provider='anthropic-messages',model='selected-model');self.assertTrue(session.gm_thread.is_alive());session.stop_gm()
   self.assertFalse(session.gm_thread.is_alive());self.assertEqual(seen[0][1]['provider'],'anthropic-messages')
   self.assertEqual(seen[0][1]['model'],'selected-model');preflight.assert_called_once()

 def test_new_population_lifecycle_requires_explicit_host_setting(self):
  self.assertFalse(self.call('read')['population_agents']['enabled'])
  with self.assertRaises(SessionError):self.call('population',enabled=True,confirmed=False)
  self.assertTrue(self.call('population',enabled=True,confirmed=True)['population_agents']['enabled'])
  self.session.start_gm.assert_not_called()
  self.assertFalse(self.call('population',enabled=False,confirmed=True)['population_agents']['enabled'])
