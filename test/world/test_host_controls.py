"""Host actions exercise the production authority with disposable Unix sockets."""
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest

from world.client import WorldClient, admin_request
from world.server import WorldServer


class HostControlsTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix='ew-host-')))
        self.socket = self.root / 'world.sock'
        self.server = WorldServer(self.socket, self.root / 'state')
        self.stack.callback(lambda: self.server.close())
        self.alice = self.server.create_identity('alice')
        self.bob = self.server.create_identity('bob')
        self.server.start()

    def action(self, action, **fields):
        return admin_request(self.socket, dict(command='host_controls', action=action, **fields))

    def connect(self, identity, **kwargs):
        client = self.stack.enter_context(WorldClient(self.socket, identity['id'], identity['token'], **kwargs))
        if not kwargs.get('control'):
            client.snapshot()
        return client

    def test_lock_rejects_new_joins_but_keeps_connected_players(self):
        alice = self.connect(self.alice)
        self.assertEqual(self.action('lock'), dict(ok=True, admission='locked', removed=[]))
        with self.assertRaisesRegex(ValueError, 'LOCKED'):
            self.connect(self.bob)
        alice.send_state(1, 0, 1, 10, 12, 2, 7, 1, 'a'*16, 'b'*16)
        self.assertIn('peers', alice.snapshot())
        self.assertEqual(self.action('unlock')['admission'], 'open')
        self.connect(self.bob)

    def test_remove_revokes_all_channels_until_readmitted_without_touching_save(self):
        bob = self.connect(self.bob)
        control = self.connect(self.bob, control=True)
        save = Path(self.bob['save_path'])
        save.write_bytes(b'private disposable trainer fixture')
        before = save.read_bytes()
        self.assertTrue(self.action('remove', trainer='bob')['ok'])
        with self.assertRaisesRegex(ValueError, 'REMOVED'):
            bob._line()
        with self.assertRaisesRegex(ValueError, 'REMOVED'):
            control._line()
        with self.assertRaisesRegex(ValueError, 'REMOVED'):
            self.connect(self.bob)
        self.assertEqual(save.read_bytes(), before)
        self.assertEqual(self.action('status')['removed'], ['bob'])
        self.assertTrue(self.action('allow', trainer='bob')['ok'])
        self.connect(self.bob)
        self.assertEqual(save.read_bytes(), before)

    def test_stop_hosting_preserves_current_session_and_split_leaves_solo_games(self):
        alice, bob = self.connect(self.alice), self.connect(self.bob)
        alice.snapshot()  # Bob's join snapshot.
        self.assertEqual(self.action('stop'), dict(ok=True, admission='stopped', removed=[]))
        alice.send_state(1, 0, 1, 10, 12, 2, 7, 1, 'a'*16, 'b'*16)
        alice.snapshot()
        bob.snapshot()
        self.assertEqual(self.action('split')['admission'], 'stopped')
        for client in (alice, bob):
            with self.assertRaisesRegex(ValueError, 'HOST_SPLIT'):
                client._line()
        for identity in (self.alice, self.bob):
            with self.assertRaisesRegex(ValueError, 'HOST_STOPPED'):
                self.connect(identity)
        self.assertEqual(self.action('unlock')['admission'], 'open')
        self.connect(self.alice)
        self.connect(self.bob)

    def link(self, identity):
        import socket
        sock = self.stack.enter_context(socket.socket(socket.AF_UNIX))
        sock.settimeout(2)
        sock.connect(str(self.socket))
        stream = self.stack.enter_context(sock.makefile('rb'))
        sock.sendall(('HELLO 1 {id} {token} LINK\n'.format(**identity)).encode())
        self.assertTrue(stream.readline().startswith(b'WELCOME '))
        return sock, stream

    def test_remove_and_split_refuse_native_reservations_atomically(self):
        alice, bob = self.connect(self.alice), self.connect(self.bob)
        alice.send_state(1, 0, 1, 10, 12, 4, 7, 1, 'a'*16, 'b'*16)
        bob.send_state(1, 0, 1, 11, 12, 3, 7, 1, 'c'*16, 'd'*16)
        for client, peer in ((alice, 'bob'), (bob, 'alice')):
            while peer not in client.snapshot()['peers']:
                pass
        a, ar = self.link(self.alice)
        b, br = self.link(self.bob)
        a.sendall(b'L OFFER 3 bob\n')
        offer = br.readline().decode().split()
        self.assertEqual(offer[:2], ['L', 'OFFER'])
        sid = offer[2]
        # An offer already reserves both peers. No administrative operation may
        # split a pending or admitted trade, including between link generations.
        expected = dict(ok=False, error='Players are in a native activity. Finish or cancel it first.')
        self.assertEqual(self.action('remove', trainer='bob'), expected)
        self.assertEqual(self.action('split'), expected)
        self.assertIsNone(admin_request(self.socket, dict(command='inspect'))['error'])
        self.assertEqual(self.action('status'), dict(ok=True, admission='open', removed=[]))
        b.sendall(f'L ACCEPT {sid}\n'.encode())
        self.assertTrue(ar.readline().startswith(b'L ADMIT '))
        self.assertTrue(br.readline().startswith(b'L ADMIT '))
        self.assertEqual(self.action('remove', trainer='alice'), expected)
        for sock, slot in ((a, 0), (b, 1)):
            sock.sendall(f'L EVENT 1 {sid} 3 {slot} 1 0 4369 {"0"*32}\n'.encode())
        self.assertTrue(ar.readline().startswith(b'L COMMIT 1 '))
        self.assertTrue(br.readline().startswith(b'L COMMIT 1 '))
        a.sendall(f'L EVENT 2 {sid} 3 0 1 0 4369 {"0"*32}\n'.encode())
        # A close-generation has no response. Read an unrelated socket barrier
        # before checking that the bilateral reservation still blocks removal.
        self.assertEqual(self.action('split'), expected)
        b.sendall(f'L EVENT 5 {sid} 3 1 1 0 4369 {"0"*32}\n'.encode())
        self.assertTrue(ar.readline().startswith(b'L ABORT '))
        self.assertTrue(br.readline().startswith(b'L ABORT '))
        self.assertTrue(self.action('split')['ok'])

    def test_policy_and_removed_trainers_survive_authority_restart(self):
        self.assertTrue(self.action('remove', trainer='bob')['ok'])
        self.assertTrue(self.action('lock')['ok'])
        self.server.close()
        self.server = WorldServer(self.socket, self.root / 'state')
        self.server.start()
        self.assertEqual(self.action('status'), dict(ok=True, admission='locked', removed=['bob']))
        with self.assertRaisesRegex(ValueError, 'REMOVED'):
            WorldClient(self.socket, self.bob['id'], self.bob['token'])
        with self.assertRaisesRegex(ValueError, 'LOCKED'):
            WorldClient(self.socket, self.alice['id'], self.alice['token'])

    def test_game_and_control_channels_cannot_apply_host_actions(self):
        import json
        alice = self.connect(self.alice, control=True)
        alice.sock.sendall(json.dumps(dict(command='host_controls', action='lock')).encode() + b'\n')
        self.assertFalse(json.loads(alice._line())['ok'])
        bob = self.connect(self.bob)
        bob.sock.sendall(b'HOST lock\n')
        with self.assertRaisesRegex(ValueError, 'MALFORMED'):
            bob._line()
        self.assertEqual(self.action('status')['admission'], 'open')

    def test_strict_host_payloads_never_change_policy_on_refusal(self):
        bad = [dict(action='lock', trainer='bob'), dict(action='unlock', extra=True),
               dict(action='remove'), dict(action='remove', trainer='../bob'),
               dict(action='remove', trainer='unknown'), dict(action='allow', trainer=[]),
               dict(action=['lock']), dict(action=True), dict(action='split', force=True)]
        for fields in bad:
            with self.subTest(fields=fields):
                request = dict(command='host_controls', **fields)
                self.assertFalse(admin_request(self.socket, request)['ok'])
                self.assertEqual(self.action('status'), dict(ok=True, admission='open', removed=[]))
        self.assertIsNone(admin_request(self.socket, dict(command='inspect'))['error'])


class HostControlsViewTests(unittest.TestCase):
    def test_existing_world_window_buttons_control_only_the_current_host(self):
        import os
        if not os.environ.get('DISPLAY'):
            self.skipTest('isolated graphical test display required')
        import tkinter as tk
        import time
        from world.session import DesktopApp, DesktopSession
        with tempfile.TemporaryDirectory(prefix='ew-ui-') as tmp:
            session = DesktopSession(DesktopSession.create_root(Path(tmp) / 'worlds'))
            session.create_world('test')
            session.host('test')
            window = tk.Tk()
            app = DesktopApp(window, session, Path('/usr/bin/false'), None)
            try:
                self.assertTrue(hasattr(app, 'host_controls'), 'existing world window has no host controls')
                panel = app.host_controls
                panel.buttons['lock'].invoke()
                deadline = time.monotonic() + 4
                while panel.future is not None and time.monotonic() < deadline:
                    window.update()
                    time.sleep(.01)
                self.assertIsNone(panel.future)
                self.assertIn('locked', panel.message.get().lower())
                self.assertEqual(session.server.host_controls.status()['admission'], 'locked')
                panel.buttons['unlock'].invoke()
                deadline = time.monotonic() + 4
                while panel.future is not None and time.monotonic() < deadline:
                    window.update()
                    time.sleep(.01)
                self.assertEqual(session.server.host_controls.status()['admission'], 'open')
                # Joining an existing local world is not hosting it, even though
                # the admin socket happens to exist on the same computer.
                host = session.server
                session.server = None
                panel.buttons['lock'].invoke()
                self.assertIsNone(panel.future)
                self.assertIn('Host a world', panel.message.get())
                self.assertEqual(host.host_controls.status()['admission'], 'open')
                session.server = host
                from concurrent.futures import Future
                app.pending = Future()  # A lifecycle operation owns the executor.
                panel.buttons['lock'].invoke()
                self.assertIsNone(panel.future, 'host action queued behind a world lifecycle change')
                self.assertIn('Wait', panel.message.get())
                app.pending = None
                # Tk's real modal dialog pumps events. A lifecycle change can
                # start while confirmation is open, so recheck after Yes too.
                window.after(20, lambda: setattr(app, 'pending', Future()))
                window.after(50, lambda: window.tk.call('.__tk__messagebox.yes', 'invoke'))
                panel.buttons['split'].invoke()
                self.assertIsNone(panel.future, 'confirmation queued a stale host action')
                self.assertEqual(host.host_controls.status()['admission'], 'open')
                app.pending = None
            finally:
                app.executor.shutdown(wait=True)
                session.close()
                window.destroy()


if __name__ == '__main__':
    unittest.main()
