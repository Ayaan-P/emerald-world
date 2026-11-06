"""Small engine-selection and launch ABI contract tests."""
import tempfile
import unittest
from pathlib import Path
from world import launcher


class ExpansionEngineTest(unittest.TestCase):
    def test_default_and_explicit_profile_namespaces(self):
        with tempfile.TemporaryDirectory() as directory:
            import inspect
            self.assertIn('engine', inspect.signature(launcher.profile_paths).parameters)
            default = launcher.profile_paths(directory, 'Ash')
            self.assertEqual(default['profile'], Path(directory)/'trainers/Ash')
            expanded = launcher.profile_paths(directory, 'Ash', engine='expansion-native')
            self.assertEqual(expanded['profile'], Path(directory)/'engines/expansion-native/trainers/Ash')
            self.assertNotEqual(default['save'], expanded['save'])
            with self.assertRaises(ValueError):
                launcher.profile_paths(directory, 'Ash', engine='typo')

    def test_online_and_offline_expansion_never_share_a_profile(self):
        from world.expansion import ExpansionSession
        with tempfile.TemporaryDirectory() as directory:
            online = ExpansionSession(directory, 'Ash')
            offline = ExpansionSession(directory, 'Ash', online=False)
            self.assertEqual(online.paths, launcher.profile_paths(directory, 'Ash', engine='expansion-native'))
            self.assertNotEqual(online.paths['save'], offline.paths['save'])
            self.assertIn('.offline', offline.paths['save'].parts)
            with self.assertRaises(ValueError):
                ExpansionSession(Path(directory)/'.offline', 'Ash')
            elsewhere = Path(directory)/'elsewhere'
            elsewhere.mkdir()
            (Path(directory)/'.offline').symlink_to(elsewhere)
            with self.assertRaises(ValueError):
                ExpansionSession(directory, 'Ash', online=False)

    def test_host_creates_engine_namespace_before_lifecycle_lock(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            with patch('world.server.WorldServer') as host:
                self.assertEqual(launcher.main(['--state-dir', directory, 'host',
                                                '--engine', 'expansion-native']), 0)
                self.assertEqual(host.call_args.args[1], str(Path(directory)/'engines/expansion-native'))

    def test_launcher_explicit_engine_routes_to_expansion_session(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            with patch('world.expansion.run', return_value=0) as run:
                self.assertEqual(launcher.main(['--state-dir', directory, 'join', 'Ash',
                                                '--engine', 'expansion-native', '--print-command']), 0)
                self.assertEqual(run.call_args.args[0].engine, 'expansion-native')

    def test_presence_session_drains_peer_broadcasts_independently(self):
        import json
        import threading
        import time
        from world.client import WorldClient
        from world.expansion import ExpansionSession
        from contextlib import closing
        from world.server import WorldServer
        with tempfile.TemporaryDirectory() as directory:
            session = ExpansionSession(directory, 'Ash')
            session.state.mkdir(parents=True)
            with closing(WorldServer(session.state/'transport/world.sock', session.state)) as server:
                server.start()
                launcher.prepare_profile(session.state, 'Ash')
                bob = launcher.prepare_profile(session.state, 'Bob')
                config = dict(line.split(' ', 1) for line in bob['config'].read_text().splitlines())
                fixture = dict(schema=1, engine='expansion-native', frame=6, field=False)
                (session.paths['profile']/'presence.json').write_text(json.dumps(fixture))
                worker = threading.Thread(target=session._presence)
                worker.start()
                try:
                    deadline = time.monotonic()+1
                    while not session.paths['telemetry'].exists() and time.monotonic() < deadline:
                        time.sleep(.01)
                    with WorldClient(config['socket'], 'Bob', config['token']) as peer:
                        peer.snapshot()
                        for seq in range(1, 101):
                            (session.paths['profile']/'presence.json').touch()
                            peer.send_state(seq, 0, 0, 0, 0, 1, 7, 0, f'{seq:016x}', '0'*16)
                            target = peer.snapshot()['revision']
                    deadline = time.monotonic()+.5
                    actual = -1
                    while time.monotonic() < deadline:
                        actual = json.loads(session.paths['telemetry'].read_text())['revision']
                        if actual >= target:
                            break
                        time.sleep(.01)
                    self.assertIsNone(session.error)
                    self.assertGreaterEqual(actual, target)
                finally:
                    session.stop.set()
                    worker.join(timeout=3)
                    self.assertFalse(worker.is_alive())

    def test_replay_staging_does_not_mount_its_parent_directory(self):
        import contextlib
        import io
        import json
        from world.expansion import ExpansionSession
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'inputs'
            source.mkdir()
            (source/'start.replay').write_text('wait 10\n')
            replay = source/'main.replay'
            replay.write_text('include start.replay\nquit\n')
            session = ExpansionSession(Path(directory)/'world', 'Ash', online=False)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                session.run('/bin/true', replay=replay, print_command=True)
            command = json.loads(output.getvalue())
            self.assertNotIn(str(source), command)
            staged = Path(command[command.index('--replay')+1])
            self.assertEqual(staged.parent, session.paths['profile'])
            self.assertEqual(staged.read_text(), 'wait 10\nquit\n')
            replay.write_text('include ../secret\n')
            with self.assertRaises(ValueError):
                session.run('/bin/true', replay=replay, print_command=True)

    def test_expansion_rejects_vanilla_save_and_control_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            for option, value in (('--seed-save', '/unused.sav'), ('--test-input', '/unused.txt'),
                                  ('--bootstrap', '/unused.txt'), ('--agent-control', None)):
                args = ['--state-dir', directory, 'join', 'Ash', '--engine', 'expansion-native', option]
                if value:
                    args.append(value)
                with self.assertRaises(ValueError):
                    launcher.main(args)
            self.assertFalse((Path(directory)/'engines').exists())

    def test_expanded_launch_uses_donor_abi_not_vanilla_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = launcher.profile_paths(directory, 'Ash', engine='expansion-native')
            command = launcher.game_command('/bin/true', directory, paths, engine='expansion-native')
            native = command[command.index('--')+1:]
            self.assertIn('--data-dir', native)
            self.assertIn('--rtc-offset', native)
            self.assertIn('--headless', native)
            self.assertNotIn('--world-config', native)
            self.assertNotIn('--config', native)
            self.assertIn('EW_EXPANSION_PRESENCE', command)
            with self.assertRaises(ValueError):
                launcher.game_command('/bin/true', directory, launcher.profile_paths(directory, 'Ash'), engine='expansion-native')
            with self.assertRaises(ValueError):
                launcher.game_command('/bin/true', directory, paths, agent_control=True, engine='expansion-native')


if __name__ == '__main__':
    unittest.main()
