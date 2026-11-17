from copy import deepcopy
import json
import unittest
from unittest.mock import patch
import test_actor_space as fixture
from test_region_admission import WireSocket
from world.client import RegionClient
from world import actor_runtime as runtime

class PlaceTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.SpaceTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
 def plan(self,actor='harbor_guide',style='rooms',identity='new_place'):
  state=deepcopy(self.s.module_state);c=state['world_characters'][actor];c['version']+=1
  bp=dict(rooms=[[3,3,6,6],[19,19,7,7]],links=[[0,1]],entrance_room=0,exit_room=1,style=style,seed=817)
  c['plan']=dict(id=identity,purpose='Create connected navigable space.',steps=[dict(id='create',tool='world.create_place',args=dict(label='New Hollow',blueprint=json.dumps(bp,separators=(',',':'))),after=[])])
  self.f.f.f.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
 def result(self):
  return json.loads(self.s.db.execute("SELECT result FROM actor_tool_receipts WHERE status='succeeded' AND step='create' ORDER BY seq DESC").fetchone()[0])
 def connect(self,name):
  identity=self.s.create_identity(name);sock=WireSocket(self.s)
  with patch('world.client.socket.socket',return_value=sock):client=RegionClient('socket',name,identity['token'])
  client.send_state(1,0,9,8,8,1,7,1,'a'*16,'b'*16)
  return client
 def test_actual_menu_transfer_ack_entry_and_restart_preserve_shared_world(self):
  old=self.s.shared_cave.identity;objects=deepcopy(self.s.objects);self.plan()
  self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded');result=self.result()
  self.assertEqual(self.s.shared_cave.identity,old);self.assertEqual(self.s.objects,objects)
  client=self.connect('Visitor');peer=client.sock.conn;peer['out'].clear()
  self.s._line(peer,b'REGION LIST 0');self.assertIn(result['place_id'],peer['out'].decode())
  peer['out'].clear();transfer=client.select_region(result['place_id'])
  self.assertEqual(peer['cave_ack'],result['revision']);self.assertEqual(len(transfer['template']),969)
  client.send_state(peer['seq']+1,*self.s.cave_map,1,1,1,7,1,'a'*16,'b'*16)
  self.assertFalse(peer['closing']);self.assertEqual(self.s._region_scope(peer),result['revision'])
  self.s.close();base=self.f.f.f.f.f.f;base.server=base.open();self.s=base.server
  self.assertEqual(self.s.shared_cave.identity,old);self.assertIsNone(runtime.tick(self.s,now=20))
  client=self.connect('AfterRestart');client.select_region(result['place_id'])
  self.assertEqual(client.sock.conn['cave_ack'],result['revision'])
 def test_distinct_actor_distinct_geometry_and_no_duplicate_identity(self):
  self.plan();self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded');first=self.result()
  self.plan('second','organic');self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded');second=self.result()
  self.assertNotEqual(first['place_id'],second['place_id']);self.assertNotEqual(first['revision'],second['revision'])
  self.plan('harbor_guide','rooms','again');self.assertEqual(runtime.tick(self.s,now=22)['status'],'blocked')
 def test_failed_receipt_leaves_no_archive_or_open_region(self):
  self.plan();archives=self.s.db.execute('SELECT count(*) FROM generated_area_archive').fetchone()[0]
  regions=self.s.db.execute('SELECT count(*) FROM world_region_revisions').fetchone()[0];original=runtime._receipt
  def fail(server,actor,row,plan,step,status,result):
   if status=='succeeded':raise ValueError('injected failure')
   return original(server,actor,row,plan,step,status,result)
  with patch.object(runtime,'_receipt',side_effect=fail):self.assertEqual(runtime.tick(self.s,now=10)['status'],'blocked')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM generated_area_archive').fetchone()[0],archives)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM world_region_revisions').fetchone()[0],regions)
 def test_legacy_cannot_select_and_invalid_blueprint_never_publishes(self):
  self.plan();self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded')
  client=self.connect('OldClient');peer=client.sock.conn;peer['region_capable']=False;peer['out'].clear()
  self.s._line(peer,('REGION SELECT '+self.result()['place_id']).encode())
  self.assertIn('REGION REFUSED',peer['out'].decode());self.assertIsNone(peer.get('region_cave'))
  state=deepcopy(self.s.module_state);c=state['world_characters']['second'];c['version']+=1
  c['plan']=dict(id='invalid',purpose='Disconnected proposal must fail.',steps=[dict(id='create',tool='world.create_place',args=dict(label='Invalid',blueprint=json.dumps(dict(rooms=[[3,3,3,3],[20,20,3,3]],links=[],entrance_room=0,exit_room=1))),after=[])])
  self.f.f.f.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects));before=self.s.db.execute('SELECT count(*) FROM world_region_revisions').fetchone()[0]
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM world_region_revisions').fetchone()[0],before)
