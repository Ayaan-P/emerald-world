"""Desktop offline wiring with disposable profiles and real owned helper children.

The helper is sleep, not the game. These checks do not claim native gameplay.
"""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

from world.launcher import ProfileLock, profile_paths
from world.session import DesktopApp, DesktopSession


class OfflineDesktopTests(unittest.TestCase):
    def test_disconnected_desktop_launches_offline_and_releases_lock_on_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = DesktopSession(root)
            calls = []
            def command(binary, state, paths, display, *, online, agent_control=False):
                self.assertFalse(agent_control)
                calls.append((state, paths, online))
                return ['/usr/bin/sleep', '30']
            try:
                with patch('world.session.game_command', command):
                    process = session.launch_offline('field', 'alice', Path('/usr/bin/sleep'), display=None)
                self.assertIsNone(process.poll())
                self.assertIsNone(session.state)
                self.assertIsNone(session.server)
                self.assertIsNone(session.broker)
                self.assertFalse(calls[0][2])
                offline = root / 'field/.offline'
                self.assertEqual(calls[0][0], offline)
                self.assertIn('offline/alice', session.games)
                self.assertIn('offline. No world connection', session.poll())
                self.assertNotIn('waiting for native connection', session.poll())
                with self.assertRaises(ValueError):
                    ProfileLock(offline, 'alice')
                from world.world_library import WorldActivityLock
                with self.assertRaises(ValueError):
                    WorldActivityLock(root / 'field', exclusive=True)
                with self.assertRaises(ValueError):
                    session.launch_offline('field', 'alice', Path('/usr/bin/sleep'), display=None)
                session.close()
                self.assertIsNotNone(process.poll())
                with ProfileLock(offline, 'alice'):
                    pass
                self.assertFalse((root / 'field/world.sqlite3').exists())
                self.assertFalse((root / 'field/transport').exists())
                self.assertFalse(calls[0][1]['config'].exists())
            finally:
                session.close()

    def test_native_spawn_error_releases_destination_and_preserves_online(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / 'field'
            online = profile_paths(state, 'alice')
            online['profile'].mkdir(parents=True)
            online['save'].write_bytes(b'disposable fixture')
            session = DesktopSession(root)
            try:
                with patch('world.session.subprocess.Popen', side_effect=OSError('fixture spawn failure')):
                    with self.assertRaises(OSError):
                        session.launch_offline('field', 'alice', Path('/usr/bin/false'), None, copy_online=True)
                self.assertEqual(online['save'].read_bytes(), b'disposable fixture')
                self.assertFalse(session.games)
                with ProfileLock(state / '.offline', 'alice'):
                    pass
            finally:
                session.close()

    def test_copy_errors_are_actionable_without_changing_progress(self):
        from world.offline import offline_profile
        from world.session import SessionError
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root/'world'
            with offline_profile(state, 'alice') as paths:
                paths['save'].write_bytes(b'keep offline progress')
            with DesktopSession(root) as session:
                with self.assertRaisesRegex(SessionError, 'already exists'):
                    session.launch_offline('world', 'alice', Path('/usr/bin/false'), None, True)
                self.assertEqual(paths['save'].read_bytes(), b'keep offline progress')
                with self.assertRaisesRegex(SessionError, 'could not be prepared'):
                    session.launch_offline('world', 'bob', Path('/usr/bin/false'), None, True)
                self.assertFalse(session.games)

    def test_view_dispatch_passes_selected_world_and_explicit_copy_choice(self):
        app = DesktopApp.__new__(DesktopApp)
        app.session = Mock()
        app.binary = Path('/usr/bin/false')
        values = {'world': 'field', 'trainer': 'alice', 'display': '', 'binary': ''}
        app._launch_offline(values, False)
        app.session.launch_offline.assert_called_once_with('field', 'alice', app.binary, None, False)
        app.session.start_display.assert_not_called()
        app.session.reset_mock()
        app._launch_offline(values, True)
        app.session.launch_offline.assert_called_once_with('field', 'alice', app.binary, None, True)


if __name__ == '__main__':
    unittest.main()
