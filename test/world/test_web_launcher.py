"""Unit checks for the local launcher bridge. No live world or game is used."""
import base64
import json
import os
import time
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from world.session import DesktopSession, SessionError
from world.web_launcher import LauncherBridge, handler_for, install_shortcut


class WebLauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.session = Mock()
        self.session.root = Path(self.tmp.name)
        self.session.friend_worlds.return_value = []
        self.session.world_library.return_value = []
        self.session.state = None
        self.session.remote_trainer = None
        self.session.games = {}
        self.session.status = 'Ready'
        self.bridge = LauncherBridge(self.session, '/nonexistent/game')

    def invitation(self):
        return {'version': 1, 'trainer': 'Trainer', 'token': 'a' * 64,
                'endpoint': {'host': 'example.org', 'port': 8765}, 'pin': 'b' * 64}

    def test_join_uses_validated_temporary_file_and_never_returns_token(self):
        seen = {}
        def connect(name, path, endpoint, pin):
            seen.update(name=name, path=path, text=path.read_text(), endpoint=endpoint, pin=pin)
            self.session.state = Path('/tmp/world')
            self.session.remote_trainer = 'Trainer'
            return {'profile': Path('/tmp/world/trainers/Trainer')}
        self.session.connect_remote.side_effect = connect
        result = self.bridge.action('join', {'invitation': json.dumps(self.invitation())})
        self.assertEqual(json.loads(seen['text']), self.invitation())
        self.assertEqual(seen['endpoint'], ('example.org', 8765))
        self.assertFalse(seen['path'].exists())
        self.assertNotIn('a' * 64, json.dumps(result))
        self.assertTrue(result['connected'])

    def test_duplicate_invitation_keys_and_oversized_files_are_rejected(self):
        raw = json.dumps(self.invitation()).replace('"version": 1', '"version": 1, "version": 1')
        with self.assertRaisesRegex(SessionError, 'Invalid invitation'):
            self.bridge.action('join', {'invitation': raw})
        with self.assertRaises(SessionError):
            self.bridge.action('join', {'invitation': 'x' * 4097})
        self.session.connect_remote.assert_not_called()

    def test_rejoin_and_forget_use_existing_session(self):
        self.session.rejoin_friend.return_value = {'profile': Path('/tmp/world/trainers/Trainer')}
        self.bridge.action('rejoin', {'world': 'world1'})
        self.session.rejoin_friend.assert_called_once_with('world1')
        self.bridge.action('forget', {'world': 'world2'})
        self.session.forget_friend.assert_called_once_with('world2')

    def test_snapshot_names_worlds_and_only_shows_running_games(self):
        self.session.friend_worlds.return_value = [
            {'name': 'remote-12345678', 'trainer': 'May'},
            {'name': 'remote-abcdefgh', 'trainer': 'Brendan'}]
        self.session._world.side_effect = lambda key: Path('/tmp') / key
        running, exited = Mock(), Mock()
        running.poll.return_value = None
        exited.poll.return_value = 0
        self.session.games = {'May': (running, {}), 'Brendan': (exited, {})}
        with patch('world.world_library._read_metadata', side_effect=[{'display_name': 'remote-12345678', 'tags': []}, {'display_name': 'Our Hoenn', 'tags': []}]):
            result = self.bridge.snapshot()
        self.assertEqual(result['worlds'][0]['name'], 'Friend’s world · 5678')
        self.assertEqual(result['worlds'][1]['name'], 'Our Hoenn')
        self.assertEqual(result['games'], ['May'])

    def test_offline_uses_saved_trainer_and_explicit_copy_choice(self):
        self.session.friend_worlds.return_value = [{'name': 'world1', 'trainer': 'May'}]
        self.session.managed_display = Mock(display=':90')
        with patch('scripts.linux_client.binary_ready', return_value=True):
            self.bridge.action('offline', {'world': 'world1', 'copy': True, 'trainer': 'someone-else'})
        self.session.launch_offline.assert_called_once_with('world1', 'May', Path('/nonexistent/game'), ':90', copy_online=True)

    def test_offline_refuses_active_session_and_unknown_world(self):
        self.session.friend_worlds.return_value = [{'name': 'world1', 'trainer': 'May'}]
        with self.assertRaises(SessionError):
            self.bridge.action('offline', {'world': 'elsewhere', 'copy': False})
        self.session.state = Path('/tmp/world1')
        with self.assertRaises(SessionError):
            self.bridge.action('offline', {'world': 'world1', 'copy': False})
        self.session.launch_offline.assert_not_called()

    def test_remote_saved_world_uses_existing_private_label(self):
        from world.friend_worlds import remember
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            world = root / 'remote-1234'
            world.mkdir(mode=0o700)
            remember(world, self.invitation())
            session = DesktopSession(root)
            session.rename_world('remote-1234', 'Our Hoenn', [])
            try:
                result = LauncherBridge(session, '/nonexistent/game').snapshot()
                self.assertEqual(result['worlds'][0]['name'], 'Our Hoenn')
                (world / '.library.json').write_text('{bad json')
                result = LauncherBridge(session, '/nonexistent/game').snapshot()
                self.assertEqual(result['worlds'][0]['name'], 'Friend’s world · 1234')
            finally:
                session.close()

    def test_presence_uses_only_fresh_sanitized_own_game_telemetry(self):
        telemetry = Path(self.tmp.name) / 'telemetry.json'
        telemetry.write_text(json.dumps({'trainer': 'May', 'connected': True, 'revision': 1, 'frame': 2,
            'roster': [{'trainer': 'Brendan', 'nearby': True, 'ready': True, 'rendered': True},
                       {'trainer': 'Hidden', 'nearby': False, 'ready': True, 'rendered': True},
                       {'trainer': '../bad', 'nearby': True, 'ready': True, 'rendered': True}]}))
        process = Mock()
        process.poll.return_value = None
        self.session.remote_trainer = 'May'
        self.session.games = {'May': (process, {'telemetry': telemetry})}
        presence = self.bridge.game_presence()
        self.assertEqual(presence, {'state': 'connected', 'nearby': [{'trainer': 'Brendan', 'ready': True, 'rendered': True}]})
        os.utime(telemetry, (time.time() - 30, time.time() - 30))
        self.assertEqual(self.bridge.game_presence()['state'], 'waiting')

    def test_solo_profiles_remain_visible_without_a_bookmark(self):
        from world.offline import offline_profile
        root = Path(self.tmp.name)
        with offline_profile(root / 'solo-abc123', 'May') as paths:
            paths['save'].write_bytes(b'private fixture')
        session = DesktopSession(root)
        try:
            result = LauncherBridge(session, '/nonexistent/game').snapshot()
            self.assertEqual(result['offline_saves'], [{'world': 'solo-abc123', 'trainer': 'May', 'name': 'Solo adventure · c123'}])
            self.assertEqual(result['worlds'], [])
        finally:
            session.close()

    def test_new_solo_starts_a_new_isolated_world(self):
        self.session.managed_display = Mock(display=':90')
        with patch('scripts.linux_client.binary_ready', return_value=True), patch('world.web_launcher.secrets.token_hex', return_value='abc123'):
            self.bridge.action('solo_new', {'trainer': 'May'})
        self.session.launch_offline.assert_called_once_with('solo-abc123', 'May', Path('/nonexistent/game'), ':90', copy_online=False)
        self.session.connect_remote.assert_not_called()

    def test_solo_import_stages_private_copy_and_removes_temporary_file(self):
        self.session.managed_display = Mock(display=':90')
        seen = {}
        def start(*args, **kwargs):
            path = kwargs['seed_save']
            seen['path'], seen['data'], seen['mode'] = path, path.read_bytes(), path.stat().st_mode & 0o777
        self.session.launch_offline.side_effect = start
        fixture = b'private save fixture'
        with patch('scripts.linux_client.binary_ready', return_value=True), patch('world.web_launcher.secrets.token_hex', return_value='abc123'):
            self.bridge.action('solo_new', {'trainer': 'May', 'seed': base64.b64encode(fixture).decode()})
        self.assertEqual(seen['data'], fixture)
        self.assertEqual(seen['mode'], 0o600)
        self.assertFalse(seen['path'].exists())

    def test_solo_import_rejects_invalid_data_without_launching(self):
        with self.assertRaises(SessionError):
            self.bridge.action('solo_new', {'trainer': 'May', 'seed': 'not base64!?'})
        self.session.launch_offline.assert_not_called()

    def test_unknown_solo_profile_cannot_be_resumed(self):
        with self.assertRaises(SessionError):
            self.bridge.action('solo_resume', {'world': 'unknown', 'trainer': 'May'})
        self.session.launch_offline.assert_not_called()

    def test_favorite_preserves_name_and_other_tags(self):
        self.session.friend_worlds.return_value = [{'name': 'world1', 'trainer': 'May'}]
        self.session._world.return_value = Path('/tmp/world1')
        with patch('world.world_library._read_metadata', return_value={'display_name': 'Hoenn', 'tags': ['friends']}):
            self.bridge.action('favorite', {'world': 'world1', 'favorite': True})
        self.session.rename_world.assert_called_once_with('world1', 'Hoenn', ['friends', 'favorite'])

    def test_rename_preserves_existing_world_tags(self):
        self.session.friend_worlds.return_value = [{'name': 'world1', 'trainer': 'May'}]
        self.session._world.return_value = Path('/tmp/world1')
        with patch('world.world_library._read_metadata', return_value={'display_name': 'Old', 'tags': ['friends']}):
            self.bridge.action('rename', {'world': 'world1', 'label': 'Hoenn'})
        self.session.rename_world.assert_called_once_with('world1', 'Hoenn', ['friends'])

    def test_setup_reports_game_dependencies_without_tkinter(self):
        checks = [('tkinter', False, 'Tk only'), ('bwrap', False, 'Install bubblewrap.'),
                  ('binary', True, 'Build the game.')]
        with patch('scripts.linux_client.prerequisites', return_value=checks):
            result = self.bridge.snapshot()['setup']
        self.assertEqual([item['name'] for item in result], ['bwrap', 'binary'])
        self.assertFalse(result[0]['ready'])
        self.assertEqual(result[0]['help'], 'Install bubblewrap.')

    def test_reconnect_uses_only_current_saved_world(self):
        self.session.state = Path('/tmp/world1')
        self.session.remote_trainer = 'May'
        self.session.friend_worlds.return_value = [{'name': 'world1', 'trainer': 'May'}]
        self.session.rejoin_friend.return_value = {'profile': Path('/tmp/world1/trainers/May')}
        self.bridge.action('reconnect', {})
        self.session.disconnect.assert_called_once_with()
        self.session.rejoin_friend.assert_called_once_with('world1')
        self.assertEqual(self.bridge.remote_paths, {'profile': Path('/tmp/world1/trainers/May')})

    def test_reconnect_without_saved_bookmark_does_not_disconnect(self):
        self.session.state = Path('/tmp/world1')
        self.session.remote_trainer = 'May'
        with self.assertRaisesRegex(SessionError, 'no longer saved'):
            self.bridge.action('reconnect', {})
        self.session.disconnect.assert_not_called()

    def test_switching_worlds_requires_disconnect(self):
        self.session.state = Path('/tmp/connected')
        with self.assertRaisesRegex(SessionError, 'Disconnect'):
            self.bridge.action('rejoin', {'world': 'world2'})
        self.session.rejoin_friend.assert_not_called()

    def test_running_offline_game_blocks_rejoin(self):
        process = Mock()
        process.poll.return_value = None
        self.session.games = {'offline/May': (process, {})}
        with self.assertRaises(SessionError):
            self.bridge.action('rejoin', {'world': 'world1'})
        self.session.rejoin_friend.assert_not_called()

    def test_shortcut_is_idempotent_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'applications'
            target = install_shortcut(directory)
            self.assertEqual(target, directory / 'emerald-world-react.desktop')
            original = target.read_text()
            self.assertIn('-m world.web_launcher', original)
            self.assertEqual(install_shortcut(directory), target)
            target.write_text('custom shortcut')
            with self.assertRaises(ValueError):
                install_shortcut(directory)
            self.assertEqual(target.read_text(), 'custom shortcut')

    def test_auth_requires_exact_host_capability_and_post_origin(self):
        handler_type = handler_for(self.bridge, 'secret', 8912)
        handler = handler_type.__new__(handler_type)
        handler.headers = {'Host': '127.0.0.1:8912', 'Authorization': 'Bearer secret',
                           'Origin': 'http://127.0.0.1:8912'}
        self.assertTrue(handler.authorized(post=True))
        handler.headers['Origin'] = 'https://attacker.example'
        self.assertFalse(handler.authorized(post=True))
        handler.headers['Origin'] = 'http://127.0.0.1:8912'
        handler.headers['Host'] = 'attacker.example:8912'
        self.assertFalse(handler.authorized(post=True))
        handler.headers['Host'] = '127.0.0.1:8912'
        handler.headers['Authorization'] = 'Bearer wrong'
        self.assertFalse(handler.authorized(post=True))


if __name__ == '__main__':
    unittest.main()
