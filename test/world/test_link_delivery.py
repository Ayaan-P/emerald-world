"""Exercise real delivery/teardown code with a synthetic OS selector boundary."""
import tempfile
import unittest
from world.link_protocol import LinkProtocol
from world.server import MAX_QUEUE, WorldServer


class Selector:
    def unregister(self, sock):
        pass
    def modify(self, *args):
        pass
    def get_map(self):
        return {}
    def close(self):
        pass


class Sock:
    def close(self):
        pass


class LinkDeliveryTests(unittest.TestCase):
    def overflow(self, stage):
        with tempfile.TemporaryDirectory(prefix='link-delivery-') as root:
            server = WorldServer(root+'/socket',root+'/state')
            server.selector = Selector()
            server.link_protocol = LinkProtocol(clock=lambda:0,id_factory=lambda:123)
            positions = {'alice':[1,4,5,5,4,7,1],'bob':[1,4,6,5,3,7,1]}
            channels = {}
            for name in positions:
                presence = dict(id=name,state=positions[name],closing=False)
                server.peers[name] = presence
                conn = dict(sock=Sock(),id=name,link=True,presence=presence,closing=False,out=bytearray())
                server.connections[conn['sock']] = conn
                server.link_channels[name] = channels[name] = conn
            p = server.link_protocol
            zero = '0'*32
            try:
                p.process('alice',b'L OFFER 1 bob',positions)
                result = p.process('bob',b'L ACCEPT 123',positions)
                if stage in ('pair','round'):
                    p.process('alice',f'L EVENT 1 123 1 0 1 0 8755 {zero}'.encode(),positions)
                    result = p.process('bob',f'L EVENT 1 123 1 1 1 0 8755 {zero}'.encode(),positions)
                if stage=='round':
                    p.process('alice',f'L EVENT 3 123 1 0 1 0 0 {zero}'.encode(),positions)
                    p.process('alice',f'L EVENT 4 123 1 0 1 0 0 {zero}'.encode(),positions)
                    result = p.process('bob',f'L EVENT 4 123 1 1 1 0 0 {zero}'.encode(),positions)
                channels['alice']['out'].extend(b'x'*MAX_QUEUE)
                server._deliver_links(result)
                self.assertEqual(bytes(channels['bob']['out']),b'L ABORT 123\n')
                self.assertNotIn('alice',server.link_channels)
                self.assertTrue(channels['alice']['closing'])
                # Buffered commands on the synchronously dropped connection
                # cannot create a new reservation under its still-live presence.
                server._link_line(channels['alice'],b'L OFFER 1 bob')
                self.assertEqual(bytes(channels['bob']['out']),b'L ABORT 123\n')
                self.assertEqual(server.link_protocol.tick(),[])
                self.assertEqual(server.link_protocol._wire,{})
            finally:
                server.close()

    def test_overflow_first_admit_is_terminal(self):
        self.overflow('admit')
    def test_overflow_first_pair_is_terminal(self):
        self.overflow('pair')
    def test_overflow_first_round_is_terminal(self):
        self.overflow('round')
