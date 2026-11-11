"""The real admin socket carries one frozen inspection to completion."""
import json
from pathlib import Path
import socket
import tempfile
import time
import unittest

from world.client import admin_request
from world.inspection_transfer import receive
from world.server import WorldServer


class InspectionSocketLifetimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ew-inspect-', dir='/tmp')
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.server = WorldServer(root/'transport/world.sock', root).start()
        self.addCleanup(self.server.close)

    def test_real_admin_client_receives_full_large_inspection(self):
        expected = self.server.inspect()
        self.assertGreater(len(json.dumps(expected).encode()), 60000)
        actual = admin_request(self.server.socket_path, {'command': 'inspect'})
        self.assertEqual(actual, json.loads(json.dumps(expected)))

    def test_frozen_transfer_stays_open_only_until_last_chunk(self):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(5)
            sock.connect(str(self.server.admin_path))
            with sock.makefile('rb') as stream:
                def exchange(value):
                    sock.sendall(json.dumps(value).encode()+b'\n')
                    raw = stream.readline(65537)
                    self.assertTrue(raw.endswith(b'\n'), 'inspection socket closed before reply')
                    self.assertLessEqual(len(raw), 65536)
                    return json.loads(raw)
                first = exchange({'command': 'inspect', 'chunked': True})
                self.assertGreater(first['inspection_chunks'], 1)
                result = receive(first, exchange)
                self.assertTrue(result['ok'])
                self.assertEqual(stream.read(1), b'')

    def test_expired_transfer_releases_admin_connection(self):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(5)
            sock.connect(str(self.server.admin_path))
            sock.sendall(b'{"command":"inspect","chunked":true}\n')
            with sock.makefile('rb') as stream:
                self.assertIn('inspection_chunks', json.loads(stream.readline(65537)))
                with self.server.lock:
                    transfers = [conn for conn in self.server.connections.values()
                                 if conn.get('inspection_transfer')]
                    self.assertEqual(len(transfers), 1)
                    conn = transfers[0]
                    _, digest, chunks, index = conn['inspection_transfer']
                    conn['inspection_transfer'] = (time.monotonic()-1, digest, chunks, index)
                self.assertEqual(stream.read(1), b'')


if __name__ == '__main__':
    unittest.main()
