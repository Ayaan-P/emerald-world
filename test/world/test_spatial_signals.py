import sqlite3,time,types,unittest
from unittest.mock import patch
from world import spatial_signals as s
class Signals(unittest.TestCase):
 def server(self):
  result=types.SimpleNamespace(db=sqlite3.connect(':memory:'),notices=[],link_protocol=types.SimpleNamespace(busy=lambda _:False))
  result.guild_chat=types.SimpleNamespace(message=lambda c,n,t:result.notices.append(t));return result
 def conn(self,id='alice',group=0,num=0,x=10,y=10):return dict(id=id,presence=dict(id=id,state=[group,num,x,y,1,0,1],state_time=time.monotonic(),chat=True))
 def test_optin_nearby_marker_notice_off_and_expiry(self):
  server=self.server();a=self.conn();b=self.conn('bob',x=11)
  self.assertEqual(s.handle(server,a,b'H SEND help'),'H CLEAR\n')
  s.handle(server,a,b'H ON');self.assertEqual(s.handle(server,a,b'H SEND help'),'H ACK\n')
  self.assertEqual(s.handle(server,b,b'H GET'),'H CLEAR\n');s.handle(server,b,b'H ON')
  frame=s.handle(server,b,b'H GET');self.assertTrue(frame.startswith('H MARK '));self.assertEqual(frame.split()[3:7],['0','0','10','10']);self.assertEqual(len(server.notices),1)
  s.handle(server,b,b'H GET');self.assertEqual(len(server.notices),1)
  s.handle(server,b,b'H OFF');self.assertEqual(s.handle(server,b,b'H GET'),'H CLEAR\n')
  s.handle(server,b,b'H ON')
  with patch('world.spatial_signals.time.time',return_value=time.time()+9):self.assertEqual(s.handle(server,b,b'H GET'),'H CLEAR\n')
 def test_private_maps_far_peer_staleness_and_cooldown(self):
  server=self.server();a=self.conn();s.handle(server,a,b'H ON');s.handle(server,a,b'H SEND look')
  self.assertEqual(s.handle(server,a,b'H SEND danger'),'H CLEAR\n')
  for peer in [self.conn('b',group=1),self.conn('b',num=50),self.conn('b',num=1),self.conn('b',x=25)]:
   s.handle(server,peer,b'H ON');self.assertEqual(s.handle(server,peer,b'H GET'),'H CLEAR\n')
  a['presence']['state_time']-=4;self.assertEqual(s.handle(server,a,b'H GET'),'H CLEAR\n')
  self.assertEqual(server.db.execute('SELECT count(*) FROM spatial_signals').fetchone()[0],1)
 def test_actor_actual_native_position_and_rollback(self):
  server=self.server();obj=dict(group=0,num=0,x=9,y=8)
  s.setup(server.db);server.db.commit()
  with patch('world.spatial_speech.ready_actor',return_value=({},obj)):
   with server.db:r=s.signal(server,'guide',{},dict(kind='meet'))
   self.assertEqual(r['position'],[0,0,9,8]);self.assertEqual(r['outcome'],'spatial_signal_committed')
   with self.assertRaises(RuntimeError):
    with server.db:
     with patch('world.spatial_signals.time.time',return_value=time.time()+3):s.signal(server,'guide',{},dict(kind='look'))
     raise RuntimeError()
   self.assertEqual(server.db.execute('SELECT kind FROM spatial_signals').fetchone()[0],1)
   obj['region_revision']='a'*64
   with self.assertRaises(ValueError):s.signal(server,'guide',{},dict(kind='help'))
 def test_busy_and_invalid_kind(self):
  server=self.server();a=self.conn();s.handle(server,a,b'H ON')
  self.assertEqual(s.handle(server,a,b'H SEND arbitrary'),'H CLEAR\n')
  server.link_protocol.busy=lambda _:True;self.assertEqual(s.handle(server,a,b'H SEND look'),'H CLEAR\n')
  self.assertEqual(server.db.execute('SELECT count(*) FROM spatial_signals').fetchone()[0],0)
