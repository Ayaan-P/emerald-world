"""Native personal settings with disposable files and real profile locks. No sockets."""
import ctypes
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from world.launcher import ProfileLock, profile_paths
from world.personal_settings import DEFAULTS, KEYS, MAX_SIZE, read_settings, write_settings
from world.session import SessionError
from world.web_launcher import LauncherBridge


class PersonalSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = self.enterContext(tempfile.TemporaryDirectory())
        self.world = Path(self.tmp) / 'e-localworld12'
        self.world.mkdir(mode=0o700)
        self.paths = profile_paths(self.world, 'Player', engine='expansion-native')
        self.profile = self.paths['profile']
        self.profile.mkdir(parents=True, mode=0o700)
        self.settings = self.profile / 'settings.ini'

    def read(self):
        return read_settings(self.world, 'Player')

    def save(self, changes, revision=None):
        return write_settings(self.world, 'Player', changes, revision or self.read()['revision'])

    def test_missing_file_reads_native_defaults_without_creating_any_files(self):
        before = list(self.world.rglob('*'))
        result = self.read()
        self.assertEqual(result['values'], DEFAULTS)
        self.assertFalse(result['exists'])
        self.assertEqual(list(self.world.rglob('*')), before)
        self.assertFalse(self.settings.exists())

    def test_writes_actual_expansion_filename_and_preserves_save_legacy_and_other_profile(self):
        self.paths['settings'].write_bytes(b'[video]\nscale=2\n')
        self.paths['save'].write_bytes(b'disposable save sentinel')
        other = self.profile.parent / 'Other'
        other.mkdir()
        (other / 'settings.ini').write_bytes(b'scale=6\n')
        result = self.save({'scale': 4, 'fullscreen': 'yes', 'a': 'space'})
        self.assertEqual(result['values']['scale'], 4)
        self.assertEqual(result['values']['a'], 'space')
        self.assertEqual(self.settings.read_text(), 'scale = 4\nfullscreen = yes\na = space\n')
        self.assertEqual(self.paths['save'].read_bytes(), b'disposable save sentinel')
        self.assertEqual(self.paths['settings'].read_bytes(), b'[video]\nscale=2\n')
        self.assertEqual((other / 'settings.ini').read_bytes(), b'scale=6\n')
        self.assertEqual(self.settings.stat().st_mode & 0o777, 0o600)

    def test_preserves_comments_unmanaged_keys_bom_crlf_and_custom_binding(self):
        original = b'\xef\xbb\xbf# player comment\r\nfast_forward = tab\r\npad_overlay = y\r\nA = international1\r\nscale=2\r\nscale = 5\r\n'
        self.settings.write_bytes(original)
        before = self.read()
        self.assertEqual(before['values']['scale'], 5)
        self.assertIsNone(before['values']['a'])
        self.assertEqual(before['custom'], ['a'])
        self.save({'scale': 3})
        self.assertEqual(self.settings.read_bytes(), original[:original.index(b'scale=2')] + b'scale = 3\r\n')
        self.assertIsNone(self.read()['values']['a'])

    def test_only_managed_fields_accept_exact_supported_types_and_values(self):
        for changes in ({}, {'scale': True}, {'scale': 0}, {'scale': 17}, {'scale': 1.5},
                {'fullscreen': 'maybe'}, {'a': 'f1'}, {'a': 'q\nfullscreen=yes'}, {'a': 'SPACE'},
                {'tera': True}, {'fast_forward_speed': 'unlimited'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.save(changes)
        self.assertFalse(self.settings.exists())

    def test_revisions_detect_manual_edit_and_missing_versus_empty_file(self):
        revision = self.read()['revision']
        self.settings.write_bytes(b'')
        with self.assertRaisesRegex(ValueError, 'Settings changed'):
            self.save({'scale': 4}, revision)
        revision = self.read()['revision']
        self.settings.write_bytes(b'scale = 2\n')
        with self.assertRaisesRegex(ValueError, 'Settings changed'):
            self.save({'scale': 4}, revision)
        self.assertEqual(self.settings.read_bytes(), b'scale = 2\n')

    def test_checks_for_an_edit_during_save_and_cleans_temporary_files(self):
        self.settings.write_bytes(b'scale = 2\n')
        revision = self.read()['revision']
        with patch('world.personal_settings._read', side_effect=[b'scale = 2\n', b'scale = 5\n']):
            with self.assertRaisesRegex(ValueError, 'Settings changed'):
                self.save({'scale': 4}, revision)
        self.assertEqual(self.settings.read_bytes(), b'scale = 2\n')
        self.assertEqual(list(self.profile.glob('.settings-*')), [])

    def test_running_game_lock_blocks_write_without_stopping_game(self):
        with ProfileLock(self.world, 'Player', engine='expansion-native'):
            with self.assertRaisesRegex(ValueError, 'already in use'):
                self.save({'scale': 4})
        self.assertFalse(self.settings.exists())

    def test_offline_profile_uses_separate_settings_and_existing_offline_lock(self):
        offline = self.world / '.offline'
        offline.mkdir(mode=0o700)
        marker = offline / '.offline-copy'
        marker.write_text('Emerald offline copy v1\n')
        marker.chmod(0o600)
        paths = profile_paths(offline, 'Player', engine='expansion-native')
        paths['profile'].mkdir(parents=True, mode=0o700)
        before = read_settings(self.world, 'Player', offline=True)
        write_settings(self.world, 'Player', {'b': 'j'}, before['revision'], offline=True)
        self.assertEqual((paths['profile'] / 'settings.ini').read_text(), 'b = j\n')
        self.assertFalse(self.settings.exists())

    def test_symlink_hardlink_fifo_directory_and_unsafe_modes_are_rejected(self):
        outside = Path(self.tmp) / 'outside'
        outside.write_bytes(b'scale=4')
        for kind in ('symlink', 'hardlink', 'fifo', 'directory', 'writable'):
            if kind == 'symlink': self.settings.symlink_to(outside)
            elif kind == 'hardlink': os.link(outside, self.settings)
            elif kind == 'fifo': os.mkfifo(self.settings)
            elif kind == 'directory': self.settings.mkdir()
            else:
                self.settings.write_bytes(b'scale=4')
                self.settings.chmod(0o666)
            with self.subTest(kind=kind), self.assertRaises((OSError, ValueError)):
                self.read()
            if kind == 'directory': self.settings.rmdir()
            else: self.settings.unlink()
        self.assertEqual(outside.read_bytes(), b'scale=4')

    def test_bad_and_oversized_text_is_never_replaced(self):
        for data in (b'a=' + b'x' * MAX_SIZE, b'a=z\0', b'\xff'):
            self.settings.write_bytes(data)
            with self.assertRaises((ValueError, UnicodeError)):
                self.read()
            self.assertEqual(self.settings.read_bytes(), data)

    def test_failed_publication_keeps_original_and_cleans_temporary_file(self):
        self.settings.write_bytes(b'scale=2\n')
        revision = self.read()['revision']
        with patch('world.personal_settings.os.replace', side_effect=OSError('fixture')):
            with self.assertRaises(OSError):
                self.save({'scale': 4}, revision)
        self.assertEqual(self.settings.read_bytes(), b'scale=2\n')
        self.assertEqual(list(self.profile.glob('.settings-*')), [])

    def test_growth_beyond_native_limit_is_rejected_without_truncation(self):
        data = b'#' + b'x' * (MAX_SIZE - 1)
        self.settings.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'exceed 16 KiB'):
            self.save({'scale': 4})
        self.assertEqual(self.settings.read_bytes(), data)

    def test_embedded_bom_is_not_mistaken_for_a_native_setting(self):
        data = b'# note\n\xef\xbb\xbfscale=9\nscale=4\n'
        self.settings.write_bytes(data)
        self.assertEqual(self.read()['values']['scale'], 4)
        self.save({'scale': 3})
        self.assertEqual(self.settings.read_bytes(), b'# note\n\xef\xbb\xbfscale=9\nscale = 3\n')

    def test_all_offered_key_names_are_recognized_by_installed_sdl_without_initializing_it(self):
        try:
            sdl = ctypes.CDLL('libSDL2-2.0.so.0')
        except OSError:
            self.skipTest('SDL2 runtime is not installed')
        sdl.SDL_GetScancodeFromName.argtypes = [ctypes.c_char_p]
        sdl.SDL_GetScancodeFromName.restype = ctypes.c_int
        self.assertTrue(all(sdl.SDL_GetScancodeFromName(key.encode()) > 0 for key in KEYS))
        self.assertNotIn('f1', KEYS)

    def bridge(self):
        session = Mock(engine='expansion-native', root=Path(self.tmp))
        session.friend_worlds.return_value = []
        session._world.return_value = self.world
        bridge = LauncherBridge(session, '/no/game', engine='expansion-native')
        self.enterContext(patch.object(bridge, 'local_expeditions', return_value=[
            {'key': self.world.name, 'trainer': 'Player', 'name': 'Cave lab', 'has_save': False}]))
        self.enterContext(patch.object(bridge, 'offline_saves', return_value=[]))
        return bridge

    def test_bridge_lists_real_profiles_and_only_returns_selected_settings(self):
        bridge = self.bridge()
        info = bridge.action('personal_settings_info', {})
        self.assertTrue(info['available'])
        self.assertEqual(len(info['profiles']), 1)
        identity = info['profiles'][0]['id']
        before = bridge.action('personal_settings_read', {'profile': identity})
        after = bridge.action('personal_settings_save', {'profile': identity, 'expected_revision': before['revision'], 'changes': {'scale': 4}})
        self.assertEqual(after['values']['scale'], 4)
        self.assertNotIn('path', info['profiles'][0])
        bridge.session.host.assert_not_called()
        bridge.session.launch.assert_not_called()

    def test_bridge_rejects_arbitrary_profile_paths_and_unsupported_engine(self):
        bridge = self.bridge()
        for identity in ('/tmp/settings.ini', 'online/unknown/Player', None):
            with self.assertRaises(SessionError):
                bridge.action('personal_settings_save', {'profile': identity})
        bridge.engine = 'vanilla'
        self.assertFalse(bridge.action('personal_settings_info', {})['available'])
        with self.assertRaises(SessionError):
            bridge.action('personal_settings_read', {'profile': 'online/e-localworld12/Player'})


if __name__ == '__main__':
    unittest.main()
