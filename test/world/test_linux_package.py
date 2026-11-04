"""Exercise real archives with a disposable compiled ELF, never the game binary."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from urllib.parse import urlsplit
import unittest

REPO = Path(__file__).resolve().parents[2]
PACKAGER = REPO / 'scripts/linux_package.py'


class LinuxPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='emerald-package-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.binary = self.root / 'fixture'
        subprocess.run(['cc', '-x', 'c', '-', '-o', str(self.binary)],
                       input='int main(void) { return 0; }\n', text=True, check=True)
        self.dist = self.root / 'dist'
        (self.dist / 'assets').mkdir(parents=True)
        (self.dist / 'index.html').write_text('<html><script src="/assets/main.js"></script></html>')
        (self.dist / 'assets/main.js').write_text('console.log("fixture");')

    def package(self, version='1.2.3', output=None, success=True):
        output = output or self.root / ('output-' + version)
        result = subprocess.run([sys.executable, str(PACKAGER), '--binary', str(self.binary),
            '--web-dist', str(self.dist), '--version', version, '--output', str(output)],
            capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return output / ('EmeraldWorld-' + version + '-linux-x86_64.tar.gz')

    def extract(self, archive):
        target = self.root / ('extracted-' + archive.parent.name)
        target.mkdir()
        with tarfile.open(archive) as stream:
            stream.extractall(target, filter='data')
        return next(target.iterdir())

    def test_archive_contains_only_release_inputs_and_checksums(self):
        bundle = self.extract(self.package())
        manifest = json.loads((bundle / 'manifest.json').read_text())
        self.assertEqual(manifest['version'], '1.2.3')
        self.assertEqual(manifest['architecture'], 'x86_64')
        self.assertEqual(manifest['runtime']['python'], '>=3.11 (system, standard library only)')
        self.assertIn('libc.so.6', manifest['runtime']['native_libraries'])
        self.assertTrue((bundle / 'scripts/__init__.py').is_file())
        self.assertTrue((bundle / 'world/web_launcher.py').is_file())
        self.assertTrue((bundle / 'launcher-web/dist/index.html').is_file())
        self.assertTrue(os.access(bundle / 'build/pokeemerald64', os.X_OK))
        for name, metadata in manifest['files'].items():
            self.assertEqual(hashlib.sha256((bundle / name).read_bytes()).hexdigest(), metadata['sha256'])
        self.assertFalse(any(p.suffix in {'.sav', '.db', '.pyc'} for p in bundle.rglob('*')))

    def install(self, bundle, success=True):
        env = dict(os.environ, HOME=str(self.root / 'home'))
        result = subprocess.run([sys.executable, '-I', str(bundle / 'install.py')],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return self.root / 'home/.local/share/emerald-world-player'

    def test_install_update_preserves_saves_and_supports_check_without_desktop(self):
        bundle = self.extract(self.package())
        prefix = self.install(bundle)
        save = self.root / 'home/.local/share/emerald-world/worlds/example/profiles/test/game.sav'
        save.parent.mkdir(parents=True)
        save.write_bytes(b'private disposable save sentinel')
        self.install(bundle)  # Idempotent.
        newer = self.extract(self.package('1.2.4'))
        self.install(newer)
        self.assertEqual((prefix / 'current').resolve(), prefix / 'releases/1.2.4')
        self.assertTrue((prefix / 'releases/1.2.3').is_dir())
        self.assertEqual(save.read_bytes(), b'private disposable save sentinel')
        shortcut = self.root / 'home/.local/share/applications/emerald-world-player.desktop'
        self.assertIn('current/entry.py', shortcut.read_text())
        result = subprocess.run([sys.executable, '-I', str(prefix / 'current/entry.py'), '--check'],
                                capture_output=True, text=True)
        self.assertIn('OK integrity', result.stdout, result.stderr)
        self.assertIn('OK Python', result.stdout)
        self.assertIn('No game or display was started', result.stdout)
        self.assertNotIn('Traceback', result.stderr)
        # Import real packaged modules and exercise their generated runtime data.
        code = 'import sys; sys.path.insert(0, sys.argv[1]); from world.build_catalog import catalog_maps; assert catalog_maps(); import world.web_launcher'
        subprocess.run([sys.executable, '-I', '-c', code, str(prefix / 'current')], check=True)

    def test_archive_is_reproducible_and_sets_supported_glibc_floor(self):
        first = self.package(output=self.root / 'first')
        second = self.package(output=self.root / 'second')
        self.assertEqual(first.read_bytes(), second.read_bytes())
        manifest = json.loads((self.extract(first) / 'manifest.json').read_text())
        self.assertGreaterEqual(tuple(map(int, manifest['runtime']['glibc_minimum'].split('.'))), (2, 35))

    def test_missing_referenced_web_asset_is_rejected(self):
        (self.dist / 'assets/main.js').unlink()
        self.package(success=False)

    def test_private_frontend_artifact_is_rejected(self):
        (self.dist / 'invitation.json').write_text('{"invite_token":"private fixture"}')
        self.package(success=False)

    def test_linked_frontend_input_is_rejected(self):
        (self.dist / 'assets/linked.js').symlink_to(self.dist / 'assets/main.js')
        self.package(success=False)

    def test_modified_installed_release_cannot_be_replaced(self):
        bundle = self.extract(self.package())
        prefix = self.install(bundle)
        (prefix / 'releases/1.2.3/entry.py').write_text('modified')
        self.install(bundle, success=False)

    def test_foreign_shortcut_is_not_overwritten(self):
        bundle = self.extract(self.package())
        shortcut = self.root / 'home/.local/share/applications/emerald-world-player.desktop'
        shortcut.parent.mkdir(parents=True)
        shortcut.write_text('user owned unrelated shortcut')
        self.install(bundle, success=False)
        self.assertEqual(shortcut.read_text(), 'user owned unrelated shortcut')
        self.assertFalse((self.root / 'home/.local/share/emerald-world-player').exists())

    def test_invalid_version_is_rejected(self):
        self.package('not-a-version', success=False)

    def test_extra_private_file_in_extracted_bundle_blocks_install(self):
        bundle = self.extract(self.package())
        (bundle / 'game.sav').write_bytes(b'private fixture')
        self.install(bundle, success=False)

    def test_help_needs_no_desktop(self):
        bundle = self.extract(self.package())
        for name in ('install.py', 'entry.py'):
            result = subprocess.run([sys.executable, '-I', str(bundle / name), '--help'],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('usage:', result.stdout)

    def test_install_check_is_read_only_and_validates_runtime_interpreter(self):
        bundle = self.extract(self.package())
        env = dict(os.environ, HOME=str(self.root / 'home'))
        result = subprocess.run([sys.executable, '-I', str(bundle / 'install.py'), '--check'],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Release and standalone Python verified', result.stdout)
        self.assertFalse((self.root / 'home').exists())

    def test_packaged_loopback_launcher_with_captured_browser_and_disposable_home(self):
        bundle = self.extract(self.package())
        prefix = self.install(bundle)
        entry = prefix / 'current/entry.py'
        result = subprocess.run([sys.executable, '-I', str(entry), '--check'],
                                capture_output=True, text=True)
        if result.returncode:
            self.skipTest('Real launcher smoke requires runtime prerequisites: ' + result.stdout)
        captured = self.root / 'browser-url'
        helper = self.root / 'browser.py'
        helper.write_text('import sys; from pathlib import Path; Path(sys.argv[1]).write_text(sys.argv[2])')
        env = dict(os.environ, HOME=str(self.root / 'smoke-home'),
                   BROWSER=f'{sys.executable} {helper} {captured} %s')
        proc = subprocess.Popen([sys.executable, '-I', str(entry)],
                                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 10
            while not captured.exists() and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(.05)
            self.assertTrue(captured.exists(), 'Packaged launcher did not invoke the capture browser')
            url = urlsplit(captured.read_text())
            origin = f'{url.scheme}://{url.netloc}'
            with urllib.request.urlopen(origin + '/', timeout=5) as response:
                self.assertIn(b'/assets/main.js', response.read())
            with urllib.request.urlopen(origin + '/assets/main.js', timeout=5) as response:
                self.assertIn(b'fixture', response.read())
            headers = {'Authorization': 'Bearer ' + url.fragment, 'Origin': origin}
            request = urllib.request.Request(origin + '/api/state', headers=headers)
            with urllib.request.urlopen(request, timeout=5) as response:
                state = json.load(response)
            self.assertEqual(state['worlds'], [])
            self.assertFalse(state['connected'])
            headers['Content-Type'] = 'application/json'
            request = urllib.request.Request(origin + '/api/action', headers=headers,
                data=b'{"action":"quit","payload":{}}')
            with urllib.request.urlopen(request, timeout=5) as response:
                self.assertEqual(response.status, 200)
            stdout, stderr = proc.communicate(timeout=10)
            self.assertEqual(proc.returncode, 0, stdout + stderr)
            self.assertFalse(any((self.root / 'smoke-home').rglob('*.sav')))
        finally:
            if proc.poll() is None:
                proc.terminate()
                proc.communicate(timeout=5)

    def test_installer_rejects_modified_archive_before_writing(self):
        bundle = self.extract(self.package())
        (bundle / 'launcher-web/dist/assets/main.js').write_text('modified')
        self.install(bundle, success=False)
        self.assertFalse((self.root / 'home/.local/share/emerald-world-player').exists())


if __name__ == '__main__':
    unittest.main()
