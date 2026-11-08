"""Activation archive safety tests. Fixtures contain no production data."""
import importlib.util
import io
import os
from pathlib import Path
import tarfile
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/rehearse_hosted_restore.py'


class RestoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.parent = Path(self.tmp.name)
        self.parent.chmod(0o700)

    def module(self):
        self.assertTrue(SCRIPT.exists(), 'safe activation restore tool is missing')
        spec = importlib.util.spec_from_file_location('rehearsal', SCRIPT)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def archive(self, rows):
        p = self.parent / 'input.tar.gz'
        with tarfile.open(p, 'w:gz') as tar:
            for name, kind, value in rows:
                entry = tarfile.TarInfo(name)
                entry.type = kind
                if kind == tarfile.REGTYPE:
                    entry.size = len(value)
                    tar.addfile(entry, io.BytesIO(value))
                else:
                    entry.linkname = value
                    tar.addfile(entry)
        p.chmod(0o600)
        return p

    def test_extracts_without_using_absolute_live_paths(self):
        mod = self.module()
        archive = self.archive([('var/lib/emerald-hosted/state/example', tarfile.REGTYPE, b'fixture')])
        dest = self.parent / 'new'
        result = mod.extract_private(archive, dest)
        self.assertEqual(result['files'], 1)
        self.assertEqual((dest / 'var/lib/emerald-hosted/state/example').read_bytes(), b'fixture')
        self.assertEqual(dest.stat().st_mode & 0o777, 0o700)
        self.assertEqual((dest / 'var/lib/emerald-hosted/state/example').stat().st_mode & 0o777, 0o600)
        for path in dest.rglob('*'):
            self.assertEqual(path.stat().st_mode & 0o777, 0o700 if path.is_dir() else 0o600)

    def test_rejects_unsafe_archives_before_creating_destination(self):
        mod = self.module()
        bad = [('../escape', tarfile.REGTYPE, b'x'),
               ('/var/lib/emerald-hosted/x', tarfile.REGTYPE, b'x'),
               ('var/lib/emerald-hosted/../../escape', tarfile.REGTYPE, b'x'),
               ('var/lib/emerald-hosted/link', tarfile.SYMTYPE, '/etc'),
               ('var/lib/emerald-hosted/hard', tarfile.LNKTYPE, 'elsewhere'),
               ('var/lib/emerald-hosted/device', tarfile.CHRTYPE, ''),
               ('var/lib/emerald-hosted/fifo', tarfile.FIFOTYPE, ''),
               ('unrecognized/file', tarfile.REGTYPE, b'x'),
               ('var/lib/emerald-hosted//x', tarfile.REGTYPE, b'x')]
        for row in bad:
            with self.subTest(kind=row[1], path=row[0]):
                dest = self.parent / 'refused'
                with self.assertRaises(ValueError):
                    mod.extract_private(self.archive([row]), dest)
                self.assertFalse(dest.exists())
        row = ('var/lib/emerald-hosted/x', tarfile.REGTYPE, b'x')
        with self.assertRaises(ValueError):
            mod.extract_private(self.archive([row, row]), self.parent / 'duplicate')
        with self.assertRaises(ValueError):
            mod.extract_private(self.archive([row, ('var/lib/emerald-hosted/x/y', tarfile.REGTYPE, b'y')]), self.parent / 'collision')

    def test_refuses_existing_active_or_symlink_destination(self):
        mod = self.module()
        archive = self.archive([('var/lib/emerald-hosted/x', tarfile.REGTYPE, b'x')])
        active = self.parent / 'active'
        active.mkdir()
        marker = active / 'hosting.lock'
        marker.write_bytes(b'active')
        link = self.parent / 'link'
        link.symlink_to(active, target_is_directory=True)
        for dest in (active, link, Path('/var/lib/emerald-hosted/new')):
            with self.subTest(destination=str(dest)):
                with self.assertRaises(ValueError):
                    mod.extract_private(archive, dest)
        self.assertEqual(marker.read_bytes(), b'active')
        self.assertEqual(list(active.iterdir()), [marker])

    def test_requires_private_parent_and_private_regular_archive(self):
        mod = self.module()
        archive = self.archive([('var/lib/emerald-hosted/x', tarfile.REGTYPE, b'x')])
        self.parent.chmod(0o755)
        with self.assertRaises(ValueError):
            mod.extract_private(archive, self.parent / 'new')
        self.parent.chmod(0o700)
        archive.chmod(0o644)
        with self.assertRaises(ValueError):
            mod.extract_private(archive, self.parent / 'new')

    def fixture(self):
        import hashlib
        import json
        import shutil
        import socket
        import ssl
        import subprocess
        from world.hosting import HostedWorldManager
        from world.server import WorldServer
        root = self.parent / 'fixture'
        tls = root / 'var/lib/emerald-hosted/tls'
        tls.mkdir(parents=True)
        root.chmod(0o700)
        cert, key = tls / 'server.pem', tls / 'server.key'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', str(key), '-out', str(cert), '-days', '1',
                        '-subj', '/CN=localhost'], capture_output=True, check=True)
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            port = s.getsockname()[1]
        # Short private source avoids AF_UNIX's path length limit.
        with tempfile.TemporaryDirectory(prefix='rt-') as short:
            manager = HostedWorldManager(Path(short) / 'h', cert=cert, key=key,
                advertise_host='localhost', port_start=port, port_end=port, max_worlds=1)
            try:
                manager.enroll(manager.create_account()['token'], 'a'*64)
                created = manager.create_world('a'*64, 'Fixture', 'Owner', 'first')
                server = manager.running[created['world']['id']][0]
                rules = server.world_rules.status()['rules']
                rules['pokemon_follower'] = True
                server.world_rules.replace(rules, 0)
            finally:
                manager.close()
            shutil.copytree(Path(short) / 'h', root / 'var/lib/emerald-hosted/state')
            standalone = WorldServer(Path(short) / 'w.sock', Path(short) / 'w')
            standalone.create_identity('Solo', 'b'*64)
            standalone.close()
            shutil.copytree(Path(short) / 'w', root / 'var/lib/emerald-world/worlds/friends')
        stls = root / 'var/lib/emerald-world/worlds/friends/tls'
        stls.mkdir()
        shutil.copyfile(cert, stls / 'certificate.pem')
        shutil.copyfile(key, stls / 'private-key.pem')
        units = root / 'etc/systemd/system'
        units.mkdir(parents=True)
        (root / 'etc/emerald-hosted.conf').write_text('EMERALD_HOST=localhost\n')
        hosted = ('--root /var/lib/emerald-hosted/state --cert /var/lib/emerald-hosted/tls/server.pem '
                  '--key /var/lib/emerald-hosted/tls/server.key --advertise-host ${EMERALD_HOST} '
                  f'--port-start {port} --port-end {port} --max-worlds 1')
        solo = ('--state-dir /var/lib/emerald-world/worlds/friends '
                '--cert /var/lib/emerald-world/worlds/friends/tls/certificate.pem '
                '--key /var/lib/emerald-world/worlds/friends/tls/private-key.pem '
                '--listen 0.0.0.0:8765 --advertise localhost:8765')
        for service, module, options in [('emerald-hosted', 'hosting start', hosted),
                                          ('emerald-world', 'server', solo)]:
            (units / (service + '.service')).write_text(
                f'[Service]\nWorkingDirectory=/opt/emerald-world/releases/fixture\n'
                f'ExecStart=/usr/bin/python3 -m world.{module} {options}\n')
        return root

    def test_offline_checks_databases_tls_topology_and_missing_source(self):
        mod = self.module()
        root = self.fixture()
        result = mod.verify_offline(root)
        self.assertEqual(result['sqlite_integrity_checks'], 3)
        self.assertEqual(result['hosted_worlds'], 1)
        self.assertTrue(result['tls_registry_pin_consistent'])
        self.assertFalse(result['original_source_bundled'])
        self.assertNotIn('localhost', str(result))
        cert = root / 'var/lib/emerald-hosted/tls/server.pem'
        cert.write_text('invalid certificate')
        with self.assertRaises(ValueError):
            mod.verify_offline(root)

    def test_corrupt_database_fails_offline(self):
        mod = self.module()
        root = self.fixture()
        (root / 'var/lib/emerald-hosted/state/hosting.sqlite3').write_bytes(b'broken')
        with self.assertRaises(ValueError):
            mod.verify_offline(root)

    def test_hash_mismatch_does_not_extract(self):
        mod = self.module()
        archive = self.archive([('var/lib/emerald-hosted/x', tarfile.REGTYPE, b'x')])
        with self.assertRaises(ValueError):
            mod.extract_private(archive, self.parent / 'hash-fail', '0'*64)
        self.assertFalse((self.parent / 'hash-fail').exists())

    def test_authority_refuses_current_network_namespace(self):
        mod = self.module()
        with self.assertRaises(ValueError):
            mod.authority_child(self.parent, os.readlink('/proc/self/ns/net'))

    def test_isolated_fixture_authority_preserves_credentials(self):
        import subprocess
        probe = subprocess.run(['unshare', '--user', '--map-root-user', '--net', 'true'],
                               capture_output=True)
        if probe.returncode:
            self.skipTest('kernel does not allow private user/network namespace')
        mod = self.module()
        result = mod.prove_authority(self.fixture())
        self.assertTrue(result['isolated_network_namespace'])
        self.assertEqual(result['hosted_worlds_started'], 1)
        self.assertEqual(result['hosted_credentials_authenticated'], 1)
        self.assertEqual(result['standalone_credentials_authenticated'], 1)
        self.assertTrue(result['no_external_network'])

    def test_offline_refuses_live_and_symlink_trees(self):
        mod = self.module()
        root = self.fixture()
        (root / 'alias').symlink_to('/var/lib')
        with self.assertRaises(ValueError):
            mod.verify_offline(root)
        with self.assertRaises(ValueError):
            mod.verify_offline(Path('/'))

    def test_registry_pin_mismatch_and_resource_limits_fail_closed(self):
        import json
        import sqlite3
        mod = self.module()
        root = self.fixture()
        with sqlite3.connect(root / 'var/lib/emerald-hosted/state/hosting.sqlite3') as db:
            endpoint = json.loads(db.execute("SELECT value FROM config WHERE key='endpoint'").fetchone()[0])
            endpoint[1] = '0'*64
            db.execute("UPDATE config SET value=? WHERE key='endpoint'", (json.dumps(endpoint),))
        with self.assertRaises(ValueError):
            mod.verify_offline(root)
        archive = self.archive([('var/lib/emerald-hosted/x', tarfile.REGTYPE, b'xx')])
        mod.MAX_BYTES = 1
        with self.assertRaises(ValueError):
            mod.extract_private(archive, self.parent / 'oversize')
        self.assertFalse((self.parent / 'oversize').exists())


if __name__ == '__main__':
    unittest.main()
