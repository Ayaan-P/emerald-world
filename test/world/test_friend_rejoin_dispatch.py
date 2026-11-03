"""Linux launcher rejoin checks. No GUI or external network. Disposable saves only."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
import unittest
from unittest.mock import Mock

from world.session import DesktopApp


class Value:
    def __init__(self, value=''):
        self.value = value
        self.writers = []

    def get(self):
        return self.value

    def set(self, value):
        self.writers.append(threading.get_ident())
        self.value = value


class FriendRejoinDispatchTests(unittest.TestCase):
    def app(self):
        app = DesktopApp.__new__(DesktopApp)
        app.session = Mock(status='TLS verified.')
        app.executor = ThreadPoolExecutor(max_workers=1)
        self.addCleanup(app.executor.shutdown, wait=True)
        app.pending = app.pending_kind = app.poll_future = None
        app.next_poll = float('inf')
        app.closing = False
        app.window = Mock()
        app.buttons = [Mock()]
        app.message = Value()
        app.fields = {key: Value(value) for key, value in
                      [('friend_world', 'visit'), ('world', 'old'), ('trainer', 'old-trainer')]}
        app.refresh = Mock()
        app.remote_paths = None
        return app

    def test_rejoin_runs_in_worker_then_updates_selected_world_on_ui_thread(self):
        app = self.app()
        main = threading.get_ident()
        workers = []
        paths = {'profile': Path('/disposable/visit/trainers/friend')}
        def rejoin(name):
            workers.append(threading.get_ident())
            return paths
        app.session.rejoin_friend.side_effect = rejoin
        app.submit(app.rejoin_friend)
        self.assertIsNotNone(app.pending)
        self.assertEqual(app.pending_kind, 'rejoin_friend')
        self.assertEqual(app.fields['trainer'].get(), 'old-trainer')
        app.pending.result(timeout=3)
        self.assertNotEqual(workers, [main])
        app.session.rejoin_friend.assert_called_once_with('visit')
        app.fields['friend_world'].set('different-selection')
        app.tick()
        self.assertIsNone(app.pending)
        self.assertEqual(app.remote_paths, paths)
        self.assertEqual(app.fields['world'].get(), 'visit')
        self.assertEqual(app.fields['trainer'].get(), 'friend')
        self.assertEqual(app.fields['world'].writers, [main])
        self.assertEqual(app.fields['trainer'].writers, [main])
        app.refresh.assert_called_once()

    def test_rejoin_failure_keeps_previous_fields_and_hides_exception_text(self):
        app = self.app()
        app.session.rejoin_friend.side_effect = RuntimeError('PRIVATE_INVITATION_SENTINEL')
        app.submit(app.rejoin_friend)
        self.assertIsNotNone(app.pending)
        try:
            app.pending.result(timeout=3)
        except RuntimeError:
            pass
        app.tick()
        self.assertIsNone(app.pending)
        self.assertIsNone(app.remote_paths)
        self.assertEqual(app.fields['world'].get(), 'old')
        self.assertEqual(app.fields['trainer'].get(), 'old-trainer')
        self.assertNotIn('PRIVATE_INVITATION_SENTINEL', app.message.get())
        self.assertIn('invitation', app.message.get())
        app.refresh.assert_not_called()
        app.buttons[0].state.assert_called_with(['!disabled'])

    def test_empty_selection_never_submits_network_work(self):
        app = self.app()
        app.fields['friend_world'].set('')
        app.submit(app.rejoin_friend)
        self.assertIsNone(app.pending)
        app.session.rejoin_friend.assert_not_called()
        self.assertEqual(app.message.get(), 'Choose a saved friend world.')

    def test_real_loopback_rejoin_dispatch_preserves_disposable_save(self):
        import json
        import shutil
        import tempfile
        from world.session import DesktopSession
        if not shutil.which('openssl'):
            self.skipTest('local TLS fixture needs openssl')
        with tempfile.TemporaryDirectory(prefix='ew-rejoin-') as tmp:
            root = Path(tmp)
            guests = root/'guests'
            guests.mkdir(mode=0o700)
            with DesktopSession(root) as host, DesktopSession(guests) as guest:
                host.create_world('host')
                host.host('host')
                cert, key = host.tls_material()
                address = host.share(cert, key, ('127.0.0.1', 0))
                invitation = root/'friend.json'
                host.export_invitation('friend', invitation, address)
                pin = json.loads(invitation.read_text())['pin']
                paths = guest.connect_remote('visit', invitation, address, pin)
                paths['save'].write_bytes(b'disposable private progress')
                config = paths['config'].read_bytes()
                guest.close()
                invitation.unlink()  # The per-world bookmark is self-contained.
                app = self.app()
                app.session = guest
                app.submit(app.rejoin_friend)
                app.pending.result(timeout=8)
                app.tick()
                if app.poll_future is not None:
                    app.poll_future.result(timeout=8)
                self.assertEqual(app.fields['world'].get(), 'visit')
                self.assertEqual(app.fields['trainer'].get(), 'friend')
                self.assertEqual(paths['save'].read_bytes(), b'disposable private progress')
                self.assertEqual(paths['config'].read_bytes(), config)
                guest.close()
                guest.forget_friend('visit')
                self.assertEqual(guest.friend_worlds(), [])
                self.assertTrue(paths['save'].exists())

    def test_rejected_saved_rejoin_releases_endpoint_and_can_retry(self):
        import json
        import shutil
        import tempfile
        from world.launcher import admin
        from world.session import DesktopSession
        if not shutil.which('openssl'):
            self.skipTest('local TLS fixture needs openssl')
        with tempfile.TemporaryDirectory(prefix='ew-reject-') as tmp:
            root = Path(tmp)
            guests = root/'guests'
            guests.mkdir(mode=0o700)
            with DesktopSession(root) as host, DesktopSession(guests) as guest:
                host.create_world('host')
                host.host('host')
                cert, key = host.tls_material()
                address = host.share(cert, key, ('127.0.0.1', 0))
                invitation = root/'friend.json'
                host.export_invitation('friend', invitation, address)
                pin = json.loads(invitation.read_text())['pin']
                paths = guest.connect_remote('visit', invitation, address, pin)
                paths['save'].write_bytes(b'private rejection progress')
                guest.close()
                marker = guests/'visit/.friend.json'
                originals = {p: p.read_bytes() for p in
                             (marker, paths['save'], paths['config'], guests/'visit/remote.json')}
                app = self.app()
                app.session = guest
                endpoint = host.state/'transport/world.sock'
                for deny, allow in [('lock', 'unlock'), ('remove', 'allow')]:
                    request = {'command': 'host_controls', 'action': deny}
                    if deny == 'remove':
                        request['trainer'] = 'friend'
                    result = admin(endpoint, request)
                    self.assertTrue(result['ok'])
                    app.submit(app.rejoin_friend)
                    with self.assertRaises((ValueError, OSError)):
                        app.pending.result(timeout=8)
                    app.tick()
                    if app.poll_future is not None:
                        app.poll_future.result(timeout=8)
                        app.tick()
                    self.assertIsNone(guest.state)
                    self.assertIsNone(guest.broker)
                    self.assertIsNone(app.remote_paths)
                    self.assertEqual(app.fields['world'].get(), 'old')
                    self.assertEqual(app.fields['trainer'].get(), 'old-trainer')
                    for path, content in originals.items():
                        self.assertEqual(path.read_bytes(), content)
                    self.assertNotIn(json.loads(marker.read_text())['token'], app.message.get())
                    self.assertFalse((guests/'visit/transport/world.sock').exists())
                    request['action'] = allow
                    self.assertTrue(admin(endpoint, request)['ok'])
                app.submit(app.rejoin_friend)
                app.pending.result(timeout=8)
                app.tick()
                if app.poll_future is not None:
                    app.poll_future.result(timeout=8)
                self.assertEqual(app.fields['world'].get(), 'visit')
                self.assertEqual(app.fields['trainer'].get(), 'friend')
                self.assertIsNotNone(guest.broker)
                self.assertEqual(paths['save'].read_bytes(), originals[paths['save']])

    def test_busy_operation_does_not_enqueue_a_second_rejoin(self):
        app = self.app()
        app.pending = Mock()
        app.submit(app.rejoin_friend)
        app.session.rejoin_friend.assert_not_called()


if __name__ == '__main__':
    unittest.main()
