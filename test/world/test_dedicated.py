"""Focused production-component checks; no emulator or SDK required."""
import socket
import tempfile
import unittest
from pathlib import Path

from world.server import WorldServer
from world.transport import _Broker


class DedicatedTests(unittest.TestCase):
    def test_channel_budget_is_not_trainer_budget(self):
        self.assertGreaterEqual(_Broker().max_clients, 32)
        self.assertEqual(_Broker(max_clients=72).max_clients, 72)
        with self.assertRaises(ValueError):
            _Broker(max_clients=1025)

    def test_configurable_players_and_control_headroom(self):
        with self.subTest('live channels'):
            directory = self.enterContext(tempfile.TemporaryDirectory(prefix='ew-', dir='/tmp'))
            root = Path(directory)
            server = WorldServer(root/'world.sock', root/'state', max_players=10,
                                 max_controls=20, connection_headroom=4)
            self.addCleanup(server.close)
            self.assertEqual(server.max_connections, 44)
            identities = [server.create_identity('P'+str(i)) for i in range(11)]
            server.start()
            def connect(identity, role=''):
                sock = socket.socket(socket.AF_UNIX)
                sock.settimeout(2)
                self.addCleanup(sock.close)
                sock.connect(str(root/'world.sock'))
                sock.sendall(('HELLO 1 {id} {token}'.format(**identity)+role+'\n').encode())
                return sock.recv(4096).split(b'\n')[0]
            for identity in identities[:10]:
                self.assertTrue(connect(identity).startswith(b'WELCOME'))
                self.assertTrue(connect(identity, ' LINK').endswith(b' LINK'))
                self.assertTrue(connect(identity, ' CONTROL').endswith(b' CONTROL'))
            self.assertEqual(connect(identities[10]), b'ERROR FULL')
            self.assertTrue(server.thread.is_alive())
            self.assertEqual(server.inspect()['capacity']['players'], 10)

    def test_thirty_two_trainers_support_sixteen_independent_pairs_and_tags(self):
        from world.link_protocol import LinkProtocol
        protocol = LinkProtocol(max_players=32, clock=lambda: 0, id_factory=lambda: 1)
        presence = {f'P{i:02}': [0, 1, 10+i//2, 10+i%2, 1, 7, 1] for i in range(34)}
        wires = []
        for i in range(0, 32, 2):
            a, b = f'P{i:02}', f'P{i+1:02}'
            offered = protocol.process(a, f'L OFFER 1 {b}'.encode(), presence)
            self.assertEqual([recipient for recipient, _ in offered], [b])
            wire = offered[0][1].split()[2]
            wires.append(wire)
            accepted = protocol.process(b, f'L ACCEPT {wire}'.encode(), presence)
            self.assertEqual({recipient for recipient, _ in accepted}, {a, b})
            tagged = protocol.process(a, f'T OFFER {b}'.encode(), presence)
            self.assertEqual([recipient for recipient, _ in tagged], [b])
        self.assertEqual(len(set(wires)), 16)
        self.assertEqual(len(protocol.sessions._sessions), 16)
        self.assertEqual(len(protocol._tag_actor), 32)
        self.assertEqual(protocol.process('P32', b'L OFFER 1 P33', presence), [('P32', 'L ERROR CAPACITY\n')])
        self.assertEqual(protocol.process('P32', b'T OFFER P33', presence), [('P32', 'T ERROR CAPACITY\n')])
        # Outsider cannot end somebody else's session; disconnect ends only its pair.
        messages = protocol.process('P32', f'L ACCEPT {wires[0]}'.encode(), presence)
        self.assertTrue(all(recipient != 'P00' for recipient, _ in messages))
        ended = protocol.disconnect('P00')
        self.assertEqual({recipient for recipient, _ in ended}, {'P00', 'P01'})
        self.assertEqual(len(protocol.sessions._sessions), 15)

    def test_native_view_is_nearest_eight_on_same_map_without_new_fields(self):
        directory = self.enterContext(tempfile.TemporaryDirectory(prefix='ew-', dir='/tmp'))
        server = WorldServer(Path(directory)/'socket', Path(directory)/'state')
        self.addCleanup(server.close)
        viewer = dict(id='Viewer', state=[0, 1, 10, 10, 1, 7, 1], social=True)
        for i in range(20):
            server.peers[f'P{i:02}'] = dict(state=[0, 1, 10+i, 10, 1, 7, 1], field=True)
        server.peers['Elsewhere'] = dict(state=[0, 2, 10, 10, 1, 7, 1], field=True)
        server.peers['Absent'] = dict(state=[0, 0, 0, 0, 1, 7, 0], field=False)
        lines = server._snapshot(viewer).splitlines()
        names = [line.split()[1] for line in lines if line.startswith('PEER ')]
        self.assertEqual(names, [f'P{i:02}' for i in range(8)])
        self.assertTrue(all(line.split()[0] in ('BEGIN', 'PEER', 'END') for line in lines))

    def test_require_existing_state_never_creates_a_new_world(self):
        import subprocess
        import sys
        directory = self.enterContext(tempfile.TemporaryDirectory(prefix='ew-', dir='/tmp'))
        root = Path(directory)/'missing'
        result = subprocess.run([sys.executable, '-m', 'world.server', '--state-dir', str(root),
                                 '--require-existing-state'], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(root.exists())
        self.assertIn(b'existing world database', result.stderr)

    def test_dedicated_cli_tls_invite_and_sigterm_preserve_identity(self):
        import subprocess
        import sys
        import time
        from world.client import admin_request, WorldClient
        from world.transport import ClientBroker, read_invitation
        directory = self.enterContext(tempfile.TemporaryDirectory(prefix='ew-', dir='/tmp'))
        root = Path(directory)
        cert, key = root/'cert.pem', root/'key.pem'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', str(key), '-out', str(cert), '-days', '1',
                        '-subj', '/CN=localhost'], check=True, capture_output=True)
        command = [sys.executable, '-m', 'world.server', '--state-dir', str(root/'state'),
                   '--listen', '127.0.0.1:0', '--advertise', 'localhost:8765',
                   '--cert', str(cert), '--key', str(key), '--max-players', '12']
        game = root/'state/transport/world.sock'
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(lambda: process.poll() is None and (process.terminate(), process.wait(timeout=10)))
        deadline = time.monotonic()+10
        while time.monotonic() < deadline:
            if process.poll() is not None:
                self.fail(str(process.communicate()))
            try:
                status = admin_request(game, dict(command='inspect'))
                if status.get('sharing'):
                    break
            except (OSError, ValueError):
                pass
            time.sleep(.05)
        else:
            self.fail('dedicated service did not become ready')
        self.assertEqual(status['capacity']['players'], 12)
        self.assertEqual(status['capacity']['connections'], 56)
        subprocess.run([sys.executable, '-m', 'world.server', '--state-dir', str(root/'state'),
                        '--invite', 'Alice', '--invitation-out', str(root/'alice.json')],
                       check=True, capture_output=True)
        invitation = read_invitation(root/'alice.json')
        address = tuple(status['sharing']['listen'])
        with ClientBroker(root/'client/world.sock', address, fingerprint=invitation['pin']):
            with WorldClient(root/'client/world.sock', 'Alice', invitation['token']) as client:
                self.assertIsInstance(client.snapshot(), dict)
        process.terminate()
        stdout, stderr = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 0, stderr)
        self.assertEqual(stdout, b'')
        self.assertFalse(game.exists())
        reopened = WorldServer(game, root/'state')
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.create_identity('Alice')['token'], invitation['token'])

    def test_live_identity_specific_invitations_are_repeatable(self):
        from world.client import admin_request
        from world.server import export_invitation
        from world.transport import read_invitation
        directory = self.enterContext(tempfile.TemporaryDirectory(prefix='ew-', dir='/tmp'))
        root = Path(directory)
        server = WorldServer(root/'transport/world.sock', root).start()
        self.addCleanup(server.close)
        server.sharing = dict(version=1, endpoint=dict(host='world.example.org', port=8765), pin='f'*64)
        def invite(trainer, name):
            export_invitation(root/'transport/world.sock', trainer, root/name)
            return read_invitation(root/name)
        a = invite('Alice', 'alice.json')
        self.assertEqual(a, invite('Alice', 'alice-again.json'))
        self.assertNotEqual(a['token'], invite('Bob', 'bob.json')['token'])
        self.assertEqual(a['endpoint']['port'], 8765)
        self.assertEqual((root/'alice.json').stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            invite('Alice', 'alice.json')
        with self.assertRaises(ValueError):
            invite('Alice', 'transport/leak.json')
        server.close()
        server.close()
        reopened = WorldServer(root/'transport/world.sock', root)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.create_identity('Alice')['token'], a['token'])
