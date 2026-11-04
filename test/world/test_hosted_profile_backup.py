"""Private owner credential backup using synthetic tokens and disposable files."""
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from world.hosted_profile_backup import copy_profile, read_profile


class ProfileBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'profile.json'
        self.value = {'kind': 'host-profile', 'version': 1,
                      'endpoint': {'host': 'example.org', 'port': 8766},
                      'pin': 'a' * 64, 'token': 'b' * 64}
        self.source.write_text(json.dumps(self.value))
        self.source.chmod(0o600)

    def test_backup_and_restore_preserve_profile_privately(self):
        backup, restored = self.root / 'backup.json', self.root / 'restored.json'
        copy_profile(self.source, backup)
        copy_profile(backup, restored)
        self.assertEqual(read_profile(restored), self.value)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        self.assertEqual(restored.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(self.source.read_text()), self.value)

    def test_cli_never_prints_the_private_credential(self):
        target = self.root / 'backup.json'
        result = subprocess.run([sys.executable, '-m', 'world.hosted_profile_backup', 'backup',
                                 '--source', str(self.source), '--destination', str(target)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(self.value['token'], result.stdout + result.stderr)
        self.assertEqual(read_profile(target), self.value)

    def test_refuses_existing_target_and_leaves_it_untouched(self):
        target = self.root / 'existing.json'
        target.write_text('keep')
        with self.assertRaises(FileExistsError):
            copy_profile(self.source, target)
        self.assertEqual(target.read_text(), 'keep')

    def test_refuses_insecure_or_linked_source(self):
        self.source.chmod(0o644)
        with self.assertRaises(ValueError):
            copy_profile(self.source, self.root / 'out.json')
        self.source.chmod(0o600)
        linked = self.root / 'link.json'
        linked.symlink_to(self.source)
        with self.assertRaises((ValueError, OSError)):
            copy_profile(linked, self.root / 'out.json')
        self.assertFalse((self.root / 'out.json').exists())

    def test_rejects_invalid_or_duplicate_json(self):
        self.source.write_text('{"kind":"host-profile","kind":"host-profile"}')
        with self.assertRaises(ValueError):
            copy_profile(self.source, self.root / 'out.json')
        self.assertFalse((self.root / 'out.json').exists())

    def test_refuses_hardlinked_profile_and_symlink_destination(self):
        hardlink = self.root / 'hardlink.json'
        os.link(self.source, hardlink)
        with self.assertRaises(ValueError):
            copy_profile(self.source, self.root / 'out.json')
        hardlink.unlink()
        target = self.root / 'target.json'
        target.write_text('untouched')
        linked = self.root / 'out.json'
        linked.symlink_to(target)
        with self.assertRaises(OSError):
            copy_profile(self.source, linked)
        self.assertEqual(target.read_text(), 'untouched')

    def test_failed_publish_leaves_no_partial_backup(self):
        target = self.root / 'out.json'
        with patch('world.hosted_profile_backup.os.link', side_effect=OSError('fixture failure')):
            with self.assertRaises(OSError):
                copy_profile(self.source, target)
        self.assertFalse(target.exists())
        self.assertFalse(list(self.root.glob('.emerald-owner-*.tmp')))
        self.assertEqual(read_profile(self.source), self.value)

    def test_rejects_group_writable_destination(self):
        directory = self.root / 'shared'
        directory.mkdir(mode=0o777)
        directory.chmod(0o777)
        with self.assertRaises(ValueError):
            copy_profile(self.source, directory / 'out.json')
        self.assertFalse((directory / 'out.json').exists())


if __name__ == '__main__':
    unittest.main()
