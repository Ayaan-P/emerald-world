import json,hashlib,unittest
from copy import deepcopy
import test_actor_object_programs
from world import actor_runtime as runtime,actor_objects
from world.mechanics import Candidate

class NetworkTests(unittest.TestCase):
 def setUp(self):
  self.f=test_actor_object_programs.ProgramTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  prop=next(o for o in self.s.objects if o['id']=='fixture');self.other=dict(prop,id='panel',x=72,y=71,text='A linked panel.')
  source=self.s.candidate.source+'\n_network_base=update\ndef update(context,state):\n result=_network_base(context,state)\n result["objects"].append('+repr(self.other)+')\n return result\n'
  self.f.f.f.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());self.f.f.f.f.commit(dict(state=self.s.module_state,tiles=[],objects=self.s.objects+[self.other]));self.assertIsNone(self.s.module_error)
  def node(text,gfx,y,action,next):return dict(objects=dict(fixture=dict(x=prop['x'],y=prop['y'],gfx=gfx,text=text),panel=dict(x=72,y=y,gfx=gfx,text=text)),on=dict(fixture={action:next}),use=dict(fixture=action))
  self.definition=dict(id='mechanism',objects=['fixture','panel'],program=dict(initial='off',states=dict(off=node('Dormant.',0,71,'activate','on'),on=node('Activated.',1,72,'reset','off'))))
 def install(self):
  state=deepcopy(self.s.module_state);actor=state['world_characters']['harbor_guide'];actor['version']+=1
  actor['plan']=dict(id='mechanism',purpose='Create a reusable shared mechanism.',steps=[dict(id='build',tool='world.program_network',args=dict(definition=json.dumps(self.definition,separators=(',',':'))),after=[])])
  self.f.f.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
  self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending');self.f.f.f.advance(0,True)
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded')
 def test_player_use_atomically_changes_both_real_objects_and_restart(self):
  self.install();peer=self.f.f.connect('User',True);send=lambda line:self.f.f.f.f.send(peer,line)
  send('CAVE GET');send('CAVE ACK '+self.s.shared_cave.identity);self.f.f.f.f.state(peer,*self.s.wilds_map,72,69);peer['state'][4]=1
  send('INTERACT_REGION %s fixture %s'%(peer['seq']+1,self.s.shared_cave.identity));self.assertIsNotNone(self.s.deployment)
  self.f.f.f.advance(1,True);actor_objects.poll_player(self.s)
  members=[o for o in self.s.objects if o['id'] in ('fixture','panel')]
  self.assertEqual([o['text'] for o in members],['Activated.','Activated.']);self.assertEqual(next(o for o in members if o['id']=='panel')['y'],72)
  self.assertEqual(self.s.module_state['world_object_network_state']['mechanism'],dict(phase='on',turn=1))
  self.s.close();base=self.f.f.f.f.f;base.server=base.open();self.s=base.server
  self.assertEqual([o for o in self.s.objects if o['id'] in ('fixture','panel')],members)
 def test_unknown_targets_reject(self):
  self.definition['program']['states']['off']['on']['fixture']['activate']='missing'
  with self.assertRaises(AssertionError):self.install()
  self.assertFalse(self.s.module_state.get('world_object_networks'))

 def test_occupied_member_destination_rolls_back_whole_player_transition(self):
  self.install();old=deepcopy(self.s.objects)
  peers=[]
  for name,x,y in [('User',72,69),('Bystander',72,72)]:
   peer=self.f.f.connect(name,True);send=lambda line:self.f.f.f.f.send(peer,line)
   send('CAVE GET');send('CAVE ACK '+self.s.shared_cave.identity);self.f.f.f.f.state(peer,*self.s.wilds_map,x,y);peers.append(peer)
  peers[0]['state'][4]=1
  self.f.f.f.f.send(peers[0],'INTERACT_REGION %s fixture %s'%(peers[0]['seq']+1,self.s.shared_cave.identity))
  with self.assertRaises(AssertionError):self.f.f.f.advance(1,True)
  actor_objects.poll_player(self.s)
  self.assertEqual(self.s.objects,old)
  self.assertEqual(self.s.module_state['world_object_network_state']['mechanism'],dict(phase='off',turn=0))
