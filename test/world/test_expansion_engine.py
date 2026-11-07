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

    def test_web_session_profiles_and_authority_are_engine_scoped(self):
        from world.session import DesktopSession
        with tempfile.TemporaryDirectory() as directory:
            session = DesktopSession(Path(directory), engine='expansion-native')
            try:
                session.create_world('world-one')
                session.host('world-one')
                paths = session.local_profile('Ash')
                expected = Path(directory)/'world-one/engines/expansion-native'
                self.assertEqual(paths['profile'], expected/'trainers/Ash')
                fields = dict(line.split(' ', 1) for line in paths['config'].read_text().splitlines())
                self.assertEqual(fields['socket'], str(expected/'transport/world.sock'))
                self.assertNotEqual(paths['profile'], Path(directory)/'world-one/trainers/Ash')
            finally:
                session.close()

    def test_engine_pinned_web_host_and_local_join_share_only_expansion_socket(self):
        from world.session import DesktopSession
        with tempfile.TemporaryDirectory() as directory:
            host = DesktopSession(Path(directory), engine='expansion-native')
            guest = DesktopSession(Path(directory), engine='expansion-native')
            try:
                host.create_world('world-one')
                self.assertEqual(host.worlds(), [{'name': 'world-one', 'path': str(Path(directory)/'world-one')}])
                host.host('world-one')
                guest.join_local('world-one')
                paths = guest.local_profile('Bob')
                engine_root = Path(directory)/'world-one/engines/expansion-native'
                assert len(list(Path(directory).rglob('world.sqlite3'))) == 1
                self.assertEqual(host.server.root, Path(directory)/'world-one')
                self.assertTrue((Path(directory)/'world-one/world.sqlite3').is_file())
                self.assertFalse((engine_root/'world.sqlite3').exists())
                self.assertEqual(paths['profile'], engine_root/'trainers/Bob')
                library = guest.world_library()
                self.assertEqual(library[0]['display_name'], 'world-one')
                self.assertEqual([trainer['name'] for trainer in library[0]['trainers']], ['Bob'])
                fields = dict(line.split(' ', 1) for line in paths['config'].read_text().splitlines())
                self.assertEqual(fields['socket'], str(engine_root/'transport/world.sock'))
                self.assertNotEqual(fields['socket'], str(Path(directory)/'world-one/transport/world.sock'))
            finally:
                guest.close()
                host.close()

    def test_web_online_launch_routes_through_expansion_session_start(self):
        from world.session import DesktopSession
        from unittest.mock import Mock, patch
        with tempfile.TemporaryDirectory() as directory:
            session = DesktopSession(Path(directory), engine='expansion-native')
            try:
                session.create_world('world-one')
                session.host('world-one')
                paths = session.local_profile('Ash')
                process, lock = Mock(), Mock()
                process.poll.return_value = 0
                with patch('world.expansion.ExpansionSession.start', autospec=True, return_value=(process, lock)) as start, \
                     patch('world.session.subprocess.Popen', return_value=process):
                    session.launch(paths, Path('/usr/bin/true'), display='')
                start.assert_called_once()
                expansion = start.call_args.args[0]
                self.assertEqual(expansion.online, True)
                self.assertEqual(start.call_args.args[1], Path('/usr/bin/true'))
                self.assertEqual(session.game_locks['Ash'], lock)
            finally:
                session.close()

    def test_expansion_nonblocking_start_uses_engine_command_and_returns_held_lock(self):
        from unittest.mock import Mock, patch
        from world.session import DesktopSession
        from world.expansion import ExpansionSession
        from world.launcher import ProfileLock
        with tempfile.TemporaryDirectory() as directory:
            session = DesktopSession(Path(directory), engine='expansion-native')
            try:
                session.create_world('world-one')
                session.host('world-one')
                expansion = ExpansionSession(session.state, 'Ash')
                process = Mock()
                with patch('world.expansion.subprocess.Popen', return_value=process) as popen, \
                     patch('shutil.which', return_value='/usr/bin/bwrap'):
                    started, lock = expansion.start(Path('/usr/bin/true'), display='')
                self.assertIs(started, process)
                command = popen.call_args.args[0]
                self.assertIn(str(expansion.paths['profile']), command)
                self.assertIn('--save', command)
                self.assertNotIn('--test-input', command)
                with self.assertRaisesRegex(ValueError, 'already in use'):
                    ProfileLock(session.state, 'Ash', engine='expansion-native')
                lock.close()
            finally:
                session.close()

    def test_web_offline_launch_routes_through_expansion_session_start(self):
        from world.session import DesktopSession
        from unittest.mock import Mock, patch
        with tempfile.TemporaryDirectory() as directory:
            session = DesktopSession(Path(directory), engine='expansion-native')
            try:
                session.create_world('world-one')
                process, lock = Mock(), Mock()
                process.poll.return_value = 0
                with patch('world.expansion.ExpansionSession.start', autospec=True, return_value=(process, lock)) as start, \
                     patch('world.session.subprocess.Popen', return_value=process):
                    session.launch_offline('world-one', 'Ash', Path('/usr/bin/true'), display='')
                start.assert_called_once()
                expansion = start.call_args.args[0]
                self.assertEqual(expansion.online, False)
                self.assertEqual(expansion.base, Path(directory)/'world-one/.offline')
            finally:
                session.close()

    def test_expansion_offline_launch_uses_disposable_engine_profile_and_command(self):
        import shutil
        from unittest.mock import Mock, patch
        from world.session import DesktopSession
        with tempfile.TemporaryDirectory() as directory:
            session = DesktopSession(Path(directory), engine='expansion-native')
            binary = Path(directory)/'pokeemerald-native'
            shutil.copy2('/usr/bin/true', binary)
            binary.chmod(0o755)
            try:
                session.create_world('world-one')
                process = Mock()
                process.poll.return_value = 0
                with patch('world.expansion.subprocess.Popen', return_value=process) as popen, \
                     patch('shutil.which', return_value='/usr/bin/bwrap'):
                    session.launch_offline('world-one', 'Ash', binary, display='')
                command = popen.call_args.args[0]
                expected = Path(directory)/'world-one/.offline/engines/expansion-native/trainers/Ash'
                self.assertIn(str(expected), command)
                self.assertIn('--save', command)
                self.assertNotIn(str(Path(directory)/'world-one/trainers/Ash'), command)
                self.assertIn('offline/Ash', session.games)
            finally:
                session.close()

    def test_expansion_web_launch_preserves_joined_invitation_credentials(self):
        import socket
        import shutil
        from unittest.mock import Mock, patch
        from world.session import DesktopSession
        with tempfile.TemporaryDirectory() as directory:
            session = DesktopSession(Path(directory), engine='expansion-native')
            world = Path(directory)/'remote-world'
            world.mkdir()
            session.state = world
            session.remote_trainer = 'Ash'
            paths = launcher.profile_paths(world, 'Ash', engine='expansion-native')
            paths['profile'].mkdir(parents=True, mode=0o700)
            engine_root = launcher.engine_state(world, 'expansion-native')
            token = 'a' * 64
            config = (f'socket {engine_root}/transport/world.sock\ntrainer Ash\ntoken {token}\n'
                      f'telemetry {paths["telemetry"]}\n')
            paths['config'].write_text(config)
            paths['config'].chmod(0o600)
            paths['settings'].write_text('[video]\nscale=2\n')
            engine_root.joinpath('transport').mkdir(parents=True, mode=0o700, exist_ok=True)
            authority = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            authority.bind(str(engine_root/'transport/world.sock'))
            Path(engine_root/'transport/world.sock').chmod(0o600)
            authority.listen(4)
            binary = Path(directory)/'pokeemerald-native'
            shutil.copy2('/usr/bin/true', binary)
            binary.chmod(0o755)
            process = Mock()
            process.poll.return_value = 0
            try:
                with patch('world.expansion.subprocess.Popen', return_value=process) as popen, \
                     patch('shutil.which', return_value='/usr/bin/bwrap'):
                    session.launch(paths, binary, display='')
                self.assertEqual(paths['config'].read_text(), config)
                self.assertNotIn(token, popen.call_args.args[0])
                self.assertFalse((world/'world.sqlite3').exists())
            finally:
                authority.close()
                session.close()

    def test_offline_expansion_profile_is_provisioned_inside_engine_state(self):
        from world.offline import offline_profile
        with tempfile.TemporaryDirectory() as directory:
            world = Path(directory)/'world'
            world.mkdir()
            with offline_profile(world, 'Ash', engine='expansion-native') as paths:
                self.assertEqual(paths['profile'], world/'.offline/engines/expansion-native/trainers/Ash')
                self.assertTrue(paths['profile'].is_dir())

    def test_join_requires_live_authority_before_profile_admission(self):
        from unittest.mock import patch
        from world.expansion import ExpansionSession
        with tempfile.TemporaryDirectory() as directory:
            session = ExpansionSession(directory, 'Ash')
            with patch('world.expansion.subprocess.Popen') as launch:
                with self.assertRaisesRegex(ValueError, 'authority'):
                    session.run('/bin/true')
                launch.assert_not_called()
            self.assertFalse(session.paths['profile'].exists())
            self.assertFalse((session.state/'world.sqlite3').exists())

    def test_launcher_explicit_engine_routes_to_expansion_session(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            with patch('world.expansion.run', return_value=0) as run:
                self.assertEqual(launcher.main(['--state-dir', directory, 'join', 'Ash',
                                                '--engine', 'expansion-native', '--print-command']), 0)
                self.assertEqual(run.call_args.args[0].engine, 'expansion-native')

    def test_native_transport_uses_the_prepared_engine_authority_identity(self):
        # The old read-only Python presence pump was replaced by native transport.
        # Exercise real provisioning/authentication; actual native peer rendering
        # and battle/save acceptance live in run_expansion_release_journey.py.
        import contextlib
        import io
        import json
        from contextlib import closing
        from world.client import WorldClient
        from world.expansion import ExpansionSession
        from world.server import WorldServer
        with tempfile.TemporaryDirectory() as directory:
            session = ExpansionSession(directory, 'Ash')
            session.state.mkdir(parents=True)
            with closing(WorldServer(session.state/'transport/world.sock', Path(directory))) as server:
                server.start()
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    session.run('/bin/true', print_command=True)
                command = json.loads(output.getvalue())
                self.assertIn('EW_WORLD_CONFIG', command)
                self.assertNotIn('EW_EXPANSION_PRESENCE', command)
                config = dict(line.split(' ', 1) for line in session.paths['config'].read_text().splitlines())
                self.assertEqual(config['socket'], str(session.state/'transport/world.sock'))
                with WorldClient(config['socket'], 'Ash', config['token']) as client:
                    self.assertGreaterEqual(client.snapshot()['revision'], 0)
                self.assertFalse((session.state/'world.sqlite3').exists())

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
            self.assertIn('EW_WORLD_CONFIG', command)
            self.assertNotIn('EW_EXPANSION_PRESENCE', command)
            with self.assertRaises(ValueError):
                launcher.game_command('/bin/true', directory, launcher.profile_paths(directory, 'Ash'), engine='expansion-native')
            controlled = launcher.game_command('/bin/true', directory, paths, agent_control=True, engine='expansion-native')
            self.assertIn('--player-control', controlled)

    def test_launch_command_rejects_cross_engine_binary_namespace_pairing(self):
        with tempfile.TemporaryDirectory() as directory:
            vanilla = launcher.profile_paths(directory, 'Ash', engine='vanilla')
            expansion = launcher.profile_paths(directory, 'Ash', engine='expansion-native')
            with self.assertRaisesRegex(ValueError, 'does not match'):
                launcher.game_command('/tmp/pokeemerald-native', directory, vanilla, engine='vanilla')
            with self.assertRaisesRegex(ValueError, 'does not match'):
                launcher.game_command('/tmp/pokeemerald64', directory, expansion, engine='expansion-native')


if __name__ == '__main__':
    unittest.main()
