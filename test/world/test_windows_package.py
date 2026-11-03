"""Portable packaging tests. No compiler, Windows, or third-party packages needed."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]


class WindowsPackageTests(unittest.TestCase):
    def module(self):
        path = ROOT / 'scripts/windows_package.py'
        self.assertTrue(path.exists(), 'Windows packager is missing')
        spec = importlib.util.spec_from_file_location('windows_package', path)
        self.assertIsNotNone(spec)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_collects_transitive_dlls_and_rejects_missing_import(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            for name in ('game.exe', 'SDL2.dll', 'libgcc.dll'):
                (p / name).write_bytes(b'MZfixture')
            imports = {'game.exe': ['SDL2.dll', 'KERNEL32.dll'],
                       'SDL2.dll': ['libgcc.dll'], 'libgcc.dll': []}
            deps = m.collect_dependencies(p / 'game.exe', [p],
                lambda path: imports[path.name], lambda name: name == 'KERNEL32.dll')
            self.assertEqual({x.name for x in deps}, {'SDL2.dll', 'libgcc.dll'})
            imports['libgcc.dll'] = ['missing.dll']
            with self.assertRaisesRegex(ValueError, 'missing.dll'):
                m.collect_dependencies(p / 'game.exe', [p], lambda path: imports[path.name], lambda n: n == 'KERNEL32.dll')

    def test_package_hashes_every_file_and_excludes_saves(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            launcher = p / 'launcher'
            launcher.mkdir()
            (launcher / 'EmeraldWorld.exe').write_bytes(b'MZlauncher')
            (launcher / '_internal').mkdir()
            (launcher / '_internal/python311.dll').write_bytes(b'MZpython')
            game = p / 'pokeemerald64.exe'
            game.write_bytes(b'MZgame')
            dll = p / 'SDL2.dll'
            dll.write_bytes(b'MZsdl')
            result = m.assemble(launcher, game, [dll], p / 'out')
            manifest = json.loads((p / 'out/checksums.json').read_text())
            with zipfile.ZipFile(result) as z:
                names = set(z.namelist())
                self.assertIn('EmeraldWorld/game/pokeemerald64.exe', names)
                self.assertIn('EmeraldWorld/game/SDL2.dll', names)
                self.assertEqual(len(manifest['files']), len(names))
                import hashlib
                for name, digest in manifest['files'].items():
                    self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(), digest)
            (launcher / 'private.sav').write_bytes(b'never package saves')
            with self.assertRaisesRegex(ValueError, 'sav'):
                m.assemble(launcher, game, [dll], p / 'bad')


    def test_private_distribution_requires_explicit_authorization_flag(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launcher, game = self.fixture(root)
            m.assemble(launcher, game, [], root / 'prepared')
            self.assertFalse(json.loads((root/'prepared/checksums.json').read_text())['distribution_authorized'])
            package = m.assemble(launcher, game, [], root / 'authorized', distribution_authorized=True)
            self.assertTrue(json.loads((root/'authorized/checksums.json').read_text())['distribution_authorized'])
            with zipfile.ZipFile(package) as archive:
                self.assertIn('Private Windows test build', archive.read('EmeraldWorld/INSTALL.txt').decode())

    def fixture(self, root):
        launcher = root / 'launcher'
        (launcher / '_internal').mkdir(parents=True)
        (launcher / 'EmeraldWorld.exe').write_bytes(b'MZlauncher')
        (launcher / '_internal/python311.dll').write_bytes(b'MZpython')
        game = root / 'pokeemerald64.exe'
        game.write_bytes(b'MZgame')
        return launcher, game

    def test_contaminated_tree_is_rejected_before_any_copy(self):
        from unittest.mock import patch
        contaminants = {
            'invite.json': b'{"token":"synthetic-invitation-secret"}',
            '_internal/a.json': b'{"token":"synthetic-invitation-secret"}',
            '.env': b'TOKEN=synthetic-secret',
            '_internal/.env.production': b'TOKEN=synthetic-secret',
            '_internal/world.sqlite3': b'SQLite format 3\x00',
            '_internal/telemetry.json': b'{"user":"private"}',
            '_internal/config.toml': b'private = true',
            '_internal/renamed.txt': b'{"token":"synthetic-secret"}',
            '_internal/private.pem': b'-----BEGIN ' + b'PRIVATE KEY-----',
            '_internal/save.sav': b'save',
            '_internal/game.gba': b'rom',
            '_internal/payload.pickle': b'\x80\x04payload',
        }
        for name, content in contaminants.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                launcher, game = self.fixture(root)
                target = launcher / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                m = self.module()
                with patch.object(Path, 'mkdir', side_effect=AssertionError('write before validation')):
                    with self.assertRaises(ValueError):
                        m.assemble(launcher, game, [], root / 'out')
                self.assertFalse((root / 'out').exists())

    def test_expected_frozen_runtime_data_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launcher, game = self.fixture(root)
            runtime = {
                '_internal/_ssl.pyd': b'MZextension',
                '_internal/_tcl_data/init.tcl': b'# Tcl runtime\nset tcl_version 8.6\n',
                '_internal/_tcl_data/encoding/cp1252.enc': b'# Encoding\nS\n00 0 1\n',
                '_internal/_tcl_data/msgs/en.msg': b'::msgcat::mcset en Hello Hello\n',
                '_internal/_tcl_data/tcl8/8.6/http-2.9.tm': b'package provide http 2.9\n',
                '_internal/_tk_data/tk.tcl': b'package require Tcl 8.6\n',
                '_internal/_tk_data/images/logo100.gif': b'GIF89a' + b'\x00' * 16,
                '_internal/_tk_data/images/logoLarge.gif': b'GIF89a' + b'\x00' * 16,
                '_internal/_tk_data/images/README': b'Tk image usage information\n',
                '_internal/_tk_data/images/logo.eps': b'%!PS-Adobe-3.0 EPSF-3.0\n',
                '_internal/tcl8/8.6/http-2.9.tm': b'package provide http 2.9\n',
            }
            for name, content in runtime.items():
                path = launcher / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            with zipfile.ZipFile(launcher / '_internal/base_library.zip', 'w') as z:
                z.writestr('encodings/__init__.pyc', b'compiled fixture')
            archive = self.module().assemble(launcher, game, [], root / 'out')
            with zipfile.ZipFile(archive) as z:
                for name, content in runtime.items():
                    self.assertEqual(z.read('EmeraldWorld/' + name), content)

    def test_runtime_data_cannot_hide_invitation_or_serialized_payload(self):
        payloads = [b'{"token":"synthetic-secret","world":"private"}',
                    b'SQLite format 3\x00data', b'\x80\x04pickle',
                    b'-----BEGIN ' + b'PRIVATE KEY-----\nprivate',
                    b'set invite_token synthetic-secret\n',
                    b'API_KEY=synthetic-secret\n']
        for payload in payloads:
            with self.subTest(payload=payload[:15]), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                launcher, game = self.fixture(root)
                path = launcher / '_internal/_tcl_data/init.tcl'
                path.parent.mkdir()
                path.write_bytes(payload)
                with self.assertRaises(ValueError):
                    self.module().assemble(launcher, game, [], root / 'out')
                self.assertFalse((root / 'out').exists())

    def test_stdlib_zip_rejects_extra_user_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launcher, game = self.fixture(root)
            with zipfile.ZipFile(launcher / '_internal/base_library.zip', 'w') as z:
                z.writestr('encodings/__init__.pyc', b'compiled fixture')
                z.writestr('invite.json', '{"token":"synthetic-secret"}')
            with self.assertRaises(ValueError):
                self.module().assemble(launcher, game, [], root / 'out')
            self.assertFalse((root / 'out').exists())

    def test_linked_and_special_inputs_fail_without_output(self):
        import os
        from types import SimpleNamespace
        from unittest.mock import patch
        for kind in ('root_symlink', 'ancestor_symlink', 'file_symlink', 'hardlink', 'reparse'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                launcher, game = self.fixture(root)
                target = launcher / '_internal/python311.dll'
                original_lstat = Path.lstat
                def lstat(path, *args, **kwargs):
                    value = original_lstat(path, *args, **kwargs)
                    if kind == 'reparse' and path == target:
                        return SimpleNamespace(st_mode=value.st_mode, st_nlink=value.st_nlink,
                                               st_file_attributes=0x400)
                    return value
                if kind == 'root_symlink':
                    alias = root / 'alias'
                    alias.symlink_to(launcher, target_is_directory=True)
                    launcher = alias
                elif kind == 'ancestor_symlink':
                    alias = root / 'alias'
                    alias.symlink_to(root, target_is_directory=True)
                    launcher = alias / 'launcher'
                elif kind == 'file_symlink':
                    target.unlink()
                    target.symlink_to(game)
                elif kind == 'hardlink':
                    target.unlink()
                    os.link(game, target)
                with patch.object(Path, 'lstat', lstat):
                    with self.assertRaises(ValueError):
                        self.module().assemble(launcher, game, [], root / 'out')
                self.assertFalse((root / 'out').exists())

    def test_existing_output_and_save_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launcher, game = self.fixture(root)
            output = root / 'out'
            output.mkdir()
            save = output / 'player.sav'
            save.write_bytes(b'existing save')
            with self.assertRaises(ValueError):
                self.module().assemble(launcher, game, [], output)
            self.assertEqual(save.read_bytes(), b'existing save')
            self.assertEqual(list(output.iterdir()), [save])

    def test_zip_and_checksums_ignore_source_timestamps(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launcher, game = self.fixture(root)
            m = self.module()
            one = m.assemble(launcher, game, [], root / 'one')
            for source in [game, *launcher.rglob('*')]:
                os.utime(source, (1700000000, 1700000000))
            two = m.assemble(launcher, game, [], root / 'two')
            self.assertEqual(one.read_bytes(), two.read_bytes())
            self.assertEqual((root / 'one/checksums.json').read_bytes(),
                             (root / 'two/checksums.json').read_bytes())

    def test_unapproved_or_colliding_dependency_fails_before_output(self):
        for name in ('invite.json', 'SDL2.dll'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                launcher, game = self.fixture(root)
                first = root / name
                first.write_bytes(b'MZfixture')
                second = root / 'other' / name
                second.parent.mkdir()
                second.write_bytes(b'MZfixture')
                with self.assertRaises(ValueError):
                    self.module().assemble(launcher, game, [first, second], root / 'out')
                self.assertFalse((root / 'out').exists())

    def test_public_ca_bundle_allowed_but_private_key_at_same_path_rejected(self):
        import ssl
        certificates = ssl.create_default_context().get_ca_certs(binary_form=True)
        self.assertTrue(certificates, 'Local public CA fixture required')
        public = ssl.DER_cert_to_PEM_cert(certificates[0]).encode('ascii')
        for payload, accepted in ((public, True),
                                  (public + b'-----BEGIN ' + b'PRIVATE KEY-----\nprivate', False),
                                  (b'-----BEGIN CERTIFICATE-----\ngARwaWNrbGU=\n-----END CERTIFICATE-----\n', False),
                                  (b'{"token":"synthetic-secret"}', False)):
            with self.subTest(accepted=accepted), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                launcher, game = self.fixture(root)
                path = launcher / '_internal/certifi/cacert.pem'
                path.parent.mkdir()
                path.write_bytes(payload)
                if accepted:
                    archive = self.module().assemble(launcher, game, [], root / 'out')
                    with zipfile.ZipFile(archive) as z:
                        self.assertEqual(z.read('EmeraldWorld/_internal/certifi/cacert.pem'), public)
                else:
                    with self.assertRaises(ValueError):
                        self.module().assemble(launcher, game, [], root / 'out')
                    self.assertFalse((root / 'out').exists())

    def test_native_artifacts_reject_disguised_data_and_static_tokens(self):
        for payload in (b'{"token":"synthetic-secret"}',
                        b'MZfixture\nINVITE_TOKEN=synthetic-secret\n'):
            with self.subTest(payload=payload[:10]), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                launcher, game = self.fixture(root)
                (launcher / '_internal/runtime.dll').write_bytes(payload)
                with self.assertRaises(ValueError):
                    self.module().assemble(launcher, game, [], root / 'out')
                self.assertFalse((root / 'out').exists())

    def test_bounded_runner_writes_only_sanitized_status(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / 'report.json'
            command = [sys.executable, str(ROOT / 'scripts/windows_verify.py'),
                       '--label', 'unit', '--timeout', '1', '--report', str(report), '--',
                       sys.executable, '-c', 'import time; print("TEST_SECRET", flush=True); time.sleep(10)']
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 1)
            self.assertTrue(report.exists(), 'bounded runner must write its report')
            data = json.loads(report.read_text())
            self.assertTrue(data['timed_out'])
            self.assertNotIn('TEST_SECRET', report.read_text() + result.stdout + result.stderr)


    def test_workflow_only_uploads_explicit_text_evidence(self):
        path = ROOT / '.github/workflows/windows-client.yml'
        self.assertTrue(path.exists(), 'Windows workflow is missing')
        text = path.read_text()
        self.assertIn('contents: read', text)
        self.assertIn('persist-credentials: false', text)
        self.assertIn('make -j4 winwsl PREFIX= CC=gcc CXX=g++ SDL_DIR=/mingw64 OS=Windows_NT WERROR=1', text)
        private_upload = text.split('name: Upload verified private Windows client')[1].split('name: Upload text verification only')[0]
        self.assertIn('if: success()', private_upload)
        self.assertIn('path: build/windows-package/EmeraldWorld-windows-x64.zip', private_upload)
        self.assertNotIn('*', private_upload)
        self.assertIn('--authorize-private-distribution', text)
        import re
        for reference in re.findall(r'uses:\s*(\S+)', text):
            self.assertRegex(reference, r'^(actions/(checkout|setup-python|upload-artifact)|msys2/setup-msys2)@[0-9a-f]{40}$')
        upload = text.split('name: Upload text verification only')[1]
        self.assertNotIn('*', upload)
        self.assertNotIn('.zip', upload)
        self.assertNotIn('.sav', upload)
        self.assertNotIn('private.log', upload)
        self.assertIn('verification/checksums.json', upload)
        self.assertIn('python -m world.windows_client --self-test', text)
        self.assertIn('scripts/windows_bridge_test.py', text)


    def test_windows_entry_and_native_fixture_are_executable_scripts(self):
        import subprocess
        import sys
        bridge = ROOT / 'scripts/windows_bridge_test.py'
        entry = ROOT / 'scripts/windows_entry.py'
        self.assertTrue(entry.exists(), 'Frozen entry point is missing')
        self.assertIn('from world.windows_client import main', entry.read_text())
        self.assertTrue(bridge.exists(), 'Windows native fixture is missing')
        result = subprocess.run([sys.executable, str(bridge), '--help'], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertIn('--binary', result.stdout)
        self.assertIn('--save', result.stdout)


if __name__ == '__main__':
    unittest.main()
