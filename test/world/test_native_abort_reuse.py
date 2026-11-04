"""Abort/reuse through both real C components and a disposable Unix peer.

No engine adapter is stubbed and no native game is launched. The socket peer
supplies protocol records, not gameplay results.
"""
import ctypes as C
import os
from pathlib import Path
import shlex
import socket
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]


class NativeAbortReuseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix='native-abort-components-')
        output = Path(cls.build.name) / 'components.so'
        command = [os.environ.get('CC', 'cc'), '-shared', '-fPIC', '-std=c99',
                   '-Wall', '-Wextra', '-Werror', '-DPORTABLE', '-I' + str(ROOT / 'include'),
                   str(ROOT / 'src/platform/native_link.c'),
                   str(ROOT / 'src/platform/link_transport.c'), '-o', str(output)]
        command += shlex.split(os.environ.get('NATIVE_LINK_CFLAGS', ''))
        subprocess.run(command, check=True, capture_output=True, text=True)
        cls.lib = C.CDLL(str(output))
        cls.lib.LinkTransport_Init.argtypes = [C.c_char_p]
        cls.lib.LinkTransport_TagOffer.argtypes = [C.c_char_p]
        cls.lib.LinkTransport_Offer.argtypes = [C.c_char_p, C.c_uint]
        cls.lib.LinkTransport_TagPeer.restype = C.c_char_p
        cls.lib.NativeLink_Open.argtypes = [C.c_uint16]
        cls.lib.NativeLink_Admit.argtypes = [C.c_uint64, C.c_uint, C.c_uint]
        cls.lib.NativeLink_EndSession.argtypes = [C.c_uint64]
        cls.lib.LinkTransport_PendingInvitation.restype = C.c_void_p

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='nr-')
        directory = Path(self.tmp.name)
        self.server = socket.socket(socket.AF_UNIX)
        self.server.bind(str(directory / 'socket'))
        self.server.listen()
        self.server.settimeout(1)
        self.peer = None
        config = directory / 'config'
        # Disposable fixture credential, never read from an operator profile.
        config.write_text(f'socket {directory}/socket\ntrainer Alice\ntoken ' + 'a' * 64 + f'\ntelemetry {directory}/ignored\n')
        self.assertEqual(self.lib.LinkTransport_Init(str(config).encode()), 1)
        self.pump()
        self.peer, _ = self.server.accept()
        self.peer.settimeout(1)
        self.assertEqual(self.peer.recv(4096), b'HELLO 1 Alice ' + b'a' * 64 + b' LINK\n')
        self.incoming(b'WELCOME 1 Alice 1 LINK\n')
        self.assertEqual(self.lib.LinkTransport_TagOffer(b'Bob'), 1)
        self.pump()
        self.assertEqual(self.peer.recv(4096), b'T OFFER Bob\n')
        self.incoming(b'T ACTIVE 50 Bob 1\n')
        self.check_tag()

    def tearDown(self):
        self.lib.LinkTransport_Close()
        if self.peer:
            self.peer.close()
        self.server.close()
        self.tmp.cleanup()

    def pump(self):
        for _ in range(5):
            self.lib.LinkTransport_Pump()
            time.sleep(.001)

    def incoming(self, record):
        self.peer.sendall(record)
        self.pump()

    def check_tag(self):
        self.assertEqual(self.lib.LinkTransport_Ready(), 1)
        self.assertEqual(self.lib.LinkTransport_TagPeer(), b'Bob')
        self.assertEqual(self.lib.LinkTransport_TagInRange(), 1)

    def offer(self, mode=4):
        self.assertEqual(self.lib.LinkTransport_Offer(b'Bob', mode), 1)
        self.pump()
        self.assertEqual(self.peer.recv(4096), f'L OFFER {mode} Bob\n'.encode())

    def admit(self, session, mode=4):
        self.offer(mode)
        self.incoming(f'L ADMIT {session} {mode} 0\n'.encode())
        self.check_tag()
        self.assertEqual(self.lib.NativeLink_IsActive(), 1)
        self.assertEqual(self.lib.LinkTransport_Mode(), mode)

    def test_remote_abort_reuses_accepted_tag_with_both_components(self):
        for session in (101, 102, 103):
            self.admit(session)
            self.lib.NativeLink_Open(0x2233)
            self.pump()
            self.assertTrue(self.peer.recv(4096).startswith(f'L EVENT 1 {session} 4 0 1 '.encode()))
            self.incoming(f'L ABORT {session}\n'.encode())
            self.assertEqual(self.lib.NativeLink_IsActive(), 0)
            self.check_tag()
            self.assertEqual(self.lib.LinkTransport_Mode(), 0)
        self.admit(104)

    def test_local_abort_then_remote_terminal_reuses_tag(self):
        self.admit(201)
        self.lib.NativeLink_Abort()
        self.pump()
        self.assertTrue(self.peer.recv(4096).startswith(b'L EVENT 5 201 4 0 '))
        self.lib.NativeLink_Abort()
        self.incoming(b'L ABORT 201\n')
        self.assertEqual(self.lib.NativeLink_IsActive(), 0)
        self.check_tag()
        self.admit(202)

    def test_unrelated_abort_keeps_current_native_session(self):
        self.admit(401)
        self.incoming(b'L ABORT 400\n')
        self.check_tag()
        self.assertEqual(self.lib.NativeLink_IsActive(), 1)
        self.assertEqual(self.lib.LinkTransport_Mode(), 4)

    def test_matching_pending_abort_releases_offer_for_retry(self):
        self.offer()
        self.incoming(b'L OFFER 501 4 Bob\n')
        self.incoming(b'L ABORT 501\n')
        self.check_tag()
        self.assertEqual(self.lib.LinkTransport_OfferPending(), 0)
        self.assertFalse(self.lib.LinkTransport_PendingInvitation())
        self.admit(502)

    def test_offer_error_releases_unassigned_intent(self):
        self.offer()
        self.incoming(b'L ERROR NOT_READY\n')
        self.check_tag()
        self.assertEqual(self.lib.LinkTransport_OfferPending(), 0)
        self.admit(601)

    def test_each_native_mode_reuses_transport_without_resetting_tag(self):
        for mode in (1, 2, 3, 4):
            with self.subTest(mode=mode):
                self.admit(700 + mode, mode)
                self.incoming(f'L ABORT {700 + mode}\n'.encode())
                self.assertEqual(self.lib.NativeLink_IsActive(), 0)
                self.check_tag()
        self.admit(705)

    def test_authoritative_abort_releases_backpressured_terminal_event(self):
        self.admit(801)
        # No transport pump drains its real bounded output queue in this loop.
        # Production queue exhaustion must retain a terminal event, not silently
        # discard it to permit a new session.
        for _ in range(2000):
            self.lib.NativeLink_Open(0x2233)
            self.lib.NativeLink_Close()
            if not self.lib.NativeLink_IsActive():
                break
        else:
            self.fail('production output queue did not reach bounded capacity')
        self.lib.NativeLink_Abort()
        self.lib.NativeLink_Reset()
        self.assertEqual(self.lib.NativeLink_Admit(802, 4, 0), 0)
        # EndSession for an unrelated ID must not clear the retained event.
        self.lib.NativeLink_EndSession(800)
        self.assertEqual(self.lib.NativeLink_Admit(802, 4, 0), 0)
        self.incoming(b'L ABORT 801\n')
        self.check_tag()
        assert self.peer is not None
        self.peer.setblocking(False)
        queued = bytearray()
        try:
            while True:
                try:
                    chunk = self.peer.recv(65536)
                except BlockingIOError:
                    break
                if not chunk:
                    break
                queued.extend(chunk)
        finally:
            self.peer.settimeout(1)
        self.assertGreater(len(queued), 60000)
        self.assertLessEqual(len(queued), 65536)
        self.assertTrue(queued.endswith(b'\n'))
        self.assertTrue(all(line.startswith(b'L EVENT ') for line in queued.splitlines()))
        self.admit(802)

    def test_production_broker_abort_and_second_admission(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from world.link_protocol import LinkProtocol
        broker = LinkProtocol(clock=lambda: 0, id_factory=lambda: 50)
        positions = {'Alice': [1, 4, 5, 5, 4, 7, 1],
                     'Bob': [1, 4, 6, 5, 3, 7, 1]}
        broker.process('Alice', b'T OFFER Bob', positions)
        active = broker.process('Bob', b'T ACCEPT 50', positions)
        self.assertIn(('Alice', 'T ACTIVE 50 Bob 1\n'), active)

        def deliver(records):
            for actor, record in records:
                if actor == 'Alice':
                    self.incoming(record.encode())

        for session in (51, 52):
            self.offer()
            admission = broker.process('Alice', b'L OFFER 4 Bob', positions)
            self.assertIn(('Alice', f'L ADMIT {session} 4 0\n'), admission)
            deliver(admission)
            self.assertEqual(self.lib.NativeLink_IsActive(), 1)
            self.lib.NativeLink_Abort()
            self.pump()
            assert self.peer is not None
            actual_event = self.peer.recv(4096).strip()
            self.assertTrue(actual_event.startswith(f'L EVENT 5 {session} 4 0 '.encode()))
            terminal = broker.process('Alice', actual_event, positions)
            self.assertIn(('Alice', f'L ABORT {session}\n'), terminal)
            deliver(terminal)
            self.check_tag()
            self.assertEqual(self.lib.NativeLink_IsActive(), 0)
        self.admit(53)

    def test_disconnect_requires_fresh_consent_and_does_not_replay_events(self):
        self.admit(901)
        self.lib.NativeLink_Open(0x2233)
        self.lib.NativeLink_Abort()
        # Both real queues still contain old-session traffic when the peer dies.
        assert self.peer is not None
        self.peer.shutdown(socket.SHUT_RDWR)
        self.peer.close()
        self.peer = None
        self.pump()
        self.assertEqual(self.lib.NativeLink_IsActive(), 0)
        self.assertEqual(self.lib.LinkTransport_Ready(), 0)
        self.assertIsNone(self.lib.LinkTransport_TagPeer())
        for _ in range(70):
            self.lib.LinkTransport_Pump()
        self.peer, _ = self.server.accept()
        self.peer.settimeout(1)
        self.pump()
        # Reconnect is a new authenticated channel, not a replay of old events.
        self.assertEqual(self.peer.recv(4096), b'HELLO 1 Alice ' + b'a' * 64 + b' LINK\n')
        self.incoming(b'WELCOME 1 Alice 2 LINK\n')
        self.assertEqual(self.lib.LinkTransport_Ready(), 1)
        self.assertIsNone(self.lib.LinkTransport_TagPeer())
        self.assertEqual(self.lib.LinkTransport_Offer(b'Bob', 4), 0)
        self.assertEqual(self.lib.LinkTransport_TagOffer(b'Bob'), 1)
        self.pump()
        self.assertEqual(self.peer.recv(4096), b'T OFFER Bob\n')
        self.incoming(b'T ACTIVE 51 Bob 1\n')
        self.admit(902)

    def test_full_width_session_abort_is_not_truncated(self):
        session = 2**64 - 1
        self.admit(session)
        self.incoming(f'L ABORT {session - 1}\n'.encode())
        self.assertEqual(self.lib.NativeLink_IsActive(), 1)
        self.incoming(f'L ABORT {session}\n'.encode())
        self.check_tag()
        self.assertEqual(self.lib.NativeLink_IsActive(), 0)
        self.admit(903)

    def test_stale_abort_cannot_cancel_new_tagged_encounter_offer(self):
        self.admit(301)
        self.incoming(b'L ABORT 301\n')
        self.offer()
        self.assertEqual(self.lib.LinkTransport_OfferPending(), 1)
        self.incoming(b'L ABORT 301\n')
        self.assertEqual(self.lib.LinkTransport_OfferPending(), 1)
        self.incoming(b'L ADMIT 302 4 0\n')
        self.check_tag()
        self.assertEqual(self.lib.NativeLink_IsActive(), 1)


if __name__ == '__main__':
    unittest.main()
