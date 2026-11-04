"""Launcher installer orchestration with disposable files and no network."""
import contextlib
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import setup_react_launcher as setup


class SetupTests(unittest.TestCase):
    def test_supported_node_versions(self):
        for version in ('v20.19.0', 'v22.12.0', 'v24.0.0', 'v26.1.0'):
            self.assertTrue(setup.node_supported(version), version)
        for version in ('v20.18.1', 'v21.5.0', 'v22.11.0', 'v23.0.0', 'garbage'):
            self.assertFalse(setup.node_supported(version), version)

    def test_builds_locked_frontend_and_optionally_installs_shortcut(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); project = root / 'launcher-web'; project.mkdir()
            (project / 'package-lock.json').write_text('{}')
            commands = []
            def run(command, **kwargs):
                commands.append((command, kwargs))
                if command[1:] == ['run', 'build']:
                    (project / 'dist').mkdir(); (project / 'dist/index.html').write_text('ok')
                return subprocess.CompletedProcess(command, 0)
            with patch.object(setup, 'REPO', root), patch.object(setup, 'check_node', return_value='/usr/bin/npm'), \
                 patch.object(setup, 'report_native', return_value=False), patch.object(setup.subprocess, 'run', side_effect=run), \
                 patch('world.web_launcher.install_shortcut') as shortcut, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(setup.main(['--install-shortcut']), 0)
            self.assertEqual([entry[0][1:] for entry in commands], [['ci', '--no-audit', '--no-fund'], ['run', 'build']])
            self.assertTrue(all(entry[1]['cwd'] == project and entry[1]['check'] for entry in commands))
            shortcut.assert_called_once_with()

    def test_check_does_not_build_or_install(self):
        with patch.object(setup, 'check_node', return_value='/usr/bin/npm'), \
             patch.object(setup, 'report_native', return_value=False), \
             patch.object(setup.subprocess, 'run') as run, patch('world.web_launcher.install_shortcut') as shortcut, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(setup.main(['--check']), 1)
        run.assert_not_called(); shortcut.assert_not_called()

    def test_failed_build_never_installs_shortcut(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); project = root / 'launcher-web'; project.mkdir()
            (project / 'package-lock.json').write_text('{}')
            with patch.object(setup, 'REPO', root), patch.object(setup, 'check_node', return_value='/usr/bin/npm'), \
                 patch.object(setup.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'npm')), \
                 patch('world.web_launcher.install_shortcut') as shortcut, contextlib.redirect_stdout(io.StringIO()), \
                 contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as result:
                    setup.main(['--install-shortcut'])
            self.assertEqual(result.exception.code, 1)
            shortcut.assert_not_called()


if __name__ == '__main__':
    unittest.main()
