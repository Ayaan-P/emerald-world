"""Real generated geometry/admission and in-memory native wire; no rendered QA."""
from copy import deepcopy
import json,unittest
import test_region_networks as fixture
from world.procedural_regions import generate
from world.cave_blueprint import proposal_from_blueprint
from world.shared_cave import SharedCave
from world.actor_linked_navigation import graph
from world.region_networks import catalog
from world import actor_runtime as runtime


def spec(seed=19,**kwargs):
 return json.dumps(dict(dict(places=3,rooms=3,loops=1,branching=2,style='organic',seed=seed,corridor_width=2),**kwargs),separators=(',',':'))

class GeometryTests(unittest.TestCase):
 def test_varied_seeds_styles_connected_unique_and_repeatable(self):
  hashes=set()
  for style in ('rooms','rounded','organic','maze'):
   for seed in range(8):
    raw=spec(seed,style=style);doc=generate('Field',raw)
    self.assertEqual(doc,generate('Field',raw));self.assertEqual(len(doc['links']),3)
    self.assertTrue(all(sum(i in e for e in doc['links'])<=2 for i in range(3)))
    for place in doc['places']:
     p=proposal_from_blueprint(place['blueprint']);c=SharedCave(b'EWGMAP01'+''.join(p['rows']).encode())
     self.assertTrue(c.walkable(1,1));self.assertTrue(c.walkable(29,29));hashes.add(c.identity)
  self.assertGreater(len(hashes),80)
 def test_invalid_constraints_do_not_silently_change_requested_topology(self):
  for raw in (spec(places=3,branching=1),spec(places=2,loops=1),spec(rooms=True),spec(seed=-1),spec(style='forest'),'{"code":"execute"}'):
   with self.assertRaises(ValueError):generate('Field',raw)
  with self.assertRaises(ValueError):generate('bad\nlabel',spec())

class GeneratedRegionTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.NetworkTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
 def plan(self,raw=None,actor='harbor_guide',identity='generate'):
  state=deepcopy(self.s.module_state);c=state['world_characters'][actor];c['version']+=1
  c['plan']=dict(id=identity,purpose='Generate a connected explorable region.',steps=[dict(id='build',tool='world.generate_region_network',args=dict(label='Field',constraints=raw or spec()),after=[])])
  self.f.p.f.f.f.f.f.f.commit(dict(state=state,objects=self.s.objects,tiles=[]));self.assertIsNone(self.s.module_error)
 def test_actual_creation_passage_roundtrip_and_restart(self):
  old=self.s.shared_cave.identity;self.plan();self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending')
  self.assertFalse(catalog(self.s)[0]['admitted']);self.assertEqual(graph(self.s),[])
  self.f.p.admit();self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded')
  places=catalog(self.s)[0]['places'];self.assertEqual(len(places),3);self.assertEqual(len(graph(self.s)),6)
  client=self.f.p.f.connect('GeneratedVisitor');peer=client.sock.conn
  peer.update(world_props_capable=True,character_region_capable=True,cave_link_capable=True)
  client.select_region(places[0]['place_id']);start=places[0]['revision']
  edge=next(e for e in graph(self.s) if e['source']==start)
  from world.cave_links import interact,line
  for seq,target in ((71,edge),(72,next(e for e in graph(self.s) if e['source']==edge['destination'] and e['destination']==start))):
   obj=next(o for o in self.s.objects if o['id']==target['object']);cave=self.s._connection_cave(peer)
   x,y=next((obj['x']+dx,obj['y']+dy) for dx,dy in ((0,1),(0,-1),(1,0),(-1,0)) if cave.walkable(obj['x']+dx,obj['y']+dy))
   client.send_state(peer['seq']+1,*self.s.cave_map,x,y,1,7,1,'a'*16,'b'*16)
   self.assertIn('REGION_PROP '+target['source']+' '+obj['id'],self.s._snapshot(peer))
   self.assertTrue(interact(self.s,peer,obj,seq));line(self.s,peer,['LINK','ACCEPT',str(seq)])
   line(self.s,peer,['LINK','ACK',str(seq),target['destination']])
   client.send_state(peer['seq']+1,*self.s.cave_map,1,1,1,7,1,'a'*16,'b'*16)
   line(self.s,peer,['LINK','ARRIVED',str(seq),target['destination']]);self.assertIsNone(peer['cave_link_pending'])
  self.assertEqual(self.s._region_scope(peer),start);self.assertEqual(self.s.shared_cave.identity,old)
  self.s.close();base=self.f.p.f.f.f.f.f.f.f;base.server=base.open();self.s=base.server
  self.assertEqual(catalog(self.s)[0]['places'],places);self.assertEqual(len(graph(self.s)),6)
 def test_looped_room_graph_is_admitted_as_playable_caves(self):
  raw=spec(77,places=2,rooms=3,loops=0,branching=1,room_loops=1)
  expected=generate('Field',raw);self.plan(raw);self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending')
  self.f.p.admit();self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded')
  places=catalog(self.s)[0]['places'];self.assertEqual(len(places),2)
  for actual,definition in zip(places,expected['places']):
   blueprint=definition['blueprint'];self.assertEqual(len(blueprint['links']),len(blueprint['rooms']))
   proposal=proposal_from_blueprint(blueprint);c=SharedCave(b'EWGMAP01'+''.join(proposal['rows']).encode())
   self.assertEqual(actual['revision'],c.identity);self.assertTrue(c.walkable(1,1));self.assertTrue(c.walkable(29,29))
 def test_second_actor_failed_admission_resumes_same_places(self):
  raw=spec(361,places=4,rooms=2,loops=0,branching=3,style='maze')
  self.plan(raw,actor='second');self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending');places=catalog(self.s)[0]['places']
  self.s.deployment=None;self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked')
  self.plan(raw,actor='second',identity='resume');self.assertEqual(runtime.tick(self.s,now=22)['status'],'pending')
  self.f.p.admit();self.assertEqual(runtime.tick(self.s,now=28)['status'],'succeeded')
  self.assertEqual(catalog(self.s)[0]['places'],places);self.assertEqual(len(catalog(self.s)),1)
 def test_impossible_graph_leaves_archive_unchanged(self):
  count=self.s.db.execute('SELECT count(*) FROM generated_area_archive').fetchone()[0]
  self.plan(spec(branching=1));self.assertEqual(runtime.tick(self.s,now=10)['status'],'blocked')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM generated_area_archive').fetchone()[0],count)
  self.assertIsNone(self.s.deployment)

