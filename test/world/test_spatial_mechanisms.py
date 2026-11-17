import unittest
from copy import deepcopy
from unittest.mock import patch
import test_object_networks
from world import object_networks

class SpatialTests(unittest.TestCase):
 def setUp(self):
  self.f=test_object_networks.NetworkTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s;self.clock=100
  self.patch=patch('world.spatial_mechanisms.time.monotonic',side_effect=lambda:self.clock);self.patch.start();self.addCleanup(self.patch.stop)
  zone=dict(x=70,y=72,radius=0,players=1,characters=0)
  zone2=dict(x=71,y=72,radius=0,players=1,characters=0)
  for phase,target,occupied in [('off','on',True),('on','off',False)]:
   node=self.f.definition['program']['states'][phase]
   node['on']={};node['use']={}
   node['when']=[dict(to=target,mode='all',occupied=occupied,hold=2,zones=[zone,zone2])]
 def install(self):self.f.install()
 def peer(self,name,x,y):
  peer=self.f.f.f.connect(name,True);send=lambda line:self.f.f.f.f.f.send(peer,line)
  send('CAVE GET');send('CAVE ACK '+self.s.shared_cave.identity)
  self.f.f.f.f.f.state(peer,*self.s.wilds_map,x,y);return peer
 def tick(self,seconds=1):
  self.clock+=seconds
  for p in self.s.peers.values():
   if not p.get('closing'):p['state_time']=self.clock
  self.f.f.f.f.advance(seconds)
 def phase(self):return self.s.module_state['world_object_network_state']['mechanism']['phase']
 def test_two_players_drive_real_shared_objects_without_interaction(self):
  self.install();a=self.peer('One',70,72);b=self.peer('Two',71,72)
  self.tick();self.assertEqual(self.phase(),'off');self.tick(2)
  self.assertEqual(self.phase(),'on');self.assertEqual(next(o for o in self.s.objects if o['id']=='panel')['y'],72)
  self.assertIn('Activated.'.encode().hex(),self.s._snapshot(a));self.assertIn('Activated.'.encode().hex(),self.s._snapshot(b))
  b['closing']=True;self.tick();self.tick(2)
  self.assertEqual(self.phase(),'off');self.assertEqual(next(o for o in self.s.objects if o['id']=='panel')['y'],71)
 def test_exact_revision_freshness_and_menu_do_not_count(self):
  self.install();a=self.peer('One',70,72);b=self.peer('Two',71,72)
  for mutate in [lambda:b.update(cave_ack='0'*64),lambda:b['state'].__setitem__(6,0),lambda:b.update(state_time=0)]:
   b['cave_ack']=self.s.shared_cave.identity;b['state'][6]=1;b['state_time']=self.clock
   mutate();result=dict(state=deepcopy(self.s.module_state),objects=deepcopy(self.s.objects),tiles=[])
   self.assertEqual(object_networks.project(result,self.s)['state']['world_object_network_state']['mechanism']['phase'],'off');self.clock+=3
  self.assertEqual(self.phase(),'off')
 def test_occupied_destination_rolls_back_and_can_retry(self):
  self.install();self.peer('One',70,72);self.peer('Two',71,72);block=self.peer('Blocker',72,72)
  self.tick()
  block['state'][6]=0;self.tick(2)
  self.assertEqual(self.phase(),'off')
  block['closing']=True;self.tick(3);self.assertEqual(self.phase(),'on')
 def test_character_counts_and_restart_keep_state_not_elapsed_hold(self):
  for phase in ('off','on'):
   rule=self.f.definition['program']['states'][phase]['when'][0]
   actor=next(o for o in self.s.objects if o['id']=='harbor_guide')
   rule['zones']=[dict(x=actor['x'],y=actor['y'],radius=0,players=0,characters=1)]
  self.install();self.tick();self.tick(2);self.assertEqual(self.phase(),'on')
  self.s.close();base=self.f.f.f.f.f.f;base.server=base.open();self.s=base.server
  self.assertEqual(self.phase(),'on');self.assertFalse(hasattr(self.s,'_spatial_mechanism_holds'))
 def test_unobserved_time_does_not_complete_a_hold(self):
  self.install();self.peer('One',70,72);self.peer('Two',71,72)
  self.tick();self.tick(20);self.assertEqual(self.phase(),'off')
  self.tick(2);self.assertEqual(self.phase(),'on')
 def test_invalid_unseen_zone_rejected(self):
  self.f.definition['program']['states']['off']['when'][0]['zones'][0]['x']=12
  with self.assertRaises(AssertionError):self.install()
  self.assertFalse(self.s.module_state.get('world_object_networks'))

 def test_manual_change_discards_prior_spatial_hold(self):
  self.install();self.s._spatial_mechanism_holds={('mechanism','off',0):(1,100)}
  result=dict(state=deepcopy(self.s.module_state),objects=deepcopy(self.s.objects),tiles=[])
  result['state']['world_object_controls']['fixture']['state']=dict(phase='on',turn=1)
  result=object_networks.project(result,self.s)
  self.assertEqual(result['state']['world_object_network_state']['mechanism']['phase'],'on')
  self.assertEqual(self.s._spatial_mechanism_holds,{})
