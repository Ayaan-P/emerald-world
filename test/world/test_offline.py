"""Offline launch/save isolation tests. No emulator gameplay is claimed here."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from world import launcher


class OfflineTests(unittest.TestCase):
    def test_offline_command_never_mounts_or_configures_world_transport(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / 'world'
            state.mkdir(mode=0o700)
            paths = launcher.profile_paths(state / '.offline', 'alice')
            paths['profile'].mkdir(parents=True)
            # An offline command must not even inspect the online transport.
            transport = state / '.offline/transport'
            transport.mkdir()
            (transport / 'not-a-public-socket').write_text('not game data')
            command = launcher.game_command('/usr/bin/false', state / '.offline', paths, online=False)
            self.assertNotIn('--world-config', command)
            self.assertNotIn(str(transport), command)
            self.assertNotIn(str(paths['config']), command)
            self.assertIn('--unshare-all', command)
            self.assertIn('--clearenv', command)
            self.assertNotIn('--share-net', command)
            self.assertIn(str(paths['save']), command)

    def test_copy_online_once_and_never_merge_back(self):
        from world.offline import offline_profile
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / 'world'
            state.mkdir(mode=0o700)
            online = launcher.profile_paths(state, 'alice')
            online['profile'].mkdir(parents=True)
            online['save'].write_bytes(b'online-disposable-save')
            online['config'].write_text('private credentials must stay here')
            with patch('world.server.create_identity', side_effect=AssertionError('offline identity creation')):
                with offline_profile(state, 'alice', copy_online=True) as paths:
                    self.assertEqual(paths['save'].read_bytes(), online['save'].read_bytes())
                    self.assertFalse(paths['config'].exists())
                    # Snapshotting must release the source so independent online
                    # progress can resume while the offline copy is played.
                    with launcher.ProfileLock(state, 'alice'):
                        pass
                    paths['save'].write_bytes(b'offline-progress')
                with offline_profile(state, 'alice') as paths:
                    self.assertEqual(paths['save'].read_bytes(), b'offline-progress')
            self.assertEqual(online['save'].read_bytes(), b'online-disposable-save')
            self.assertEqual(online['config'].read_text(), 'private credentials must stay here')
            self.assertFalse((state / '.offline/world.sqlite3').exists())
            with self.assertRaisesRegex(ValueError, 'overwrite|exists'):
                with offline_profile(state, 'alice', copy_online=True):
                    pass

    def test_active_source_and_destination_are_not_copied_over(self):
        from world.offline import offline_profile
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / 'world'
            state.mkdir(mode=0o700)
            online = launcher.profile_paths(state, 'alice')
            online['profile'].mkdir(parents=True)
            online['save'].write_bytes(b'source')
            with launcher.ProfileLock(state, 'alice'):
                with self.assertRaisesRegex(ValueError, 'use|active'):
                    with offline_profile(state, 'alice', copy_online=True):
                        pass
            with offline_profile(state, 'alice'):
                with self.assertRaisesRegex(ValueError, 'use|active'):
                    with offline_profile(state, 'alice'):
                        pass
            self.assertEqual(online['save'].read_bytes(), b'source')

    def test_refuses_linked_offline_root_save_and_seed(self):
        from world.offline import offline_profile
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / 'world'
            state.mkdir(mode=0o700)
            outside = state / 'outside'
            outside.mkdir()
            (state / '.offline').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                with offline_profile(state, 'alice'):
                    pass
            (state / '.offline').unlink()
            seed = state / 'seed'
            seed.write_bytes(b'disposable')
            linked_seed = state / 'seed-link'
            linked_seed.symlink_to(seed)
            with self.assertRaises(ValueError):
                with offline_profile(state, 'alice', seed_save=linked_seed):
                    pass
            with offline_profile(state, 'alice') as paths:
                paths['save'].symlink_to(seed)
            with self.assertRaises(ValueError):
                with offline_profile(state, 'alice'):
                    pass
            self.assertEqual(seed.read_bytes(), b'disposable')

    def test_cli_offline_prepares_no_service_or_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / 'world'
            seed = Path(tmp) / 'seed'
            seed.write_bytes(b'fixture')
            result = subprocess.run([sys.executable, '-m', 'world.launcher', '--state-dir', str(state),
                                     'offline', 'alice', '--seed-save', str(seed), '--print-command'],
                                    text=True, capture_output=True, timeout=10,
                                    cwd=Path(__file__).resolve().parents[2])
            self.assertEqual(result.returncode, 0, result.stderr)
            command = json.loads(result.stdout)
            self.assertNotIn('--world-config', command)
            self.assertFalse((state / 'transport').exists())
            self.assertFalse((state / 'world.sqlite3').exists())
            self.assertFalse((state / 'trainers').exists())
            self.assertEqual((state / '.offline/trainers/alice/game.sav').read_bytes(), b'fixture')

    def test_offline_namespace_cannot_be_relaunched_as_online(self):
        from world.offline import offline_profile
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / 'world'
            with offline_profile(state, 'alice') as paths:
                offline = state / '.offline'
                with self.assertRaisesRegex(ValueError, 'Offline copies'):
                    launcher.game_command('/usr/bin/false', offline, paths)
            for command in ('host', 'inspect', 'join'):
                args = ['--state-dir', str(offline), command]
                if command == 'join':
                    args.append('alice')
                with self.assertRaisesRegex(ValueError, 'Offline copies'):
                    launcher.main(args)
            self.assertFalse((offline / 'transport').exists())
            self.assertFalse((offline / 'world.sqlite3').exists())

    def test_cli_retains_lock_until_actual_child_exits(self):
        from world.offline import run_offline
        import argparse
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / 'world'
            state.mkdir(mode=0o700)
            args = argparse.Namespace(state_dir=state, trainer='alice', seed_save=None,
                                      copy_online=False, binary=Path('/usr/bin/false'), display=None,
                                      test_input=None, print_command=False)
            def command(binary, state_dir, paths, display, *, online):
                self.assertFalse(online)
                with self.assertRaises(ValueError):
                    launcher.ProfileLock(state / '.offline', 'alice')
                return ['/usr/bin/false']
            with patch('world.offline.game_command', command):
                self.assertEqual(run_offline(args), 1)
            with launcher.ProfileLock(state / '.offline', 'alice'):
                pass


if __name__ == '__main__':
    unittest.main()
