"""Exercise the real server's bounded presence batching without sockets."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from world.server import WorldServer, PRESENCE_BATCH_INTERVAL

class CountingServer(WorldServer):
 def __init__(self,*args,**kwargs):
  self.broadcasts=0
  super().__init__(*args,**kwargs)
 def _broadcast(self):
  self.broadcasts+=1
  super()._broadcast()

class PresenceBatching(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)
  self.server=CountingServer(root/'sock',root/'world',max_players=64)
  self.clients=[]
  for i in range(32):
   name=f'P{i:02}';self.server.create_identity(name)
   c={'id':name,'sock':object(),'out':bytearray(),'closing':False,'seq':0,'state':None,'social':True,'field':False,'travel':False,'chat':False}
   self.server.peers[name]=c;self.clients.append(c)
 def tearDown(self):self.server.close();self.tmp.cleanup()
 def send(self,c,seq,x):
  msg=f'STATE {seq} 0 0 {x} 4 1 7 1 '+('a'*16)+' '+('b'*16)
  self.server._line(c,msg.encode())
 def test_burst_is_coalesced_and_latest_positions_are_sent(self):
  with patch('world.server.time.monotonic',return_value=100.0):
   self.server.last_presence_broadcast=100.0
   for i,c in enumerate(self.clients):self.send(c,1,i%25+1)
   self.send(self.clients[1],2,3)
   self.assertEqual(self.server.broadcasts,0);self.assertTrue(self.server.presence_dirty)
   self.server._poll_presence(100.0+PRESENCE_BATCH_INTERVAL-.001);self.assertEqual(self.server.broadcasts,0)
   self.server._poll_presence(100.0+PRESENCE_BATCH_INTERVAL+.001)
   self.assertEqual(self.server.broadcasts,1);self.assertFalse(self.server.presence_dirty)
   wire=self.clients[0]['out'].decode();self.assertEqual(wire.count('BEGIN '),1)
   # The emitted snapshot contains the final update, not the intermediate one.
   self.assertEqual(self.clients[1]['state'][2],3)
   self.assertIn('PEER P01 0 0 3 4 1 7 1',wire)
 def test_unchanged_heartbeats_do_not_spam_but_refresh_once_per_second(self):
  with patch('world.server.time.monotonic') as clock:
   clock.return_value=100.0;self.server.last_presence_broadcast=100.0
   for i,c in enumerate(self.clients):self.send(c,1,i%25+1)
   clock.return_value=100.06;self.server._poll_presence(clock());self.assertEqual(self.server.broadcasts,1)
   for c in self.clients:c['out'].clear()
   self.clients[0]['travel']=True
   for n in range(1,10):
    clock.return_value=100.06+n*.1
    for i,c in enumerate(self.clients):self.send(c,n+1,i%25+1)
    self.server._poll_presence(clock())
   self.assertEqual(self.server.broadcasts,1)
   clock.return_value=101.07;self.send(self.clients[0],11,1)
   self.assertTrue(self.server.presence_dirty)
   clock.return_value=101.13;self.server._poll_presence(clock())
   self.assertEqual(self.server.broadcasts,2)
   self.assertIn(b'BEGIN ',self.clients[0]['out'])
   self.assertIn(b'FRIEND P01 ',self.clients[0]['out'])
 def test_ready_to_field_change_is_batched_and_visible(self):
  with patch('world.server.time.monotonic') as clock:
   clock.return_value=100.0;self.server.last_presence_broadcast=100.0
   self.send(self.clients[0],1,1);self.send(self.clients[1],1,2)
   clock.return_value=100.06;self.server._poll_presence(clock())
   self.clients[0]['out'].clear()
   clock.return_value=100.1
   self.server._line(self.clients[1],('FIELD 2 0 0 2 4 1 7 0 '+('a'*16)+' '+('b'*16)).encode())
   self.assertTrue(self.server.presence_dirty)
   clock.return_value=100.16;self.server._poll_presence(clock())
   self.assertIn(b'PEER P01 0 0 2 4 1 7 0',self.clients[0]['out'])
 def test_identical_returning_state_revives_expired_friend(self):
  with patch('world.server.time.monotonic') as clock:
   clock.return_value=100.0;self.server.last_presence_broadcast=100.0
   self.clients[0]['travel']=True
   self.send(self.clients[0],1,1);self.send(self.clients[1],1,2)
   clock.return_value=100.06;self.server._poll_presence(clock())
   clock.return_value=103.2;self.send(self.clients[0],2,1)
   clock.return_value=103.26;self.server._poll_presence(clock())
   self.clients[0]['out'].clear()
   clock.return_value=103.3;self.send(self.clients[1],2,2)
   self.assertTrue(self.server.presence_dirty)
   clock.return_value=103.36;self.server._poll_presence(clock())
   self.assertIn(b'FRIEND P01 ',self.clients[0]['out'])
 def test_return_after_ttl_rounds_to_zero_is_not_suppressed(self):
  with patch('world.server.time.monotonic') as clock:
   clock.return_value=100.0;self.server.last_presence_broadcast=100.0
   self.send(self.clients[1],1,2)
   clock.return_value=100.06;self.server._poll_presence(clock())
   # At 2.99 seconds the wire TTL has already rounded down to zero.
   clock.return_value=102.98;self.server._broadcast()
   clock.return_value=102.99;self.send(self.clients[1],2,2)
   self.assertTrue(self.server.presence_dirty)
 def test_immediate_event_broadcast_flushes_pending_batch(self):
  with patch('world.server.time.monotonic',return_value=100.0):
   self.server.last_presence_broadcast=100.0;self.send(self.clients[0],1,1)
   self.assertTrue(self.server.presence_dirty)
   self.server._broadcast();self.assertEqual(self.server.broadcasts,1)
   self.server._poll_presence(101.0);self.assertEqual(self.server.broadcasts,1)

if __name__=='__main__':unittest.main()
