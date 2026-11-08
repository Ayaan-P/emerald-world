import tempfile
import unittest
from pathlib import Path

RESEARCH = '/home/ayaan/projects/emerald-world-research'


class SessionTests(unittest.TestCase):
    def test_create_host_join_and_resume_independent_profiles(self):
        from world import session
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            root = Path(tmp)
            with session.DesktopSession(root) as host:
                state = host.create_world('friends')
                host.host('friends')
                alice = host.local_profile('alice')
                bob = host.local_profile('bob')
                alice['save'].write_bytes(b'alice save')
                bob['save'].write_bytes(b'bob save')
                self.assertEqual(host.local_profile('alice')['save'].read_bytes(), b'alice save')
                self.assertEqual(host.worlds(), [{'name': 'friends', 'path': str(state)}])
                self.assertNotEqual(alice['save'], bob['save'])
                self.assertIn('Hosting', host.status)
            self.assertFalse((state/'transport/world.sock').exists())
            self.assertEqual(bob['save'].read_bytes(), b'bob save')

    def test_remote_pin_invite_authentication_save_isolation_and_cleanup(self):
        import hashlib
        import ssl
        import subprocess
        from world import session
        from world.client import WorldClient
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            root = Path(tmp)
            cert, key = root/'cert.pem', root/'key.pem'
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                            '-keyout', str(key), '-out', str(cert), '-days', '1',
                            '-subj', '/CN=localhost'], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            pin = hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text())).hexdigest()
            with session.DesktopSession(root) as host, session.DesktopSession(root) as guest:
                host.create_world('host')
                host.host('host')
                address = host.share(cert, key, ('127.0.0.1', 0))
                invite = root/'invite.json'
                host.invite('remote', invite)
                with self.assertRaises(ValueError): host.invite('remote', invite)
                with self.assertRaises((OSError, ValueError)):
                    guest.connect_remote('guest', invite, address, '0'*64)
                self.assertIsNone(guest.state)
                self.assertIsNone(guest.broker)
                paths = guest.connect_remote('guest', invite, address, pin)
                self.assertIn('TLS verified', guest.status)
                from world.launcher import ProfileLock
                config_before = paths['config'].stat().st_mtime_ns
                with ProfileLock(guest.state, 'remote'), session.DesktopSession(root) as duplicate:
                    with self.assertRaises(ValueError):
                        duplicate.connect_remote('guest', invite, address, pin)
                self.assertEqual(paths['config'].stat().st_mtime_ns, config_before)
                with WorldClient(guest.state/'transport/world.sock', 'remote', __import__('json').loads(invite.read_text())['token']) as native:
                    identifier = guest.submit_intent('remote', 'Explore with friends')
                    self.assertEqual(guest.intent_status(identifier)['status'], 'queued')
                    self.assertIn('remote', server_players := {p['id'] for p in host.server.inspect()['players']})
                    self.assertEqual(server_players, {'remote'})
                    self.assertEqual(native.snapshot()['peers'], {})
                    self.assertTrue(guest.connection_status()['connected'])
                self.assertFalse((root/'guest/world.sqlite3').exists())
                self.assertEqual(paths['save'], root/'guest/trainers/remote/game.sav')
                self.assertEqual(invite.stat().st_mode & 0o777, 0o600)
                import json
                identity = json.loads(invite.read_text())
                with WorldClient(guest.state/'transport/world.sock', 'remote', identity['token']) as client:
                    self.assertEqual(client.snapshot()['peers'], {})
                command = session.game_command(session.REPO/'build/pokeemerald64', guest.state, paths, ':93')
                self.assertNotIn(str(invite), command)
                self.assertNotIn(str(key), command)
                self.assertIn('--unshare-all', command)
                guest.close()
                self.assertFalse((root/'guest/transport/world.sock').exists())
                self.assertTrue((root/'host/transport/world.sock').exists())

    def test_remote_health_uses_the_rejoined_trainer_not_an_old_profile(self):
        from world import session
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            root = Path(tmp)
            with session.DesktopSession(root) as host, session.DesktopSession(root) as guest:
                host.create_world('host')
                host.host('host')
                cert, key = host.tls_material()
                address = host.share(cert, key, ('127.0.0.1', 0))
                host.invite('alice', root/'alice.json')
                host.invite('bob', root/'bob.json')
                alice = guest.connect_remote('guest', root/'alice.json', address, host.sharing_pin)
                guest.close()
                bob = guest.connect_remote('guest', root/'bob.json', address, host.sharing_pin)
                # Old profiles are not the active invitation. A stale or removed
                # old config must not make the newly authenticated trainer offline.
                alice['config'].unlink()
                self.assertTrue(guest.connection_status()['connected'])
                with self.assertRaisesRegex(ValueError, 'invitation'):
                    guest.launch(alice, '/usr/bin/true', None)
                self.assertEqual(guest.remote_trainer, bob['profile'].name)
                guest.close()
                self.assertIsNone(guest.remote_trainer)

    def test_killed_desktop_session_rejoins_own_save_without_orphaned_child(self):
        import fcntl
        import subprocess
        import sys
        import time
        from world import session
        from world.launcher import ProfileLock
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            root = Path(tmp)
            fixture = root/'idle.py'
            # This is a disposable process fixture, not the native game or a
            # simulated battle. Its guard proves sandbox lifetime independently
            # of the launcher's own profile lock and reaper thread.
            fixture.write_text(
                '#!/usr/bin/python3\nimport fcntl, pathlib, time\n'
                'guard = open("fixture.lock", "w")\n'
                'fcntl.flock(guard, fcntl.LOCK_EX)\n'
                'pathlib.Path("ready").touch()\n'
                'while True: time.sleep(1)\n')
            fixture.chmod(0o700)
            def wait_for(predicate):
                deadline = time.monotonic() + 5
                while not predicate() and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertTrue(predicate())
            with session.DesktopSession(root) as host, session.DesktopSession(root) as guest:
                host.create_world('host')
                host.host('host')
                own = host.local_profile('alice')
                own['save'].write_bytes(b'host save fixture')
                cert, key = host.tls_material()
                address = host.share(cert, key, ('127.0.0.1', 0))
                invitation = root/'bob.json'
                host.invite('bob', invitation)
                paths = guest.connect_remote('guest', invitation, address, host.sharing_pin)
                paths['save'].write_bytes(b'bob save fixture')
                config = paths['config'].read_bytes()
                guest.close()
                source = (
                    'import pathlib, sys, time\nfrom world.session import DesktopSession\n'
                    's = DesktopSession(pathlib.Path(sys.argv[1]))\n'
                    'p = s.connect_remote("guest", sys.argv[2], (sys.argv[3], int(sys.argv[4])), sys.argv[5])\n'
                    's.launch(p, pathlib.Path(sys.argv[6]), None)\n'
                    'while True: time.sleep(1)\n')
                log = root/'worker.log'
                with log.open('wb') as output:
                    worker = subprocess.Popen(
                        [sys.executable, '-B', '-c', source, str(root), str(invitation),
                         address[0], str(address[1]), host.sharing_pin, str(fixture)],
                        stdin=subprocess.DEVNULL, stdout=output, stderr=output)
                try:
                    wait_for((paths['profile']/'ready').exists)
                    with self.assertRaisesRegex(ValueError, 'in use'):
                        ProfileLock(root/'guest', 'bob')
                    with (paths['profile']/'fixture.lock').open('r') as guard:
                        with self.assertRaises(BlockingIOError):
                            fcntl.flock(guard.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        worker.kill()
                        worker.wait(3)
                        def sandbox_stopped():
                            try:
                                fcntl.flock(guard.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                                return True
                            except BlockingIOError:
                                return False
                        wait_for(sandbox_stopped)
                    with ProfileLock(root/'guest', 'bob'):
                        pass
                    resumed = guest.connect_remote('guest', invitation, address, host.sharing_pin)
                    self.assertEqual(resumed, paths)
                    self.assertEqual(paths['config'].read_bytes(), config)
                    self.assertEqual(paths['save'].read_bytes(), b'bob save fixture')
                    self.assertEqual(own['save'].read_bytes(), b'host save fixture')
                    self.assertTrue(guest.connection_status()['connected'])
                    with self.assertRaises(ValueError):
                        guest.local_profile('alice')
                    with session.DesktopSession(root) as accidental_host:
                        with self.assertRaises(ValueError):
                            accidental_host.host('guest')
                    self.assertFalse((root/'guest/world.sqlite3').exists())
                    self.assertEqual(log.read_bytes(), b'')
                finally:
                    if worker.poll() is None:
                        worker.kill()
                    worker.wait(3)

    def test_transport_outage_and_explicit_rejoin_keep_identity_and_save_ownership(self):
        import json
        import time
        from world import session
        from world.client import WorldClient
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            root = Path(tmp)
            with session.DesktopSession(root) as host, session.DesktopSession(root) as guest:
                host.create_world('host')
                host.host('host')
                cert, key = host.tls_material()
                address = host.share(cert, key, ('127.0.0.1', 0))
                invitation = root/'bob.json'
                host.invite('bob', invitation)
                token = json.loads(invitation.read_text())['token']
                paths = guest.connect_remote('guest', invitation, address, host.sharing_pin)
                paths['save'].write_bytes(b'guest save fixture')
                config = paths['config'].read_bytes()
                endpoint = guest.state/'transport/world.sock'
                with WorldClient(endpoint, 'bob', token) as presence:
                    presence.snapshot()
                    host.broker.close()
                    host.broker = None
                    deadline = time.monotonic() + 3
                    while host.server.inspect()['players'] and time.monotonic() < deadline:
                        time.sleep(.01)
                    self.assertEqual(host.server.inspect()['players'], [])
                    self.assertFalse(guest.connection_status()['connected'])
                    status = guest.poll()
                    self.assertIn('Host unavailable', status)
                    self.assertIn('Connect remote TLS', status)
                    self.assertNotIn('hosting or joining', status)
                    self.assertNotIn(token, status)
                    host.share(cert, key, address)
                    self.assertTrue(guest.connection_status()['connected'])
                    # A new connection carries no retried game input. This is a
                    # protocol fixture, not proof of native activity recovery.
                    with WorldClient(endpoint, 'bob', token) as resumed:
                        resumed.snapshot()
                        self.assertEqual([p['id'] for p in host.server.inspect()['players']], ['bob'])
                guest.close()
                self.assertTrue((host.state/'transport/world.sock').is_socket())
                self.assertEqual(guest.connect_remote('guest', invitation, address, host.sharing_pin), paths)
                self.assertEqual(paths['save'].read_bytes(), b'guest save fixture')
                self.assertEqual(paths['config'].read_bytes(), config)
                self.assertFalse((guest.state/'world.sqlite3').exists())

    def test_launch_tracks_owned_children_and_reports_exit(self):
        from unittest.mock import patch
        from world import session
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            with session.DesktopSession(Path(tmp)) as host:
                host.create_world('world')
                host.host('world')
                paths = host.local_profile('alice')
                with patch('world.session.subprocess.Popen') as spawn:
                    process = spawn.return_value
                    process.poll.return_value = None
                    host.launch(paths, Path('/usr/bin/true'), None)
                    with self.assertRaises(ValueError):
                        host.launch(paths, Path('/usr/bin/true'), None)
                    self.assertIn('--unshare-all', spawn.call_args.args[0])
                    self.assertIn('starting', host.poll())
                    process.poll.return_value = 7
                    self.assertIn('exited 7', host.poll())
                    process.poll.return_value = None
                    host.close()
                    process.terminate.assert_called_once()
                    process.wait.assert_called()

    def test_actual_isolated_child_runs_and_can_be_relaunched(self):
        from world import session
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            with session.DesktopSession(Path(tmp)) as host:
                host.create_world('world')
                host.host('world')
                paths = host.local_profile('alice')
                for attempt in range(2):
                    process = host.launch(paths, '/usr/bin/true', None)
                    self.assertEqual(process.wait(timeout=5), 0, (paths['profile']/'native.log').read_text())
                self.assertIn('exited 0', host.poll())

    def test_launch_checks_display_and_keeps_scoped_stderr_log(self):
        from world import session
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            with session.DesktopSession(Path(tmp)) as host:
                host.create_world('world')
                host.host('world')
                paths = host.local_profile('alice')
                from unittest.mock import patch
                with patch('world.session.Path.is_socket', return_value=False):
                    with self.assertRaisesRegex(ValueError, 'Xephyr'):
                        host.launch(paths, '/usr/bin/false', ':93')
                process = host.launch(paths, '/usr/bin/false', None)
                process.wait(timeout=3)
                self.assertTrue((paths['profile']/'native.log').exists())
                self.assertIn('native.log', host.poll())
                (paths['profile']/'native.log').unlink()
                (paths['profile']/'native.log').symlink_to(Path(tmp)/'outside')
                with self.assertRaises(ValueError): host.launch(paths, '/usr/bin/false', None)

    def test_local_guest_disconnect_does_not_stop_the_host(self):
        from world import session
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            root = Path(tmp)
            with session.DesktopSession(root) as host, session.DesktopSession(root) as guest:
                host.create_world('shared')
                host.host('shared')
                guest.join_local('shared')
                guest.local_profile('bob')
                guest.close()
                self.assertTrue((root/'shared/transport/world.sock').exists())
                self.assertTrue(host.server.thread.is_alive())

    def test_poll_rejects_malformed_telemetry_without_losing_session(self):
        from unittest.mock import patch
        from world import session
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            with session.DesktopSession(Path(tmp)) as host:
                host.create_world('world')
                host.host('world')
                paths = host.local_profile('alice')
                with patch('world.session.subprocess.Popen') as spawn:
                    spawn.return_value.poll.return_value = None
                    host.launch(paths, Path('/usr/bin/true'), None)
                    paths['telemetry'].write_text('[]')
                    self.assertIn('waiting', host.poll())
                    paths['telemetry'].write_text('{"trainer":"alice","frame":6,"connected":true,"revision":3,"peers":[{"trainer":"bob","visible":true}]}')
                    self.assertIn('Nearby trainers: bob', host.poll())

    def test_human_connection_status_requires_fresh_own_native_telemetry(self):
        import json
        import os
        import time
        from world import session
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            root = Path(tmp)
            fixture = root/'idle.py'
            fixture.write_text('#!/usr/bin/python3\nimport time\ntime.sleep(30)\n')
            fixture.chmod(0o700)
            with session.DesktopSession(root) as host:
                host.create_world('world')
                host.host('world')
                paths = host.local_profile('alice')
                child = host.launch(paths, fixture, None)
                self.assertIsNone(child.poll())
                telemetry = paths['telemetry']
                value = {'trainer': 'alice', 'frame': 6, 'connected': True,
                         'ready': True, 'revision': 3, 'peers': []}
                telemetry.write_text(json.dumps(value))
                self.assertIn('alice: connected', host.poll())
                old = time.time() - 30
                os.utime(telemetry, (old, old))
                self.assertNotIn('alice: connected', host.poll())
                future = time.time() + 30
                os.utime(telemetry, (future, future))
                self.assertNotIn('alice: connected', host.poll())
                telemetry.write_text(json.dumps(value) + ' ' * 65536)
                self.assertNotIn('alice: connected', host.poll())
                for invalid in (dict(value, trainer='bob'), dict(value, frame=True),
                                dict(value, revision=-1)):
                    telemetry.write_text(json.dumps(invalid))
                    self.assertNotIn('alice: connected', host.poll())
                telemetry.unlink()
                other = root/'other.json'
                other.write_text(json.dumps(value))
                telemetry.symlink_to(other)
                self.assertNotIn('alice: connected', host.poll())
                telemetry.unlink()
                os.mkfifo(telemetry, 0o600)
                started = time.monotonic()
                self.assertNotIn('alice: connected', host.poll())
                self.assertLess(time.monotonic() - started, 1)
            self.assertIsNotNone(child.poll())

    def test_runtime_gm_host_controls_queue_real_intents_and_stop_cleanly(self):
        import time
        from world import session
        from world.runtime_gm import MODEL
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            root = Path(tmp)
            with session.DesktopSession(root) as host, session.DesktopSession(root) as guest:
                with self.assertRaises(ValueError): host.start_gm()
                host.create_world('shared')
                host.host('shared')
                host.start_gm()
                deadline = time.monotonic() + 3
                while host.gm_status().get('runtime', {}).get('state') != 'idle' and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertEqual(host.gm_status()['runtime']['model'], MODEL)
                with self.assertRaises(ValueError): host.start_gm()
                host.stop_gm()
                self.assertFalse(host.gm_thread.is_alive())
                identifier = host.submit_intent('alice', 'I want to explore the ruins with my friends.')
                latest = host.gm_status()['requests'][-1]
                self.assertEqual(latest['id'], identifier)
                self.assertEqual(latest['status'], 'queued')
                self.assertEqual(latest['text'], 'I want to explore the ruins with my friends.')
                guest.join_local('shared')
                with self.assertRaises(ValueError): guest.start_gm()
                guest.local_profile('bob')
                identifier = guest.submit_intent('bob', 'Explore')
                self.assertEqual(guest.intent_status(identifier)['player'], 'bob')
                self.assertIn('queued', host.poll())

    def test_graphical_root_picker_is_explicit_and_requires_disconnection(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        from world import session
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            root = Path(tmp)
            next_root = root/'chosen'
            next_root.mkdir()
            app = session.DesktopApp.__new__(session.DesktopApp)
            app.session = session.DesktopSession(root)
            app.window = Mock()
            app.root_label = Mock()
            app.fields = {'world': Mock()}
            app.world_entry = {}
            dialog = Mock(return_value=str(next_root))
            with patch.dict(sys.modules, {'tkinter': SimpleNamespace(filedialog=SimpleNamespace(askdirectory=dialog))}):
                app.choose_root()
            self.assertEqual(app.session.root, next_root)
            self.assertEqual(dialog.call_args.kwargs['initialdir'], str(root))
            app.session.create_world('world')
            app.session.host('world')
            with self.assertRaises(ValueError): app.choose_root()
            app.session.close()

    def test_host_tls_key_cannot_be_inside_a_trainer_profile(self):
        from world import session
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            with session.DesktopSession(Path(tmp)) as host:
                host.create_world('world')
                host.host('world')
                paths = host.local_profile('alice')
                with self.assertRaisesRegex(ValueError, 'game-visible'):
                    host.share(paths['profile']/'cert.pem', paths['profile']/'key.pem')

    def test_missing_graphical_display_reports_a_useful_prerequisite(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        from world import session
        class DisplayError(Exception):
            pass
        fake_tk = SimpleNamespace(Tk=Mock(side_effect=DisplayError()), TclError=DisplayError)
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            with patch.dict(sys.modules, {'tkinter': fake_tk}):
                with self.assertRaisesRegex(ValueError, 'DISPLAY'):
                    session.run_desktop(Path(tmp))

    def test_desktop_entrypoint_requires_explicit_root_and_dispatches_ui(self):
        from unittest.mock import patch
        from world import launcher
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            with patch('world.session.run_desktop', return_value=0) as ui:
                self.assertEqual(launcher.main(['desktop', '--worlds-root', tmp]), 0)
                self.assertEqual(ui.call_args.args[0], Path(tmp))
            with self.assertRaises(SystemExit):
                launcher.main(['desktop'])

    def test_live_presence_profiles_and_reconnect_after_host_restart(self):
        import json
        from world import session
        from world.client import WorldClient
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            root = Path(tmp)
            with session.DesktopSession(root) as host, session.DesktopSession(root) as guest:
                host.create_world('friends')
                host.host('friends')
                paths = host.local_profile('alice')
                self.assertEqual(host.trainers(), ['alice'])
                token = dict(line.split(' ', 1) for line in paths['config'].read_text().splitlines())['token']
                guest.join_local('friends')
                with WorldClient(root/'friends/transport/world.sock', 'alice', token):
                    self.assertIn('alice', guest.connection_status()['players'])
                    self.assertIn('Online trainers: alice', guest.poll())
                host.close()
                self.assertFalse(guest.connection_status()['connected'])
                self.assertIn('Retry', guest.poll())
                host.host('friends')
                self.assertTrue(guest.connection_status()['connected'])
                self.assertEqual(host.local_profile('alice')['config'].read_text(), paths['config'].read_text())

    def test_host_can_share_without_manual_certificate_choreography(self):
        from world import session
        import hashlib
        import ssl
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            root = Path(tmp)
            with session.DesktopSession(root) as host:
                host.create_world('friends')
                host.host('friends')
                cert, key = host.tls_material()
                self.assertEqual(key.stat().st_mode & 0o777, 0o600)
                first = cert.read_bytes()
                self.assertEqual(host.tls_material(), (cert, key))
                self.assertEqual(cert.read_bytes(), first)
                address = host.share(cert, key, ('127.0.0.1', 0))
                invitation = root/'friend.json'
                host.invite('bob', invitation)
                pin = hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text())).hexdigest()
                with session.DesktopSession(root) as guest:
                    guest.connect_remote('remote-save', invitation, address, pin)
                    self.assertTrue(guest.connection_status()['connected'])

    def test_explicit_new_root_can_be_created_without_discovering_home(self):
        from world import session
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            root = Path(tmp)/'new-worlds'
            session.DesktopSession.create_root(root)
            self.assertTrue(root.is_dir())
            self.assertEqual(root.stat().st_mode & 0o777, 0o700)
            with self.assertRaises(ValueError):
                session.DesktopSession.create_root(Path('relative'))
            linked = Path(tmp)/'linked'
            linked.symlink_to(root)
            with self.assertRaises(ValueError):
                session.DesktopSession.create_root(linked/'child')

    def test_session_manages_only_its_new_display(self):
        from world import session
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            with session.DesktopSession(Path(tmp)) as host:
                self.assertIsNone(host.managed_display)
                with self.assertRaisesRegex(ValueError, 'dedicated'):
                    host.start_display(':0')
                self.assertIsNone(host.managed_display)

    def test_graphical_remote_health_outage_and_poll_remain_responsive(self):
        import os
        import time
        import hashlib
        import ssl
        import threading
        try:
            import tkinter as tk
        except ImportError:
            self.skipTest('Tk runtime is not configured')
        if not os.environ.get('DISPLAY'):
            self.skipTest('No graphical desktop')
        from world import session
        from world.client import WorldClient
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            root = Path(tmp)
            with session.DesktopSession(root) as host, session.DesktopSession(root) as guest:
                host.create_world('host')
                host.host('host')
                cert, key = host.tls_material()
                address = host.share(cert, key, ('127.0.0.1', 0))
                invitation = root/'invite.json'
                host.invite('bob', invitation)
                pin = hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text())).hexdigest()
                paths = guest.connect_remote('guest', invitation, address, pin)
                token = __import__('json').loads(invitation.read_text())['token']
                window = tk.Tk()
                app = session.DesktopApp(window, guest, Path('/usr/bin/false'), None)
                def until(predicate):
                    deadline = time.monotonic() + 6
                    while not predicate() and time.monotonic() < deadline:
                        window.update()
                        time.sleep(.01)
                    self.assertTrue(predicate(), app.message.get())
                try:
                    with WorldClient(paths['config'].parent.parent.parent/'transport/world.sock', 'bob', token) as native:
                        until(lambda: 'Remote TLS host reachable' in app.message.get())
                        self.assertEqual([p['id'] for p in host.server.inspect()['players']], ['bob'])
                        self.assertEqual(native.snapshot()['peers'], {})
                    host.close()
                    until(lambda: 'Host unavailable' in app.message.get())
                    # A deliberately blocked status worker cannot stall Tk.
                    entered, release = threading.Event(), threading.Event()
                    original = guest.poll
                    def blocked():
                        entered.set()
                        release.wait(3)
                        return original()
                    guest.poll = blocked
                    until(lambda: entered.is_set())
                    beats = []
                    window.after(10, lambda: beats.append(True))
                    start = time.monotonic()
                    until(lambda: bool(beats))
                    self.assertLess(time.monotonic() - start, .5)
                    release.set()
                finally:
                    if 'release' in locals(): release.set()
                    app.executor.shutdown(wait=True)
                    window.destroy()

    def test_graphical_play_tabs_create_host_launch_and_disconnect(self):
        import os
        try:
            import tkinter as tk
        except ImportError:
            self.skipTest('Tk runtime is not configured')
        if not os.environ.get('DISPLAY'):
            self.skipTest('No graphical desktop')
        from world import session
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            window = tk.Tk()
            app = session.DesktopApp(window, session.DesktopSession(Path(tmp)), Path('/usr/bin/false'), None)
            try:
                self.assertEqual([app.notebook.tab(tab, 'text') for tab in app.notebook.tabs()],
                                 ['Play', 'Connect friends', 'Optional GM', 'Settings', 'World library', 'Host controls'])
                buttons = {button.cget('text'): button for button in app.buttons}
                buttons['Host selected'].invoke()
                self.assertIn('Choose an existing world', app.message.get())
                app.fields['world'].set('friends')
                buttons['Create world'].invoke()
                buttons['Host selected'].invoke()
                app.fields['trainer'].set('alice')
                buttons['Launch / resume trainer'].invoke()
                import time
                def finish_launch():
                    deadline = time.monotonic() + 5
                    while app.pending is not None and time.monotonic() < deadline:
                        window.update()
                        time.sleep(.01)
                    self.assertIsNone(app.pending, app.message.get())
                finish_launch()
                app.session.games['alice'][0].wait(timeout=5)
                app.fields['trainer'].set('bob')
                buttons['Launch / resume trainer'].invoke()
                finish_launch()
                app.session.games['bob'][0].wait(timeout=5)
                self.assertEqual(app.session.trainers(), ['alice', 'bob'])
                self.assertIn('Launch AI-controlled trainer', buttons)
                self.assertEqual(app.fields['ai_trainer'].get(), 'hermes')
                app.fields['ai_trainer'].set('bob')
                buttons['Launch AI-controlled trainer'].invoke()
                finish_launch()
                self.assertIn('distinct AI trainer', app.session.status)
                self.assertNotIn('bob', app.session.agent_games)
                app.fields['ai_trainer'].set('hermes')
                buttons['Launch AI-controlled trainer'].invoke()
                finish_launch()
                app.session.games['hermes'][0].wait(timeout=5)
                self.assertEqual(app.session.agent_games, {'hermes'})
                self.assertEqual(app.session.trainers(), ['alice', 'bob', 'hermes'])
                buttons['Disconnect'].invoke()
                import time
                deadline = time.monotonic() + 5
                while app.pending is not None and time.monotonic() < deadline:
                    window.update()
                    time.sleep(.01)
                self.assertIsNone(app.session.state)
                window.update()
            finally:
                app.executor.shutdown(wait=True)
                app.session.close()
                window.destroy()

    def test_cross_session_and_cli_exclusion_until_real_child_exit_or_cleanup(self):
        import subprocess
        import sys
        import time
        from unittest.mock import patch
        from world import session, launcher
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            root = Path(tmp)
            with session.DesktopSession(root) as first, session.DesktopSession(root) as second:
                first.create_world('world'); first.host('world'); second.join_local('world')
                alice = first.local_profile('alice')
                bob = first.local_profile('bob')
                original = alice['config'].read_bytes()
                seed = root/'seed'; seed.write_bytes(b'seed')
                with patch('world.session.game_command', return_value=['/usr/bin/sleep', '30']):
                    child = first.launch(alice, '/usr/bin/sleep', None)
                    with self.assertRaises(ValueError): second.launch(alice, '/usr/bin/sleep', None)
                    with self.assertRaises(ValueError): second.local_profile('alice', seed)
                    cli = subprocess.run([sys.executable, '-m', 'world.launcher', '--state-dir', str(first.state),
                                          'join', 'alice', '--seed-save', str(seed), '--print-command'],
                                         capture_output=True, text=True, timeout=5)
                    self.assertEqual(cli.returncode, 1, cli.stderr)
                    self.assertIn('in use', cli.stderr)
                    self.assertFalse(alice['save'].exists())
                    self.assertEqual(alice['config'].read_bytes(), original)
                    other = second.launch(bob, '/usr/bin/sleep', None)
                    first.close()
                    self.assertIsNotNone(child.poll())
                    with launcher.ProfileLock(root/'world', 'alice'):
                        pass
                    self.assertIsNone(other.poll())
                    other.terminate(); other.wait(timeout=3)
                    # Automatic exit cleanup must not require a GUI poll.
                    deadline = time.monotonic() + 3
                    while True:
                        try:
                            with launcher.ProfileLock(root/'world', 'bob'):
                                break
                        except ValueError:
                            if time.monotonic() >= deadline: raise
                            time.sleep(.01)

    def test_launch_error_releases_profile_lock(self):
        from unittest.mock import patch
        from world import session, launcher
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            with session.DesktopSession(Path(tmp)) as host:
                host.create_world('world'); host.host('world')
                paths = host.local_profile('alice')
                with patch('world.session.subprocess.Popen', side_effect=OSError('spawn failed')):
                    with self.assertRaises(OSError): host.launch(paths, '/usr/bin/false', None)
                with launcher.ProfileLock(host.state, 'alice'):
                    pass

    def test_watcher_start_error_stops_child_before_releasing_lock(self):
        import subprocess
        from unittest.mock import patch
        from world import session, launcher
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            with session.DesktopSession(Path(tmp)) as host:
                host.create_world('world'); host.host('world')
                paths = host.local_profile('alice')
                original = subprocess.Popen
                children = []
                def spawn(*args, **kwargs):
                    child = original(*args, **kwargs); children.append(child); return child
                import threading
                original_start = threading.Thread.start
                def start_watcher(thread):
                    if thread.name == 'native-profile-lock':
                        raise RuntimeError('no watcher thread')
                    return original_start(thread)
                with patch('world.session.game_command', return_value=['/usr/bin/sleep', '30']), \
                     patch('world.session.subprocess.Popen', side_effect=spawn), \
                     patch('threading.Thread.start', new=start_watcher):
                    with self.assertRaises(RuntimeError): host.launch(paths, '/usr/bin/sleep', None)
                self.assertIsNotNone(children[0].poll())
                with launcher.ProfileLock(host.state, 'alice'):
                    pass

    def test_startup_operations_snapshot_form_and_run_off_ui_thread(self):
        import threading
        import time
        from concurrent.futures import ThreadPoolExecutor
        from unittest.mock import Mock, patch
        from world import session
        owner = threading.get_ident()
        class Variable:
            def __init__(self, value=''): self.value = value
            def get(self):
                self.assert_ui(); return self.value
            def set(self, value):
                self.assert_ui(); self.value = value
            def assert_ui(self):
                if threading.get_ident() != owner:
                    raise AssertionError('Tk variable touched from worker')
        for operation in ('start_display', 'launch', 'share'):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
                app = session.DesktopApp.__new__(session.DesktopApp)
                app.session = Mock(status='ready')
                app.window = Mock()
                app.executor = ThreadPoolExecutor(max_workers=1)
                app.pending = app.pending_kind = app.poll_future = None
                app.next_poll = float('inf'); app.closing = False
                app.remote_paths = None; app.buttons = []
                app.binary = Path('/usr/bin/false')
                app.fields = {key: Variable(value) for key, value in {
                    'display': ':199', 'trainer': 'alice', 'seed': '', 'binary': '/usr/bin/false',
                    'cert': '', 'key': '', 'listen': '127.0.0.1:0', 'pin': ''}.items()}
                app.message = Variable(); app.refresh = Mock()
                entered, release = threading.Event(), threading.Event()
                worker_threads = []
                def slow(*args):
                    worker_threads.append(threading.get_ident())
                    entered.set(); release.wait(.7)
                    return Path(tmp)/'cert.pem', Path(tmp)/'key.pem'
                (Path(tmp)/'cert.pem').write_text('certificate')
                app.session.tls_material.side_effect = slow
                app.session.start_display.side_effect = slow
                app.session.share.return_value = ('127.0.0.1', 1234)
                try:
                    with patch('world.session.Path.is_socket', return_value=False), patch('ssl.PEM_cert_to_DER_cert', return_value=b'cert'):
                        start = time.monotonic()
                        app.submit(getattr(app, operation))
                        self.assertLess(time.monotonic() - start, .3)
                        self.assertIsNotNone(app.pending)
                        self.assertTrue(entered.wait(.3))
                        self.assertNotEqual(worker_threads, [owner])
                        app.fields['display'].set(':198')
                        release.set()
                        app.pending.result(timeout=2)
                        # Worker returns data only. Tk completion owns widget updates.
                        self.assertEqual(app.fields['pin'].get(), '')
                        app.tick()
                    self.assertIsNone(app.pending)
                    if operation == 'share':
                        self.assertTrue(app.fields['pin'].get())
                    else:
                        app.session.start_display.assert_called_once_with(':199')
                    if operation == 'launch': app.refresh.assert_called_once()
                finally:
                    release.set(); app.executor.shutdown(wait=True)

    def test_agent_launch_is_owned_separate_and_reports_only_verified_readiness(self):
        import json
        import socket
        from unittest.mock import patch
        from world import session, launcher
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            with session.DesktopSession(Path(tmp)) as host:
                host.create_world('w'); host.host('w')
                human = host.local_profile('alice')
                ai = host.local_profile('hermes')
                endpoint = ai['profile']/'player.sock'
                with patch('world.session.game_command', return_value=['/usr/bin/sleep', '30']) as command:
                    host.launch(human, '/usr/bin/sleep', None)
                    host.launch(ai, '/usr/bin/sleep', None, agent_control=True)
                    self.assertTrue(command.call_args.kwargs['agent_control'])
                    waiting = host.poll()
                    self.assertIn('AI control starting', waiting)
                    self.assertNotIn('AI control ready', waiting)
                    with self.assertRaises(ValueError):
                        host.launch(human, '/usr/bin/sleep', None, agent_control=True)
                    with self.assertRaises(ValueError):
                        launcher.ProfileLock(host.state, 'hermes')
                    with socket.socket(socket.AF_UNIX) as server:
                        server.bind(str(endpoint)); server.listen(1)
                        endpoint.chmod(0o600)
                        ai['telemetry'].write_text(json.dumps({
                            'trainer': 'hermes', 'frame': 6, 'ready': True,
                            'connected': True, 'revision': 1, 'peers': []}))
                        ready = host.poll()
                    self.assertIn('hermes: AI control ready', ready)
                    self.assertNotIn('AI control starting', ready)
                    self.assertIn(str(endpoint), ready)
                    self.assertIn('PlayerClient', ready)
                    self.assertIn('.observe()', ready)
                    self.assertNotIn(str(human['profile']/'player.sock'), ready)
                    self.assertNotIn('token', ready)

    def test_agent_poll_never_occupies_idle_or_connected_controller_socket(self):
        import json
        import socket
        from unittest.mock import patch
        from world import session
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            with session.DesktopSession(Path(tmp)) as host:
                host.create_world('w'); host.host('w')
                paths = host.local_profile('hermes')
                with patch('world.session.game_command', return_value=['/usr/bin/sleep', '30']):
                    host.launch(paths, '/usr/bin/sleep', None, agent_control=True)
                paths['telemetry'].write_text(json.dumps({
                    'trainer': 'hermes', 'frame': 6, 'ready': True,
                    'connected': True, 'revision': 1, 'peers': []}))
                endpoint = paths['profile']/'player.sock'
                with socket.socket(socket.AF_UNIX) as listener:
                    listener.bind(str(endpoint)); listener.listen(16)
                    endpoint.chmod(0o600)
                    listener.setblocking(False)
                    for _ in range(3):
                        status = host.poll()
                        # No queued UI connection, even while the slot is idle.
                        with self.assertRaises(BlockingIOError):
                            unexpected, _ = listener.accept()
                            unexpected.close()
                        self.assertIn('AI control ready', status)
                    with socket.socket(socket.AF_UNIX) as controller:
                        controller.settimeout(1)
                        controller.connect(str(endpoint))
                        native, _ = listener.accept()
                        with native:
                            native.settimeout(1)
                            for identifier in range(1, 4):
                                self.assertIn('AI control ready', host.poll())
                                with self.assertRaises(BlockingIOError):
                                    unexpected, _ = listener.accept()
                                    unexpected.close()
                                # Valid JSONL player requests still cross the
                                # original persistent controller connection.
                                request = {'id': identifier, 'op': 'observe'}
                                controller.sendall((json.dumps(request)+'\n').encode())
                                self.assertEqual(json.loads(native.recv(4096)), request)
                                response = {'id': identifier, 'ok': True}
                                native.sendall((json.dumps(response)+'\n').encode())
                                self.assertEqual(json.loads(controller.recv(4096)), response)

    def test_agent_readiness_requires_fresh_own_telemetry_and_private_socket(self):
        import json
        import os
        import socket
        import time
        from unittest.mock import patch
        from world import session
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            with session.DesktopSession(Path(tmp)) as host:
                host.create_world('w'); host.host('w')
                paths = host.local_profile('hermes')
                with patch('world.session.game_command', return_value=['/usr/bin/sleep', '30']):
                    child = host.launch(paths, '/usr/bin/sleep', None, agent_control=True)
                endpoint = paths['profile']/'player.sock'
                telemetry = paths['telemetry']
                value = {'trainer': 'hermes', 'frame': 6, 'ready': False,
                         'connected': False, 'revision': 0, 'peers': []}
                with socket.socket(socket.AF_UNIX) as listener:
                    listener.bind(str(endpoint)); listener.listen(16)
                    endpoint.chmod(0o600)
                    def starting():
                        status = host.poll()
                        self.assertIn('AI control starting', status)
                        self.assertNotIn('AI control ready', status)
                        self.assertNotIn('SDK:', status)
                        self.assertNotIn('MCP:', status)
                    starting()  # A socket alone is not native readiness.
                    for invalid in ({}, [], dict(value, trainer='alice'),
                                    dict(value, frame=True), dict(value, ready='yes'),
                                    dict(value, revision=-1)):
                        with self.subTest(telemetry=invalid):
                            telemetry.write_text(json.dumps(invalid))
                            starting()
                    telemetry.write_text(json.dumps(value))
                    old = time.time() - 30
                    os.utime(telemetry, (old, old))
                    starting()
                    telemetry.unlink()
                    other = paths['profile']/'other.json'
                    other.write_text(json.dumps(value))
                    telemetry.symlink_to(other)
                    starting()
                    telemetry.unlink()
                    telemetry.write_text(json.dumps(value))
                    endpoint.chmod(0o666)
                    starting()
                    endpoint.chmod(0o600)
                    # Native control is available even while world transport
                    # reconnects or the game is outside the overworld.
                    status = host.poll()
                    self.assertIn('AI control ready', status)
                    self.assertIn('connecting or disconnected', status)
                    self.assertIn('MCP:', status)
                    self.assertIn('One controller only', status)
                    child.terminate(); child.wait(timeout=3)
                    status = host.poll()
                    self.assertIn('hermes exited', status)
                    self.assertNotIn('AI control ready', status)
                    self.assertNotIn('SDK:', status)
                    self.assertNotIn('MCP:', status)

    def test_agent_launch_refuses_unknown_existing_control_endpoint(self):
        import socket
        from unittest.mock import patch
        from world import session
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            with session.DesktopSession(Path(tmp)) as host:
                host.create_world('w'); host.host('w')
                paths = host.local_profile('hermes')
                with socket.socket(socket.AF_UNIX) as existing:
                    existing.bind(str(paths['profile']/'player.sock'))
                    existing.listen(1)
                    (paths['profile']/'player.sock').chmod(0o600)
                    with patch('world.session.subprocess.Popen') as spawn:
                        with self.assertRaisesRegex(ValueError, 'existing|exists'):
                            host.launch(paths, '/usr/bin/true', None, agent_control=True)
                        spawn.assert_not_called()
                    self.assertTrue((paths['profile']/'player.sock').is_socket())

    def test_agent_resume_defers_only_private_stale_socket_recovery_to_native(self):
        import os
        import socket
        from unittest.mock import patch
        from world import session
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            with session.DesktopSession(Path(tmp)) as host:
                host.create_world('w'); host.host('w')
                paths = host.local_profile('hermes')
                endpoint = paths['profile']/'player.sock'
                with socket.socket(socket.AF_UNIX) as stale:
                    stale.bind(str(endpoint))
                endpoint.chmod(0o600)
                inode = endpoint.stat().st_ino
                # This tests the launcher preflight. Native code separately
                # verifies and recovers this inode before binding its listener.
                import subprocess
                from world import launcher
                native_spawn = subprocess.Popen
                commands = []
                original_check = launcher.check_player_endpoint
                def check(checked_paths):
                    with self.assertRaisesRegex(ValueError, 'in use'):
                        launcher.ProfileLock(host.state, 'hermes')
                    return original_check(checked_paths)
                def spawn(command, **kwargs):
                    commands.append(command)
                    self.assertEqual(endpoint.stat().st_ino, inode)
                    # Only replace the child, not the production command builder.
                    return native_spawn(['/usr/bin/true'], **kwargs)
                with patch('world.session.subprocess.Popen', side_effect=spawn), \
                     patch.object(launcher, 'check_player_endpoint', side_effect=check) as preflight:
                    process = host.launch(paths, '/usr/bin/true', None, agent_control=True)
                    self.assertEqual(process.wait(timeout=3), 0)
                    preflight.assert_called_once_with(paths)
                self.assertEqual(commands[0][-2:], ['--player-control', str(endpoint)])
                self.assertIn('--unshare-all', commands[0])
                self.assertEqual(endpoint.stat().st_ino, inode)
                self.assertEqual(endpoint.stat().st_uid, os.geteuid())

    def test_gui_ai_role_requires_explicit_distinct_trainer_not_selected_human(self):
        from unittest.mock import Mock
        from world import session
        app = session.DesktopApp.__new__(session.DesktopApp)
        app.session = Mock()
        app.session.trainers.return_value = ['alice']
        app.remote_paths = None
        app.binary = Path('/usr/bin/true')
        value = {'trainer': 'alice', 'ai_trainer': 'hermes', 'seed': '', 'display': '', 'binary': '/usr/bin/true'}
        app.session.local_profile.return_value = {'profile': Path('/tmp/hermes')}
        app._launch_ai(value, None)
        app.session.local_profile.assert_called_once_with('hermes', None)
        self.assertTrue(app.session.launch.call_args.kwargs['agent_control'])
        value['ai_trainer'] = 'alice'
        with self.assertRaisesRegex(ValueError, 'distinct|different|Human'):
            app._launch_ai(value, None)
        value['ai_trainer'] = 'hermes'
        with self.assertRaisesRegex(ValueError, 'invitation|assigned'):
            app._launch_ai(value, {'profile': Path('/tmp/alice')})

    def test_rejects_world_escape_and_existing_creation(self):
        from world import session
        with tempfile.TemporaryDirectory(dir=RESEARCH) as tmp:
            with session.DesktopSession(Path(tmp)) as host:
                for name in ('../escape', '/absolute', '', 'has spaces'):
                    with self.assertRaises(ValueError): host.create_world(name)
                host.create_world('one')
                with self.assertRaises(ValueError): host.create_world('one')
                with self.assertRaises(ValueError): host.host('missing')
                self.assertFalse((Path(tmp)/'missing').exists())


if __name__ == '__main__':
    unittest.main()
