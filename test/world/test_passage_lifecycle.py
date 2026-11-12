import json,unittest
from copy import deepcopy
import test_place_connections
from world import passage_lifecycle as life,cave_links,actor_runtime,actor_linked_navigation
class Lifecycle(unittest.TestCase):
 def setUp(self):
  self.f=test_place_connections.ConnectionTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.f.install();self.s=self.f.s
  self.key=next(iter(self.s.module_state['world_place_connections']));self.value=self.s.module_state['world_place_connections'][self.key]
 def change(self,operation,revision=0,actor='harbor_guide'):
  with self.s.db:return life.configure(self.s,actor,{},dict(connection=self.key,revision=revision,operation=operation))
 def client(self):
  c=self.f.p.f.connect('Traveller');p=c.sock.conn;p.update(world_props_capable=True,character_region_capable=True,cave_link_capable=True,cave_link_wildlife=True)
  c.select_region(self.f.a['place_id']);edge=next(l for l in self.value['links'] if l['source']==self.f.a['revision']);obj=next(o for o in self.s.objects if o['id']==edge['object']);cave=self.s._connection_cave(p)
  x,y=next((obj['x']+dx,obj['y']+dy) for dx,dy in ((0,1),(0,-1),(1,0),(-1,0)) if cave.walkable(obj['x']+dx,obj['y']+dy))
  c.send_state(p['seq']+1,*self.s.cave_map,x,y,1,7,1,'a'*16,'b'*16);return c,p,obj
 def test_native_passage_denied_both_directions_then_real_transfer(self):
  c,p,obj=self.client();prior=life.program_revision(self.s,obj)
  result=self.change('close');self.assertEqual(actor_linked_navigation.graph(self.s),[])
  self.assertIn('Passage closed'.encode().hex(),self.s._snapshot(p));self.assertTrue(cave_links.interact(self.s,p,obj,50));self.assertFalse(p.get('cave_link_pending'))
  with self.assertRaises(ValueError):self.change('open',0)
  result=self.change('open',result['revision']);self.assertEqual(len(actor_linked_navigation.graph(self.s)),2);self.assertNotEqual(prior,life.program_revision(self.s,obj))
  self.assertTrue(cave_links.interact(self.s,p,obj,51));cave_links.line(self.s,p,['LINK','ACCEPT','51']);cave_links.line(self.s,p,['LINK','ACK','51',self.f.b['revision']])
  c.send_state(p['seq']+1,*self.s.cave_map,1,1,1,7,1,'a'*16,'b'*16);cave_links.line(self.s,p,['LINK','ARRIVED','51',self.f.b['revision']]);self.assertIsNone(p['cave_link_pending'])
 def test_inflight_transfer_ownership_and_original_routes_preserved(self):
  c,p,obj=self.client();before=deepcopy(self.s.objects)
  with self.assertRaises(ValueError):self.change('close',actor='second')
  cave_links.interact(self.s,p,obj,60)
  with self.assertRaises(ValueError):self.change('close')
  cave_links.line(self.s,p,['LINK','ACCEPT','60'])
  with self.assertRaises(ValueError):self.change('close')
  cave_links.line(self.s,p,['LINK','ACK','60',self.f.b['revision']])
  with self.assertRaises(ValueError):self.change('close')
  cave_links.abort(self.s,p,60);r=self.change('close');self.assertEqual(self.s.objects,before)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM cave_links').fetchone()[0],2)
  self.assertEqual(p['region_place'],self.f.a['place_id'])
  self.s.close();base=self.f.p.f.f.f.f.f.f.f;base.server=base.open();self.s=base.server
  self.assertEqual(life.catalog(self.s)[0]['revision'],r['revision']);self.assertEqual(actor_linked_navigation.graph(self.s),[])
 def test_pending_npc_route_blocks_but_cancelled_plan_does_not(self):
  # Fixture of a durable, currently executing linked journey; no travel claimed.
  self.s.db.execute('CREATE TABLE IF NOT EXISTS actor_linked_journeys(id TEXT PRIMARY KEY,actor TEXT,data TEXT)')
  plan=self.s.module_state['world_characters']['harbor_guide']['plan']['id']
  self.s.db.execute('INSERT INTO actor_linked_journeys VALUES(?,?,?)',('fixture','harbor_guide',json.dumps(dict(edges=actor_linked_navigation.graph(self.s),index=0,active=None))))
  self.s.db.execute('INSERT INTO actor_tool_receipts VALUES(?,?,?,?,?,NULL)',('harbor_guide',plan,'journey_fixture','pending',json.dumps(dict(journey='fixture'))))
  with self.assertRaises(ValueError):self.change('close')
  self.s.db.execute("UPDATE actor_tool_receipts SET status='cancelled' WHERE step='journey_fixture'")
  self.assertEqual(self.change('close')['outcome'],'paired_passage_closed')
 def test_transaction_rollback_and_endpoint_change_fail_closed(self):
  try:
   with self.s.db:
    life.configure(self.s,'harbor_guide',{},dict(connection=self.key,revision=0,operation='close'))
    raise ValueError('receipt failure')
  except ValueError:pass
  self.assertEqual(len(actor_linked_navigation.graph(self.s)),2)
  r=self.change('close');self.s.module_state['world_place_connections'][self.key]['objects'][0]['text']='Changed'
  with self.assertRaises(ValueError):self.change('open',r['revision'])
  self.assertFalse(life.status(self.s,self.value['links'][0]['object'])['enabled'])
 def test_real_actor_plan_and_receipt_failure_rollback(self):
  from unittest.mock import patch
  state=deepcopy(self.s.module_state);actor=state['world_characters']['harbor_guide'];actor['version']+=1
  actor['plan']=dict(id='close_passage',purpose='Close our unused route.',steps=[dict(id='close',tool='world.set_passage',args=dict(connection=self.key,revision=0,operation='close'),after=[])])
  self.f.p.f.f.f.f.f.f.commit(dict(state=state,objects=self.s.objects,tiles=[]))
  original=actor_runtime._receipt
  def fail(server,actor,row,plan,step,status,result):
   if status=='succeeded':raise ValueError('injected receipt failure')
   return original(server,actor,row,plan,step,status,result)
  with patch.object(actor_runtime,'_receipt',side_effect=fail):self.assertEqual(actor_runtime.tick(self.s,now=40)['status'],'blocked')
  self.assertEqual(len(actor_linked_navigation.graph(self.s)),2)
  state=deepcopy(self.s.module_state);actor=state['world_characters']['harbor_guide'];actor['version']+=1;actor['plan']['id']='close_again'
  self.f.p.f.f.f.f.f.f.commit(dict(state=state,objects=self.s.objects,tiles=[]))
  self.assertEqual(actor_runtime.tick(self.s,now=46)['status'],'succeeded');self.assertEqual(actor_linked_navigation.graph(self.s),[])
