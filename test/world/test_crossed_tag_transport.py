"""Real C tag parsers and native-link state, driven by server tag authority.

No native game, SDL, save fixture, or SDK gameplay is launched.
"""
import ctypes as C
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from world.link_protocol import LinkProtocol

ROOT = Path(__file__).resolve().parents[2]

class Invitation(C.Structure):
    _fields_ = [('id', C.c_uint64), ('mode', C.c_uint), ('name', C.c_char * 25)]

class CrossedTagTransport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix='crossed-tags-build-')
        cls.libs = {}
        for name in ('alice', 'bob'):
            path = Path(cls.build.name)/(name+'.so')
            subprocess.run(['cc','-shared','-fPIC','-std=c99','-Wall','-Wextra','-Werror',
                            '-DPORTABLE','-I'+str(ROOT/'include'),
                            str(ROOT/'src/platform/link_transport.c'),
                            str(ROOT/'src/platform/native_link.c'),
                            '-Wl,-Bsymbolic','-o',str(path)], check=True, capture_output=True)
            lib = C.CDLL(str(path))
            lib.LinkTransport_Init.argtypes = [C.c_char_p]
            lib.LinkTransport_TagOffer.argtypes = [C.c_char_p]
            for method in ('LinkTransport_TagAccept','LinkTransport_TagReject'):
                getattr(lib, method).argtypes = [C.c_uint64]
            lib.LinkTransport_PendingTag.restype = C.POINTER(Invitation)
            lib.LinkTransport_TagPeer.restype = C.c_char_p
            cls.libs[name] = lib

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='xtag-')
        self.addCleanup(self.tmp.cleanup)
        self.peers = {}
        self.now = 0
        self.authority = LinkProtocol(clock=lambda: self.now, id_factory=lambda: 100)
        self.presence = {'alice': [1,4,5,5,4,7,1], 'bob': [1,4,6,5,3,7,1]}
        for name, lib in self.libs.items():
            path = Path(self.tmp.name)/name
            listener = socket.socket(socket.AF_UNIX)
            self.addCleanup(listener.close)
            listener.bind(str(path)); listener.listen(); listener.settimeout(1)
            config = path.with_suffix('.conf')
            config.write_text(f'socket {path}\ntrainer {name}\ntoken '+ 'a'*64+f'\ntelemetry {path}.telemetry\n')
            self.addCleanup(lib.LinkTransport_Close)
            self.assertEqual(lib.LinkTransport_Init(str(config).encode()), 1)
            self.pump(name)
            peer, _ = listener.accept(); peer.settimeout(1)
            self.addCleanup(peer.close)
            self.assertTrue(peer.recv(4096).startswith(('HELLO 1 '+name+' ').encode()))
            self.peers[name] = peer
            self.deliver(name, 'WELCOME 1 '+name+' 1 LINK\n')
            self.assertEqual(lib.LinkTransport_Ready(), 1)

    def pump(self, name):
        for _ in range(5):
            self.libs[name].LinkTransport_Pump()

    def deliver(self, name, text):
        self.peers[name].sendall(text.encode())
        self.pump(name)

    def request(self, name):
        self.pump(name)
        raw = self.peers[name].recv(4096)
        self.assertTrue(raw.endswith(b'\n') and raw.count(b'\n') == 1)
        return self.authority.process(name, raw[:-1], self.presence)

    def route(self, events):
        for name, text in events:
            self.deliver(name, text)

    def cross(self, winner, *, delay_busy=False):
        loser = 'bob' if winner == 'alice' else 'alice'
        for name, target in ((winner, loser), (loser, winner)):
            self.assertEqual(self.libs[name].LinkTransport_TagOffer(target.encode()), 1)
        offer = self.request(winner)
        busy = self.request(loser)
        self.assertEqual(offer, [(loser, f'T OFFER 100 {winner}\n')])
        self.assertEqual(busy, [(loser, 'T ERROR BUSY\n')])
        # Real C parser buffers an incomplete OFFER without exposing consent.
        self.deliver(loser, offer[0][1][:-1])
        self.assertFalse(self.libs[loser].LinkTransport_PendingTag())
        self.assertEqual(self.libs[loser].LinkTransport_TagOfferPending(), 1)
        self.deliver(loser, '\n')
        pending = self.libs[loser].LinkTransport_PendingTag()
        self.assertTrue(pending)
        self.assertEqual((pending.contents.id, pending.contents.name), (100, winner.encode()))
        self.assertIsNone(self.libs[loser].LinkTransport_TagPeer())
        self.assertEqual(self.libs[loser].NativeLink_IsActive(), 0)
        if delay_busy:
            self.delayed_busy = busy
            return winner, loser
        self.route(busy)
        self.assertTrue(self.libs[loser].LinkTransport_PendingTag())
        self.assertEqual(self.libs[loser].LinkTransport_TagOfferPending(), 0)
        self.assertTrue(all(lib.LinkTransport_Ready() for lib in self.libs.values()))
        return winner, loser

    def test_accept_before_delayed_busy_preserves_pending_consent(self):
        winner, loser = self.cross('alice', delay_busy=True)
        self.assertEqual(self.libs[loser].LinkTransport_TagAccept(100), 1)
        active = self.request(loser)
        # TCP order remains OFFER, BUSY, ACTIVE. The user's click can occur
        # between reads, before BUSY, but ACTIVE must never overtake BUSY.
        self.route(self.delayed_busy)
        self.assertTrue(self.libs[loser].LinkTransport_PendingTag())
        self.assertIsNone(self.libs[loser].LinkTransport_TagPeer())
        self.route(active)
        self.assertEqual(self.libs[loser].LinkTransport_TagPeer(), winner.encode())
        self.assertEqual(self.libs[winner].LinkTransport_TagPeer(), loser.encode())
        self.assertTrue(all(lib.LinkTransport_Ready() for lib in self.libs.values()))

    def test_decline_before_delayed_busy_does_not_restore_consent(self):
        winner, loser = self.cross('bob', delay_busy=True)
        self.assertEqual(self.libs[loser].LinkTransport_TagReject(100), 1)
        ended = self.request(loser)
        self.route(self.delayed_busy)
        self.route(ended)
        self.assertTrue(all(not lib.LinkTransport_PendingTag() for lib in self.libs.values()))
        self.assertTrue(all(lib.LinkTransport_TagPeer() is None for lib in self.libs.values()))
        self.assertTrue(all(lib.NativeLink_IsActive() == 0 for lib in self.libs.values()))
        self.assertEqual(self.libs[winner].LinkTransport_TagOffer(loser.encode()), 1)
        self.route(self.request(winner))
        self.assertEqual(self.libs[loser].LinkTransport_PendingTag().contents.id, 101)

    def test_authority_keepalives_preserve_pending_clients_until_human_accepts(self):
        winner, loser = self.cross('bob')
        for self.now in (10, 20, 30, 40, 50):
            events = self.authority.tick()
            self.assertEqual(len(events), 2)
            self.route(events)
            self.assertTrue(self.libs[loser].LinkTransport_PendingTag())
            self.assertEqual(self.libs[winner].LinkTransport_TagOfferPending(), 1)
            for lib in self.libs.values():
                self.assertEqual(lib.LinkTransport_Ready(), 1)
                self.assertIsNone(lib.LinkTransport_TagPeer())
                self.assertEqual(lib.NativeLink_IsActive(), 0)
        self.now = 59.999
        self.assertEqual(self.libs[loser].LinkTransport_TagAccept(100), 1)
        self.route(self.request(loser))
        self.assertEqual(self.libs[winner].LinkTransport_TagPeer(), loser.encode())
        self.assertEqual(self.libs[loser].LinkTransport_TagPeer(), winner.encode())

    def test_wait_keepalive_is_read_only_even_after_local_rejection(self):
        winner, loser = self.cross('alice')
        for name in (winner, loser):
            self.deliver(name, 'T WAIT 100\n')
            self.assertEqual(self.libs[name].LinkTransport_Ready(), 1)
            self.assertIsNone(self.libs[name].LinkTransport_TagPeer())
            self.assertEqual(self.libs[name].NativeLink_IsActive(), 0)
        self.assertEqual(self.libs[loser].LinkTransport_TagReject(100), 1)
        # A keepalive already in flight may arrive after the local No click.
        self.deliver(loser, 'T WAIT 100\n')
        self.assertEqual(self.libs[loser].LinkTransport_Ready(), 1)
        self.assertFalse(self.libs[loser].LinkTransport_PendingTag())
        self.route(self.request(loser))

    def test_expired_cross_releases_both_and_refuses_stale_accept(self):
        winner, loser = self.cross('alice')
        self.now = 60
        self.route(self.authority.tick())
        self.assertTrue(all(not lib.LinkTransport_PendingTag() for lib in self.libs.values()))
        self.assertEqual(self.libs[loser].LinkTransport_TagAccept(100), 0)
        self.assertTrue(all(lib.LinkTransport_TagPeer() is None for lib in self.libs.values()))
        self.assertEqual(self.libs[loser].LinkTransport_TagOffer(winner.encode()), 1)
        self.route(self.request(loser))
        self.assertEqual(self.libs[winner].LinkTransport_PendingTag().contents.id, 101)

    def test_cross_disconnect_clears_offer_and_survivor_can_retry(self):
        winner, loser = self.cross('bob')
        self.route(self.authority.disconnect(winner))
        self.libs[winner].LinkTransport_Close()
        self.assertTrue(all(not lib.LinkTransport_PendingTag() for lib in self.libs.values()))
        self.assertTrue(all(lib.LinkTransport_TagPeer() is None for lib in self.libs.values()))
        self.assertEqual(self.libs[loser].LinkTransport_TagOfferPending(), 0)
        self.assertEqual(self.libs[loser].LinkTransport_TagOffer(winner.encode()), 1)

    def test_unsolicited_active_still_fails_closed(self):
        winner, loser = self.cross('alice')
        # A crossed invitation does not itself grant consent. Even a line
        # with the correct pending ID cannot silently activate the target.
        self.deliver(loser, f'T ACTIVE 100 {winner} 1\n')
        self.assertEqual(self.libs[loser].LinkTransport_Ready(), 0)
        self.assertIsNone(self.libs[loser].LinkTransport_TagPeer())
        self.assertEqual(self.libs[loser].NativeLink_IsActive(), 0)

    def test_alice_first_cross_requires_explicit_target_consent(self):
        winner, loser = self.cross('alice')
        self.assertEqual(self.libs[loser].LinkTransport_TagAccept(99), 0)
        self.assertEqual(self.libs[loser].LinkTransport_TagAccept(100), 1)
        self.route(self.request(loser))
        self.assertEqual(self.libs[winner].LinkTransport_TagPeer(), loser.encode())
        self.assertEqual(self.libs[loser].LinkTransport_TagPeer(), winner.encode())
        self.assertTrue(all(lib.NativeLink_IsActive() == 0 for lib in self.libs.values()))
        self.assertEqual(self.libs[winner].LinkTransport_TagEnd(), 1)
        self.route(self.request(winner))
        self.assertTrue(all(lib.LinkTransport_TagPeer() is None for lib in self.libs.values()))
        self.assertEqual(self.libs[winner].LinkTransport_TagOffer(loser.encode()), 1)
        self.route(self.request(winner))
        self.assertEqual(self.libs[loser].LinkTransport_PendingTag().contents.id, 101)

    def test_bob_first_cross_can_be_declined_and_reused(self):
        winner, loser = self.cross('bob')
        self.assertEqual(self.libs[loser].LinkTransport_TagReject(100), 1)
        self.route(self.request(loser))
        self.assertTrue(all(lib.LinkTransport_Ready() for lib in self.libs.values()))
        self.assertTrue(all(lib.LinkTransport_TagPeer() is None for lib in self.libs.values()))
        self.assertEqual(self.libs[loser].LinkTransport_TagOffer(winner.encode()), 1)
        self.route(self.request(loser))
        self.assertEqual(self.libs[winner].LinkTransport_PendingTag().contents.id, 101)
