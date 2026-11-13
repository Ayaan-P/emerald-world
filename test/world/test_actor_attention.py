import copy,json,unittest
from unittest.mock import patch
import test_actor_navigation as fixture
from world import actor_attention as attention,actor_runtime,character_reactions
from world.mechanics import Candidate
import hashlib

class AttentionTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.NavigationTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s;self.f.f.state(self.f.peer,0,9,8,8)
 def configure(self,actor='harbor_guide',radius=4):
  with patch.object(attention.time,'time',return_value=100),self.s.db:
   return attention.configure(self.s,actor,{},dict(mode='local',radius=radius,cooldown=30))
 def commit(self,objects,state=None):
  source='def update(context,state):\n return dict(state=state,tiles=[],objects='+repr(objects)+')\n'
  self.f.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
  self.f.f.commit(dict(state=copy.deepcopy(state or self.s.module_state),objects=objects,tiles=[]));self.assertIsNone(self.s.module_error)
 def event(self,seq):return json.loads(self.s.db.execute('SELECT data FROM events WHERE seq=?',(seq,)).fetchone()[0])
 def test_real_public_change_reaction_and_no_fake_meeting(self):
  self.configure();self.assertEqual(attention.tick(self.s,130),[])
  objects=copy.deepcopy(self.s.objects);objects.append(dict(objects[0],id='sign',kind='prop',gfx=0,x=72,text='Trail open'))
  self.commit(objects);seq=attention.tick(self.s,131)[0];event=self.event(seq)
  self.assertEqual([x['id'] for x in event['entered']],['sign']);self.assertTrue(character_reactions.dynamic_result(event,'harbor_guide',self.s.module_state['world_characters']['harbor_guide']))
  self.assertFalse(character_reactions.dynamic_result(event,'second',self.s.module_state['world_characters']['second']))
  self.assertNotIn('Alice',json.dumps(event));self.assertIn('not an exhaustive timeline',event['limits'])
  self.assertEqual(attention.tick(self.s,200),[])
  objects[-1]['text']='Trail changed';self.commit(objects)
  event=self.event(attention.tick(self.s,201)[0]);self.assertEqual(event['changed'][0]['after']['text'],'Trail changed')
 def test_cooldown_relocation_restart_and_no_repeated_event(self):
  self.configure();objects=copy.deepcopy(self.s.objects);objects.append(dict(objects[0],id='sign',kind='prop',gfx=0,x=72,text='Marker'));self.commit(objects)
  self.assertEqual(attention.tick(self.s,110),[]);self.assertEqual(len(attention.tick(self.s,131)),1)
  self.s.close();self.f.f.f.server=self.f.f.f.open();self.s=self.f.f.f.server
  self.assertEqual(attention.tick(self.s,170),[])
  # Repositioning the observer rebases its own neighborhood, not a meeting.
  next(o for o in self.s.objects if o['id']=='harbor_guide')['x']=69
  self.assertEqual(attention.tick(self.s,200),[])
  self.assertEqual(attention.tick(self.s,10),[]) # Clock rollback rebase.
  with self.s.db:attention.configure(self.s,'harbor_guide',{},dict(mode='off',radius=4,cooldown=30))
  self.assertEqual(attention.discover(self.s),[])
 def test_no_distant_or_cross_revision_entity_leak_and_no_thought_loop(self):
  self.configure(radius=2)
  objects=copy.deepcopy(self.s.objects);objects.append(dict(objects[0],id='far',kind='prop',gfx=0,x=90,text='Far'));self.commit(objects)
  self.assertEqual(attention.tick(self.s,150),[])
  self.configure(radius=4)
  state=copy.deepcopy(self.s.module_state);state['world_characters']['second']['version']+=1;state['world_characters']['second']['goals']=['Think about another goal.']
  self.commit(objects,state);self.assertEqual(attention.tick(self.s,150),[])
  self.s.objects.append(dict(objects[0],id='other_place',kind='prop',gfx=0,x=72,region_revision='0'*64))
  self.assertEqual(attention.tick(self.s,200),[])
 def test_two_independent_actors_and_real_runtime_registration(self):
  state=copy.deepcopy(self.s.module_state);actor=state['world_characters']['second'];actor['version']+=1
  actor['plan']=dict(id='notice',purpose='Notice my surroundings while choosing independent plans.',steps=[dict(id='listen',tool='world.attend_local',args=dict(mode='local',radius=4,cooldown=30),after=[])])
  self.commit(copy.deepcopy(self.s.objects),state)
  with patch.object(attention.time,'time',return_value=100):self.assertEqual(actor_runtime.tick(self.s,now=10)['status'],'succeeded')
  self.configure()
  objects=copy.deepcopy(self.s.objects);objects.append(dict(objects[0],id='sign',kind='prop',gfx=0,x=72,text='New sign'));self.commit(objects)
  events=[self.event(s) for s in attention.tick(self.s,131)];self.assertEqual({e['character_id'] for e in events},{'second','harbor_guide'})
  self.assertEqual(len(self.s.inspect()['actor_runtime']['local_attention']),2)
 def test_notice_enters_enrolled_author_queue_with_exact_source(self):
  import tempfile
  from world.runtime_gm import IntentQueue
  self.configure()
  with tempfile.TemporaryDirectory() as root:
   queue=IntentQueue(root)
   try:
    character_reactions.configure(queue,self.s.inspect(),'harbor_guide','Choose independently how to respond to real local changes.')
    objects=copy.deepcopy(self.s.objects);objects.append(dict(objects[0],id='sign',kind='prop',gfx=0,x=72,text='A public marker'));self.commit(objects)
    seq=attention.tick(self.s,131)[0]
    fetch=lambda query:dict(ok=True,world_id=self.s.memory.world_id,**self.s.memory.history(**{k:v for k,v in query.items() if k!='command'}))
    queued=character_reactions.observe(queue,self.s.inspect(),fetch);self.assertEqual(len(queued),1)
    packet=json.loads(queue.db.execute('SELECT result FROM requests WHERE id=?',(queued[0],)).fetchone()[0]);self.assertEqual(packet['evidence'],seq)
    context=self.s.inspect();context['runtime']={'kind':'character','observed_event':packet,'previous_source':self.s.candidate.source}
    self.assertEqual(character_reactions.prepare(context,fetch)['evidence'],seq)
    # The worker's existing context validator accepts only this actor's real notice.
    self.assertTrue(character_reactions.dynamic_result(self.event(packet['evidence']),'harbor_guide',self.s.module_state['world_characters']['harbor_guide']))
    self.assertEqual(character_reactions.observe(queue,self.s.inspect(),fetch),[])
    # A fixture author chooses a supported visible response to this actual
    # notice. This is not a live model test or an automatic prescribed reply.
    from world.character_actions import compile_actions
    obj=dict(next(o for o in self.s.objects if o['id']=='harbor_guide'),text='A new marker nearby.')
    action=dict(id='harbor_guide',expected_version=packet['expected_version'],evidence=[seq],reason='Respond to the actual public local change.',changes={},object=obj)
    source=compile_actions([action],context);ns={};exec(source,ns)
    self.f.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
    self.f.f.commit(ns['update'](self.s._context(),copy.deepcopy(self.s.module_state)))
    self.assertIsNone(self.s.module_error)
    self.assertEqual(next(o for o in self.s.objects if o['id']=='harbor_guide')['text'],'A new marker nearby.')

   finally:queue.close()
