import json,unittest,time
from copy import deepcopy
import test_actor_navigation as fixture
from world import actor_runtime as runtime,npc_accompaniment as walk,npc_conversations as speech,character_reactions

class AccompanimentTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.NavigationTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s;self.peer=self.f.peer;self.now=0
 def invite(self,actor='harbor_guide'):
  speech.command(self.s,self.peer,['walk-with',actor]);return walk.inbox(self.s)[-1]['request']
 def plan(self,key,actor='harbor_guide'):
  state=deepcopy(self.s.module_state);c=state['world_characters'][actor];c['version']+=1
  c['plan']=dict(id='walk_'+str(c['version']),purpose='Choose to accompany an actual visitor.',steps=[dict(id='go',tool='world.accompany_player',args=dict(request=key),after=[])])
  self.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
 def tick(self):self.now+=6;return runtime.tick(self.s,now=self.now)
 def test_actual_steps_follow_same_session_without_warp_and_stop(self):
  key=self.invite();self.assertIsNone(self.s.deployment)
  self.assertTrue(character_reactions.dynamic_result(self.s.memory.history()['events'][-1],'harbor_guide',{}))
  self.plan(key);self.assertEqual(self.tick()['status'],'pending')
  self.f.f.state(self.peer,*self.s.wilds_map,78,70)
  self.assertIsNone(self.tick());self.assertIsNotNone(self.s.deployment)
  self.f.advance(0,True)
  path=self.s.module_state['world_character_controls']['harbor_guide']['journey']['path']
  self.assertEqual(len(path),2);self.assertEqual(path[0],[71,70]);self.assertNotIn([74,70],path)
  self.f.advance(1);self.f.advance(2)
  obj=next(o for o in self.s.objects if o['id']=='harbor_guide');self.assertEqual([obj['x'],obj['y']],path[1])
  self.assertIn('CHARACTER_WALK',self.s._snapshot(self.peer))
  event=next(e for e in reversed(self.s.memory.history()['events']) if e.get('event')=='character_journey_arrived')
  self.assertFalse(character_reactions.dynamic_result(event,'harbor_guide',self.s.module_state['world_characters']['harbor_guide']))
  speech.command(self.s,self.peer,['walk-stop']);self.tick()
  if self.s.deployment:self.f.advance(3,True)
  result=self.tick();self.assertEqual(result['status'],'succeeded')
  saved=self.s.db.execute('SELECT data FROM npc_accompaniment WHERE request=?',(key,)).fetchone()
  self.assertEqual(json.loads(saved[0])['steps'],1)
  self.assertEqual(walk.inbox(self.s),[]);self.assertNotIn('journey',self.s.module_state['world_character_controls']['harbor_guide'])
  self.assertEqual(self.peer['state'][2:4],[78,70])
 def test_no_forced_acceptance_and_player_can_withdraw_offer(self):
  key=self.invite();speech.command(self.s,self.peer,['walk-stop']);self.plan(key)
  self.assertEqual(self.tick()['status'],'blocked');self.assertIsNone(self.s.deployment)
 def test_menu_pause_disconnect_and_new_session_do_not_resume(self):
  key=self.invite();self.plan(key);self.tick()
  self.f.f.state(self.peer,*self.s.wilds_map,78,70);self.peer['state'][6]=0
  self.assertIsNone(self.tick());self.assertIsNone(self.s.deployment)
  self.peer['state'][6]=1;self.peer['npc_speech_session']='new_session'
  result=self.tick();self.assertEqual(result['status'],'succeeded');self.assertIsNone(self.s.deployment)
 def test_restart_ends_session_not_silently_resume_on_same_trainer(self):
  key=self.invite();self.plan(key);self.tick()
  self.s.close();self.f.f.f.server=self.f.f.f.open();self.s=self.f.f.f.server;self.f.s=self.s;self.f.f.server=self.s
  self.assertEqual(self.tick()['status'],'succeeded');self.assertEqual(walk.inbox(self.s),[])
 def test_inflight_collision_can_be_cancelled_without_waiting_for_blocker(self):
  key=self.invite();self.plan(key);self.tick();self.f.f.state(self.peer,*self.s.wilds_map,78,70);self.tick();self.f.advance(0,True)
  path=self.s.module_state['world_character_controls']['harbor_guide']['journey']['path']
  self.f.f.state(self.peer,*self.s.wilds_map,*path[1]);self.f.advance(1)
  self.assertEqual(self.s.module_state['world_character_controls']['harbor_guide']['walk']['index'],0)
  speech.command(self.s,self.peer,['walk-stop']);self.tick();self.assertIsNotNone(self.s.deployment);self.f.advance(2,True)
  self.assertEqual(self.tick()['status'],'succeeded')
  obj=next(o for o in self.s.objects if o['id']=='harbor_guide');self.assertEqual([obj['x'],obj['y']],path[0])
 def test_second_actor_and_request_boundaries(self):
  self.f.f.state(self.peer,*self.s.wilds_map,75,70)
  key=self.invite('second');self.plan(key,'harbor_guide');self.assertEqual(self.tick()['status'],'blocked')
  self.plan(key,'second');self.assertEqual(self.tick()['status'],'pending')
  self.f.f.state(self.peer,*self.s.wilds_map,79,72);self.tick();self.f.advance(0,True)
  path=self.s.module_state['world_character_controls']['second']['journey']['path'];self.assertEqual(path[0],[74,70]);self.assertEqual(len(path),2)

 def test_actual_author_queue_invitation_and_missing_movement_capability(self):
  import tempfile
  from world.runtime_gm import IntentQueue
  from world.guilds import GuildError
  self.peer['character_walk_capable']=False
  with self.assertRaises(GuildError):self.invite()
  self.peer['character_walk_capable']=True
  with tempfile.TemporaryDirectory() as d:
   queue=IntentQueue(d)
   try:
    character_reactions.configure(queue,self.s.inspect(),'harbor_guide','Choose whether to accompany a visitor.')
    key=self.invite()
    def fetch(q):return dict(ok=True,world_id=self.s.memory.world_id,**self.s.memory.history(**{k:v for k,v in q.items() if k!='command'}))
    self.assertEqual(len(character_reactions.observe(queue,self.s.inspect(),fetch)),1)
    job=queue.claim();packet=json.loads(job['result']);self.assertEqual(packet['evidence'],key)
    context=self.s.inspect();context['runtime']=dict(kind='character',observed_event=packet)
    self.assertEqual(character_reactions.prepare(context,fetch)['id'],'harbor_guide')
    self.assertNotIn('trainer',json.dumps(walk.inbox(self.s)))
   finally:queue.close()
