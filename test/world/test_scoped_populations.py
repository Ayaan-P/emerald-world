from copy import deepcopy
from unittest.mock import patch
import hashlib,json,unittest
import test_region_characters as fixture
from world.mechanics import Candidate,validate_objects
from world import inspection_transfer
from world.client import admin_request

class AdminSocket:
 def __init__(self,server):self.s=server;self.conn=dict(out=bytearray(),closing=False,sock=self,id=None)
 def __enter__(self):return self
 def __exit__(self,*_):pass
 def settimeout(self,_):pass
 def connect(self,_):pass
 def makefile(self,_):return self
 def sendall(self,data):self.s._admin_line(self.conn,data.strip())
 def readline(self,limit):
  data=bytes(self.conn['out']);self.conn['out'].clear()
  if len(data)>limit:raise AssertionError('oversized queue frame')
  return data

class ScopedPopulations(unittest.TestCase):
 def setUp(self):
  self.f=fixture.RegionCharacterTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.server
 def populate(self,count=8):
  state=deepcopy(self.s.module_state);objects=[]
  for place,revision in enumerate((self.f.f.a,self.f.f.b)):
   for i in range(count):
    key='harbor_guide' if place==i==0 else f'person_{place}_{i}'
    record=deepcopy(self.f.character);record.update(name=f'Researcher {place} {i}',object_id=key);record.pop('offer',None)
    if key=='harbor_guide':record=deepcopy(self.f.character)
    state['world_characters'][key]=record
    objects.append(dict(self.f.obj,id=key,region_revision=revision,x=3+i,y=3))
  source='def update(context,state):\n return dict(state=state,tiles=[],objects='+repr(objects)+')\n'
  self.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
  self.f.commit(dict(state=state,tiles=[],objects=objects));self.assertIsNone(self.s.module_error)
  return objects
 def test_two_populated_regions_stream_independently_and_persist(self):
  objects=self.populate();self.assertEqual(len(self.s.module_state['world_characters']),16)
  peers=[self.f.connect('Alice',self.f.f.ra['place_id'],self.f.f.a),self.f.connect('Bob',self.f.f.rb['place_id'],self.f.f.b)]
  for n,peer in enumerate(peers):
   wire=self.s._snapshot(peer);rows=[line for line in wire.splitlines() if line.startswith('REGION_OBJECT ')]
   self.assertEqual(len(rows),8);self.assertTrue(all(line.split()[1]==(self.f.f.a,self.f.f.b)[n] for line in rows))
   self.assertNotIn('person_'+str(1-n)+'_',wire)
  self.s.close();self.f.f.server=self.f.f.open();self.s=self.f.f.server;self.f.server=self.s
  self.assertEqual(self.s.objects,objects);self.assertEqual(len(self.s.module_state['world_characters']),16)
  p=self.f.connect('Revisit',self.f.f.ra['place_id'],self.f.f.a)
  self.assertEqual(sum(line.startswith('REGION_OBJECT ') for line in self.s._snapshot(p).splitlines()),8)
 def test_ninth_same_scope_refused_without_changing_world(self):
  objects=self.populate();before=deepcopy(self.s.objects)
  moved=deepcopy(objects);moved[8].update(region_revision=self.f.f.a,x=12)
  self.f.commit(dict(state=self.s.module_state,tiles=[],objects=moved))
  self.assertIn('eight objects per map',self.s.module_error);self.assertEqual(self.s.objects,before)
 def test_normal_maps_also_stream_only_current_scope(self):
  objects=[dict(id=f'normal_{group}',group=0,num=group,x=10,y=12,gfx=7,text='Hello.') for group in (0,1)]
  self.f.commit(dict(state=self.s.module_state,tiles=[],objects=objects+[self.f.obj]));self.assertIsNone(self.s.module_error)
  peer=dict(state=[0,0,9,12,4,7,1],id='Observer',out=bytearray(),closing=False)
  wire=self.s._snapshot(peer);self.assertIn('normal_0',wire);self.assertNotIn('normal_1',wire)
  peer['state'][1]=1;wire=self.s._snapshot(peer);self.assertIn('normal_1',wire);self.assertNotIn('normal_0',wire)
 def test_large_host_inspection_roundtrip_has_no_silent_truncation(self):
  self.populate()
  count=len(json.dumps(self.s.module_state,separators=(',',':')))
  self.s.module_state['extra']='x'*(32000-count)
  self.s._validated(dict(state=self.s.module_state,objects=self.s.objects,tiles=[]))
  expected=self.s.inspect();self.assertGreater(len(json.dumps(expected)),60000)
  sock=AdminSocket(self.s)
  with patch('world.client.socket.socket',return_value=sock):actual=admin_request('fake',dict(command='inspect'))
  self.assertEqual(actual,json.loads(json.dumps(expected)));self.assertNotIn('inspection_transfer',sock.conn)
 def test_frozen_inspection_order_and_corruption_fail_closed(self):
  conn={};value=dict(ok=True,state='x'*70000);head=inspection_transfer.begin(conn,value)
  value['state']='changed'
  self.assertEqual(inspection_transfer.receive(head,lambda req:inspection_transfer.next_chunk(conn,req))['state'],'x'*70000)
  head=inspection_transfer.begin(conn,dict(ok=True,state='x'*70000))
  with self.assertRaises(ValueError):inspection_transfer.next_chunk(conn,dict(command='inspect_chunk',digest=head['digest'],index=2))
  head=inspection_transfer.begin(conn,dict(ok=True,state='x'*70000));head['data']='AAAA'
  with self.assertRaises(ValueError):inspection_transfer.receive(head,lambda req:inspection_transfer.next_chunk(conn,req))
 def test_global_resource_bound_remains(self):
  objects=[dict(self.f.obj,id='x'+str(i),x=3+i%8,region_revision=('%064x'%(i//8+1))) for i in range(64)]
  validate_objects(objects)
  with self.assertRaises(ValueError):validate_objects(objects+[dict(self.f.obj,id='extra')])

 def test_actual_population_tool_admits_fifteenth_character_in_other_region(self):
  from world import actor_runtime
  self.populate(7);state=deepcopy(self.s.module_state)
  actor=state['world_characters']['harbor_guide'];actor['version']+=1
  definition=dict(id='new_researcher',kind='character',x=11,y=3,gfx=7,text='New arrival.',name='New Researcher',role='Explore this place',goals=['Explore'],team=[dict(species=278,level=18)])
  actor['plan']=dict(id='new_population',purpose='Populate another existing destination.',steps=[dict(id='create',tool='world.populate',args=dict(revision=self.f.f.b,definition=json.dumps(definition)),after=[])])
  self.f.commit(dict(state=state,objects=self.s.objects,tiles=[]));self.assertIsNone(self.s.module_error)
  self.assertEqual(actor_runtime.tick(self.s,now=10)['status'],'pending')
  _,path,_=self.s.deployment;source=path.read_text();self.s.deployment=None
  self.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());namespace={};exec(source,namespace)
  self.f.commit(namespace['update'](self.s._context(),deepcopy(self.s.module_state)));self.assertIsNone(self.s.module_error)
  self.assertEqual(actor_runtime.tick(self.s,now=16)['status'],'succeeded')
  peer=self.f.connect('Visitor',self.f.f.rb['place_id'],self.f.f.b)
  wire=self.s._snapshot(peer);self.assertIn('new_researcher',wire)
  self.assertEqual(sum(line.startswith('REGION_OBJECT ') for line in wire.splitlines()),8)
  self.assertEqual(len(self.s.module_state['world_characters']),15)

 def test_large_legacy_inspection_refuses_clearly_and_gm_preserves_request_limit(self):
  self.populate();self.s.module_state['extra']='x'*25000
  sock=AdminSocket(self.s);sock.sendall(json.dumps(dict(command='inspect')).encode())
  result=json.loads(sock.readline(65536));self.assertFalse(result['ok']);self.assertIn('chunked',result['error'])
  from world import gm
  with patch('world.client.socket.socket') as socket:
   with self.assertRaises(ValueError):gm.admin_request('fake',dict(command='inspect',extra='x'*2000))
   socket.assert_not_called()
 def test_gm_reads_complete_chunked_inspection_and_transfer_expiry_is_enforced(self):
  self.populate();self.s.module_state['extra']='x'*25000
  from world import gm
  with patch('world.client.socket.socket',return_value=AdminSocket(self.s)):
   result=gm.admin_request('fake',dict(command='inspect'))
  self.assertEqual(len(result['state']['world_characters']),16)
  conn={};head=inspection_transfer.begin(conn,dict(ok=True,state='x'*70000))
  with patch('world.inspection_transfer.time.monotonic',return_value=conn['inspection_transfer'][0]+1):
   with self.assertRaises(ValueError):inspection_transfer.next_chunk(conn,dict(command='inspect_chunk',digest=head['digest'],index=1))
  self.assertNotIn('inspection_transfer',conn)
