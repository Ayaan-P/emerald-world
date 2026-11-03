"""Native launch logs cannot truncate a save through a filesystem alias."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from world.offline import offline_profile
from world.session import DesktopSession, SessionError


class NativeLogIsolationTests(unittest.TestCase):
    def test_hardlinked_log_does_not_truncate_save_or_start_game(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / 'world'
            with offline_profile(state, 'alice') as paths:
                paths['save'].write_bytes(b'disposable saved progress')
            os.link(paths['save'], paths['profile'] / 'native.log')
            process = Mock()
            process.poll.return_value = 0
            process.wait.return_value = 0
            with DesktopSession(root) as session, patch('world.session.subprocess.Popen', return_value=process) as spawn:
                with self.assertRaisesRegex(SessionError, 'log'):
                    session.launch(paths, '/usr/bin/false', None, _offline_state=state / '.offline')
                spawn.assert_not_called()
            self.assertEqual(paths['save'].read_bytes(), b'disposable saved progress')

    def test_fifo_log_is_rejected_without_blocking_or_starting_game(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / 'world'
            with offline_profile(state, 'alice') as paths:
                paths['save'].write_bytes(b'disposable saved progress')
            os.mkfifo(paths['profile'] / 'native.log')
            with DesktopSession(root) as session, patch('world.session.subprocess.Popen') as spawn:
                with self.assertRaisesRegex(SessionError, 'log'):
                    session.launch(paths, '/usr/bin/false', None, _offline_state=state / '.offline')
                spawn.assert_not_called()
            self.assertEqual(paths['save'].read_bytes(), b'disposable saved progress')

    def test_regular_owned_log_is_replaced_and_profile_lock_released(self):
        from world.launcher import ProfileLock
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / 'world'
            with offline_profile(state, 'alice') as paths:
                paths['save'].write_bytes(b'disposable saved progress')
            logfile = paths['profile'] / 'native.log'
            logfile.write_bytes(b'previous run output')
            process = Mock()
            process.poll.return_value = 0
            process.wait.return_value = 0
            with DesktopSession(root) as session, patch('world.session.subprocess.Popen', return_value=process) as spawn:
                session.launch(paths, '/usr/bin/false', None, _offline_state=state / '.offline')
                spawn.assert_called_once()
            self.assertEqual(logfile.read_bytes(), b'')
            self.assertEqual(paths['save'].read_bytes(), b'disposable saved progress')
            with ProfileLock(state / '.offline', 'alice'):
                pass


if __name__ == '__main__':
    unittest.main()
