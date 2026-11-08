"""Windows guest contracts, using local sockets and disposable profiles only."""
import importlib.util
import socket
import time
import unittest


def wait_for(predicate, timeout=2):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError('condition did not become true')


class GatewayTests(unittest.TestCase):
    def test_native_config_contract_and_safe_module_import(self):
        from pathlib import Path
        import subprocess
        import sys
        source = (Path(__file__).resolve().parents[2]/'src/platform/world_bridge.c').read_text()
        for key in ('loopback_port', 'loopback_token', 'trainer', 'token', 'telemetry'):
            self.assertIn('"' + key + '"', source)
        self.assertIn('"EWLOCAL1 %s\\nHELLO 1 %s %s %s%s%s%s\\n"', source)
        self.assertIn('SOCIALTRAVELRALLY', source)
        self.assertIn('htonl(INADDR_LOOPBACK)', source)
        code = ("import sys, subprocess; sys.modules.pop('fcntl', None); import world.windows_client; "
                "assert not any(m in sys.modules for m in "
                "('world.launcher','world.session','world.server','fcntl'))")
        subprocess.run([sys.executable, '-c', code], check=True,
                       cwd=Path(__file__).resolve().parents[2], capture_output=True)

    def test_auth_completion_after_absolute_deadline_cannot_dial(self):
        from unittest.mock import Mock, patch
        from world.windows_client import LoopbackGateway
        gateway = LoopbackGateway(('127.0.0.1', 1), fingerprint='a'*64, local_token='b'*64)
        local = Mock()
        local.recv.return_value = b'EWLOCAL1 ' + b'b'*64 + b'\n'
        with patch('world.windows_client.time.monotonic', side_effect=[0, .1, 6]), \
             patch('world.windows_client.ClientBroker._pair') as dial:
            with self.assertRaises(TimeoutError):
                gateway._pair(local, [])
        dial.assert_not_called()

    def test_partial_wrong_key_does_not_expose_prefix_oracle(self):
        from world.windows_client import LoopbackGateway
        gateway = LoopbackGateway(('127.0.0.1', 1), fingerprint='a'*64,
                                  local_token='b'*64, auth_timeout=.5).start()
        self.addCleanup(gateway.close)
        with socket.create_connection(gateway.address, timeout=1) as native:
            native.sendall(b'EWLOCAL1 c')
            native.settimeout(.05)
            with self.assertRaises(socket.timeout):
                native.recv(1)

    def test_absolute_auth_deadline_and_worker_cap(self):
        from world.windows_client import LoopbackGateway
        gateway = LoopbackGateway(('127.0.0.1', 1), fingerprint='a'*64,
                                  local_token='b'*64, max_clients=2, auth_timeout=.25).start()
        self.addCleanup(gateway.close)
        clients = [socket.create_connection(gateway.address, timeout=1) for _ in range(2)]
        for client in clients:
            self.addCleanup(client.close)
        wait_for(lambda: gateway.active_clients == 2)
        with socket.create_connection(gateway.address, timeout=1) as excess:
            self.assertEqual(excess.recv(1), b'')
        start = time.monotonic()
        for byte in b'EWL':
            try:
                clients[0].sendall(bytes([byte]))
            except OSError:
                break
            time.sleep(.09)
        wait_for(lambda: gateway.active_clients == 0)
        self.assertLess(time.monotonic() - start, .7)
        with self.assertRaises(ValueError):
            LoopbackGateway(('localhost', 1), fingerprint='a'*64, local_token='b'*64, max_clients=9)
        with self.assertRaises(ValueError):
            LoopbackGateway(('localhost', 1), fingerprint='a'*64, local_token='b'*64, auth_timeout=6)

    def test_close_interrupts_partial_header_and_is_idempotent(self):
        from world.windows_client import LoopbackGateway
        gateway = LoopbackGateway(('127.0.0.1', 1), fingerprint='a'*64, local_token='b'*64).start()
        self.addCleanup(gateway.close)
        with socket.create_connection(gateway.address, timeout=1) as native:
            native.sendall(b'EWLOCAL1 ')
            wait_for(lambda: gateway.active_clients == 1)
            start = time.monotonic()
            gateway.close()
            gateway.close()
            self.assertLess(time.monotonic() - start, 1)
            self.assertEqual(gateway.active_clients, 0)
            self.assertEqual(native.recv(1), b'')
        with self.assertRaises(RuntimeError):
            gateway.start()

    def test_module_exists(self):
        self.assertIsNotNone(importlib.util.find_spec('world.windows_client'),
                             'Windows client module is missing')

    def test_local_header_bounds_reject_extra_short_and_embedded_newline(self):
        from world.windows_client import LoopbackGateway
        with socket.socket() as host:
            host.bind(('127.0.0.1', 0))
            host.listen()
            host.settimeout(.1)
            gateway = LoopbackGateway(host.getsockname(), fingerprint='a'*64,
                                      local_token='b'*64, auth_timeout=.15).start()
            self.addCleanup(gateway.close)
            for header in (b'EWLOCAL1 '+b'b'*65+b'\n', b'X'*10000,
                           b'EWLOCAL1 '+b'b'*63+b'\n', b'EWLOCAL1 \n'+b'b'*64):
                with self.subTest(header_size=len(header)):
                    with socket.create_connection(gateway.address, timeout=1) as native:
                        native.sendall(header)
                        try:
                            self.assertEqual(native.recv(1), b'')
                        except ConnectionResetError:
                            pass
                    wait_for(lambda: gateway.active_clients == 0)
            with self.assertRaises(socket.timeout):
                host.accept()

    def test_wrong_local_key_never_dials_host(self):
        from world.windows_client import LoopbackGateway
        with socket.socket() as host:
            host.bind(('127.0.0.1', 0))
            host.listen()
            host.settimeout(.2)
            gateway = LoopbackGateway(host.getsockname(), fingerprint='a'*64,
                                      local_token='b'*64).start()
            self.addCleanup(gateway.close)
            self.assertEqual(gateway.address[0], '127.0.0.1')
            with socket.create_connection(gateway.address, timeout=1) as native:
                native.sendall(b'EWLOCAL1 ' + b'c'*64 + b'\nHELLO secret\n')
                try:
                    self.assertEqual(native.recv(1), b'')
                except ConnectionResetError:
                    pass  # Rejecting unread attacker bytes may reset TCP.
            with self.assertRaises(socket.timeout):
                host.accept()
            wait_for(lambda: gateway.active_clients == 0)
            gateway.close()
            self.assertEqual(gateway.active_clients, 0)


class TLSTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import hashlib
        import shutil
        import ssl
        import subprocess
        import tempfile
        from pathlib import Path
        openssl = shutil.which('openssl')
        if not openssl:
            raise unittest.SkipTest('local TLS fixture needs an existing openssl executable')
        cls.tmp = tempfile.TemporaryDirectory(prefix='public tls fixture ')
        cls.root = Path(cls.tmp.name)
        cls.cert, cls.key = cls.root/'cert.pem', cls.root/'key.pem'
        subprocess.run([openssl, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', str(cls.key), '-out', str(cls.cert), '-days', '1',
                        '-subj', '/CN=localhost'], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.pin = hashlib.sha256(ssl.PEM_cert_to_DER_cert(cls.cert.read_text())).hexdigest()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def peer(self, handler, count=1):
        import ssl
        import threading
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(8)
        listener.settimeout(3)
        self.addCleanup(listener.close)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        # TLS 1.2 avoids post-handshake TLS 1.3 ticket writes racing pin rejection.
        context.maximum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(str(self.cert), str(self.key))
        errors = []
        def run():
            try:
                for _ in range(count):
                    raw, _ = listener.accept()
                    with raw:
                        raw.settimeout(2)
                        with context.wrap_socket(raw, server_side=True) as tls:
                            handler(tls)
            except BaseException as error:
                errors.append(error)
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        self.addCleanup(lambda: thread.join(3))
        return listener.getsockname(), thread, errors

    def test_wrong_pin_sends_no_preface_or_game_bytes(self):
        from world.windows_client import LoopbackGateway
        observed = []
        address, thread, errors = self.peer(lambda tls: observed.append(tls.recv(4096)))
        gateway = LoopbackGateway(address, fingerprint='0'*64, local_token='b'*64).start()
        self.addCleanup(gateway.close)
        with socket.create_connection(gateway.address, timeout=2) as native:
            native.sendall(b'EWLOCAL1 ' + b'b'*64 + b'\nHELLO 1 Alice secret\n')
            try:
                self.assertEqual(native.recv(1), b'')
            except ConnectionResetError:
                pass
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(observed, [b''])

    def test_partial_auth_framed_stream_and_reconnect(self):
        import struct
        from world.transport import _magic
        from world.windows_client import LoopbackGateway
        for _ in range(2):
            received = []
            def handle(tls):
                _magic(tls)
                def exact(size):
                    result = b''
                    while len(result) < size:
                        part = tls.recv(size - len(result))
                        if not part:
                            raise AssertionError('unexpected EOF')
                        result += part
                    return result
                size = struct.unpack('!I', exact(4))[0]
                received.append(exact(size))
                reply = struct.pack('!I', 7) + b'WELCOME'
                for byte in reply:
                    tls.sendall(bytes([byte]))
                tls.sendall(b'\0\0\0\0')
                self.assertEqual(exact(4), b'\0\0\0\0')
            address, thread, errors = self.peer(handle)
            gateway = LoopbackGateway(address, fingerprint=self.pin, local_token='b'*64).start()
            self.addCleanup(gateway.close)
            with socket.create_connection(gateway.address, timeout=2) as native:
                native.sendall(b'EWLOCAL')
                time.sleep(.01)
                native.sendall(b'1 ' + b'b'*64 + b'\nHELLO')
                native.shutdown(socket.SHUT_WR)
                result = b''
                while True:
                    part = native.recv(4096)
                    if not part:
                        break
                    result += part
                self.assertEqual(result, b'WELCOME')
            thread.join(3)
            self.assertEqual(errors, [])
            self.assertEqual(received, [b'HELLO'])
            gateway.close()
            self.assertEqual(gateway.active_clients, 0)

    def test_gateway_native_hello_reaches_existing_host_broker(self):
        import os
        import tempfile
        from pathlib import Path
        if os.name != 'posix':
            self.skipTest('Linux HostBroker integration uses its existing Unix world service')
        from world.server import WorldServer
        from world.transport import HostBroker
        from world.windows_client import LoopbackGateway
        with tempfile.TemporaryDirectory(prefix='windows world tls ') as temporary:
            root = Path(temporary)
            server = WorldServer(root/'transport/world.sock', root)
            self.addCleanup(server.close)
            identity = server.create_identity('Alice')
            server.start()
            host = HostBroker(server.socket_path, self.cert, self.key).start()
            self.addCleanup(host.close)
            gateway = LoopbackGateway(host.address, fingerprint=self.pin, local_token='b'*64).start()
            self.addCleanup(gateway.close)
            with socket.create_connection(gateway.address, timeout=2) as native:
                native.sendall(('EWLOCAL1 ' + 'b'*64 + '\nHELLO 1 Alice '
                                + identity['token'] + ' SOCIAL\n').encode('ascii'))
                with native.makefile('rb') as stream:
                    self.assertTrue(stream.readline(256).startswith(b'WELCOME 1 Alice '))
            gateway.close()
            host.close()
            server.close()

    def test_native_reconnect_uses_same_live_gateway(self):
        from world.transport import _magic
        from world.windows_client import LoopbackGateway
        seen = []
        def handle(tls):
            _magic(tls)
            raw = b''
            while len(raw) < 9:
                part = tls.recv(9-len(raw))
                if not part:
                    raise AssertionError('truncated fixture request')
                raw += part
            seen.append(raw)
            tls.sendall(b'\0\0\0\3ACK\0\0\0\0')
            self.assertEqual(tls.recv(4), b'\0\0\0\0')
        address, thread, errors = self.peer(handle, count=2)
        gateway = LoopbackGateway(address, fingerprint=self.pin, local_token='b'*64).start()
        self.addCleanup(gateway.close)
        for _ in range(2):
            with socket.create_connection(gateway.address, timeout=2) as native:
                native.sendall(b'EWLOCAL1 ' + b'b'*64 + b'\nHELLO')
                native.shutdown(socket.SHUT_WR)
                self.assertEqual(native.recv(3), b'ACK')
                self.assertEqual(native.recv(1), b'')
            wait_for(lambda: gateway.active_clients == 0)
        thread.join(3)
        self.assertEqual(errors, [])
        self.assertEqual(seen, [b'\0\0\0\5HELLO']*2)

    def test_oversize_frame_stops_worker(self):
        import struct
        from world.transport import _magic, CHUNK
        from world.windows_client import LoopbackGateway
        def malformed(tls):
            _magic(tls)
            tls.sendall(struct.pack('!I', CHUNK + 1))
            tls.recv(1)
        address, thread, errors = self.peer(malformed)
        gateway = LoopbackGateway(address, fingerprint=self.pin, local_token='b'*64).start()
        self.addCleanup(gateway.close)
        with socket.create_connection(gateway.address, timeout=2) as native:
            native.sendall(b'EWLOCAL1 ' + b'b'*64 + b'\n')
            self.assertEqual(native.recv(1), b'')
        thread.join(3)
        self.assertEqual(errors, [])
        wait_for(lambda: gateway.active_clients == 0)


class ProfileTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        import json
        self.tmp = tempfile.TemporaryDirectory(prefix='windows guest ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.invitation = self.root / 'invite.json'
        self.invitation.write_text(json.dumps({'trainer': 'Alice', 'token': 'd'*64}))
        self.exe = self.root / 'game/pokeemerald64.exe'
        self.exe.parent.mkdir()
        self.exe.write_bytes(b'fixture, never executed')

    def session(self, **kwargs):
        from world.windows_client import WindowsGuestSession
        session = WindowsGuestSession('127.0.0.1', 8765, 'a'*64, self.invitation,
                                      data_root=self.root/'Local App Data', binary=self.exe,
                                      **kwargs)
        self.addCleanup(session.close)
        return session

    def test_trusted_root_alias_is_canonicalized_before_profile_checks(self):
        from pathlib import Path
        from unittest.mock import patch
        from world.windows_client import WindowsGuestSession
        canonical = (self.root/'Local App Data').resolve()
        alias = self.root/'RUNNER~1'
        original_resolve = Path.resolve

        def resolve(path, *args, **kwargs):
            try:
                suffix = path.relative_to(alias)
            except ValueError:
                return original_resolve(path, *args, **kwargs)
            return original_resolve(canonical/suffix, *args, **kwargs)

        with patch.object(Path, 'resolve', resolve):
            first = WindowsGuestSession('127.0.0.1', 8765, 'a'*64, self.invitation,
                                        data_root=alias, binary=self.exe)
            self.addCleanup(first.close)
            first.prepare()
            self.assertEqual(first.paths['profile'].parent.parent, canonical)
            second = self.session()
            with self.assertRaisesRegex(RuntimeError, 'profile is already in use'):
                second.prepare()
        self.assertNotIn('d'*64, str(first.paths))

    def test_profile_files_and_lock_reject_existing_hardlinks(self):
        import os
        for name in ('game.sav', 'pokeemerald.ini', 'world.conf', 'telemetry.json', 'profile.lock'):
            with self.subTest(name=name):
                session = self.session()
                profile = session.paths['profile']
                profile.mkdir(parents=True, exist_ok=True)
                outside = self.root/'private-file'
                outside.write_bytes(b'private content')
                target = profile/name
                target.unlink(missing_ok=True)
                os.link(outside, target)
                try:
                    with self.assertRaisesRegex((ValueError, RuntimeError), 'unsafe profile'):
                        session.prepare()
                    self.assertEqual(outside.read_bytes(), b'private content')
                    self.assertIsNone(session.gateway)
                    self.assertIsNone(session._profile_lock)
                finally:
                    session.close()
                    target.unlink()
                    outside.unlink()

    def test_reparse_points_are_rejected_even_when_not_symlinks(self):
        from pathlib import Path
        import stat
        from types import SimpleNamespace
        from unittest.mock import patch
        original_lstat = Path.lstat
        for name in ('namespace', 'profile', 'game.sav', 'profile.lock'):
            with self.subTest(name=name):
                session = self.session()
                profile = session.paths['profile']
                profile.mkdir(parents=True, exist_ok=True)
                target = profile.parent if name == 'namespace' else (
                    profile if name == 'profile' else profile/name)
                if name in ('game.sav', 'profile.lock'):
                    target.write_bytes(b'private content')

                def lstat(path, *args, **kwargs):
                    info = original_lstat(path, *args, **kwargs)
                    if path == target:
                        return SimpleNamespace(st_mode=info.st_mode, st_nlink=info.st_nlink,
                                               st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)
                    return info

                with patch.object(Path, 'lstat', lstat):
                    with self.assertRaisesRegex((ValueError, RuntimeError), 'unsafe profile'):
                        session.prepare()
                self.assertIsNone(session.gateway)
                self.assertIsNone(session._profile_lock)
                if name == 'game.sav':
                    target.unlink()

    def test_windows_junction_beneath_trusted_root_is_rejected(self):
        import os
        import subprocess
        if os.name != 'nt':
            self.skipTest('real junction fixture requires Windows')
        session = self.session()
        namespace = session.paths['profile'].parent
        namespace.parent.mkdir(parents=True)
        outside = self.root/'outside-junction'
        outside.mkdir()
        subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(namespace), str(outside)],
                       check=True, capture_output=True)
        try:
            with self.assertRaisesRegex(ValueError, 'unsafe profile directory'):
                session.prepare()
            self.assertEqual(list(outside.iterdir()), [])
        finally:
            os.rmdir(namespace)

    def test_untrusted_namespace_profile_and_files_reject_symlinks(self):
        for name in ('namespace', 'profile', 'game.sav', 'profile.lock'):
            with self.subTest(name=name):
                session = self.session()
                profile = session.paths['profile']
                outside = self.root/('outside-' + name)
                directory = name in ('namespace', 'profile')
                if directory:
                    outside.mkdir()
                else:
                    outside.write_bytes(b'private content')
                target = profile.parent if name == 'namespace' else (
                    profile if name == 'profile' else profile/name)
                target.parent.mkdir(parents=True, exist_ok=True)
                if name == 'profile.lock':
                    target.unlink(missing_ok=True)
                try:
                    target.symlink_to(outside, target_is_directory=directory)
                except OSError as error:
                    self.skipTest('symlinks unavailable: ' + str(error))
                try:
                    with self.assertRaisesRegex((ValueError, RuntimeError), 'unsafe profile'):
                        session.prepare()
                    self.assertIsNone(session.gateway)
                finally:
                    target.unlink()

    def test_profile_created_before_explicit_game_args_and_no_host_save_copy(self):
        session = self.session()
        session.prepare()
        paths = session.paths
        self.assertTrue(paths['profile'].is_dir())
        import hashlib
        import json
        namespace = hashlib.sha256(json.dumps(['127.0.0.1', 8765, 'a'*64],
                                              separators=(',', ':')).encode()).hexdigest()
        trainer_dir = hashlib.sha256(b'Alice').hexdigest()
        self.assertEqual(paths['profile'].parts[-2:], (namespace, trainer_dir))
        self.assertFalse(paths['save'].exists())
        command = session.game_args()
        self.assertEqual(command, [str(self.exe), '--save', str(paths['save']),
                                  '--config', str(paths['settings']),
                                  '--world-config', str(paths['config'])])
        config = paths['config'].read_text()
        self.assertIn('token ' + 'd'*64 + '\n', config)
        self.assertIn('loopback_port ', config)
        self.assertIn('loopback_token ' + session.gateway.local_token, config)
        self.assertIn('telemetry ' + paths['telemetry'].as_posix(), config)
        self.assertNotIn('d'*64, repr(session))
        paths['save'].write_bytes(b'own native save')
        paths['settings'].write_bytes(b'own keys')
        previous_capability = session.gateway.local_token
        session.close()
        session.prepare()
        self.assertNotEqual(session.gateway.local_token, previous_capability)
        self.assertEqual(paths['save'].read_bytes(), b'own native save')
        self.assertEqual(paths['settings'].read_bytes(), b'own keys')

    def test_windows_namespace_exact_case_endpoint_and_reserved_ids(self):
        import json
        from world.windows_client import WindowsGuestSession
        paths = []
        for trainer in ('ALICE', 'alice', 'CON', 'NUL', 'COM1'):
            self.invitation.write_text(json.dumps({'trainer': trainer, 'token': 'd'*64}))
            session = self.session()
            session.prepare()
            paths.append(str(session.paths['profile']).casefold())
            self.assertEqual(len(session.paths['profile'].name), 64)
            self.assertNotIn(session.paths['profile'].name.upper(), ('CON', 'NUL', 'COM1'))
            self.assertNotIn('d'*64, str(session.paths['profile']))
        self.assertEqual(len(set(paths)), 5)
        variants = []
        for host, port, pin in (('host', 8765, 'a'*64), ('HOST', 8765, 'a'*64),
                                ('host', 8766, 'a'*64), ('host', 8765, 'b'*64)):
            session = WindowsGuestSession(host, port, pin, self.invitation,
                                          data_root=self.root/'Local App Data', binary=self.exe)
            self.addCleanup(session.close)
            variants.append(str(session.paths['profile']).casefold())
        self.assertEqual(len(set(variants)), 4)

    def test_real_lock_rejects_distinct_same_profile_then_releases(self):
        first, second = self.session(), self.session()
        first.prepare()
        with self.assertRaisesRegex(RuntimeError, 'profile is already in use'):
            second.prepare()
        first.close()
        second.prepare()
        second.close()
        self.assertTrue(second.paths['profile'].is_dir())

    def test_start_launches_normal_child_and_close_releases_lock(self):
        from unittest.mock import Mock, patch
        from world.windows_client import WindowsGuestSession
        session = self.session()
        child = Mock()
        child.poll.return_value = None
        with patch('world.windows_client.subprocess.Popen', return_value=child) as launch, \
             patch('world.windows_client._request_child_close') as request:
            self.assertIs(session.start(), session)
            command = launch.call_args.args[0]
            self.assertNotIn('--player-control', command)
            self.assertNotIn('--headless', command)
            self.assertNotIn('d'*64, ' '.join(command))
            self.assertTrue(session.paths['config'].is_file())
            self.assertEqual(launch.call_args.kwargs['cwd'], str(session.paths['profile']))
            self.assertFalse(launch.call_args.kwargs['shell'])
            with self.assertRaises(RuntimeError):
                session.start()
            session.close()
        request.assert_called_once_with(child)
        child.wait.assert_called()
        session.prepare()

    def test_launch_failure_is_secret_free_and_releases_lock(self):
        from unittest.mock import patch
        session = self.session()
        with patch('world.windows_client.subprocess.Popen', side_effect=OSError('d'*64)):
            with self.assertRaisesRegex(RuntimeError, '^could not launch game$'):
                session.start()
        second = self.session()
        second.prepare()

    def test_status_retries_atomic_read_errors_and_never_infers_online_from_child(self):
        from unittest.mock import Mock
        import json
        session = self.session()
        session.prepare()
        self.assertEqual(session.status()['state'], 'stopped')
        session.child = Mock()
        session.child.poll.return_value = None
        session._started_ns = time.time_ns()
        self.assertNotEqual(session.status()['state'], 'online')
        telemetry = session.paths['telemetry']
        telemetry.write_text('{')
        self.assertEqual(session.status()['state'], 'waiting')
        telemetry.write_text(json.dumps({'trainer': 'Alice', 'connected': True, 'frame': 120}))
        self.assertEqual(session.status()['state'], 'online')
        telemetry.write_text(json.dumps({'trainer': 'Bob', 'connected': True, 'frame': 120}))
        self.assertEqual(session.status()['state'], 'waiting')
        telemetry.write_text(json.dumps({'trainer': 'Alice', 'connected': 'true', 'frame': 120}))
        self.assertNotEqual(session.status()['state'], 'online')
        telemetry.write_text(json.dumps({'trainer': 'Alice', 'connected': False, 'frame': 121}))
        self.assertEqual(session.status()['state'], 'connecting')
        import os
        os.utime(telemetry, (time.time()-30, time.time()-30))
        self.assertEqual(session.status()['state'], 'waiting')
        telemetry.unlink()
        self.assertEqual(session.status()['state'], 'waiting')
        session.child.poll.return_value = 0
        self.assertEqual(session.status()['state'], 'stopped')

    def test_packaged_and_development_binary_lookup(self):
        from unittest.mock import patch
        from world.windows_client import locate_game
        with patch('world.windows_client.sys.frozen', True, create=True), \
             patch('world.windows_client.sys.executable', str(self.root/'EmeraldWorld.exe')):
            self.assertEqual(locate_game(), self.exe)
        self.exe.unlink()
        with patch('world.windows_client.sys.frozen', True, create=True), \
             patch('world.windows_client.sys.executable', str(self.root/'EmeraldWorld.exe')):
            with self.assertRaisesRegex(ValueError, '^packaged game is missing$'):
                locate_game()
        devexe = self.root/'build/windows/pokeemerald64.exe'
        devexe.parent.mkdir(parents=True)
        devexe.write_bytes(b'fixture')
        self.assertEqual(locate_game(root=self.root), devexe)

    def test_close_keeps_profile_locked_until_child_is_confirmed_dead(self):
        from unittest.mock import Mock, patch
        import subprocess
        session, other = self.session(), self.session()
        session.prepare()
        child = Mock()
        child.poll.return_value = None
        child.wait.side_effect = subprocess.TimeoutExpired('private child', 3)
        session.child = child
        with patch('world.windows_client._request_child_close') as request:
            with self.assertRaises(subprocess.TimeoutExpired):
                session.close()
            request.assert_called_once_with(child)
        with self.assertRaises(RuntimeError):
            other.prepare()
        child.poll.return_value = 0
        child.wait.side_effect = None
        session.close()
        other.prepare()

    def test_controller_disconnect_timeout_keeps_owned_profile_until_explicit_retry(self):
        from unittest.mock import Mock, patch
        import subprocess
        from world.windows_client import GuestController
        session, other = self.session(), self.session()
        session.prepare()
        child = Mock()
        child.poll.return_value = None
        child.wait.side_effect = subprocess.TimeoutExpired('private capability', 3)
        session.child = child
        with patch('world.windows_client.WindowsGuestSession', return_value=session), \
             patch.object(session, 'start', return_value=session), \
             patch('world.windows_client._request_child_close'), \
             patch('threading.excepthook'):
            controller = GuestController()
            try:
                self.assertTrue(controller.submit('join', ()))
                wait_for(lambda: not controller.snapshot()['busy'])
                self.assertTrue(controller.submit('disconnect'))
                wait_for(lambda: not controller.snapshot()['busy'])
                state = controller.snapshot()
                self.assertEqual(state['state'], 'error')
                self.assertIn('Disconnect', str(state['message']))
                self.assertNotIn('private capability', repr(state))
                self.assertTrue(controller._thread.is_alive())
                self.assertFalse(controller.closed.is_set())
                self.assertIs(controller._session, session)
                with self.assertRaisesRegex(RuntimeError, 'profile is already in use'):
                    other.prepare()
                time.sleep(.3)
                self.assertEqual(controller.snapshot()['state'], 'error')
                self.assertIs(controller._session, session)
                child.poll.return_value = 0
                child.wait.side_effect = None
                self.assertTrue(controller.submit('disconnect'))
                wait_for(lambda: not controller.snapshot()['busy'])
                self.assertEqual(controller.snapshot()['state'], 'stopped')
                self.assertIsNone(controller._session)
                other.prepare()
            finally:
                child.poll.return_value = 0
                child.wait.side_effect = None
                controller.shutdown()
                self.assertTrue(controller.closed.wait(2))
                controller._thread.join(2)

    def test_windows_requests_wm_close_without_stealing_focus(self):
        import types
        from unittest.mock import Mock, patch
        from world.windows_client import _request_child_close
        child = Mock(pid=123)
        user32 = Mock()
        user32.EnumWindows.side_effect = lambda callback, arg: callback(99, arg)
        def owner(hwnd, pointer):
            pointer.value = 123
        user32.GetWindowThreadProcessId.side_effect = owner
        ctypes = types.SimpleNamespace(WinDLL=Mock(return_value=user32),
                                       WINFUNCTYPE=lambda *args: lambda function: function,
                                       byref=lambda value: value, POINTER=lambda value: value,
                                       wintypes=Mock())
        ctypes.wintypes.DWORD.return_value = types.SimpleNamespace(value=0)
        with patch.dict('sys.modules', {'ctypes': ctypes}), \
             patch('world.windows_client.os.name', 'nt'):
            _request_child_close(child)
        user32.PostMessageW.assert_called_once_with(99, 0x0010, 0, 0)
        child.terminate.assert_not_called()

    def test_strict_invitation_and_pin_validation_never_echo_secrets(self):
        from world.windows_client import WindowsGuestSession
        import json
        for identity in ({'trainer': '../Alice', 'token': 'd'*64},
                         {'trainer': 'A'*25, 'token': 'd'*64},
                         {'trainer': 'Alice', 'token': 'd'*63},
                         {'trainer': 'Alice', 'token': 'd'*64, 'extra': 1}):
            self.invitation.write_text(json.dumps(identity))
            with self.assertRaisesRegex(ValueError, '^invalid invitation$'):
                self.session()
        self.invitation.write_text('{"trainer":"Alice","trainer":"Bob","token":"' + 'd'*64 + '"}')
        with self.assertRaisesRegex(ValueError, '^invalid invitation$'):
            self.session()
        with self.assertRaises(ValueError) as error:
            WindowsGuestSession('127.0.0.1', 1, 'a'*63 + '\n', self.invitation)
        self.assertNotIn('d'*64, str(error.exception))


class EntryTests(unittest.TestCase):
    def test_self_test_exercises_tk_without_launch_or_profile(self):
        import contextlib
        import io
        import json
        import types
        from pathlib import Path
        from unittest.mock import Mock, patch
        from world.windows_client import main
        tk = Mock()
        tkinter = types.SimpleNamespace(Tk=Mock(return_value=tk))
        output = io.StringIO()
        with patch.dict('sys.modules', {'tkinter': tkinter}), \
             patch('world.windows_client.locate_game', return_value=Path('game/pokeemerald64.exe')), \
             patch('world.windows_client.subprocess.Popen') as launch, \
             patch('world.windows_client.WindowsGuestSession') as session, \
             contextlib.redirect_stdout(output):
            self.assertEqual(main(['--self-test']), 0)
        self.assertTrue(json.loads(output.getvalue())['ok'])
        tkinter.Tk.assert_called_once()
        tk.withdraw.assert_called_once()
        tk.update.assert_called_once()
        tk.destroy.assert_called_once()
        launch.assert_not_called()
        session.assert_not_called()

    def test_self_test_failure_is_machine_readable_and_secret_free(self):
        import contextlib
        import io
        import json
        from unittest.mock import patch
        from world.windows_client import main
        output = io.StringIO()
        with patch('world.windows_client.locate_game', side_effect=ValueError('secret')), \
             contextlib.redirect_stdout(output):
            self.assertEqual(main(['--self-test']), 1)
        self.assertFalse(json.loads(output.getvalue())['ok'])
        self.assertNotIn('secret', output.getvalue())

    def test_self_test_cleanup_failure_still_returns_secret_free_json(self):
        import contextlib
        import io
        import json
        import types
        from pathlib import Path
        from unittest.mock import Mock, patch
        from world.windows_client import main
        tk = Mock()
        tk.destroy.side_effect = RuntimeError('private failure')
        output = io.StringIO()
        with patch.dict('sys.modules', {'tkinter': types.SimpleNamespace(Tk=Mock(return_value=tk))}), \
             patch('world.windows_client.locate_game', return_value=Path('game/pokeemerald64.exe')), \
             contextlib.redirect_stdout(output):
            self.assertEqual(main(['--self-test']), 1)
        self.assertFalse(json.loads(output.getvalue())['ok'])
        self.assertNotIn('private', output.getvalue())

    def test_window_fields_picker_and_remote_only_actions_without_real_tk(self):
        import types
        from unittest.mock import Mock, patch
        from world.windows_client import GuestWindow
        class Variable:
            def __init__(self, **kwargs):
                self.value = kwargs.get('value', '')
            def get(self):
                return self.value
            def set(self, value):
                self.value = value
        ttk = Mock()
        filedialog = Mock()
        filedialog.askopenfilename.return_value = 'invite path.json'
        tkinter = types.SimpleNamespace(StringVar=Variable, ttk=ttk, filedialog=filedialog)
        controller, root = Mock(), Mock()
        controller.snapshot.return_value = {'state': 'stopped', 'busy': False}
        with patch.dict('sys.modules', {'tkinter': tkinter}):
            window = GuestWindow(root, controller)
            self.assertEqual(set(window.values), {'Host', 'Port', 'Pin', 'Invitation'})
            window.pick_invitation()
            self.assertEqual(window.values['Invitation'].get(), 'invite path.json')
            window.values['Host'].set('my-host')
            window.values['Port'].set('8765')
            window.values['Pin'].set('a'*64)
            window.join('join')
            controller.submit.assert_called_with('join', ('my-host', 8765, 'a'*64, 'invite path.json'))
            window.join('rejoin')
            controller.submit.assert_called_with('rejoin', ('my-host', 8765, 'a'*64, 'invite path.json'))
            window.disconnect()
            controller.submit.assert_called_with('disconnect')
            root.after.assert_called()

    def test_controller_idle_failures_keep_worker_live_and_allow_disconnect_retry(self):
        import subprocess
        from unittest.mock import Mock, patch
        from world.windows_client import GuestController
        for operation in ('status', 'cleanup'):
            for error in (OSError('private capability'),
                          subprocess.TimeoutExpired('private capability', 3)):
                with self.subTest(operation=operation, error=type(error).__name__):
                    session = Mock()
                    session.status.return_value = {'state': 'connecting'}
                    with patch('world.windows_client.WindowsGuestSession', return_value=session), \
                         patch('threading.excepthook'):
                        controller = GuestController()
                        try:
                            self.assertTrue(controller.submit('join', ()))
                            wait_for(lambda: not controller.snapshot()['busy'])
                            if operation == 'status':
                                session.status.side_effect = error
                            else:
                                session.status.return_value = {'state': 'stopped'}
                                session.close.side_effect = error
                            wait_for(lambda: controller.snapshot()['state'] == 'error'
                                     or controller.closed.is_set())
                            self.assertEqual(controller.snapshot()['state'], 'error')
                            self.assertIn('Disconnect', str(controller.snapshot().get('message')))
                            self.assertNotIn('private capability', repr(controller.snapshot()))
                            self.assertTrue(controller._thread.is_alive())
                            self.assertFalse(controller.closed.is_set())
                            self.assertIs(controller._session, session)
                            time.sleep(.3)
                            self.assertEqual(controller.snapshot()['state'], 'error')
                            session.status.side_effect = None
                            session.close.side_effect = None
                            self.assertTrue(controller.submit('disconnect'))
                            wait_for(lambda: not controller.snapshot()['busy'])
                            self.assertEqual(controller.snapshot()['state'], 'stopped')
                            self.assertIsNone(controller._session)
                        finally:
                            session.status.side_effect = None
                            session.close.side_effect = None
                            controller.shutdown()
                            self.assertTrue(controller.closed.wait(2))
                            controller._thread.join(2)

    def test_controller_unexpected_worker_failure_closes_honestly_and_refuses_commands(self):
        from unittest.mock import Mock, patch
        from world.windows_client import GuestController
        session = Mock()
        session.status.side_effect = KeyError('private capability')
        with patch('world.windows_client.WindowsGuestSession', return_value=session), \
             patch('threading.excepthook') as uncaught:
            controller = GuestController()
            try:
                self.assertTrue(controller.submit('join', ()))
                self.assertTrue(controller.closed.wait(2))
                controller._thread.join(2)
                self.assertFalse(controller._thread.is_alive())
                self.assertEqual(controller.snapshot()['state'], 'error')
                self.assertFalse(controller.snapshot()['busy'])
                self.assertNotIn('private capability', repr(controller.snapshot()))
                self.assertFalse(controller.submit('join', ()))
                self.assertFalse(controller.submit('rejoin', ()))
                self.assertFalse(controller.submit('disconnect'))
                uncaught.assert_not_called()
                session.close.assert_called_once()
            finally:
                controller.shutdown()
                controller._thread.join(2)

    def test_controller_shutdown_waits_for_cleanup_and_refuses_commands(self):
        import subprocess
        from unittest.mock import Mock, patch
        from world.windows_client import GuestController
        session = Mock()
        session.status.return_value = {'state': 'connecting'}
        session.close.side_effect = subprocess.TimeoutExpired('private capability', 3)
        with patch('world.windows_client.WindowsGuestSession', return_value=session):
            controller = GuestController()
            try:
                self.assertTrue(controller.submit('join', ()))
                wait_for(lambda: not controller.snapshot()['busy'])
                controller.shutdown()
                wait_for(lambda: controller.snapshot()['state'] == 'error')
                self.assertFalse(controller.closed.is_set())
                self.assertTrue(controller._thread.is_alive())
                self.assertIs(controller._session, session)
                self.assertFalse(controller.submit('disconnect'))
                self.assertNotIn('private capability', repr(controller.snapshot()))
                session.close.side_effect = None
                self.assertTrue(controller.closed.wait(2))
                controller._thread.join(2)
                self.assertFalse(controller.submit('join', ()))
            finally:
                session.close.side_effect = None
                controller.shutdown()
                controller._thread.join(2)

    def test_controller_does_not_block_caller_and_closes_session(self):
        import threading
        from unittest.mock import Mock, patch
        from world.windows_client import GuestController
        gate = threading.Event()
        entered = threading.Event()
        session = Mock()
        def start():
            entered.set()
            gate.wait(2)
        session.start.side_effect = start
        session.status.return_value = {'state': 'connecting', 'trainer': 'Alice'}
        with patch('world.windows_client.WindowsGuestSession', return_value=session):
            controller = GuestController()
            self.addCleanup(controller.shutdown)
            before = time.monotonic()
            self.assertTrue(controller.submit('join', ('host', 1, 'a'*64, 'invite.json')))
            self.assertLess(time.monotonic() - before, .1)
            self.assertTrue(entered.wait(1))
            self.assertFalse(controller.submit('join', ('host', 1, 'a'*64, 'invite.json')))
            controller.shutdown()
            self.assertFalse(controller.closed.is_set())
            gate.set()
            self.assertTrue(controller.closed.wait(2))
        session.close.assert_called()


if __name__ == '__main__':
    unittest.main()
