"""Operational rehearsals use disposable authorities, never a deployed root."""
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from test.world import test_hosting


class BackupRehearsal(unittest.TestCase):
    setUp = test_hosting.HostingTests.setUp
    manager = test_hosting.HostingTests.manager
    def test_source_symlink_and_standalone_live_world_refused(self):
        import fcntl
        from world import hosting_backup as ops
        manager = self.manager()
        try:
            manager.enroll(manager.create_account()['token'], 'a'*64)
            world_id = manager.create_world('a'*64, 'World', 'Owner', 'first')['world']['id']
        finally:
            manager.close()
        root = self.root/'m'
        archive = self.root/'backup.tar'
        alias = root/'private-alias'
        alias.symlink_to(self.key)
        with self.assertRaises(ValueError):
            ops.backup(root, self.cert, self.key, archive)
        alias.unlink()
        self.assertFalse(archive.exists())
        with (root/'worlds'/world_id/'world.lock').open('rb') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(ValueError):
                ops.backup(root, self.cert, self.key, archive)
        self.assertFalse(archive.exists())

    def test_cli_live_failure_contains_no_secrets(self):
        import contextlib
        import io
        from world import hosting_backup as ops
        manager = self.manager()
        try:
            access = manager.create_account()
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = ops.main(['backup', '--root', str(self.root/'m'),
                                  '--cert', str(self.cert), '--key', str(self.key),
                                  '--archive', str(self.root/'backup.tar')])
            self.assertEqual(result, 1)
            self.assertNotIn(access['token'], output.getvalue())
            self.assertNotIn(str(self.root), output.getvalue())
            self.assertFalse(json.loads(output.getvalue())['ok'])
        finally:
            manager.close()

    def test_cold_round_trip(self):
        from world import hosting_backup as ops
        from world.hosting import HostedWorldManager
        manager = self.manager()
        try:
            access = manager.create_account()
            manager.enroll(access['token'], 'a'*64)
            owner = manager.create_world('a'*64, 'Private world', 'Owner', 'first')
            invite = manager.invite('a'*64, owner['world']['id'], 'guest')
            guest = manager.join(invite['token'], 'Guest')
            archive = self.root/'backup.tar'
            with self.assertRaises(ValueError):
                ops.backup(self.root/'m', self.cert, self.key, archive)
            self.assertFalse(archive.exists())
        finally:
            manager.close()
        ops.backup(self.root/'m', self.cert, self.key, archive)
        self.assertEqual(archive.stat().st_mode & 0o777, 0o600)
        with self.assertRaises((ValueError, FileExistsError)):
            ops.backup(self.root/'m', self.cert, self.key, archive)
        destination = self.root/'r'
        old_umask = os.umask(0)
        try:
            ops.restore(archive, destination)
        finally:
            os.umask(old_umask)
        for path in destination.rglob('*'):
            self.assertEqual(path.stat().st_mode & 0o777, 0o700 if path.is_dir() else 0o600)
        for db in (destination/'root').rglob('*.sqlite3'):
            with sqlite3.connect(db) as conn:
                self.assertEqual(conn.execute('PRAGMA integrity_check').fetchall(), [('ok',)])
        restored = HostedWorldManager(destination/'root', cert=destination/'tls/cert.pem',
                    key=destination/'tls/key.pem', advertise_host='localhost',
                    port_start=self.port, port_end=self.port, max_worlds=1)
        try:
            self.assertEqual(restored.resume('a'*64, owner['world']['id']), owner)
            self.assertEqual(restored.join(invite['token'], 'Guest'), guest)
            world = restored.running[owner['world']['id']][0]
            self.assertEqual(world.db.execute('SELECT count(*) FROM identities').fetchone()[0], 2)
        finally:
            restored.close()
        with self.assertRaises((ValueError, FileExistsError)):
            ops.restore(archive, destination)
        self.assertEqual((destination/'tls/key.pem').read_bytes(), self.key.read_bytes())


class SafetyTests(unittest.TestCase):
    def test_corrupt_database_restore_rolls_back_and_existing_destination_survives(self):
        import io
        import tarfile
        from world import hosting_backup as ops
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root/'bad.tar'
            with tarfile.open(archive, 'w') as bundle:
                for name in ('root/hosting.sqlite3', 'root/hosting.lock', 'tls/cert.pem', 'tls/key.pem'):
                    entry = tarfile.TarInfo(name)
                    entry.size = 11
                    bundle.addfile(entry, io.BytesIO(b'not sqlite!'))
            with self.assertRaises(sqlite3.DatabaseError):
                ops.restore(archive, root/'new')
            self.assertFalse((root/'new').exists())
            destination = root/'existing'
            destination.mkdir()
            sentinel = destination/'sentinel'
            sentinel.write_text('untouched')
            with self.assertRaises(ValueError):
                ops.restore(archive, destination)
            self.assertEqual(sentinel.read_text(), 'untouched')

    def test_malicious_archives_and_symlinks_refused(self):
        import io
        import tarfile
        from world import hosting_backup as ops
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('../escape', '/absolute', 'root/../../escape', 'root/link'):
                archive = root/'bad.tar'
                with tarfile.open(archive, 'w') as bundle:
                    entry = tarfile.TarInfo(name)
                    if name.endswith('link'):
                        entry.type = tarfile.SYMTYPE
                        entry.linkname = '/tmp'
                    else:
                        entry.size = 1
                    bundle.addfile(entry, io.BytesIO(b'x'))
                with self.assertRaises(ValueError):
                    ops.restore(archive, root/'new')
                self.assertFalse((root/'new').exists())
            (root/'alias').symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError):
                ops.restore(archive, root/'alias/new')


class HealthRehearsal(unittest.TestCase):
    setUp = test_hosting.HostingTests.setUp
    manager = test_hosting.HostingTests.manager

    def test_health_only_exposes_counts(self):
        from world import hosting_backup as ops
        from world.client import WorldClient
        manager = self.manager()
        try:
            manager.enroll(manager.create_account()['token'], 'a'*64)
            owner = manager.create_world('a'*64, 'Secret name', 'SecretTrainer', 'first')
            invitation = owner['invitation']
            server = next(iter(manager.running.values()))[0]
            with WorldClient(server.socket_path, invitation['trainer'], invitation['token']):
                report = ops.health(self.root/'m')
                self.assertTrue(report['ok'])
                self.assertEqual(report['connected_players'], 1)
                self.assertEqual(report['player_capacity'], server.max_players)
                self.assertEqual(report['registered_worlds'], 1)
                self.assertNotIn('Secret', json.dumps(report))
                self.assertNotIn(invitation['token'], json.dumps(report))
        finally:
            manager.close()
        report = ops.health(self.root/'m')
        self.assertFalse(report['ok'])
        self.assertEqual(report['unavailable_worlds'], 1)


if __name__ == '__main__':
    unittest.main()
