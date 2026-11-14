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
                  f'--port-start {port} --port-end {port} --max-worlds 1 '
                  '--listen 0.0.0.0:8766 --management-advertise localhost:8766')
        solo = ('--state-dir /var/lib/emerald-world/worlds/friends '
                '--cert /var/lib/emerald-world/worlds/friends/tls/certificate.pem '
                '--key /var/lib/emerald-world/worlds/friends/tls/private-key.pem '
                '--listen 0.0.0.0:8765 --advertise localhost:8765')
        for service, module, options in [('emerald-hosted', 'hosting start', hosted),
                                          ('emerald-world', 'server', solo)]:
            environment = 'EnvironmentFile=/etc/emerald-hosted.conf\n' if service == 'emerald-hosted' else ''
            (units / (service + '.service')).write_text(
                f'[Service]\nWorkingDirectory=/opt/emerald-world/releases/fixture\n'
                f'{environment}ExecStart=/usr/bin/python3 -m world.{module} {options}\n')
        return root

    def test_topology_rejects_unsupported_service_semantics(self):
        mod = self.module()
        root = self.parent / 'metadata'
        units = root / 'etc/systemd/system'
        units.mkdir(parents=True)
        unit = units / 'emerald-world.service'
        command = ('/usr/bin/python3 -m world.server --state-dir /var/lib/emerald-world/state '
                   '--cert /var/lib/emerald-world/cert --key /var/lib/emerald-world/key '
                   '--listen 0.0.0.0:8765 --advertise localhost:8765')
        valid = '[Service]\nWorkingDirectory=/opt/emerald-world/releases/fixture\nExecStart=' + command + '\n'
        unit.write_text(valid)
        self.assertEqual(mod.topology(root, 'emerald-world')['options']['--listen'], '0.0.0.0:8765')
        bad = [valid.replace('[Service]', '[Unit]'),
               valid.replace('[Service]', '[Unsupported]'),
               valid.replace('/usr/bin/python3 -m world.server', '/bin/false'),
               valid.replace('world.server', 'world.hosting'),
               valid + 'EnvironmentFile=/private/secret\n',
               valid + 'Environment=PYTHONPATH=/private/secret\n',
               valid + 'ExecStartPre=/bin/false\n',
               valid + 'RootDirectory=/private/secret\n',
               valid + 'ExecStart=\n', valid + 'WorkingDirectory=/opt/emerald-world/other\n',
               valid.replace('--listen 0.0.0.0:8765', '--listen'),
               valid.replace('--listen 0.0.0.0:8765', '--listen 0.0.0.0:0'),
               valid.replace('--listen 0.0.0.0:8765', '--listen 0.0.0.0:65536'),
               valid + 'ExecStart=' + command + '\n',
               valid.replace('--cert /var/lib/emerald-world/cert ', ''),
               valid.replace('--state-dir /var/lib/emerald-world/state ', ''),
               valid.replace(command, command + ' --listen 0.0.0.0:9999'),
               valid.replace(command, command + ' --unknown value'),
               valid.replace(command, command + ' --max-players 65'),
               valid.replace(command, command + ' --max-controls -1'),
               valid.replace(command, command + ' --connection-headroom nope'),
               valid.replace(command, command + ' positional'),
               valid.replace('--listen', '\\\n--listen'),
               valid.replace('localhost:8765', '${UNKNOWN}:8765')]
        for text in bad:
            with self.subTest(metadata=bad.index(text)):
                unit.write_text(text)
                with self.assertRaises(ValueError) as failure:
                    mod.topology(root, 'emerald-world')
                self.assertNotIn('/private/secret', str(failure.exception))
        unit.write_text(valid)
        dropins = units / 'emerald-world.service.d'
        dropins.mkdir()
        (dropins / 'override.conf').write_text('[Service]\nExecStart=' + command + '\n')
        with self.assertRaises(ValueError):
            mod.topology(root, 'emerald-world')

    def test_offline_rejects_missing_standalone_database_and_port_collisions(self):
        mod = self.module()
        root = self.fixture()
        self.assertTrue(mod.verify_offline(root)['service_topology_consistent'])
        database = root / 'var/lib/emerald-world/worlds/friends/world.sqlite3'
        contents = database.read_bytes()
        database.unlink()
        with self.subTest(case='missing standalone database'), self.assertRaises(ValueError):
            mod.verify_offline(root)
        database.write_bytes(contents)
        units = root / 'etc/systemd/system'
        solo = units / 'emerald-world.service'
        hosted = units / 'emerald-hosted.service'
        original_solo, original_hosted = solo.read_text(), hosted.read_text()
        port = mod.topology(root, 'emerald-hosted')['options']['--port-start']
        for text in (original_solo.replace(':8765', ':' + port),
                     original_solo.replace(':8765', ':8766')):
            solo.write_text(text)
            with self.subTest(case='standalone port collision', metadata=text), self.assertRaises(ValueError):
                mod.verify_offline(root)
        solo.write_text(original_solo)
        hosted.write_text(original_hosted.replace(':8766', ':' + port))
        with self.subTest(case='management port collision'), self.assertRaises(ValueError):
            mod.verify_offline(root)
        hosted.write_text(original_hosted)
        # Existing but wrong state root cannot substitute for standalone state.
        wrong = root / 'var/lib/emerald-world/empty'
        wrong.mkdir()
        solo.write_text(original_solo.replace('--state-dir /var/lib/emerald-world/worlds/friends',
                                             '--state-dir /var/lib/emerald-world/empty'))
        with self.subTest(case='wrong standalone root'), self.assertRaises(ValueError):
            mod.verify_offline(root)

    def test_hosted_topology_rejects_invalid_limits_and_environment(self):
        mod = self.module()
        root = self.fixture()
        unit = root / 'etc/systemd/system/emerald-hosted.service'
        original = unit.read_text()
        for text in (original.replace('--max-worlds 1', '--max-worlds 17'),
                     original.replace('--port-end ', '--port-end 0 --ignored '),
                     original.replace('--max-worlds 1', '--max-worlds 0'),
                     original.replace('--root /var/lib/emerald-hosted/state ', ''),
                     original.replace('--listen 0.0.0.0:8766 ', ''),
                     original.replace('--management-advertise localhost:8766', ''),
                     original.replace('--listen 0.0.0.0:8766 --management-advertise localhost:8766', ''),
                     original.replace('--max-worlds 1', '--max-worlds 1 --port-start 9999')):
            unit.write_text(text)
            with self.assertRaises(ValueError):
                mod.topology(root, 'emerald-hosted')
        unit.write_text(original)
        config = root / 'etc/emerald-hosted.conf'
        for text in ('EMERALD_HOST=localhost\nEMERALD_HOST=other\n',
                     'EMERALD_HOST=localhost\nPYTHONPATH=/private/secret\n',
                     'EMERALD_HOST="localhost --unknown value"\n',
                     'EMERALD_HOST="localhost --game-listen-host 0.0.0.0"\n'):
            config.write_text(text)
            with self.assertRaises(ValueError):
                mod.topology(root, 'emerald-hosted')

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

    def test_hosted_topology_rejects_oversized_range_and_conflicting_management_port(self):
        mod = self.module()
        root = self.fixture()
        unit = root / 'etc/systemd/system/emerald-hosted.service'
        original = unit.read_text()
        options = mod.topology(root, 'emerald-hosted')['options']
        start, end = options['--port-start'], options['--port-end']
        bad = [original.replace('--port-start ' + start, '--port-start 9001')
                       .replace('--port-end ' + end, '--port-end 9017')
                       .replace('--max-worlds 1', '--max-worlds 17'),
               original.replace('localhost:8766', 'localhost:8767')]
        for i, text in enumerate(bad):
            with self.subTest(case=i):
                unit.write_text(text)
                with self.assertRaises(ValueError):
                    mod.topology(root, 'emerald-hosted')

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

    def authority_lifecycle(self, cancel):
        """Real unshare, fork and setsid. Only the workload/clock are substituted."""
        import ctypes
        import signal
        import socket
        import subprocess
        import sys
        import time
        from unittest.mock import patch
        probe = subprocess.run(['unshare', '--user', '--map-root-user', '--net', '--pid', '--fork', 'true'],
                               capture_output=True)
        if probe.returncode:
            self.skipTest('kernel does not allow private user/network/PID namespace')
        mod = self.module()
        script, record = self.parent / 'sleeper.py', self.parent / 'pids'
        # A pathname Unix listener can be tested from the caller namespace.
        address = str(record) + '.sock'
        script.write_text('''import json, os, signal, socket, sys, time
from pathlib import Path
listener = socket.socket(socket.AF_UNIX)
listener.bind(sys.argv[1] + '.sock')
listener.listen()
child = os.fork()
if child == 0:
    os.setsid()
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    Path(sys.argv[1] + '.child').write_text(Path('/proc/self/stat').read_text().split()[0])
    while True: time.sleep(1)
Path(sys.argv[1]).write_text(Path('/proc/self/stat').read_text().split()[0])
while True: time.sleep(1)
''')
        # Reap fixture orphans after a deliberately failing RED run, without
        # changing the production caller's process-wide subreaper policy.
        libc = ctypes.CDLL(None, use_errno=True)
        prior = ctypes.c_int()
        self.assertEqual(libc.prctl(37, ctypes.byref(prior), 0, 0, 0), 0)
        self.assertEqual(libc.prctl(36, 1, 0, 0, 0), 0)
        real_popen, processes, pids = subprocess.Popen, [], []
        def ready(proc):
            deadline = time.monotonic() + 5
            while not (record.exists() and record.read_text()
                       and Path(str(record) + '.child').exists()
                       and Path(str(record) + '.child').read_text()):
                if proc.poll() is not None or time.monotonic() > deadline:
                    self.fail('isolated fixture failed to start')
                time.sleep(.01)
            if not pids:
                pids.extend([int(record.read_text()), int(Path(str(record) + '.child').read_text())])
            with socket.socket(socket.AF_UNIX) as client:
                client.connect(address)
        def launch(command, *args, **kwargs):
            index = command.index(sys.executable)
            command = command[:index] + [sys.executable, str(script), str(record)]
            proc = real_popen(command, *args, **kwargs)
            processes.append(proc)
            communicate = proc.communicate
            first = True
            def bounded_communicate(*args, **kwargs):
                nonlocal first
                if first:
                    first = False
                    ready(proc)
                    if cancel == 'sigterm':
                        os.kill(os.getpid(), signal.SIGTERM)
                    elif cancel:
                        raise KeyboardInterrupt()
                    kwargs['timeout'] = .15
                elif kwargs.get('timeout') is None:
                    kwargs['timeout'] = .5
                return communicate(*args, **kwargs)
            proc.communicate = bounded_communicate
            if cancel == 'spawn-sigterm':
                ready(proc)
                os.kill(os.getpid(), signal.SIGTERM)
            return proc
        try:
            with patch.object(mod.subprocess, 'Popen', side_effect=launch):
                with self.assertRaises(KeyboardInterrupt if cancel else ValueError):
                    mod.prove_authority(self.parent)
            self.assertEqual(len(pids), 2)
            # No kill(0)/zombie exception: both descendants must actually be reaped.
            deadline = time.monotonic() + 3
            while any(Path('/proc', str(pid)).exists() for pid in pids) and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertFalse([pid for pid in pids if Path('/proc', str(pid)).exists()],
                             'authority descendant survived or was not reaped')
            self.assertIsNotNone(processes[0].returncode, 'supervisor was not reaped')
            with socket.socket(socket.AF_UNIX) as client:
                with self.assertRaises(OSError):
                    client.connect(address)
        finally:
            # Exact disposable fixture PIDs only, including on expected RED failure.
            for pid in reversed(pids):
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            for proc in processes:
                if proc.poll() is None:
                    proc.kill()
                proc.wait(timeout=5)
            for pid in pids:
                try:
                    os.waitpid(pid, 0)
                except ChildProcessError:
                    pass
            libc.prctl(36, prior.value, 0, 0, 0)

    def test_authority_timeout_reaps_session_escaping_descendants(self):
        self.authority_lifecycle(cancel=False)

    def test_authority_cancellation_reaps_session_escaping_descendants(self):
        self.authority_lifecycle(cancel=True)

    def test_authority_sigterm_reaps_session_escaping_descendants(self):
        self.authority_lifecycle(cancel='sigterm')

    def test_authority_spawn_cancellation_reaps_session_escaping_descendants(self):
        self.authority_lifecycle(cancel='spawn-sigterm')

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
