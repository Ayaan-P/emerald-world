"""Real loopback TLS integration tests. No external services or credentials."""
import hashlib
from pathlib import Path
import socket
import ssl
import subprocess
import tempfile
import time
import unittest

RESEARCH = '/home/ayaan/projects/emerald-world-research'


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='tls-', dir=RESEARCH)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cert, self.key = self.root / 'cert.pem', self.root / 'key.pem'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', str(self.key), '-out', str(self.cert), '-days', '1',
                        '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       shell=False)
        self.key.chmod(0o600)
        self.pin = hashlib.sha256(ssl.PEM_cert_to_DER_cert(self.cert.read_text())).hexdigest()

    def start_world(self):
        from world.server import WorldServer
        server = WorldServer(self.root / 'state/transport/world.sock', self.root / 'state')
        self.addCleanup(server.close)
        identities = [server.create_identity(name) for name in ('Alice', 'Bob')]
        server.start()
        return server, identities

    def host(self, server, **kwargs):
        from world.transport import HostBroker
        host = HostBroker(server.socket_path, self.cert, self.key, **kwargs).start()
        self.addCleanup(host.close)
        return host

    def connector(self, host, name, **kwargs):
        from world.transport import ClientBroker
        client = ClientBroker(self.root / name / 'world.sock', host.address, **kwargs).start()
        self.addCleanup(client.close)
        return client

    def test_two_world_clients_exchange_state_over_tls(self):
        from world.client import WorldClient
        server, identities = self.start_world()
        host = self.host(server)
        self.assertEqual(host.address[0], '127.0.0.1')
        brokers = [self.connector(host, name, fingerprint=self.pin) for name in ('a', 'b')]
        clients = [WorldClient(b.socket_path, i['id'], i['token'])
                   for b, i in zip(brokers, identities)]
        for client in clients:
            self.addCleanup(client.close)
        for n, client in enumerate(clients):
            client.send_state(1, 0, 1, 10+n, 12, 2, 7, 1, 'a'*16, 'b'*16)
        for client, peer in zip(clients, ('Bob', 'Alice')):
            for _ in range(12):
                snapshot = client.snapshot()
                if peer in snapshot['peers']:
                    break
            self.assertIn(peer, snapshot['peers'])
        self.assertEqual(Path(brokers[0].socket_path).stat().st_mode & 0o777, 0o600)

    def test_authenticated_intentions_cross_tls_without_displacing_game(self):
        from world.client import WorldClient, IntentClient
        from world.runtime_gm import IntentQueue
        server, identities = self.start_world()
        host = self.host(server)
        broker = self.connector(host, 'intent-game', fingerprint=self.pin)
        identity = identities[0]
        with WorldClient(broker.socket_path, 'Alice', identity['token']) as native:
            native.snapshot()
            with IntentClient(broker.socket_path, 'Alice', identity['token']) as control:
                result = control.submit_intent('Please add an optional guide.', request_id='tls-first')
                self.assertTrue(result['ok'], result)
                self.assertEqual(control.intent_status(result['id'])['request']['player'], 'Alice')
                native.send_state(1,0,1,10,12,2,7,1,'a'*16,'b'*16)
                native.snapshot()
                self.assertEqual(len(server.inspect()['players']), 1)
                self.assertEqual(server.inspect()['players'][0]['id'], 'Alice')
        queue = IntentQueue(self.root/'state')
        try:
            request = queue.claim()
            self.assertEqual(request['id'], result['id'])
            self.assertEqual(request['player'], 'Alice')
            self.assertEqual(request['text'], 'Please add an optional guide.')
        finally:
            queue.close()

    def test_half_close_drains_large_reply_with_minimum_buffer(self):
        import threading
        from world.transport import HostBroker, CHUNK
        path = self.root / 'transport/world.sock'
        path.parent.mkdir()
        listener = socket.socket(socket.AF_UNIX)
        self.addCleanup(listener.close)
        listener.bind(str(path))
        listener.listen()
        payload = bytes(range(256)) * 1024
        errors = []
        def backend():
            try:
                conn, _ = listener.accept()
                with conn:
                    conn.settimeout(4)
                    request = bytearray()
                    while True:
                        part = conn.recv(4096)
                        if not part:
                            break
                        request.extend(part)
                    self.assertEqual(request, b'request')
                    conn.sendall(payload)
            except BaseException as exc:
                errors.append(exc)
        thread = threading.Thread(target=backend, daemon=True)
        thread.start()
        host = HostBroker(path, self.cert, self.key, timeout=2, buffer_limit=CHUNK+4).start()
        self.addCleanup(host.close)
        client = self.connector(host, 'local', fingerprint=self.pin, timeout=2, buffer_limit=CHUNK+4)
        with socket.socket(socket.AF_UNIX) as sock:
            sock.settimeout(5)
            sock.connect(client.socket_path)
            sock.sendall(b'request')
            sock.shutdown(socket.SHUT_WR)
            response = bytearray()
            while True:
                data = sock.recv(777)
                if not data:
                    break
                response.extend(data)
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(response), len(payload))
        self.assertEqual(response, payload)

    def test_destination_replacement_cannot_expose_admin(self):
        import struct
        from world.transport import MAGIC
        server, _ = self.start_world()
        host = self.host(server)
        path = Path(server.socket_path)
        path.unlink()
        path.symlink_to(server.admin_path)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with socket.create_connection(host.address, timeout=2) as raw:
            with context.wrap_socket(raw, server_hostname='localhost') as tls:
                tls.sendall(MAGIC)
                self.assertEqual(tls.recv(len(MAGIC)), MAGIC)
                command = b'{"command":"inspect"}\n'
                tls.sendall(struct.pack('!I', len(command)) + command)
                try:
                    response = tls.recv(4096)
                except (ConnectionError, ssl.SSLError):
                    response = b''
                self.assertEqual(response, b'', 'private admin endpoint became network reachable')

    def wait_for(self, predicate, seconds=3):
        deadline = time.monotonic() + seconds
        while not predicate() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(predicate())

    def test_trust_rejections_send_no_hello_to_world(self):
        from world.client import WorldClient
        server, identities = self.start_world()
        host = self.host(server)
        bad = self.connector(host, 'bad-pin', fingerprint='0'*64)
        untrusted = self.connector(host, 'untrusted', cafile='/etc/ssl/certs/ca-certificates.crt',
                                   server_hostname='localhost')
        mismatch = self.connector(host, 'bad-name', cafile=self.cert, server_hostname='wrong.invalid')
        for broker in (bad, untrusted, mismatch):
            with self.assertRaises((OSError, ValueError)):
                WorldClient(broker.socket_path, 'Alice', identities[0]['token'], timeout=2)
        self.wait_for(lambda: host.active_clients == 0)
        self.assertEqual(server.peers, {})
        self.assertEqual(server.db.execute('SELECT count(*) FROM events').fetchone()[0], 0)

    def test_ca_verification_and_end_to_end_bad_token(self):
        from world.client import WorldClient
        server, identities = self.start_world()
        host = self.host(server)
        broker = self.connector(host, 'trusted', cafile=self.cert, server_hostname='localhost')
        with self.assertRaisesRegex(ValueError, 'AUTH'):
            WorldClient(broker.socket_path, 'Alice', '0'*64)
        with WorldClient(broker.socket_path, 'Alice', identities[0]['token']) as client:
            self.assertEqual(client.snapshot()['peers'], {})

    def test_admin_and_arbitrary_targets_rejected(self):
        from world.transport import HostBroker, ClientBroker
        server, _ = self.start_world()
        for path in (server.admin_path, self.root / 'other.sock'):
            with self.assertRaises(ValueError):
                HostBroker(path, self.cert, self.key)
        for options in ({}, {'fingerprint':'x'*64}, {'fingerprint':'a'*63},
                        {'fingerprint':'a'*64, 'cafile':self.cert}):
            with self.assertRaises(ValueError):
                ClientBroker(self.root / 'unused.sock', ('127.0.0.1', 1), **options)
        for n in (0, 9):
            with self.assertRaises(ValueError):
                HostBroker(server.socket_path, self.cert, self.key, max_clients=n)
        host = self.host(server)
        broker = self.connector(host, 'game', fingerprint=self.pin)
        with socket.socket(socket.AF_UNIX) as sock:
            sock.settimeout(2)
            sock.connect(broker.socket_path)
            sock.sendall(b'{"command":"inspect","destination":"admin.sock"}\n')
            self.assertTrue(sock.recv(4096).startswith(b'ERROR AUTH'))
        self.assertEqual(server.peers, {})

    def test_stalled_handshakes_bounded_to_eight_workers_and_clean_shutdown(self):
        server, _ = self.start_world()
        host = self.host(server, handshake_timeout=5)
        sockets = [socket.create_connection(host.address, timeout=2) for _ in range(8)]
        for sock in sockets:
            self.addCleanup(sock.close)
        # Observe admitted workers before filling the listen backlog. Connecting
        # twelve first can outlast a short handshake timeout under CPU load.
        self.wait_for(lambda: host.active_clients == 8)
        for _ in range(4):
            with socket.create_connection(host.address, timeout=2) as excess:
                self.assertEqual(excess.recv(1), b'')
                self.assertLessEqual(host.active_clients, 8)
        for sock in sockets:
            sock.close()
        self.wait_for(lambda: host.active_clients == 0)
        host.handshake_timeout = 0.25
        with socket.create_connection(host.address, timeout=2) as expiring:
            self.wait_for(lambda: host.active_clients == 1)
            self.wait_for(lambda: host.active_clients == 0)
            self.assertEqual(expiring.recv(1), b'')
        host.handshake_timeout = 5
        stalled = socket.create_connection(host.address, timeout=2)
        self.addCleanup(stalled.close)
        self.wait_for(lambda: host.active_clients == 1)
        start = time.monotonic()
        host.close()
        self.assertLess(time.monotonic() - start, 1)
        self.assertEqual(host.active_clients, 0)
        self.assertFalse(host._thread.is_alive())

    def test_malformed_tls_and_oversized_frames_cleanup(self):
        import struct
        from world.transport import MAGIC, CHUNK
        server, _ = self.start_world()
        host = self.host(server, handshake_timeout=0.3)
        with socket.create_connection(host.address, timeout=2) as sock:
            sock.sendall(b'not TLS at all\n')
        context = ssl.create_default_context(cafile=str(self.cert))
        for data in (b'WRONG', MAGIC + struct.pack('!I', CHUNK+1),
                     MAGIC + struct.pack('!I', 10) + b'truncated'):
            with socket.create_connection(host.address, timeout=2) as raw:
                with context.wrap_socket(raw, server_hostname='localhost') as tls:
                    tls.sendall(data)
                    if data.startswith(MAGIC):
                        self.assertEqual(tls.recv(len(MAGIC)), MAGIC)
        self.wait_for(lambda: host.active_clients == 0)
        self.assertEqual(server.peers, {})

    def test_idle_relay_expires_and_existing_socket_is_not_replaced(self):
        from world.transport import ClientBroker
        server, _ = self.start_world()
        host = self.host(server, timeout=0.2)
        broker = self.connector(host, 'idle', fingerprint=self.pin, timeout=0.2)
        inode = Path(broker.socket_path).stat().st_ino
        with self.assertRaises(OSError):
            ClientBroker(broker.socket_path, host.address, fingerprint=self.pin).start()
        self.assertEqual(Path(broker.socket_path).stat().st_ino, inode)
        with socket.socket(socket.AF_UNIX) as sock:
            sock.settimeout(2)
            sock.connect(broker.socket_path)
            self.wait_for(lambda: broker.active_clients == 1)
            self.assertEqual(sock.recv(1), b'')
        self.wait_for(lambda: broker.active_clients == host.active_clients == 0)
        broker.close()
        self.assertFalse(Path(broker.socket_path).exists())

    def test_real_cli_pair_and_sigterm_cleanup(self):
        import sys
        from world.client import WorldClient
        server, identities = self.start_world()
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        address = f'127.0.0.1:{port}'
        log = (self.root / 'cli.log').open('wb')
        self.addCleanup(log.close)
        def launch(args):
            process = subprocess.Popen([sys.executable, '-B', '-m', 'world.transport'] + args,
                                       stdout=log, stderr=log, shell=False)
            def cleanup():
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            self.addCleanup(cleanup)
            return process
        host = launch(['serve', '--listen', address, '--game-socket', server.socket_path,
                       '--cert', str(self.cert), '--key', str(self.key)])
        def listening():
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=0.1):
                    return True
            except OSError:
                return False
        self.wait_for(listening)
        path = self.root / 'cli/world.sock'
        connector = launch(['connect', '--remote', address, '--fingerprint', self.pin,
                            '--socket', str(path)])
        self.wait_for(path.exists)
        with WorldClient(path, 'Alice', identities[0]['token']) as client:
            self.assertEqual(client.snapshot()['peers'], {})
        connector.terminate()
        connector.wait(3)
        self.assertFalse(path.exists())
        host.terminate()
        host.wait(3)
        self.assertEqual(host.returncode, 0)
        self.assertEqual(connector.returncode, 0)
        self.assertEqual((self.root / 'cli.log').read_bytes(), b'')


if __name__ == '__main__':
    unittest.main()
