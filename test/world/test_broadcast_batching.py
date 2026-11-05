"""World authority state batching with deterministic time and mocked transport."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from world.server import WorldServer

class Clock:
    now=100.
    def __call__(self):return self.now
class Server(WorldServer):
    def _queue(self,conn,text):conn['out'].extend(text.encode())
    def _broadcast(self):
        self.broadcasts+=1
        super()._broadcast()
class BatchingTests(unittest.TestCase):
    def setUp(self):
        self.clock=Clock(); self.patch=patch('world.server.time.monotonic',self.clock);self.patch.start()
        self.tmp=tempfile.TemporaryDirectory();p=Path(self.tmp.name);self.s=Server(p/'s',p/'state',max_players=64);self.s.broadcasts=0
        self.peers=[]
        for name in ('alice','bob'):
            self.s.create_identity(name)
            peer=dict(id=name,seq=-1,state=None,closing=False,out=bytearray(),sock=None,social=True,field=False,chat=False,travel=False)
            self.s.peers[name]=peer;self.peers.append(peer)
    def tearDown(self):self.s.close();self.tmp.cleanup();self.patch.stop()
    def state(self,i,seq,x):
        self.s._line(self.peers[i],f'STATE {seq} 0 1 {x} 12 4 7 1 '.encode()+b'a'*16+b' '+b'b'*16)
    def test_burst_coalesces_latest_positions_with_bounded_delay(self):
        self.state(0,1,10);self.state(1,1,11);self.state(0,2,12)
        self.assertEqual(self.s.broadcasts,0)
        self.clock.now+=.04;self.s._flush_presence_broadcast();self.assertEqual(self.s.broadcasts,0)
        self.clock.now+=.02;self.s._flush_presence_broadcast();self.assertEqual(self.s.broadcasts,1)
        self.assertIn(b'PEER alice 0 1 12 12',self.peers[1]['out'])
        self.s._flush_presence_broadcast();self.assertEqual(self.s.broadcasts,1)
    def test_each_state_still_gets_sender_snapshot(self):
        self.state(0,1,10);self.state(0,2,11)
        self.assertEqual(self.peers[0]['out'].count(b'BEGIN '),2)
        self.assertEqual(self.s.broadcasts,0)

    def test_continuous_traffic_cannot_postpone_first_deadline(self):
        self.state(0,1,10)
        for seq in range(2,7):
            self.clock.now+=.01;self.state(0,seq,10+seq)
        self.s._flush_presence_broadcast();self.assertEqual(self.s.broadcasts,1)
    def test_sixty_four_peer_updates_coalesce_across_each_tick(self):
        for i in range(2,64):
            name=f'p{i:02}';self.s.create_identity(name)
            peer=dict(id=name,seq=-1,state=None,closing=False,out=bytearray(),sock=None,
                      social=True,field=False,chat=False,travel=False)
            self.s.peers[name]=peer;self.peers.append(peer)
        for peer in self.peers:peer['travel']=True
        for tick in range(10):
            if tick:
                self.clock.now+=.1;self.s._flush_presence_broadcast()
            for i in range(64):self.state(i,tick+1,10+i%10)
        self.clock.now+=.1;self.s._flush_presence_broadcast()
        self.assertEqual(self.s.broadcasts,10)
        self.assertIn(b'TRAVEL 63',self.peers[0]['out'])
        for i in range(64):self.assertEqual(self.peers[i]['state'][2],10+i%10)

    def test_staggered_updates_make_progress_without_per_packet_snapshots(self):
        for i in range(2,64):
            name=f'p{i:02}';self.s.create_identity(name)
            peer=dict(id=name,seq=-1,state=None,closing=False,out=bytearray(),sock=None,
                      social=True,field=False,chat=False,travel=False)
            self.s.peers[name]=peer;self.peers.append(peer)
        for event in range(640):
            self.clock.now=100+event/640
            self.s._flush_presence_broadcast()
            i=event%64;self.state(i,event//64+1,10+i%10)
        self.clock.now=101.1;self.s._flush_presence_broadcast()
        self.assertGreaterEqual(self.s.broadcasts,15)
        self.assertLessEqual(self.s.broadcasts,21)
        self.assertTrue(all(p['seq']==10 for p in self.peers))

    def test_server_loop_flushes_without_further_network_activity(self):
        self.state(0,1,10)
        clock,stop=self.clock,self.s.stopping
        class IdleSelector:
            def select(self, timeout):
                clock.now+=.03
                if clock.now>=100.09:stop.set()
                return []
        self.s.selector=IdleSelector()
        try:self.s._loop()
        finally:self.s.selector=None
        self.assertEqual(self.s.broadcasts,1)
        self.assertIsNone(self.s.presence_broadcast_due)

    def test_immediate_broadcast_absorbs_pending_update(self):
        self.state(0,1,10);self.assertEqual(self.s.broadcasts,0)
        self.s._broadcast();self.assertEqual(self.s.broadcasts,1)
        self.clock.now+=1;self.s._flush_presence_broadcast()
        self.assertEqual(self.s.broadcasts,1)

    def test_state_is_immediately_available_to_authority(self):
        self.state(0,1,10);self.state(1,1,11)
        self.assertEqual(self.s._fresh_link_presence()['bob'][2],11)
        self.assertEqual(self.s.broadcasts,0)

if __name__=='__main__':unittest.main()
