from copy import deepcopy
import hashlib,json,tempfile,unittest
import test_actor_navigation as fixture
from world import actor_runtime as runtime,character_reactions as reactions
from world.runtime_gm import IntentQueue
from world.character_actions import compile_actions
from world.mechanics import Candidate

class SocialTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.NavigationTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
 def plan(self,target='second',version=1):
  state=deepcopy(self.s.module_state);a=state['world_characters']['harbor_guide'];a['version']+=1
  a['plan']=dict(id='visit',purpose='Approach another actor and speak, without determining its response.',steps=[
   dict(id='near',tool='world.approach',args=dict(target=target,expected_version=version),after=[]),
   dict(id='speak',tool='world.address',args=dict(target=target,expected_version=version,text='What should we explore next?'),after=['near'])])
  self.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
 def arrive(self):
  self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending');self.f.advance(0,True)
  for tick in range(1,15):self.f.advance(tick)
  self.assertEqual(runtime.tick(self.s,now=30)['status'],'succeeded')
 def fetch(self,query):return dict(ok=True,world_id=self.s.memory.world_id,**self.s.memory.history(**{k:v for k,v in query.items() if k!='command'}))
 def test_approach_delivery_independent_recipient_response_and_restart(self):
  self.plan()
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    reactions.configure(q,self.s.inspect(),'second','Choose independently whether and how to respond.')
    self.arrive();self.assertEqual(reactions.observe(q,self.s.inspect(),self.fetch),[])
    self.assertEqual(runtime.tick(self.s,now=36)['status'],'succeeded')
    self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.fetch)),1)
    job=q.claim();context=self.s.inspect();context['runtime']=dict(kind='character',observed_event=json.loads(job['result']),previous_source=self.f.f.candidate.source)
    observed=reactions.prepare(context,self.fetch);event=json.loads(job['result'])['evidence']
    version=self.s.module_state['world_characters']['harbor_guide']['version']
    reply=dict(id='reply',purpose='Offer a different idea.',steps=[dict(id='answer',tool='world.address',args=dict(target='harbor_guide',expected_version=version,text='I prefer studying this area.'),after=[])])
    obj=next(o for o in self.s.objects if o['id']=='second')
    action=dict(id='second',expected_version=1,evidence=[event],reason='Respond to the actual nearby speaker.',changes=dict(plan=reply),object=obj)
    reactions.check_response(dict(character_actions=[action],tests='assert True'),observed)
    source=compile_actions([action],context);self.f.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());self.f.advance(16)
    self.assertEqual(runtime.tick(self.s,now=42)['status'],'succeeded')
    events=[e for e in [json.loads(r[0]) for r in self.s.db.execute("SELECT data FROM events WHERE kind='world_memory' ORDER BY seq")] if e.get('event')=='character_encounter']
    self.assertEqual([(e['character_id'],e['recipient']) for e in events],[('harbor_guide','second'),('second','harbor_guide')])
    self.assertTrue(all(e['outcome']=='public_message_delivered' for e in events))
    self.assertTrue(all('arrival_receipt' not in e for e in events))
    self.s.close();self.f.f.f.server=self.f.f.f.open();self.s=self.f.f.f.server
    self.assertIsNone(runtime.tick(self.s,now=48))
   finally:q.close()
 def test_changed_recipient_after_real_arrival_is_not_delivered(self):
  self.plan();self.arrive()
  state=deepcopy(self.s.module_state);state['world_characters']['second']['version']+=1
  self.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
  self.assertEqual(runtime.tick(self.s,now=36)['status'],'blocked')
  self.assertFalse(any(e.get('event')=='character_encounter' for e in [json.loads(r[0]) for r in self.s.db.execute("SELECT data FROM events WHERE kind='world_memory' ORDER BY seq")]))
 def test_other_revision_and_missing_target_do_not_create_remote_meetings(self):
  from world.actor_social import approach,address
  for target in ('missing','harbor_guide'):
   with self.assertRaises(ValueError):approach(self.s,'harbor_guide',{},dict(target=target,expected_version=1))
  with self.assertRaises(ValueError):address(self.s,'harbor_guide',{},dict(target='second',expected_version=1,text='Hello.'))
  self.s.objects[1]['region_revision']='f'*64
  with self.assertRaises(ValueError):approach(self.s,'harbor_guide',{},dict(target='second',expected_version=1))

 def test_approach_computes_new_route_around_unseen_wall(self):
  import test_actor_observation as observations
  f=observations.ObservationTests();f.setUp();self.addCleanup(f.doCleanups)
  f.test_unseen_wall_blocks_observation_not_just_navigation()
  self.f=f.f;self.s=f.s
  self.plan(version=2);self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending');self.f.advance(0,True)
  path=self.s.module_state['world_character_controls']['harbor_guide']['journey']['path']
  self.assertFalse(any(x==72 and 67<=y<=73 for x,y in path))
  for tick in range(1,40):self.f.advance(tick)
  self.assertEqual(runtime.tick(self.s,now=50)['status'],'succeeded')
  self.assertEqual(runtime.tick(self.s,now=56)['status'],'succeeded')
