"""Offline copies cannot be converted to online profiles by another entry point."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from world import launcher
from world.offline import offline_profile
from world.session import DesktopSession


class OfflineNamespaceTests(unittest.TestCase):
    def test_direct_online_preparation_cannot_issue_identity_for_offline_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / 'world'
            with offline_profile(state, 'alice') as paths:
                paths['save'].write_bytes(b'disposable progress')
            with patch('world.server.create_identity', return_value='0' * 64) as identity:
                with self.assertRaisesRegex(ValueError, 'Offline copies'):
                    launcher.prepare_profile(state / '.offline', 'alice')
                identity.assert_not_called()
            self.assertFalse(paths['config'].exists())
            self.assertEqual(paths['save'].read_bytes(), b'disposable progress')

    def test_renamed_offline_root_cannot_join_online_or_be_selected_in_desktop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / 'world'
            with offline_profile(state, 'alice') as paths:
                paths['save'].write_bytes(b'disposable progress')
            moved = root / 'renamed'
            (state / '.offline').rename(moved)
            for command in ('host', 'join'):
                args = ['--state-dir', str(moved), command]
                if command == 'join':
                    args.append('alice')
                with patch('world.server.WorldServer'):
                    with self.assertRaisesRegex(ValueError, 'Offline copies'):
                        launcher.main(args)
            with DesktopSession(root) as session:
                with self.assertRaisesRegex(ValueError, 'Offline copies'):
                    session._world('renamed')
            self.assertFalse((moved / 'transport').exists())
            self.assertFalse((moved / 'world.sqlite3').exists())
            self.assertFalse((moved / 'trainers/alice/world.conf').exists())
            self.assertEqual((moved / 'trainers/alice/game.sav').read_bytes(), b'disposable progress')

    def test_existing_online_state_cannot_be_reclassified_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / 'world'
            target = state / '.offline'
            target.mkdir(parents=True, mode=0o700)
            database = target / 'world.sqlite3'
            database.write_bytes(b'disposable database fixture')
            with self.assertRaisesRegex(ValueError, 'online'):
                with offline_profile(state, 'alice'):
                    pass
            self.assertEqual(database.read_bytes(), b'disposable database fixture')
            self.assertFalse((target / 'trainers/alice').exists())


if __name__ == '__main__':
    unittest.main()
