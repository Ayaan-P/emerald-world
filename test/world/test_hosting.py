"""Real hosted authority journeys, using disposable state and TLS only."""
import hashlib
import socket
import ssl
import subprocess
import tempfile
import unittest
from pathlib import Path


class HostingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='hosting-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cert, self.key = self.root/'cert.pem', self.root/'key.pem'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', str(self.key), '-out', str(self.cert), '-days', '1',
                        '-subj', '/CN=localhost'], check=True, capture_output=True)
        self.pin = hashlib.sha256(ssl.PEM_cert_to_DER_cert(self.cert.read_text())).hexdigest()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]

    def manager(self):
        from world.hosting import HostedWorldManager
        return HostedWorldManager(self.root/'m', cert=self.cert, key=self.key,
                                  advertise_host='localhost', listen_host='127.0.0.1',
                                  port_start=self.port, port_end=self.port, max_worlds=1)

    def test_single_use_guest_invite_collision_and_rejoin_after_restart(self):
        from world.hosting import HostingError
        from world.transport import ClientBroker
        from world.client import WorldClient
        manager = self.manager()
        try:
            access = manager.create_account()
            manager.enroll(access['token'], 'a'*64)
            result = manager.create_world('a'*64, 'Friends', 'Alice', 'friends')
            world_id = result['world']['id']
            invite = manager.invite('a'*64, world_id, 'invite-one')
            with self.assertRaises(HostingError) as collision:
                manager.join(invite['token'], 'Alice')
            self.assertEqual(collision.exception.status, 409)
            guest = manager.join(invite['token'], 'Bob')
            self.assertEqual(manager.join(invite['token'], 'Bob'), guest)
            with self.assertRaises(HostingError):
                manager.join(invite['token'], 'Carol')
            second = manager.invite('a'*64, world_id, 'invite-two')
            with self.assertRaises(HostingError):
                manager.join(second['token'], 'Bob')
            self.assertEqual(manager.invite('a'*64, world_id, 'invite-one'), invite)
            invitation = guest['invitation']
            owner_invitation = result['invitation']
            brokers = [ClientBroker(self.root/name/'world.sock', ('localhost', self.port),
                                    fingerprint=self.pin).start() for name in ('owner', 'guest')]
            clients = []
            try:
                clients = [WorldClient(b.socket_path, i['trainer'], i['token'])
                           for b, i in zip(brokers, (owner_invitation, invitation))]
                for n, client in enumerate(clients):
                    client.send_state(1, 0, 1, 10+n, 12, 2, 7, 1, 'a'*16, 'b'*16)
                for client, peer in zip(clients, ('Bob', 'Alice')):
                    for _ in range(12):
                        snapshot = client.snapshot()
                        if peer in snapshot['peers']:
                            break
                    self.assertIn(peer, snapshot['peers'])
                self.assertEqual(set(snapshot['peers']), {'Alice'})
            finally:
                for client in clients:
                    client.close()
                for broker in brokers:
                    broker.close()
        finally:
            manager.close()
        manager = self.manager()
        try:
            self.assertEqual(manager.join(invite['token'], 'Bob'), guest)
            broker = ClientBroker(self.root/'again/world.sock', ('localhost', self.port),
                                  fingerprint=self.pin).start()
            try:
                with WorldClient(broker.socket_path, 'Alice', owner_invitation['token']) as client:
                    client.send_state(2, 0, 1, 10, 12, 2, 7, 1, 'a'*16, 'b'*16)
                    self.assertIn('peers', client.snapshot())
                self.assertEqual(manager.running[world_id][0].db.execute(
                    'SELECT token FROM identities WHERE id=?', ('Alice',)).fetchone()[0],
                    owner_invitation['token'])
            finally:
                broker.close()
            self.assertFalse(list((self.root/'m').rglob('*.sav')))
        finally:
            manager.close()

    def test_https_client_enrollment_create_invite_join_and_private_files(self):
        from world.hosting import HostingService, HostingError
        from world.hosting_client import HostingClient, read_private, write_private
        manager = self.manager()
        service = HostingService(manager, ('127.0.0.1', 0)).start()
        try:
            endpoint = dict(host='localhost', port=service.address[1])
            access = dict(manager.create_account(), endpoint=endpoint, pin=self.pin)
            access_path = self.root/'access.json'
            write_private(access_path, access)
            owner = HostingClient.enroll(access_path, self.root/'profile.json')
            self.assertEqual((self.root/'profile.json').stat().st_mode & 0o777, 0o600)
            self.assertEqual((self.root/'m/hosting.sqlite3').stat().st_mode & 0o777, 0o600)
            self.assertEqual(HostingClient.enroll(access_path, self.root/'profile.json').list(), [])
            result = owner.create('Remote friends', 'Owner', request_id='remote')
            world_id = result['world']['id']
            native_path = self.root/'owner-native.json'
            owner.save_invitation(result, native_path)
            from world.transport import read_invitation
            self.assertEqual(read_invitation(native_path), result['invitation'])
            self.assertEqual(owner.list(), [result['world']])
            self.assertEqual(owner.resume(world_id), result)
            join_path = self.root/'friend.json'
            owner.invite(world_id, join_path, request_id='guest')
            friend = HostingClient.join(join_path, 'Friend', self.root/'friend-native.json')
            self.assertEqual(friend['invitation']['trainer'], 'Friend')
            self.assertEqual(HostingClient.join(join_path, 'Friend', self.root/'friend-native2.json'), friend)
            with self.assertRaises(HostingError):
                HostingClient.join(join_path, 'Owner', self.root/'stolen.json')
            bad = HostingClient(dict(kind='host-profile', version=1, endpoint=endpoint,
                                     pin='0'*64, token=owner.profile['token']))
            with self.assertRaisesRegex(ValueError, 'TLS trust failed'):
                bad.list()
            outsider_access = dict(manager.create_account(), endpoint=endpoint, pin=self.pin)
            write_private(self.root/'outsider.json', outsider_access)
            outsider = HostingClient.enroll(self.root/'outsider.json', self.root/'outsider-profile.json')
            self.assertEqual(outsider.list(), [])
            with self.assertRaises(HostingError):
                outsider.resume(world_id)
            with self.assertRaises(HostingError):
                owner.create('Another', 'Other', request_id='over-capacity')
            self.assertEqual(read_private(self.root/'profile.json')['kind'], 'host-profile')
        finally:
            service.close()
            manager.close()

    def test_management_rejects_unauthorized_and_oversized_requests(self):
        import http.client
        from world.hosting import HostingService, HostingError
        manager = self.manager()
        service = HostingService(manager, ('127.0.0.1', 0)).start()
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            def request(method, path, body=None, headers=None):
                conn = http.client.HTTPSConnection('localhost', service.address[1], context=context)
                try:
                    conn.request(method, path, body, headers or {})
                    response = conn.getresponse()
                    return response.status, response.read()
                finally:
                    conn.close()
            self.assertEqual(request('POST', '/v1/worlds', '{}'),
                             (403, b'{"error":"forbidden"}'))
            access = manager.create_account()
            manager.enroll(access['token'], 'a'*64)
            with self.assertRaises(HostingError):
                manager.enroll(access['token'], 'b'*64)
            headers = {'Authorization': 'Bearer '+'a'*64, 'Content-Type': 'application/json'}
            self.assertEqual(request('POST', '/v1/worlds', 'x'*4097, headers),
                             (400, b'{"error":"invalid_request"}'))
            self.assertEqual(request('POST', '/v1/worlds', '{"name":1,"name":2}', headers),
                             (400, b'{"error":"invalid_request"}'))
            self.assertEqual(manager.list_worlds('a'*64), [])
        finally:
            service.close()
            manager.close()

    def test_wrong_pin_sends_no_authorization_to_tls_peer(self):
        import threading
        from world.hosting_client import HostingClient
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.cert, self.key)
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        received = []
        def peer():
            raw, _ = listener.accept()
            try:
                with raw, context.wrap_socket(raw, server_side=True) as tls:
                    tls.settimeout(5)
                    received.append(tls.recv(4096))
            except (BrokenPipeError, ConnectionResetError, ssl.SSLEOFError):
                # Pin rejection can close before OpenSSL sends session tickets.
                received.append(b'')
        thread = threading.Thread(target=peer)
        thread.start()
        try:
            client = HostingClient(dict(kind='host-profile', version=1,
                endpoint=dict(host='localhost', port=listener.getsockname()[1]),
                pin='0'*64, token='a'*64))
            with self.assertRaisesRegex(ValueError, 'TLS trust failed'):
                client.list()
            thread.join(10)
            self.assertFalse(thread.is_alive())
            self.assertEqual(received, [b''])
        finally:
            listener.close()

    def test_cli_account_bootstrap_and_client_journey_never_print_secrets(self):
        import json
        import sys
        import time
        from world.hosting_client import read_private
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            management_port = sock.getsockname()[1]
        endpoint = 'localhost:' + str(management_port)
        common = ['--root', str(self.root/'cli'), '--cert', str(self.cert), '--key', str(self.key),
                  '--advertise-host', 'localhost', '--game-listen-host', '127.0.0.1',
                  '--port-start', str(self.port), '--port-end', str(self.port), '--max-worlds', '1',
                  '--management-advertise', endpoint]
        access = self.root/'cli-access.json'
        bootstrap = subprocess.run([sys.executable, '-m', 'world.hosting', 'create-account', *common,
                                   '--invitation-out', str(access)], capture_output=True, text=True)
        self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)
        self.assertEqual(bootstrap.stdout, '')
        service = subprocess.Popen([sys.executable, '-m', 'world.hosting', 'start', *common,
                                   '--listen', '127.0.0.1:'+str(management_port)],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            # Readiness is a real TLS handshake, never an arbitrary startup sleep.
            deadline = time.monotonic()+10
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            while True:
                try:
                    with socket.create_connection(('localhost', management_port), timeout=.2) as raw:
                        with context.wrap_socket(raw, server_hostname='localhost'):
                            break
                except OSError:
                    if service.poll() is not None or time.monotonic() > deadline:
                        self.fail('management service did not become ready')
                    time.sleep(.02)
            def cli(*args):
                result = subprocess.run([sys.executable, '-m', 'world.hosting_client', *args],
                                        capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                return result.stdout
            profile = self.root/'cli-profile.json'
            native = self.root/'cli-native.json'
            self.assertEqual(cli('enroll', '--access', str(access), '--profile', str(profile)), '')
            self.assertEqual(cli('invite-account', '--profile', str(profile), '--request-id', 'new-owner',
                                 '--invitation-out', str(self.root/'cli-other-access.json')), '')
            self.assertEqual(cli('enroll', '--access', str(self.root/'cli-other-access.json'),
                                 '--profile', str(self.root/'cli-other-profile.json')), '')
            output = cli('create', '--profile', str(profile), '--name', 'CLI world', '--trainer', 'Owner',
                         '--request-id', 'cli-world', '--invitation-out', str(native))
            world_id = json.loads(output)['id']
            self.assertEqual(len(json.loads(cli('list', '--profile', str(profile)))), 1)
            join = self.root/'cli-join.json'
            self.assertEqual(cli('invite', '--profile', str(profile), '--world', world_id,
                                 '--request-id', 'cli-guest', '--invitation-out', str(join)), '')
            self.assertEqual(cli('join', '--invitation', str(join), '--trainer', 'Guest',
                                 '--invitation-out', str(self.root/'cli-guest-native.json')), '')
            self.assertNotIn(read_private(profile)['token'], output)
            self.assertNotIn(read_private(native)['token'], output)
        finally:
            service.terminate()
            stdout, stderr = service.communicate(timeout=15)
            self.assertEqual(service.returncode, 0, stderr)
            self.assertEqual(stdout, '')
            self.assertEqual(stderr, '')

    def test_registered_world_missing_database_is_not_silently_reset(self):
        manager = self.manager()
        try:
            access = manager.create_account()
            manager.enroll(access['token'], 'a'*64)
            result = manager.create_world('a'*64, 'Keep history', 'Owner', 'persistent')
            world_id = result['world']['id']
        finally:
            manager.close()
        database = self.root/'m/worlds'/world_id/'world.sqlite3'
        database.rename(database.with_suffix('.backup'))
        with self.assertRaisesRegex(RuntimeError, 'registered world database missing'):
            self.manager()
        self.assertFalse(database.exists())

    def test_bootstrap_owner_remotely_invites_independent_host_accounts(self):
        from world.hosting import HostingService, HostingError
        from world.hosting_client import HostingClient, write_private
        manager = self.manager()
        service = HostingService(manager, ('127.0.0.1', 0)).start()
        try:
            endpoint = dict(host='localhost', port=service.address[1])
            write_private(self.root/'bootstrap.json', dict(manager.create_account(), endpoint=endpoint, pin=self.pin))
            bootstrap = HostingClient.enroll(self.root/'bootstrap.json', self.root/'bootstrap-profile.json')
            account_invite = self.root/'new-account.json'
            access = bootstrap.invite_account(account_invite, request_id='new-owner')
            self.assertEqual(bootstrap.invite_account(account_invite, request_id='new-owner'), access)
            friend = HostingClient.enroll(account_invite, self.root/'friend-profile.json')
            self.assertNotEqual(friend.profile['token'], bootstrap.profile['token'])
            created = friend.create('Friend owns this', 'Friend', request_id='friend-owned')
            self.assertEqual(friend.list(), [created['world']])
            self.assertEqual(bootstrap.list(), [])
            with self.assertRaises(HostingError):
                bootstrap.resume(created['world']['id'])
            with self.assertRaises(HostingError):
                HostingClient.enroll(account_invite, self.root/'other-profile.json')
            with self.assertRaises(HostingError):
                friend.invite_account(self.root/'not-authorized.json', request_id='denied')
        finally:
            service.close()
            manager.close()

    def test_two_remote_owners_have_isolated_worlds_and_stable_allocated_ports(self):
        from world.hosting import HostedWorldManager, HostingError
        from world.transport import ClientBroker
        from world.client import WorldClient
        # Reserve an explicit adjacent disposable two-port pool for this test.
        for _ in range(100):
            first, second = socket.socket(), socket.socket()
            try:
                first.bind(('127.0.0.1', 0))
                start = first.getsockname()[1]
                if start == 65535:
                    continue
                second.bind(('127.0.0.1', start+1))
                break
            except OSError:
                continue
            finally:
                first.close()
                second.close()
        else:
            self.fail('no disposable adjacent port pool')
        def manager_factory():
            return HostedWorldManager(self.root/'multi', cert=self.cert, key=self.key,
                advertise_host='localhost', listen_host='127.0.0.1',
                port_start=start, port_end=start+1, max_worlds=2)
        manager = manager_factory()
        brokers, clients = [], []
        try:
            results = []
            for n, account_token in enumerate(('a'*64, 'b'*64)):
                access = manager.create_account()
                manager.enroll(access['token'], account_token)
                result = manager.create_world(account_token, 'World '+str(n), 'SameTrainer', 'same-request')
                results.append(result)
                invitation = result['invitation']
                broker = ClientBroker(self.root/('multi'+str(n))/'world.sock',
                    ('localhost', invitation['endpoint']['port']), fingerprint=self.pin).start()
                brokers.append(broker)
                clients.append(WorldClient(broker.socket_path, invitation['trainer'], invitation['token']))
            self.assertNotEqual(results[0]['world']['id'], results[1]['world']['id'])
            self.assertNotEqual(results[0]['invitation']['token'], results[1]['invitation']['token'])
            self.assertEqual({r['invitation']['endpoint']['port'] for r in results}, {start, start+1})
            for client in clients:
                self.assertEqual(client.snapshot()['peers'], {})
            self.assertEqual(manager.list_worlds('a'*64), [results[0]['world']])
            self.assertEqual(manager.list_worlds('b'*64), [results[1]['world']])
            with self.assertRaises(HostingError):
                manager.create_world('a'*64, 'Third', 'Third', 'capacity')
        finally:
            for client in clients:
                client.close()
            for broker in brokers:
                broker.close()
            manager.close()
        manager = manager_factory()
        try:
            for token, result in zip(('a'*64, 'b'*64), results):
                self.assertEqual(manager.resume(token, result['world']['id']), result)
        finally:
            manager.close()

    def test_owner_creates_persistent_world_with_native_invitation(self):
        from world.transport import ClientBroker, validate_invitation
        from world.client import WorldClient
        manager = self.manager()
        try:
            access = manager.create_account()
            manager.enroll(access['token'], 'a'*64)
            result = manager.create_world('a'*64, 'My world', 'Alice', 'request-1')
            invitation = validate_invitation(result['invitation'])
            self.assertEqual(invitation['trainer'], 'Alice')
            self.assertEqual(invitation['endpoint']['port'], self.port)
            self.assertEqual(invitation['pin'], self.pin)
            broker = ClientBroker(self.root/'c/world.sock', ('localhost', self.port),
                                  fingerprint=self.pin).start()
            try:
                with WorldClient(broker.socket_path, 'Alice', invitation['token']) as client:
                    self.assertIn('peers', client.snapshot())
            finally:
                broker.close()
            self.assertEqual(manager.create_world('a'*64, 'My world', 'Alice', 'request-1'), result)
            world_id = result['world']['id']
        finally:
            manager.close()
        manager = self.manager()
        try:
            self.assertEqual(manager.list_worlds('a'*64)[0]['id'], world_id)
            self.assertEqual(manager.resume('a'*64, world_id)['invitation'], invitation)
        finally:
            manager.close()
