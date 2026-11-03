"""Headless tests for the Linux checkout launcher. Never open a GUI."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2] / 'scripts/linux_client.py'


class LinuxClientTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='emerald linux ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.repo = self.root / 'checkout'
        (self.repo / 'scripts').mkdir(parents=True)
        self.script = self.repo / 'scripts/linux_client.py'
        if SOURCE.exists():
            shutil.copyfile(SOURCE, self.script)
        self.hooks = self.root / 'hooks'
        self.hooks.mkdir()
        (self.hooks / 'sitecustomize.py').write_text(
            'import os, shutil, ctypes, sys, types\n'
            'present = os.environ.get("TEST_DEPS") == "present"\n'
            'shutil.which = lambda name: "/usr/bin/" + name if present else None\n'
            'def load(name):\n'
            '    if not present: raise OSError("missing")\n'
            '    return object()\n'
            'ctypes.CDLL = load\n'
            'sys.modules["tkinter"] = types.ModuleType("tkinter") if present else None\n')

    def binary(self, relative='build/pokeemerald64', mode=0o700):
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'\x7fELF' + b'\x00' * 60)
        path.chmod(mode)
        return path

    def cli(self, *args, present=True):
        env = dict(os.environ, HOME=str(self.home), PYTHONPATH=str(self.hooks),
                   TEST_DEPS='present' if present else 'missing')
        return subprocess.run([sys.executable, str(self.script), *args], env=env,
                              cwd='/', capture_output=True, text=True, timeout=10)

    def test_check_cli_reports_missing_without_writes(self):
        result = self.cli('--check', present=False)
        self.assertEqual(result.returncode, 1, result.stderr)
        for item in ('tkinter', 'bwrap', 'Xephyr', 'binary', 'SDL2'):
            self.assertIn('MISSING ' + item, result.stdout)
        self.assertEqual(list(self.home.iterdir()), [])

    def load(self):
        spec = importlib.util.spec_from_file_location('linux_client_test_target', SOURCE)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_check_present_and_binary_permissions(self):
        self.binary()
        result = self.cli('--check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('OK binary', result.stdout)
        (self.repo / 'build/pokeemerald64').chmod(0o600)
        result = self.cli('--check')
        self.assertEqual(result.returncode, 1)
        self.assertIn('MISSING binary', result.stdout)

    def test_install_cli_is_explicit_and_preserves_existing_data(self):
        self.binary()
        state = self.home / '.local/share/emerald-world/worlds/friends'
        state.mkdir(parents=True)
        save = state / 'game.sav'
        save.write_bytes(b'existing save')
        result = self.cli('--install-user')
        self.assertEqual(result.returncode, 0, result.stderr)
        launcher = self.home / '.local/share/applications/emerald-world.desktop'
        text = launcher.read_text()
        self.assertIn('Exec="' + str(Path(sys.executable).resolve()) + '" "' + str(self.script) + '"', text)
        self.assertNotIn('sh -c', text)
        self.assertEqual(self.cli('--install-user').returncode, 0)
        launcher.write_text('[Desktop Entry]\nName=Someone else\n')
        self.assertEqual(self.cli('--install-user').returncode, 1)
        self.assertEqual(launcher.read_text(), '[Desktop Entry]\nName=Someone else\n')
        self.assertEqual(save.read_bytes(), b'existing save')

    def test_launch_uses_existing_api_and_local_root(self):
        client = self.load()
        binary = self.binary('pokeemerald64')
        with patch.object(client, 'REPO', self.repo), patch.object(client, 'discover_display', return_value=':98'), patch.object(client, 'prerequisites', return_value=[]), patch.dict(os.environ, HOME=str(self.home)), patch('world.session.run_desktop', return_value=0) as run:
            self.assertEqual(client.main([]), 0)
        run.assert_called_once_with(self.home / '.local/share/emerald-world/worlds', binary=binary, display=':98')
        self.binary()
        with patch.object(client, 'REPO', self.repo):
            self.assertEqual(client.discover_binary(), self.repo / 'build/pokeemerald64')

    def test_display_selection_avoids_sockets_locks_and_dangling_links(self):
        client = self.load()
        displays = self.root/'displays'
        (displays/'.X11-unix').mkdir(parents=True)
        (displays/'.X11-unix/X90').touch()
        (displays/'.X91-lock').touch()
        (displays/'.X11-unix/X92').symlink_to(displays/'absent')
        self.assertEqual(client.discover_display(displays), ':93')
        for number in range(93, 200):
            (displays/('.X' + str(number) + '-lock')).touch()
        with self.assertRaises(ValueError):
            client.discover_display(displays)

    def test_invitation_prefills_via_existing_app_without_connecting(self):
        import json
        from world import session
        client = self.load()
        invitation = self.root / 'friend.json'
        invitation.write_text(json.dumps({'version': 1, 'trainer': 'friend', 'token': 'a' * 64,
                                         'endpoint': {'host': 'example.org', 'port': 8765}, 'pin': 'b' * 64}))
        calls = []
        class App:
            def __init__(self, *args):
                calls.append('created')
            def import_friend_invitation(self, path):
                calls.append(path)
        def run(*args, **kwargs):
            session.DesktopApp(None, None, None, None)
            return 0
        with patch.object(client, 'prerequisites', return_value=[]), patch.object(session, 'DesktopApp', App), patch.object(session, 'run_desktop', side_effect=run):
            self.assertEqual(client.main(['--invitation', str(invitation)]), 0)
            self.assertIs(session.DesktopApp, App)
        self.assertEqual(calls, ['created', invitation])
        from unittest.mock import Mock
        class ChangedApp(App):
            message = Mock()
            def import_friend_invitation(self, path):
                raise ValueError('DO_NOT_PRINT')
        with patch.object(client, 'prerequisites', return_value=[]), patch.object(session, 'DesktopApp', ChangedApp), patch.object(session, 'run_desktop', side_effect=run):
            self.assertEqual(client.main(['--invitation', str(invitation)]), 0)
            self.assertIs(session.DesktopApp, ChangedApp)
        ChangedApp.message.set.assert_called_once_with('Invalid friend invitation. No connection settings were changed.')
        invitation.write_text('{"token": "DO_NOT_PRINT"}')
        with patch('world.session.run_desktop') as run, patch('sys.stderr') as stderr:
            self.assertEqual(client.main(['--invitation', str(invitation)]), 1)
            run.assert_not_called()
            self.assertNotIn('DO_NOT_PRINT', str(stderr.write.call_args_list))

    def test_rejects_non_native_or_unreadable_binary(self):
        client = self.load()
        binary = self.binary()
        binary.write_bytes(b'not a native executable')
        self.assertFalse(client.binary_ready(binary))
        self.binary()
        with patch.object(client.os, 'access', return_value=False):
            self.assertFalse(client.binary_ready(binary))

    def test_install_rejects_symlink_and_unsafe_exec_token(self):
        self.binary()
        directory = self.home / '.local/share/applications'
        directory.mkdir(parents=True)
        other = self.home / 'unrelated'
        other.write_text('keep')
        (directory / 'emerald-world.desktop').symlink_to(other)
        self.assertEqual(self.cli('--install-user').returncode, 1)
        self.assertEqual(other.read_text(), 'keep')
        client = self.load()
        for token in ('bad\npath', 'bad%F', '$(touch bad)', 'bad"quote'):
            with self.assertRaises(ValueError):
                client.exec_token(token)


if __name__ == '__main__':
    unittest.main()
