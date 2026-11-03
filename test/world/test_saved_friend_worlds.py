"""Saved friend connections use disposable roots and loopback TLS only."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from world.session import DesktopSession


class SavedFriendWorldTests(unittest.TestCase):
    def setUp(self):
        if not shutil.which('openssl'):
            self.skipTest('TLS fixture needs openssl')
        self.tmp = tempfile.TemporaryDirectory(prefix='ew-saved-friends-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.host = DesktopSession(self.root)
        self.addCleanup(self.host.close)
        self.host.create_world('host')
        self.host.host('host')
        cert, key = self.host.tls_material()
        self.address = self.host.share(cert, key, ('127.0.0.1', 0))
        self.invite = self.root/'invitation.json'
        self.host.export_invitation('friend', self.invite, self.address)
        self.pin = json.loads(self.invite.read_text())['pin']
        self.guest = DesktopSession(self.root)
        self.addCleanup(self.guest.close)

    def connect(self):
        return self.guest.connect_remote('visited', self.invite, self.address, self.pin)

    def test_rejoin_after_restart_without_original_invitation_preserves_progress(self):
        paths = self.connect()
        paths['save'].write_bytes(b'disposable progress sentinel')
        self.guest.close()
        self.invite.unlink()
        replacement = DesktopSession(self.root)
        self.addCleanup(replacement.close)
        self.assertEqual(replacement.friend_worlds(), [{'name': 'visited', 'trainer': 'friend'}])
        resumed = replacement.rejoin_friend('visited')
        self.assertEqual(resumed['save'].read_bytes(), b'disposable progress sentinel')
        self.assertEqual(replacement.remote_trainer, 'friend')
        self.assertEqual((self.root/'visited/.friend.json').stat().st_mode & 0o777, 0o600)

    def test_forget_removes_bookmark_not_private_progress(self):
        paths = self.connect()
        paths['save'].write_bytes(b'private progress')
        config = paths['config'].read_bytes()
        self.guest.close()
        self.guest.forget_friend('visited')
        self.assertEqual(self.guest.friend_worlds(), [])
        self.assertEqual(paths['save'].read_bytes(), b'private progress')
        self.assertEqual(paths['config'].read_bytes(), config)
        self.assertTrue((self.root/'visited/remote.json').is_file())
        with self.assertRaises(ValueError):
            self.guest.rejoin_friend('visited')
        self.assertEqual(self.connect()['save'].read_bytes(), b'private progress')

    def test_failed_authentication_never_remembers_world(self):
        value = json.loads(self.invite.read_text())
        value['token'] = '0'*64
        self.invite.write_text(json.dumps(value))
        with self.assertRaises((ValueError, OSError)):
            self.connect()
        self.assertEqual(self.guest.friend_worlds(), [])
        self.assertFalse((self.root/'visited/.friend.json').exists())

    def test_unsafe_bookmark_fails_closed_without_changing_progress(self):
        paths = self.connect()
        self.guest.close()
        paths['save'].write_bytes(b'keep')
        marker = self.root/'visited/.friend.json'
        content = marker.read_bytes()
        marker.chmod(0o644)
        with self.assertRaises(ValueError):
            self.guest.rejoin_friend('visited')
        marker.chmod(0o600)
        marker.unlink()
        outside = self.root/'outside.json'
        outside.write_bytes(content)
        marker.symlink_to(outside)
        with self.assertRaises(ValueError):
            self.guest.rejoin_friend('visited')
        self.assertEqual(paths['save'].read_bytes(), b'keep')
        self.assertEqual(outside.read_bytes(), content)


    def test_changed_pin_is_rejected_and_saved_connection_is_preserved(self):
        self.connect()
        self.guest.close()
        marker = self.root/'visited/.friend.json'
        original = marker.read_bytes()
        wrong_pin = ('0' if self.pin[0] != '0' else '1') + self.pin[1:]
        with self.assertRaises((ValueError, OSError)):
            self.guest.connect_remote('visited', self.invite, self.address, wrong_pin)
        self.assertEqual(marker.read_bytes(), original)
        self.assertIsNone(self.guest.state)
        self.assertEqual(self.guest.rejoin_friend('visited')['profile'].name, 'friend')

    def test_connected_world_cannot_be_forgotten_or_rejoined(self):
        self.connect()
        with self.assertRaises(ValueError):
            self.guest.forget_friend('visited')
        with self.assertRaises(ValueError):
            self.guest.rejoin_friend('visited')
        self.assertEqual(len(self.guest.friend_worlds()), 1)

    def test_move_restore_keeps_bookmark_with_progress(self):
        paths = self.connect()
        paths['save'].write_bytes(b'private move sentinel')
        self.guest.close()
        token = self.guest.delete_world('visited')
        self.assertEqual(self.guest.friend_worlds(), [])
        self.guest.restore_world(token)
        self.assertEqual(self.guest.friend_worlds(), [{'name': 'visited', 'trainer': 'friend'}])
        self.assertEqual(self.guest.rejoin_friend('visited')['save'].read_bytes(), b'private move sentinel')

    def test_duplicate_keys_and_hardlinks_fail_closed(self):
        import os
        from world.friend_worlds import read
        self.connect()
        self.guest.close()
        directory = self.root/'visited'
        marker = directory/'.friend.json'
        content = marker.read_bytes()
        marker.write_bytes(b'{"trainer":"other",' + content[1:])
        with self.assertRaises(ValueError):
            read(directory)
        self.assertEqual(self.guest.friend_worlds(), [])
        marker.write_bytes(content)
        os.link(marker, self.root/'linked-bookmark')
        with self.assertRaises(ValueError):
            read(directory)


class SavedFriendViewTests(unittest.TestCase):
    def test_rejoin_selects_the_same_world_and_assigned_trainer(self):
        from unittest.mock import Mock
        from world.session import DesktopApp
        app = DesktopApp.__new__(DesktopApp)
        app.session = Mock()
        app.values = lambda: {'friend_world': 'visited'}
        app.fields = {'world': Mock(), 'trainer': Mock()}
        app.refresh = Mock()
        paths = {'profile': Path('/disposable/visited/trainers/friend')}
        app.session.rejoin_friend.return_value = paths
        app.rejoin_friend()
        app.session.rejoin_friend.assert_called_once_with('visited')
        self.assertIs(app.remote_paths, paths)
        app.fields['world'].set.assert_called_once_with('visited')
        app.fields['trainer'].set.assert_called_once_with('friend')

    def test_forget_requires_confirmation_and_never_calls_delete(self):
        from unittest.mock import Mock, patch
        from world.session import DesktopApp
        app = DesktopApp.__new__(DesktopApp)
        app.session, app.window, app.refresh = Mock(), Mock(), Mock()
        app.values = lambda: {'friend_world': 'visited'}
        with patch('tkinter.messagebox.askyesno', return_value=False):
            app.forget_friend()
        app.session.forget_friend.assert_not_called()
        with patch('tkinter.messagebox.askyesno', return_value=True):
            app.forget_friend()
        app.session.forget_friend.assert_called_once_with('visited')
        app.session.delete_world.assert_not_called()


if __name__ == '__main__':
    unittest.main()
