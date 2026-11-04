"""Real AF_UNIX transport with production bridge networking bodies, no game.

Engine/catalog predicates are stubbed; socket, parser, staging, cleanup, polling
and retry bodies are extracted verbatim from the compiled production source.
"""
import ctypes as C
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest

from test.world.test_save_isolation import function

ROOT = Path(__file__).resolve().parents[2]


class PresenceHandshake(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix='ew-presence-component-')
        p = Path(cls.build.name)
        bridge = (ROOT/'src/platform/world_bridge.c').read_text()
        declarations = bridge[bridge.index('#define WB_PEERS'):bridge.index('static bool8 Identifier')]
        source = r'''
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdlib.h>
#include <limits.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <poll.h>
typedef uint8_t bool8;
typedef uint8_t u8;
typedef uint16_t u16;
#define FALSE 0
#define TRUE 1
#define ARRAY_COUNT(a) (sizeof(a)/sizeof((a)[0]))
static bool8 MapCoords(unsigned g,unsigned n,unsigned x,unsigned y) {
    return g < 2 && n < 2 && x < 64 && y < 64;
}
static bool8 WorldCatalog_Metatile(unsigned g,unsigned n,unsigned t) {
    return g < 2 && n < 2 && t < 1024;
}
''' + declarations
        for name in ('Identifier', 'Decimal', 'ObjectText', 'Disconnect', 'Line',
                     'SocketOpen', 'QueueHello', 'Flush', 'Connect', 'Receive', 'WorldBridge_Poll'):
            source += function(bridge, name)
        source += r'''
void start(const char *path) {
    memset(&sWorld,0,sizeof(sWorld));sWorld.fd=-1;
    strcpy(sWorld.socketPath,path);strcpy(sWorld.trainer,"alice");
    memset(sWorld.token,'a',64);sWorld.token[64]=0;
    sWorld.enabled=TRUE;
}
void finish(void) { Disconnect();sWorld.enabled=FALSE; }
unsigned ready(void) { return sWorld.connected; }
unsigned peer_count(void) { return sWorld.live.peerCount; }
unsigned input_size(void) { return sWorld.inputSize; }
'''
        (p/'presence.c').write_text(source)
        subprocess.run(['cc', '-shared', '-fPIC', '-std=c99', '-Wall', '-Wextra',
                        '-Werror', str(p/'presence.c'), '-o', str(p/'presence.so')], check=True)
        cls.lib = C.CDLL(str(p/'presence.so'))
        cls.lib.start.argtypes = [C.c_char_p]
        cls.lib.WorldBridge_Poll.argtypes = [C.c_ubyte]

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ew-ph-')
        self.path = Path(self.tmp.name)/'sock'
        self.listener = socket.socket(socket.AF_UNIX)
        self.listener.bind(str(self.path))
        self.listener.listen()
        self.listener.settimeout(.1)
        self.peer = None
        self.lib.start(str(self.path).encode())
        self.pump(2)
        self.accept()

    def tearDown(self):
        self.lib.finish()
        if self.peer is not None:
            self.peer.close()
        self.listener.close()
        self.tmp.cleanup()

    def pump(self, count=1):
        for _ in range(count):
            self.lib.WorldBridge_Poll(0)

    def accept(self):
        self.peer, _ = self.listener.accept()
        self.peer.settimeout(.1)
        self.pump()
        self.assertEqual(self.peer.recv(4096), b'HELLO 1 alice ' + b'a'*64 + b' SOCIAL\n')

    def incoming(self, data):
        self.peer.sendall(data)
        self.pump(2)

    def test_silent_presence_expires_and_retries_same_identity(self):
        self.pump(300)
        self.assertEqual(self.lib.ready(), 0)
        self.assertEqual(self.peer.recv(4096), b'')
        self.peer.close()
        self.peer = None
        self.pump(31)
        self.accept()
        self.incoming(b'WELCOME 1 alice 7\nBEGIN 7\nPEER bob 0 1 10 12 1 7 1\nEND\n')
        self.assertEqual(self.lib.ready(), 1)
        self.assertEqual(self.lib.peer_count(), 1)

    def test_repeated_silent_attempts_get_fresh_bounded_budget(self):
        for _ in range(3):
            self.pump(300)
            self.assertEqual(self.peer.recv(4096), b'')
            self.peer.close()
            self.peer = None
            self.pump(31)
            self.accept()
        self.incoming(b'WELCOME 1 alice 9\n')
        self.assertEqual(self.lib.ready(), 1)

    def test_valid_welcome_near_deadline_keeps_channel_alive(self):
        self.pump(280)
        self.incoming(b'WELCOME 1 alice 7\n')
        self.pump(1000)
        self.assertEqual(self.lib.ready(), 1)

    def test_partial_welcome_never_resets_total_attempt_budget(self):
        self.incoming(b'WELCOME 1 alice')
        self.assertNotEqual(self.lib.input_size(), 0)
        self.pump(300)
        self.assertEqual(self.peer.recv(4096), b'')
        self.assertEqual(self.lib.ready(), 0)
        self.assertEqual(self.lib.input_size(), 0)

    def test_ready_presence_stays_alive_and_reconnect_clears_stale_peers(self):
        self.incoming(b'WELCOME 1 alice 7\nBEGIN 7\nPEER bob 0 1 10 12 1 7 1\nEND\n')
        self.assertEqual(self.lib.peer_count(), 1)
        self.pump(1000)
        self.assertEqual(self.lib.ready(), 1)
        self.peer.close()
        self.peer = None
        self.pump()
        self.assertEqual(self.lib.peer_count(), 0)
        self.pump(31)
        self.accept()
        self.incoming(b'WELCOME 1 alice 8\nBEGIN 8\nEND\n')
        self.assertEqual(self.lib.ready(), 1)
        self.assertEqual(self.lib.peer_count(), 0)

    def test_real_authority_restart_reuses_identity_and_rejects_bad_version(self):
        from world.server import WorldServer
        self.lib.finish()
        path = Path(self.tmp.name)/'authority.sock'
        state = Path(self.tmp.name)/'world'
        server = WorldServer(str(path), str(state))
        server.create_identity('alice', token='a'*64)
        server.start()

        def admitted():
            for _ in range(200):
                self.pump()
                players = server.inspect()['players']
                if self.lib.ready() and [p['id'] for p in players] == ['alice']:
                    return
                time.sleep(.002)
            self.fail('real authority failed to admit the same presence identity')

        try:
            self.lib.start(str(path).encode())
            admitted()
            for hello, error in ((b'HELLO 2 alice ', b'ERROR AUTH'),
                                 (b'HELLO 1 alice ', b'ERROR DUPLICATE')):
                with socket.socket(socket.AF_UNIX) as sock:
                    sock.settimeout(1)
                    sock.connect(str(path))
                    sock.sendall(hello + b'a'*64 + b' SOCIAL\n')
                    self.assertEqual(sock.recv(4096).split(b'\n')[0], error)
                self.pump()
                self.assertEqual(self.lib.ready(), 1)
            server.close()
            self.pump()
            self.assertEqual(self.lib.ready(), 0)
            self.assertEqual(self.lib.peer_count(), 0)
            server = WorldServer(str(path), str(state)).start()
            admitted()
            with server.lock:
                self.assertEqual(server.db.execute('SELECT count(*) FROM identities').fetchone()[0], 1)
        finally:
            self.lib.finish()
            server.close()

    def test_incompatible_version_is_not_admitted(self):
        self.incoming(b'WELCOME 2 alice 7\n')
        self.assertEqual(self.lib.ready(), 0)
        self.assertEqual(self.peer.recv(4096), b'')


if __name__ == '__main__':
    unittest.main()
