"""Wire/session integration tests, not claims of a native battle or trade."""
import unittest


class LinkProtocolTests(unittest.TestCase):
    def make(self):
        from world.link_protocol import LinkProtocol
        return LinkProtocol(clock=lambda: 0, id_factory=lambda: 123)

    def presence(self):
        return {'alice': [1,4,5,5,4,7,1], 'bob': [1,4,6,5,3,7,1]}

    def paired(self):
        p = self.make()
        positions = self.presence()
        self.assertEqual(p.process('alice', b'L OFFER 1 bob', positions),
                         [('bob', 'L OFFER 123 1 alice\n')])
        self.assertEqual(p.process('bob', b'L ACCEPT 123', positions),
                         [('alice', 'L ADMIT 123 1 0\n'), ('bob', 'L ADMIT 123 1 1\n')])
        return p, positions

    def event(self, p, actor, kind, slot, generation=1, step=0, words=None):
        import struct
        data = struct.pack('<8H', *(words or [0]*8)).hex()
        return p.process(actor, f'L EVENT {kind} 123 1 {slot} {generation} {step} 8755 {data}'.encode(), self.presence())

    def test_real_coordinator_pair_bootstrap_handshake_and_command_round(self):
        p, positions = self.paired()
        self.assertEqual(self.event(p, 'alice', 1, 0), [])
        pair = self.event(p, 'bob', 1, 1)
        zero = '0'*32
        self.assertEqual(pair, [(name, f'L COMMIT 1 123 1 0 {zero} {zero}\n') for name in ('alice','bob')])
        # The native lobby must clock zero ticks to reach host ADVANCE.
        self.assertEqual(self.event(p, 'alice', 4, 0), [])
        round0 = self.event(p, 'bob', 4, 1)
        self.assertEqual(round0[0][1], f'L COMMIT 3 123 1 0 {zero} {zero}\n')
        handshake = self.event(p, 'alice', 3, 0, step=1)
        self.assertEqual(handshake[0][1], f'L COMMIT 2 123 1 0 {zero} {zero}\n')
        a, b = [0x2222]+[1]*7, [0]*8
        self.assertEqual(self.event(p, 'alice', 4, 0, step=1, words=a), [])
        frame = self.event(p, 'bob', 4, 1, step=1, words=b)
        self.assertIn('L COMMIT 3 123 1 1 ', frame[0][1])
        self.assertEqual(self.event(p, 'alice', 4, 0, step=1, words=a), [])

    def test_offer_consent_presence_membership_and_slot_checks(self):
        p = self.make()
        positions = self.presence()
        positions['bob'][6] = 0
        self.assertEqual(p.process('alice', b'L OFFER 1 bob', positions), [('alice', 'L ERROR NOT_READY\n')])
        p, positions = self.paired()
        bad = p.process('mallory', b'L ACCEPT 123', positions)
        self.assertEqual(bad, [('mallory','L ERROR NOT_MEMBER\n')])
        bad = self.event(p, 'alice', 1, 1)
        self.assertIn(('alice','L ERROR SLOT\n'), bad)
        self.assertIn(('bob','L ABORT 123\n'), bad)

    def test_delayed_previous_close_cannot_abort_or_clear_next_open(self):
        for early, early_slot, late, late_slot in (('alice',0,'bob',1),('bob',1,'alice',0)):
            with self.subTest(early=early):
                p, _ = self.paired()
                self.event(p,'alice',1,0)
                self.event(p,'bob',1,1)
                self.assertEqual(self.event(p,early,2,early_slot),[])
                self.assertEqual(self.event(p,early,1,early_slot,generation=2),[])
                self.assertEqual(self.event(p,late,2,late_slot),[])
                pair = self.event(p,late,1,late_slot,generation=2)
                self.assertTrue(pair[0][1].startswith('L COMMIT 1 123 2 '), pair)

    def test_generation_close_reopen_retains_reservation(self):
        p, _ = self.paired()
        self.event(p, 'alice', 1, 0)
        self.event(p, 'bob', 1, 1)
        self.assertEqual(self.event(p, 'alice', 2, 0), [])
        self.assertEqual(self.event(p, 'bob', 2, 1), [])
        self.assertEqual(self.event(p, 'bob', 1, 1, generation=2), [])
        self.assertTrue(self.event(p, 'alice', 1, 0, generation=2)[0][1].startswith('L COMMIT 1 123 2 '))
        ended = p.disconnect('bob')
        self.assertEqual(ended, [('alice','L ABORT 123\n'),('bob','L ABORT 123\n')])

    def test_oversize_overflow_malformed_inputs_never_echo_or_allocate(self):
        for raw in (b'x'*513,b'L OFFER 5 bob',b'L ACCEPT 18446744073709551616',
                    b'L ACCEPT +123',b'L ACCEPT 123 extra',b'L OFFER 1 bad/name',
                    b'L EVENT 4 123 1 0 1 0 8755 nothex',b'L OFFER 1 \xff'):
            p = self.make()
            result = p.process('alice', raw, self.presence())
            self.assertEqual(result, [('alice','L ERROR MALFORMED\n')], repr(raw[:30]))

    def test_closed_activity_wire_id_is_never_reused(self):
        p, positions = self.paired()
        p.disconnect('alice')
        offered = p.process('alice', b'L OFFER 1 bob', positions)
        new_sid = offered[0][1].split()[2]
        self.assertNotEqual(new_sid, '123')
        stale = p.process('bob', b'L ACCEPT 123', positions)
        self.assertIn(('bob', 'L ERROR UNKNOWN_SESSION\n'), stale)

    def test_expiration_delivers_abort_and_frees_wire_id(self):
        p = self.make()
        p.process('alice', b'L OFFER 1 bob', self.presence())
        self.assertEqual(p.tick(now=16), [('alice','L ABORT 123\n'),('bob','L ABORT 123\n')])
        self.assertEqual(p.process('bob', b'L ACCEPT 123', self.presence(), now=16),
                         [('bob','L ERROR UNKNOWN_SESSION\n')])
