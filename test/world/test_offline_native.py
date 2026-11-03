"""Opt-in real native offline checks using freshly generated smoke fixtures.

Run smoke.py first, then set EMERALD_OFFLINE_BINARY to its built binary and
EMERALD_OFFLINE_SCENARIOS to that smoke output directory. No personal saves.
These are scripted headless engine runs, not human graphical acceptance.
"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from world.launcher import game_command, profile_paths
from world.session import DesktopSession

ROOT = Path(__file__).resolve().parents[2]
BINARY = os.environ.get('EMERALD_OFFLINE_BINARY', '')
SCENARIOS = os.environ.get('EMERALD_OFFLINE_SCENARIOS', '')


@unittest.skipUnless(BINARY and SCENARIOS, 'Set explicit binary and disposable smoke scenario directory')
class OfflineNativeTests(unittest.TestCase):
    def seed(self, state):
        paths = profile_paths(state, 'alice')
        paths['profile'].mkdir(parents=True)
        shutil.copyfile(Path(SCENARIOS)/'new_game/game.sav', paths['save'])
        return paths

    def validate(self, save, party, counter, map_id):
        result = subprocess.run([sys.executable, str(ROOT/'test/headless/savecheck.py'), str(save),
                                 '--expect-party', str(party), '--expect-counter', str(counter),
                                 '--expect-map', map_id], text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_cli_real_native_copy_progress_resume_without_online_mutation(self):
        with tempfile.TemporaryDirectory(prefix='ew-off-native-') as tmp:
            state = Path(tmp)/'world'
            paths = self.seed(state)
            before = hashlib.sha256(paths['save'].read_bytes()).hexdigest()
            base = [sys.executable, '-m', 'world.launcher', '--state-dir', str(state), 'offline',
                    'alice', '--binary', str(Path(BINARY).resolve())]
            for scenario in ('continue_game', 'first_battle'):
                command = base + (['--copy-online'] if scenario == 'continue_game' else [])
                command += ['--test-input', str((Path(SCENARIOS)/scenario/'input.txt').resolve())]
                result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=90)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, '')
            offline = state/'.offline/trainers/alice/game.sav'
            self.validate(offline, 1, 3, '1.4')
            self.assertEqual(before, hashlib.sha256(paths['save'].read_bytes()).hexdigest())
            self.assertNotEqual(offline.read_bytes(), paths['save'].read_bytes())
            self.assertFalse((state/'world.sqlite3').exists())
            self.assertFalse((state/'transport').exists())
            self.assertFalse((offline.parent/'world.conf').exists())
            self.assertTrue((state/'.offline/.offline-copy').is_file())

    def test_desktop_real_child_runs_without_host_and_cleanup_keeps_online_save(self):
        with tempfile.TemporaryDirectory(prefix='ew-off-desktop-') as tmp:
            root = Path(tmp)
            state = root/'world'
            paths = self.seed(state)
            before = paths['save'].read_bytes()
            # Only add bounded upstream test controls to the real sandbox command.
            # Native executable, mounts, save path and process ownership are real.
            def scripted_command(binary, offline, target, display, *, online):
                self.assertFalse(online)
                command = game_command(binary, offline, target, display, online=False)
                self.assertNotIn('--world-config', command)
                controls = target['profile']/'input.txt'
                shutil.copyfile(Path(SCENARIOS)/'continue_game/input.txt', controls)
                return command + ['--test-input', str(controls)]
            with DesktopSession(root) as session:
                with patch('world.session.game_command', scripted_command):
                    process = session.launch_offline('world', 'alice', Path(BINARY).resolve(),
                                                     display=None, copy_online=True)
                self.assertEqual(process.wait(timeout=90), 0)
                self.assertIsNone(session.server)
                self.assertIsNone(session.broker)
                self.assertIsNone(session.state)
                self.assertIn('Save kept', session.poll())
            offline = state/'.offline/trainers/alice/game.sav'
            self.validate(offline, 0, 2, '1.0')
            self.assertEqual(paths['save'].read_bytes(), before)
            self.assertFalse((state/'world.sqlite3').exists())
            self.assertFalse((state/'transport').exists())
            log = (offline.parent/'native.log').read_text()
            self.assertNotIn('expected "name = value"', log)


if __name__ == '__main__':
    unittest.main()
