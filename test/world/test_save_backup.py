"""Local trainer save export with synthetic files, no game or server."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from world.launcher import ProfileLock, profile_paths
from world.offline import offline_profile, OfflineGameLock
from world.save_backup import backup_save


class SaveBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = self.root / 'world'
        self.world.mkdir(mode=0o700)
        self.paths = profile_paths(self.world, 'May')
        self.paths['profile'].parent.mkdir(mode=0o700)
        self.paths['profile'].mkdir(mode=0o700)
        self.fixture = b'synthetic save bytes'
        self.paths['save'].write_bytes(self.fixture)
        self.destination = self.root / 'backup.sav'

    def test_online_copy_preserves_source_and_is_private(self):
        backup_save(self.world, 'May', self.destination)
        self.assertEqual(self.destination.read_bytes(), self.fixture)
        self.assertEqual(self.paths['save'].read_bytes(), self.fixture)
        self.assertEqual(self.destination.stat().st_mode & 0o777, 0o600)

    def test_running_profile_refuses_without_creating_backup(self):
        with ProfileLock(self.world, 'May'):
            with self.assertRaises(ValueError):
                backup_save(self.world, 'May', self.destination)
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.paths['save'].read_bytes(), self.fixture)

    def test_existing_destination_never_replaced_and_no_temporary_left(self):
        self.destination.write_bytes(b'keep')
        with self.assertRaises(FileExistsError):
            backup_save(self.world, 'May', self.destination)
        self.assertEqual(self.destination.read_bytes(), b'keep')
        self.assertFalse(list(self.root.glob('.emerald-save-*.tmp')))

    def test_offline_backup_uses_separate_profile_and_respects_lock(self):
        with offline_profile(self.world, 'May') as offline:
            offline['save'].write_bytes(b'offline save')
        lock = OfflineGameLock(self.world, 'May')
        try:
            with self.assertRaises(ValueError):
                backup_save(self.world, 'May', self.destination, offline=True)
        finally:
            lock.close()
        backup_save(self.world, 'May', self.destination, offline=True)
        self.assertEqual(self.destination.read_bytes(), b'offline save')
        self.assertEqual(self.paths['save'].read_bytes(), self.fixture)

    def test_rejects_symlink_hardlink_and_oversized_saves(self):
        self.paths['save'].unlink()
        outside = self.root / 'outside'
        outside.write_bytes(b'keep')
        self.paths['save'].symlink_to(outside)
        with self.assertRaises(ValueError):
            backup_save(self.world, 'May', self.destination)
        self.paths['save'].unlink()
        os.link(outside, self.paths['save'])
        with self.assertRaises(ValueError):
            backup_save(self.world, 'May', self.destination)
        self.paths['save'].unlink()
        self.paths['save'].write_bytes(b'x' * 131073)
        with self.assertRaises(ValueError):
            backup_save(self.world, 'May', self.destination)
        self.assertEqual(outside.read_bytes(), b'keep')
        self.assertFalse(self.destination.exists())

    def test_failed_staging_never_publishes_partial_backup(self):
        with patch('world.save_backup.os.link', side_effect=OSError('fixture failure')):
            with self.assertRaises(OSError):
                backup_save(self.world, 'May', self.destination)
        self.assertFalse(self.destination.exists())
        self.assertFalse(list(self.root.glob('.emerald-save-*.tmp')))
        self.assertEqual(self.paths['save'].read_bytes(), self.fixture)


if __name__ == '__main__':
    unittest.main()
