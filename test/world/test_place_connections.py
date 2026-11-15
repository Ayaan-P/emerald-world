import json
import unittest
from copy import deepcopy
import test_actor_population as fixture
from world import actor_runtime as runtime
from world.actor_linked_navigation import graph

class ConnectionTests(unittest.TestCase):
 def setUp(self):
  self.p=fixture.PopulationTests();self.p.setUp();self.addCleanup(self.p.doCleanups);self.s=self.p.s
  self.p.f.plan();self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded');self.a=self.p.f.result()
  self.p.f.plan(style='organic',identity='second_place');self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded');self.b=self.p.f.result()
 def plan(self,actor='harbor_guide',identity='connect'):
  state=deepcopy(self.s.module_state);c=state['world_characters'][actor];c['version']+=1
  c['plan']=dict(id=identity,purpose='Connect real places.',steps=[dict(id='join',tool='world.connect_places',args=dict(source=self.a['place_id'],source_revision=self.a['revision'],target=self.b['place_id'],target_revision=self.b['revision']),after=[])])
  self.p.f.f.f.f.f.f.commit(dict(state=state,objects=self.s.objects,tiles=[]));self.assertIsNone(self.s.module_error)
 def install(self):
  self.plan();self.assertEqual(runtime.tick(self.s,now=22)['status'],'pending');self.assertEqual(graph(self.s),[])
  self.p.admit();self.assertEqual(runtime.tick(self.s,now=28)['status'],'succeeded')
 def test_paired_physical_links_actual_transfer_and_restart(self):
  self.install();edges=graph(self.s);self.assertEqual(len(edges),2)
  # Re-evaluate the installed source with retained state: props must not disappear.
  ns={};exec(self.s.candidate.source,ns)
  value=ns['update'](self.s._context(),deepcopy(self.s.module_state))
  self.p.f.f.f.f.f.f.commit(value)
  self.assertEqual(graph(self.s),edges)
  self.assertEqual(len([o for o in self.s.objects if o['id'].startswith('passage_')]),2)
  client=self.p.f.connect('Traveller');peer=client.sock.conn
  peer.update(world_props_capable=True,character_region_capable=True,cave_link_capable=True,cave_link_wildlife=True)
  client.select_region(self.a['place_id'])
  edge=next(e for e in edges if e['source']==self.a['revision']);obj=next(o for o in self.s.objects if o['id']==edge['object'])
  cave=self.s._connection_cave(peer)
  x,y=next((obj['x']+dx,obj['y']+dy) for dx,dy in ((0,1),(0,-1),(1,0),(-1,0)) if cave.walkable(obj['x']+dx,obj['y']+dy))
  client.send_state(peer['seq']+1,*self.s.cave_map,x,y,1,7,1,'a'*16,'b'*16)
  self.assertIn('REGION_PROP '+self.a['revision']+' '+obj['id'],self.s._snapshot(peer))
  from world.cave_links import interact,line
  self.assertTrue(interact(self.s,peer,obj,50));self.assertEqual(peer['cave_ack'],self.a['revision'])
  line(self.s,peer,['LINK','ACCEPT','50']);line(self.s,peer,['LINK','ACK','50',self.b['revision']])
  client.send_state(peer['seq']+1,*self.s.cave_map,1,1,1,7,1,'a'*16,'b'*16)
  line(self.s,peer,['LINK','ARRIVED','50',self.b['revision']]);self.assertIsNone(peer['cave_link_pending'])
  self.s.close();base=self.p.f.f.f.f.f.f.f;base.server=base.open();self.s=base.server
  self.assertEqual(graph(self.s),edges);self.assertIsNone(runtime.tick(self.s,now=40))
 def test_unadmitted_source_has_no_links(self):
  self.plan();self.assertEqual(runtime.tick(self.s,now=22)['status'],'pending');self.s.deployment=None
  self.assertEqual(runtime.tick(self.s,now=28)['status'],'blocked');self.assertEqual(graph(self.s),[])
 def test_second_actor_cannot_duplicate_pair(self):
  self.install();self.plan('second','duplicate');self.assertEqual(runtime.tick(self.s,now=34)['status'],'blocked');self.assertEqual(len(graph(self.s)),2)
 def test_wrong_revision_has_no_side_effect(self):
  self.b['revision']='f'*64;before=deepcopy(self.s.objects);self.plan()
  self.assertEqual(runtime.tick(self.s,now=22)['status'],'blocked');self.assertEqual(self.s.objects,before);self.assertIsNone(self.s.deployment)
 def test_receipt_failure_rolls_back_both_links(self):
  from unittest.mock import patch
  self.plan();runtime.tick(self.s,now=22);self.p.admit();original=runtime._receipt
  def fail(server,actor,row,plan,step,status,result):
   if status=='succeeded':raise ValueError('injected receipt failure')
   return original(server,actor,row,plan,step,status,result)
  with patch.object(runtime,'_receipt',side_effect=fail):
   self.assertEqual(runtime.tick(self.s,now=28)['status'],'blocked')
  self.assertEqual(graph(self.s),[])
  before=deepcopy(self.s.objects);self.plan(identity='resume_install')
  self.assertEqual(runtime.tick(self.s,now=34)['status'],'pending')
  self.assertEqual(runtime.tick(self.s,now=40)['status'],'succeeded')
  self.assertEqual(self.s.objects,before);self.assertEqual(len(graph(self.s)),2)
 def test_no_free_slot_preserves_existing_objects(self):
  from unittest.mock import patch
  self.plan();before=deepcopy(self.s.objects);original=self.s._validated
  def reject(value):
   if len(value['objects'])>len(before):raise ValueError('no population capacity')
   return original(value)
  with patch.object(self.s,'_validated',side_effect=reject):
   self.assertEqual(runtime.tick(self.s,now=22)['status'],'blocked')
  self.assertEqual(self.s.objects,before);self.assertIsNone(self.s.deployment)
 def test_changed_admitted_prop_does_not_install_links(self):
  self.plan();runtime.tick(self.s,now=22);self.p.admit()
  next(o for o in self.s.objects if o['id'].startswith('passage_'))['text']='Changed independently'
  self.assertEqual(runtime.tick(self.s,now=28)['status'],'blocked');self.assertEqual(graph(self.s),[])
