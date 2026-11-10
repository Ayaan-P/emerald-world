from copy import deepcopy
import json,unittest
from unittest.mock import patch
import test_actor_population as fixture
from world import actor_runtime as runtime
from world.actor_linked_navigation import graph
from world.region_networks import catalog

def network():
 return dict(places=[dict(label='Hollow '+str(i),blueprint=dict(rooms=[[3+i,3,6,6],[19,19-i,7,7]],links=[[0,1]],entrance_room=0,exit_room=1)) for i in range(3)],links=[[0,1],[1,2]])
class NetworkTests(unittest.TestCase):
 def setUp(self):
  self.p=fixture.PopulationTests();self.p.setUp();self.addCleanup(self.p.doCleanups);self.s=self.p.s
 def plan(self,doc=None,name='network',actor='harbor_guide'):
  state=deepcopy(self.s.module_state);c=state['world_characters'][actor];c['version']+=1
  c['plan']=dict(id=name,purpose='Create a connected place graph.',steps=[dict(id='build',tool='world.create_region_network',args=dict(network=json.dumps(doc or network(),separators=(',',':'))),after=[])])
  self.p.f.f.f.f.f.f.commit(dict(state=state,objects=self.s.objects,tiles=[]));self.assertIsNone(self.s.module_error)
 def test_real_three_places_links_transfer_and_restart(self):
  self.plan();self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending')
  pending=catalog(self.s)[0];self.assertFalse(pending['admitted']);self.assertEqual(graph(self.s),[])
  self.p.admit();self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded')
  places=pending['places'];self.assertEqual(len(graph(self.s)),4)
  client=self.p.f.connect('Traveller');peer=client.sock.conn;peer.update(world_props_capable=True,character_region_capable=True,cave_link_capable=True)
  client.select_region(places[0]['place_id'])
  from world.cave_links import interact,line
  for i in (0,1):
   edge=next(e for e in graph(self.s) if e['source']==places[i]['revision'] and e['destination']==places[i+1]['revision']);obj=next(o for o in self.s.objects if o['id']==edge['object']);cave=self.s._connection_cave(peer)
   x,y=next((obj['x']+dx,obj['y']+dy) for dx,dy in ((0,1),(0,-1),(1,0),(-1,0)) if cave.walkable(obj['x']+dx,obj['y']+dy))
   client.send_state(peer['seq']+1,*self.s.cave_map,x,y,1,7,1,'a'*16,'b'*16)
   self.assertIn('REGION_PROP '+places[i]['revision']+' '+obj['id'],self.s._snapshot(peer));seq=50+i
   self.assertTrue(interact(self.s,peer,obj,seq));line(self.s,peer,['LINK','ACCEPT',str(seq)]);line(self.s,peer,['LINK','ACK',str(seq),places[i+1]['revision']])
   client.send_state(peer['seq']+1,*self.s.cave_map,1,1,1,7,1,'a'*16,'b'*16);line(self.s,peer,['LINK','ARRIVED',str(seq),places[i+1]['revision']]);self.assertIsNone(peer['cave_link_pending'])
  self.s.close();base=self.p.f.f.f.f.f.f.f;base.server=base.open();self.s=base.server
  self.assertEqual(len(graph(self.s)),4);self.assertTrue(catalog(self.s)[0]['admitted']);self.assertIsNone(runtime.tick(self.s,now=30))
 def test_rejected_admission_resume_does_not_duplicate_places(self):
  self.plan();runtime.tick(self.s,now=10);self.s.deployment=None
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked');before=catalog(self.s)
  self.plan(name='resume');self.assertEqual(runtime.tick(self.s,now=22)['status'],'pending');self.p.admit()
  self.assertEqual(runtime.tick(self.s,now=28)['status'],'succeeded');self.assertEqual(catalog(self.s)[0]['places'],before[0]['places']);self.assertEqual(len(catalog(self.s)),1)
 def test_invalid_graph_or_placement_rolls_back_archive(self):
  before=self.s.db.execute('SELECT count(*) FROM generated_area_archive').fetchone()[0]
  doc=network();doc['links']=[[0,1],[1,0]];self.plan(doc);self.assertEqual(runtime.tick(self.s,now=10)['status'],'blocked')
  self.plan(name='occupied')
  with patch.object(self.s,'_validated',side_effect=ValueError('no free object capacity')):
   self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM generated_area_archive').fetchone()[0],before);self.assertEqual(catalog(self.s),[])

 def test_second_actor_four_places_branching_and_receipt_failure_recovery(self):
  doc=network();doc['places'].append(dict(label='Fourth',blueprint=dict(rooms=[[7,4,6,6],[18,17,7,7]],links=[[0,1]],entrance_room=0,exit_room=1)));doc['links']=[[0,1],[0,2],[2,3]]
  self.plan(doc,actor='second');runtime.tick(self.s,now=10);self.p.admit()
  original=runtime._receipt
  def fail(server,actor,row,plan,step,status,result):
   if status=='succeeded':raise ValueError('receipt unavailable')
   return original(server,actor,row,plan,step,status,result)
  with patch.object(runtime,'_receipt',side_effect=fail):self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked')
  self.assertEqual(graph(self.s),[]);before=deepcopy(self.s.objects)
  self.plan(doc,name='resume',actor='second');self.assertEqual(runtime.tick(self.s,now=22)['status'],'pending')
  self.assertEqual(runtime.tick(self.s,now=28)['status'],'succeeded');self.assertEqual(len(graph(self.s)),6);self.assertEqual(self.s.objects,before)
