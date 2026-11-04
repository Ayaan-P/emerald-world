"""Reconnect with BOTH production C transport and native cable, no game adapter."""
import ctypes as C
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class LinkReconnect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix='ew-link-reconnect-')
        target = Path(cls.build.name)/'link.so'
        subprocess.run(['cc', '-shared', '-fPIC', '-std=c99', '-Wall', '-Wextra',
                        '-Werror', '-DPORTABLE', '-I'+str(ROOT/'include'),
                        str(ROOT/'src/platform/link_transport.c'),
                        str(ROOT/'src/platform/native_link.c'), '-o', str(target)], check=True)
        cls.lib = C.CDLL(str(target))
        cls.lib.LinkTransport_Init.argtypes = [C.c_char_p]
        cls.lib.LinkTransport_TagOffer.argtypes = [C.c_char_p]
        cls.lib.LinkTransport_Offer.argtypes = [C.c_char_p, C.c_uint]
        cls.lib.LinkTransport_TagPeer.restype = C.c_char_p

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ew-lr-')
        self.path = Path(self.tmp.name)
        self.listener = socket.socket(socket.AF_UNIX)
        self.listener.bind(str(self.path/'sock'))
        self.listener.listen()
        self.listener.settimeout(.1)
        self.peer = None
        config = self.path/'config'
        config.write_text(f'socket {self.path}/sock\ntrainer Alice\ntoken ' + 'a'*64 +
                          f'\ntelemetry {self.path}/ignored\n')
        self.assertEqual(self.lib.LinkTransport_Init(str(config).encode()), 1)
        self.accept()

    def tearDown(self):
        self.lib.LinkTransport_Close()
        if self.peer is not None:
            self.peer.close()
        self.listener.close()
        self.tmp.cleanup()

    def pump(self, count=2):
        for _ in range(count):
            self.lib.LinkTransport_Pump()

    def accept(self):
        self.pump()
        self.peer, _ = self.listener.accept()
        self.peer.settimeout(.1)
        self.pump()
        self.assertEqual(self.peer.recv(4096), b'HELLO 1 Alice ' + b'a'*64 + b' LINK\n')

    def incoming(self, wire):
        self.peer.sendall(wire)
        self.pump()

    def welcome_and_admit(self, session):
        self.incoming(b'WELCOME 1 Alice 1 LINK\n')
        self.assertEqual(self.lib.LinkTransport_Ready(), 1)
        self.assertEqual(self.lib.LinkTransport_TagOffer(b'Bob'), 1)
        self.pump()
        self.assertEqual(self.peer.recv(4096), b'T OFFER Bob\n')
        self.incoming(b'T ACTIVE 50 Bob 1\n')
        self.assertEqual(self.lib.LinkTransport_TagPeer(), b'Bob')
        self.assertEqual(self.lib.LinkTransport_Offer(b'Bob', 4), 1)
        self.pump()
        self.assertEqual(self.peer.recv(4096), b'L OFFER 4 Bob\n')
        self.incoming(f'L ADMIT {session} 4 0\n'.encode())
        self.assertEqual(self.lib.NativeLink_IsActive(), 1)
        self.assertEqual(self.lib.LinkTransport_Mode(), 4)

    def test_fast_render_pumps_do_not_expire_wan_handshake(self):
        # Dummy/software rendering may poll thousands of times per frame.
        self.pump(10000)
        self.incoming(b'WELCOME 1 Alice 1 LINK\n')
        self.assertEqual(self.lib.LinkTransport_Ready(), 1)

    def test_expired_handshake_allows_real_cable_admission_after_retry(self):
        import time
        time.sleep(5.1)
        self.pump(300)
        self.assertEqual(self.peer.recv(4096), b'')
        self.assertEqual(self.lib.NativeLink_IsActive(), 0)
        self.peer.close()
        self.peer = None
        self.pump(61)
        self.accept()
        self.welcome_and_admit(101)

    def test_eof_active_session_reconnects_then_requires_new_tag_and_offer(self):
        self.welcome_and_admit(101)
        self.peer.close()
        self.peer = None
        self.pump()
        self.assertEqual(self.lib.LinkTransport_Ready(), 0)
        self.assertEqual(self.lib.NativeLink_IsActive(), 0)
        self.assertIsNone(self.lib.LinkTransport_TagPeer())
        self.assertEqual(self.lib.LinkTransport_Mode(), 0)
        self.pump(61)
        self.accept()
        self.assertEqual(self.lib.LinkTransport_Offer(b'Bob', 4), 0)
        self.welcome_and_admit(102)


if __name__ == '__main__':
    unittest.main()
