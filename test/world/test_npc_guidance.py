from copy import deepcopy
import json,time,unittest
import test_actor_navigation as fixture
from world import actor_runtime as runtime,npc_guidance as guide,npc_conversations as speech,character_reactions

class GuidanceTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.NavigationTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s;self.peer=self.f.peer;self.now=0;self.frame=0
 def plan(self,actor='harbor_guide',destination=(73,70)):
  state=deepcopy(self.s.module_state);c=state['world_characters'][actor];c['version']+=1
  c['plan']=dict(id='guide_'+str(c['version']),purpose='Lead willing visitors to an independently chosen location.',steps=[dict(id='go',tool='world.guide_players',args=dict(revision=self.f.revision,x=destination[0],y=destination[1],text='Follow me to the clearing if you would like.'),after=[])])
  self.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
 def tick(self):self.now+=6;return runtime.tick(self.s,now=self.now)
 def step(self):
  self.frame+=1;self.f.advance(self.frame,True)
  self.frame+=1;self.f.advance(self.frame)
  self.frame+=1;self.f.advance(self.frame)
 def join(self,conn=None,actor='harbor_guide'):return speech.command(self.s,conn or self.peer,['join-guide',actor])
 def test_actual_group_leading_waits_then_arrives_without_moving_player(self):
  self.plan();self.assertEqual(self.tick()['status'],'pending');self.assertIsNone(self.s.deployment)
  self.assertIn('guide offered',str(speech.command(self.s,self.peer,['nearby'])))
  self.assertIsNone(self.tick());self.assertIsNone(self.s.deployment)
  bob=self.f.f.connect_shared_xl('Bob',walking=True)
  self.join();self.join(bob);self.assertEqual(guide.discover(self.s)[0]['participants'],2)
  public=json.dumps(self.s.inspect()['actor_runtime']['guided_journeys']);self.assertNotIn('Alice',public);self.assertNotIn('Bob',public)
  self.tick();self.step()
  arrival=next(e for e in reversed(self.s.memory.history()['events']) if e.get('event')=='character_journey_arrived')
  self.assertFalse(character_reactions.dynamic_result(arrival,'harbor_guide',self.s.module_state['world_characters']['harbor_guide']))
  self.tick();self.step()
  obj=next(o for o in self.s.objects if o['id']=='harbor_guide');self.assertEqual((obj['x'],obj['y']),(73,70))
  self.assertIsNone(self.tick());self.assertEqual(self.peer['state'][2:4],[70,70]);self.assertEqual(bob['state'][2:4],[70,70])
  self.f.f.state(self.peer,*self.s.wilds_map,72,70);self.f.f.state(bob,*self.s.wilds_map,73,71)
  result=self.tick();self.assertEqual(result['status'],'succeeded')
  end=self.s.memory.history()['events'][-1];self.assertTrue(character_reactions.dynamic_result(end,'harbor_guide',self.s.module_state['world_characters']['harbor_guide']));self.assertNotIn('Alice',json.dumps(end));self.assertNotIn('Bob',json.dumps(end))
  saved=json.loads(self.s.db.execute('SELECT data FROM npc_guidance').fetchone()[0]);self.assertEqual(saved['result']['outcome'],'guided_destination_reached');self.assertEqual(saved['steps'],2);self.assertEqual(saved['members'],[])
 def test_pause_for_menu_and_distance_and_no_automatic_player_control(self):
  self.plan(destination=(78,70));self.tick();self.join();self.peer['state'][6]=0
  self.assertIsNone(self.tick());self.assertIsNone(self.s.deployment)
  self.peer['state'][6]=1;self.f.f.state(self.peer,*self.s.wilds_map,65,70)
  self.tick();self.assertIsNone(self.s.deployment)
  self.f.f.state(self.peer,*self.s.wilds_map,70,70);self.tick();self.assertIsNotNone(self.s.deployment)
  self.assertEqual(self.peer['state'][2:4],[70,70])
 def test_cancellation_of_blocked_actual_step(self):
  self.plan();self.tick();self.join();self.tick();self.frame+=1;self.f.advance(self.frame,True)
  path=self.s.module_state['world_character_controls']['harbor_guide']['journey']['path']
  self.f.f.state(self.peer,*self.s.wilds_map,*path[1]);self.frame+=1;self.f.advance(self.frame)
  speech.command(self.s,self.peer,['leave-guide']);self.tick();self.assertIsNotNone(self.s.deployment)
  self.frame+=1;self.f.advance(self.frame,True);self.assertEqual(self.tick()['status'],'succeeded')
  self.assertNotIn('journey',self.s.module_state['world_character_controls']['harbor_guide'])
  obj=next(o for o in self.s.objects if o['id']=='harbor_guide');self.assertEqual([obj['x'],obj['y']],path[0])
 def test_restart_does_not_rejoin_same_named_player(self):
  self.plan();self.tick();self.join()
  self.s.close();self.f.f.f.server=self.f.f.f.open();self.s=self.f.f.f.server;self.f.s=self.s;self.f.f.server=self.s
  self.assertEqual(self.tick()['status'],'succeeded');self.assertEqual(guide.discover(self.s),[])
 def test_second_actor_and_blocked_destination(self):
  self.plan('second',(77,72));self.tick();self.f.f.state(self.peer,*self.s.wilds_map,75,70);self.join(actor='second');self.tick();self.step()
  obj=next(o for o in self.s.objects if o['id']=='second');self.assertNotEqual((obj['x'],obj['y']),(74,70))
  self.assertIn('CHARACTER_WALK',self.s._snapshot(self.peer))
 def test_unreachable_destination_never_offered(self):
  self.plan(destination=(0,0));self.assertEqual(self.tick()['status'],'blocked');self.assertEqual(guide.discover(self.s),[])

 def test_changed_plan_retires_old_invitation_without_stalling_actor(self):
  self.plan();self.tick();old=guide.discover(self.s)[0]['id']
  self.plan(destination=(77,72));self.assertEqual(self.tick()['status'],'blocked') # prior plan retired
  result=self.tick();self.assertEqual(result['status'],'pending',result)
  current=guide.discover(self.s);self.assertEqual(len(current),1);self.assertNotEqual(current[0]['id'],old)
  self.assertEqual(guide.load(self.s,old)[1],'ended')
