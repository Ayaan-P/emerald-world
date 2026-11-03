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
        self.assertIn('make -j2 winwsl PREFIX= CC=gcc CXX=g++ SDL_DIR=/mingw64 OS=Windows_NT WERROR=1', text)
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
