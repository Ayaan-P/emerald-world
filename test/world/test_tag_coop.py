"""Production consent and native admission regressions, no game build."""
import unittest
from world.link_protocol import LinkProtocol


class TagCoopTests(unittest.TestCase):
    def setUp(self):
        self.p = LinkProtocol(clock=lambda: 0, id_factory=lambda: 100)
        self.pos = {'alice': [1, 4, 5, 5, 4, 7, 1],
                    'bob': [1, 4, 17, 17, 3, 7, 1]}

    def send(self, who, text, **kwargs):
        return self.p.process(who, text.encode(), self.pos, **kwargs)

    def tag(self):
        self.assertEqual(self.send('alice', 'T OFFER bob'), [('bob', 'T OFFER 100 alice\n')])
        self.assertEqual(self.send('bob', 'T ACCEPT 100'),
                         [('alice', 'T ACTIVE 100 bob 1\n'), ('bob', 'T ACTIVE 100 alice 1\n')])

    def test_active_tag_refreshes_existing_range_wire_before_tls_idle_expiry(self):
        self.tag()
        for now in (10, 20, 30, 40):
            self.assertEqual(self.p.tick(now=now),
                             [('alice', 'T RANGE 100 1\n'), ('bob', 'T RANGE 100 1\n')])
        # A keepalive must never turn an out-of-range tag into consent/admission.
        self.pos['bob'][6] = 0
        self.p.update_presence(self.pos)
        self.assertEqual(self.p.tick(now=50),
                         [('alice', 'T RANGE 100 0\n'), ('bob', 'T RANGE 100 0\n')])
        self.assertEqual(self.p.tick(now=51), [])

    def test_bilateral_tag_and_atomic_coop_first_offer_wins(self):
        self.tag()
        self.assertEqual(self.send('bob', 'L OFFER 4 alice'),
                         [('alice', 'L OFFER 101 4 bob\n'), ('alice', 'L ADMIT 101 4 0\n'),
                          ('bob', 'L ADMIT 101 4 1\n')])
        self.pos['alice'][6] = self.pos['bob'][6] = 0
        self.assertEqual(self.send('alice', 'L OFFER 4 bob'),
                         [('alice', 'L ADMIT 101 4 0\n')])
        self.assertEqual(self.send('bob', 'L OFFER 4 alice'),
                         [('bob', 'L ADMIT 101 4 1\n')])
        self.assertEqual(self.send('alice', 'L EVENT 5 101 4 0 0 0 0 ' + '0'*32),
                         [('alice', 'L ABORT 101\n'), ('bob', 'L ABORT 101\n')])
        self.pos['alice'][6] = self.pos['bob'][6] = 1
        self.assertTrue(self.send('alice', 'L OFFER 4 bob')[0][1].startswith('L OFFER 102 4'))

    def test_target_only_consent_and_expiry(self):
        self.send('alice', 'T OFFER bob')
        self.assertEqual(self.send('alice', 'T ACCEPT 100'), [('alice', 'T ERROR NOT_TARGET\n')])
        self.assertEqual(self.send('eve', 'T ACCEPT 100'), [('eve', 'T ERROR NOT_MEMBER\n')])
        self.assertEqual(self.p.tick(now=15), [('alice', 'T WAIT 100\n'), ('bob', 'T WAIT 100\n')])
        self.assertEqual(self.p.tick(now=59.999), [('alice', 'T WAIT 100\n'), ('bob', 'T WAIT 100\n')])
        self.assertEqual(self.p.tick(now=60), [('alice', 'T END 100\n'), ('bob', 'T END 100\n')])
        self.assertEqual(self.send('bob', 'T ACCEPT 100', now=60),
                         [('bob', 'T ERROR UNKNOWN_SESSION\n')])
        self.assertFalse(self.p._tags)

    def test_human_can_accept_just_before_deadline_but_not_at_deadline(self):
        self.send('alice', 'T OFFER bob', now=0)
        self.assertEqual(self.send('bob', 'T ACCEPT 100', now=59.999),
                         [('alice', 'T WAIT 100\n'), ('bob', 'T WAIT 100\n'),
                          ('alice', 'T ACTIVE 100 bob 1\n'), ('bob', 'T ACTIVE 100 alice 1\n')])
        self.assertFalse(any('T END' in line for _, line in self.p.tick(now=60)))
        self.setUp()
        self.send('alice', 'T OFFER bob', now=0)
        self.assertEqual(self.send('bob', 'T ACCEPT 100', now=60),
                         [('alice', 'T END 100\n'), ('bob', 'T END 100\n'),
                          ('bob', 'T ERROR UNKNOWN_SESSION\n')])

    def test_pending_tag_keepalive_does_not_grant_consent_or_extend_expiry(self):
        self.send('alice', 'T OFFER bob', now=0)
        for now in (10, 20, 30, 40, 50):
            self.assertEqual(self.p.tick(now=now),
                             [('alice', 'T WAIT 100\n'), ('bob', 'T WAIT 100\n')])
            self.assertFalse(self.p._tags[100].active)
        self.assertEqual(self.p.tick(now=60),
                         [('alice', 'T END 100\n'), ('bob', 'T END 100\n')])

    def test_busy_and_out_of_range_never_autoadmit(self):
        self.tag()
        self.pos['bob'][6] = 0
        result = self.send('alice', 'L OFFER 4 bob')
        self.assertIn(('alice', 'L ERROR NOT_READY\n'), result)
        self.assertFalse(any('ADMIT' in line for _, line in result))

    def test_range_updates_do_not_end_tag_or_admitted_coop(self):
        self.tag()
        self.send('alice', 'L OFFER 4 bob')
        self.pos['bob'][6] = 0
        self.assertEqual(self.p.update_presence(self.pos),
                         [('alice', 'T RANGE 100 0\n'), ('bob', 'T RANGE 100 0\n')])
        self.assertEqual(self.p.update_presence(self.pos), [])
        self.assertIn(('alice', 'T END 100\n'), self.p.disconnect('bob'))

    def test_coop_uses_existing_native_round_pipeline(self):
        self.tag()
        self.send('alice', 'L OFFER 4 bob')
        zero = '0'*32
        self.assertEqual(self.send('alice', 'L EVENT 1 101 4 0 1 0 8789 ' + zero), [])
        self.assertEqual(len(self.send('bob', 'L EVENT 1 101 4 1 1 0 8789 ' + zero)), 2)
        self.assertEqual(len(self.send('alice', 'L EVENT 3 101 4 0 1 0 8789 ' + zero)), 2)
        self.assertEqual(self.send('alice', 'L EVENT 4 101 4 0 1 0 8789 ' + '0100'*8), [])
        lines = self.send('bob', 'L EVENT 4 101 4 1 1 0 8789 ' + zero)
        self.assertTrue(lines[0][1].startswith('L COMMIT 3 101 1 0 0100'))

    def test_tag_capacity_one_per_actor_and_reject_release(self):
        for i in range(10):
            self.pos[str(i)] = [1, 4, 5, 5, 4, 7, 1]
        for a, b in (('0', '1'), ('2', '3'), ('4', '5'), ('6', '7')):
            self.assertTrue(self.send(a, 'T OFFER ' + b)[0][1].startswith('T OFFER'))
        self.assertEqual(self.send('8', 'T OFFER 9'), [('8', 'T ERROR CAPACITY\n')])
        self.assertEqual(self.send('0', 'T OFFER 9'), [('0', 'T ERROR BUSY\n')])
        self.assertEqual(self.send('1', 'T REJECT 100'),
                         [('0', 'T END 100\n'), ('1', 'T END 100\n')])
        self.assertTrue(self.send('8', 'T OFFER 9')[0][1].startswith('T OFFER'))

    def test_coop_radius_same_map_and_accept_readiness_are_rechecked(self):
        self.send('alice', 'T OFFER bob')
        self.pos['bob'][2] = 18
        self.assertEqual(self.send('bob', 'T ACCEPT 100'), [('bob', 'T ERROR NOT_IN_RANGE\n')])
        self.pos['bob'][2] = 17
        self.pos['bob'][6] = 0
        self.assertEqual(self.send('bob', 'T ACCEPT 100'), [('bob', 'T ERROR NOT_READY\n')])
        self.pos['bob'][6] = 1
        self.send('bob', 'T ACCEPT 100')
        self.pos['bob'][1] = 5
        self.assertEqual(self.send('alice', 'L OFFER 4 bob'), [('alice', 'L ERROR NOT_IN_RANGE\n')])
        self.assertEqual(self.p.update_presence(self.pos),
                         [('alice', 'T RANGE 100 0\n'), ('bob', 'T RANGE 100 0\n')])

    def test_server_link_role_filter_and_tag_delivery_abort_are_authoritative(self):
        import tempfile
        import time
        from world.server import WorldServer, MAX_QUEUE
        from test.world.test_link_delivery import Selector, Sock
        with tempfile.TemporaryDirectory() as root:
            server = WorldServer(root + '/socket', root + '/state')
            server.selector = Selector()
            server.link_protocol = self.p
            channels = {}
            try:
                for actor in self.pos:
                    peer = dict(id=actor, state=self.pos[actor], state_time=time.monotonic(), closing=False)
                    server.peers[actor] = peer
                    conn = dict(id=actor, presence=peer, sock=Sock(), link=True,
                                closing=False, out=bytearray())
                    server.connections[conn['sock']] = conn
                    server.link_channels[actor] = channels[actor] = conn
                del server.link_channels['bob']
                server._link_line(channels['alice'], b'T OFFER bob')
                self.assertEqual(bytes(channels['alice']['out']), b'T ERROR UNAVAILABLE\n')
                server.link_channels['bob'] = channels['bob']
                channels['alice']['out'].clear()
                server._link_line(channels['alice'], b'T OFFER bob')
                self.assertEqual(bytes(channels['bob']['out']), b'T OFFER 100 alice\n')
                channels['bob']['out'].clear()
                channels['alice']['out'].extend(b'x' * MAX_QUEUE)
                server._link_line(channels['bob'], b'T ACCEPT 100')
                self.assertEqual(bytes(channels['bob']['out']), b'T END 100\n')
                self.assertEqual(self.p._tags, {})
            finally:
                server.close()

    def test_tag_required_and_pvp_still_requires_adjacency(self):
        self.assertEqual(self.send('alice', 'L OFFER 4 bob'), [('alice', 'L ERROR DENIED\n')])
        self.assertEqual(self.send('alice', 'L OFFER 1 bob'), [('alice', 'L ERROR NOT_ADJACENT\n')])


if __name__ == '__main__':
    unittest.main()
