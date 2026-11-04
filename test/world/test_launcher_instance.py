"""Launcher ownership checks using temporary roots, without games or browsers."""
import tempfile
from pathlib import Path
import unittest

from world.session import DesktopSession, SessionError
from world.transport import ClientBroker
from world.friend_worlds import remember


class LauncherInstanceTests(unittest.TestCase):
    def test_five_shortcuts_leave_one_owner_and_quit_or_sigterm_releases_it(self):
        import http.client
        import json
        import subprocess
        import sys
        import time
        from world.launcher_instance import LauncherInstance
        from world.web_launcher import REPO
        # Only replace the browser side effect and built assets. The real CLI,
        # HTTP server, locks, signals and DesktopSession lifecycle all run.
        code = ('import sys; from pathlib import Path; import world.web_launcher as w; '
                'w.DIST=Path(sys.argv[1]); w.open_browser=lambda url: True; '
                'sys.exit(w.main(["--worlds-root",sys.argv[1],"--binary","/no/game"]))')
        for exit_method in ('quit', 'sigterm'):
            with self.subTest(exit_method=exit_method), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'index.html').write_text('fixture')
                command = [sys.executable, '-c', code, directory]
                process = subprocess.Popen(command, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    deadline = time.monotonic() + 5
                    while True:
                        try:
                            value = json.loads((root / '.launcher-instance').read_text())
                            break
                        except (OSError, ValueError):
                            if process.poll() is not None or time.monotonic() >= deadline:
                                self.fail('owner did not publish its listener')
                            time.sleep(0.02)
                    followers = [subprocess.Popen(command, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                                 for _ in range(5)]
                    try:
                        for second in followers:
                            stdout, stderr = second.communicate(timeout=5)
                            self.assertEqual(second.returncode, 0, stderr)
                            self.assertEqual(stdout + stderr, b'')
                            self.assertIsNone(process.poll())
                            self.assertEqual(json.loads((root / '.launcher-instance').read_text()), value)
                    finally:
                        for second in followers:
                            if second.poll() is None:
                                second.kill()
                            second.communicate(timeout=5)
                    if exit_method == 'quit':
                        connection = http.client.HTTPConnection('127.0.0.1', value['port'], timeout=3)
                        origin = f'http://127.0.0.1:{value["port"]}'
                        connection.request('POST', '/api/action', json.dumps({'action': 'quit', 'payload': {}}),
                                           {'Authorization': 'Bearer ' + value['capability'],
                                            'Origin': origin, 'Content-Type': 'application/json'})
                        self.assertEqual(connection.getresponse().status, 200)
                        connection.close()
                    else:
                        process.terminate()
                    stdout, stderr = process.communicate(timeout=5)
                    self.assertEqual(process.returncode, 0, stderr)
                    self.assertEqual(stdout + stderr, b'')
                    self.assertEqual((root / '.launcher-instance').read_bytes(), b'')
                    replacement = LauncherInstance(root)
                    self.assertTrue(replacement.owner)
                    replacement.close()
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.communicate(timeout=5)

    def test_unsafe_state_and_unresponsive_owner_fail_closed(self):
        import os
        from world.launcher_instance import LauncherInstance, InstanceError
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / '.launcher-instance'
            target = root / 'untouched'
            target.write_text('unchanged')
            state.symlink_to(target)
            with self.assertRaises(InstanceError):
                LauncherInstance(root)
            self.assertEqual(target.read_text(), 'unchanged')
            state.unlink()
            os.link(target, state)
            with self.assertRaises(InstanceError):
                LauncherInstance(root)
            self.assertEqual(target.read_text(), 'unchanged')
            state.unlink()
            owner = LauncherInstance(root)
            try:
                state.chmod(0o644)
                with self.assertRaises(InstanceError):
                    LauncherInstance(root)
                state.chmod(0o600)
                second = LauncherInstance(root)
                try:
                    with self.assertRaisesRegex(InstanceError, 'not responding'):
                        second.existing_url(timeout=0)
                    self.assertFalse(second.owner)
                finally:
                    second.close()
            finally:
                owner.close()
            # Dead owner's data is not trusted or opened as an arbitrary URL.
            state.write_text('{"port": 1, "capability": "private-stale-value"}')
            replacement = LauncherInstance(root)
            self.assertTrue(replacement.owner)
            self.assertEqual(state.read_bytes(), b'')
            replacement.close()

    def test_browser_start_failure_closes_session_and_releases_ownership(self):
        import contextlib
        import io
        from unittest.mock import patch
        from world.launcher_instance import LauncherInstance
        from world.web_launcher import main
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'index.html').write_text('fixture')
            errors = io.StringIO()
            with patch('world.web_launcher.DIST', root), \
                 patch('world.web_launcher.open_browser', return_value=False), \
                 patch.object(DesktopSession, 'close', autospec=True) as close, \
                 contextlib.redirect_stderr(errors):
                self.assertEqual(main(['--worlds-root', directory, '--binary', '/no/game']), 1)
                close.assert_called_once()
            self.assertEqual(errors.getvalue(), 'Could not open the local launcher in a browser. Retry the shortcut.\n')
            self.assertEqual((root / '.launcher-instance').read_bytes(), b'')
            owner = LauncherInstance(root)
            self.assertTrue(owner.owner)
            owner.close()

    def test_browser_provider_output_and_errors_cannot_disclose_capability(self):
        import contextlib
        import io
        import subprocess
        from unittest.mock import patch
        from world.web_launcher import open_browser
        private_url = 'http://127.0.0.1:1234/#' + 'a' * 43
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            with patch('world.web_launcher.subprocess.run', side_effect=OSError(private_url)) as run:
                self.assertFalse(open_browser(private_url))
            self.assertNotIn(private_url, repr(run.call_args.args))
            self.assertEqual(run.call_args.kwargs['input'], private_url)
            self.assertEqual(run.call_args.kwargs['stdout'], subprocess.DEVNULL)
            self.assertEqual(run.call_args.kwargs['stderr'], subprocess.DEVNULL)
        self.assertEqual(output.getvalue(), '')

    def test_shortcut_reuses_owner_without_constructing_session(self):
        import threading
        from http.server import ThreadingHTTPServer
        from unittest.mock import Mock, patch
        from world.launcher_instance import LauncherInstance
        from world.web_launcher import handler_for, main
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'index.html').write_text('launcher fixture')
            owner = LauncherInstance(root)
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(Mock(), 'a' * 43, 0))
            server.RequestHandlerClass = handler_for(Mock(), 'a' * 43, server.server_port)
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            owner.publish(server.server_port, 'a' * 43)
            try:
                with patch('world.web_launcher.DIST', root), \
                     patch('world.web_launcher.DesktopSession') as session, \
                     patch('world.web_launcher.open_browser', return_value=True) as browser, \
                     patch('world.web_launcher.ThreadingHTTPServer'):
                    session.create_root.return_value = root
                    self.assertEqual(main(['--worlds-root', str(root), '--binary', '/no/game']), 0)
                    session.assert_not_called()
                    browser.assert_called_once_with(f'http://127.0.0.1:{server.server_port}/#' + 'a' * 43)
            finally:
                server.shutdown()
                thread.join()
                server.server_close()
                owner.close()

    def test_same_root_reuses_authenticated_running_listener_and_releases_on_close(self):
        import threading
        from http.server import ThreadingHTTPServer
        from unittest.mock import Mock
        from world.launcher_instance import LauncherInstance
        from world.web_launcher import handler_for
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = LauncherInstance(root)
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(Mock(), 'a' * 43, 0))
            server.RequestHandlerClass = handler_for(Mock(), 'a' * 43, server.server_port)
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                self.assertTrue(first.owner)
                first.publish(server.server_port, 'a' * 43)
                second = LauncherInstance(root)
                try:
                    self.assertFalse(second.owner)
                    self.assertEqual(second.existing_url(), f'http://127.0.0.1:{server.server_port}/#' + 'a' * 43)
                finally:
                    second.close()
                other_root = root / 'other'
                other_root.mkdir(mode=0o700)
                other = LauncherInstance(other_root)
                self.assertTrue(other.owner)
                other.close()
            finally:
                server.shutdown()
                thread.join()
                server.server_close()
                first.close()
            replacement = LauncherInstance(root)
            self.assertTrue(replacement.owner)
            replacement.close()


class LegacyBrokerTests(unittest.TestCase):
    def test_rejoin_busy_legacy_broker_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            world = root / 'remote-test'
            world.mkdir(mode=0o700)
            remember(world, {'version': 1, 'trainer': 'May', 'token': 'a' * 64,
                             'endpoint': {'host': '127.0.0.1', 'port': 1}, 'pin': 'b' * 64})
            broker = ClientBroker(world / 'transport/world.sock', ('127.0.0.1', 1), fingerprint='b' * 64)
            broker.start()
            session = DesktopSession(root)
            try:
                with self.assertRaisesRegex(SessionError, 'another launcher.*Disconnect.*Quit'):
                    session.rejoin_friend('remote-test')
                self.assertIsNone(session.broker)
                self.assertIsNone(session.state)
                self.assertTrue(Path(broker.socket_path).is_socket())
            finally:
                session.close()
                broker.close()
