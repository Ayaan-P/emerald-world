import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

class LauncherTests(unittest.TestCase):
    def load(self):
        spec=importlib.util.spec_from_file_location('world_launcher',ROOT/'world/launcher.py')
        self.assertIsNotNone(spec)
        self.assertTrue(Path(spec.origin).exists(),'local host/join launcher must exist')
        mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod
    def test_scoped_identity_paths_and_strict_id(self):
        mod=self.load()
        with tempfile.TemporaryDirectory(dir='/home/ayaan/projects/emerald-world-research') as tmp:
            paths=mod.profile_paths(Path(tmp),'alice')
            self.assertEqual(paths['save'],Path(tmp)/'trainers/alice/game.sav')
            with self.assertRaises(ValueError): mod.profile_paths(Path(tmp),'../bob')
    def test_game_command_isolated_no_real_home_or_host_display(self):
        mod=self.load()
        with tempfile.TemporaryDirectory(dir='/home/ayaan/projects/emerald-world-research') as tmp:
            state=Path(tmp); (state/'trainers/alice').mkdir(parents=True)
            paths=mod.profile_paths(state,'alice')
            cmd=mod.game_command(ROOT/'build/pokeemerald64',state,paths,None)
            self.assertIn('--unshare-all',cmd); self.assertIn('--clearenv',cmd)
            self.assertNotIn('/home/ayaan/.ssh',cmd)
            self.assertNotIn('/tmp/.X11-unix/X1',cmd)
            self.assertIn('--world-config',cmd)
            self.assertIn(str(paths['save']),cmd)
    def test_rejects_symlinked_profile_ancestor_and_leaf(self):
        mod=self.load()
        with tempfile.TemporaryDirectory(dir='/home/ayaan/projects/emerald-world-research') as tmp:
            root=Path(tmp); target=root/'outside'; target.mkdir(); (root/'trainers').symlink_to(target)
            with self.assertRaises(ValueError): mod.profile_paths(root,'alice')
            (root/'trainers').unlink(); (root/'trainers/alice').mkdir(parents=True)
            (root/'trainers/alice/world.conf').symlink_to(target/'private')
            with self.assertRaises(ValueError): mod.profile_paths(root,'alice')

    def test_world_discovery_lists_only_valid_immediate_non_symlink_worlds(self):
        import sqlite3
        mod=self.load()
        with tempfile.TemporaryDirectory(dir='/home/ayaan/projects/emerald-world-research') as tmp:
            root=Path(tmp)
            valid=root/'zeta'; valid.mkdir()
            db=sqlite3.connect(valid/'world.sqlite3')
            db.executescript('CREATE TABLE identities (id TEXT); CREATE TABLE events (seq INTEGER); CREATE TABLE module (singleton INTEGER); CREATE TABLE status (singleton INTEGER);')
            db.close()
            invalid=root/'invalid'; invalid.mkdir(); (invalid/'world.sqlite3').write_text('not a database')
            missing=root/'missing'; missing.mkdir()
            outside=root/'outside'; outside.mkdir()
            (root/'linked').symlink_to(outside, target_is_directory=True)
            nested=root/'nested'; nested.mkdir(); child=nested/'hidden'; child.mkdir()
            self.assertEqual(mod.discover_worlds(root), [{'name':'zeta','path':str(valid.resolve())}])
            with self.assertRaises(ValueError): mod.discover_worlds(root/'missing-root')

    def test_managed_display_refuses_host_and_existing_unowned_displays(self):
        mod = self.load()
        with self.assertRaisesRegex(ValueError, 'dedicated'):
            mod.ManagedDisplay(':0')
        display = mod.ManagedDisplay(':199')
        from unittest.mock import patch
        with patch.object(Path, 'exists', return_value=True):
            with self.assertRaisesRegex(ValueError, 'already'):
                display.start()
        display.close()

    def test_local_tk_runtime_environment_is_scoped(self):
        mod = self.load()
        root = Path('/home/ayaan/projects/emerald-world-research/deps/tk-sysroot')
        environment = mod.tk_environment(root)
        self.assertIn(str(root/'usr/lib/python3.10/lib-dynload'), environment['PYTHONPATH'])
        self.assertEqual(environment['TK_LIBRARY'], str(root/'usr/share/tcltk/tk8.6'))

    def test_managed_xephyr_real_process_lifecycle(self):
        import os
        import shutil
        if not os.environ.get('DISPLAY') or not shutil.which('Xephyr'):
            self.skipTest('Dedicated graphical test display required')
        mod = self.load()
        display = next((':' + str(n) for n in range(190, 200)
                        if not Path('/tmp/.X11-unix/X' + str(n)).exists()
                        and not Path('/tmp/.X' + str(n) + '-lock').exists()), None)
        if display is None:
            self.skipTest('No free test display')
        managed = mod.ManagedDisplay(display)
        try:
            self.assertEqual(managed.start(), display)
            process = managed.process
            self.assertIsNone(process.poll())
        finally:
            managed.close()
        self.assertIsNotNone(process.poll())

    def test_profile_lock_real_process_exclusion_and_owner_exit(self):
        import subprocess
        import sys
        from world.launcher import ProfileLock
        with tempfile.TemporaryDirectory(dir='/home/ayaan/projects/emerald-world-research') as tmp:
            state = Path(tmp)
            code = ('import sys; from world.launcher import ProfileLock; '
                    'lock = ProfileLock(sys.argv[1], "alice"); '
                    'print("locked", flush=True); sys.stdin.read()')
            child = subprocess.Popen([sys.executable, '-c', code, tmp], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, text=True, cwd=ROOT)
            try:
                self.assertEqual(child.stdout.readline().strip(), 'locked')
                with self.assertRaisesRegex(ValueError, 'running|active|use'):
                    ProfileLock(state, 'alice')
                with ProfileLock(state, 'bob'):
                    pass
                child.kill()
                child.wait(timeout=3)
                with ProfileLock(state, 'alice'):
                    pass
            finally:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=3)
                child.stdin.close()
                child.stdout.close()

    def test_preparation_and_cli_refuse_active_profile_before_any_mutation(self):
        from unittest.mock import patch
        from world import launcher
        with tempfile.TemporaryDirectory(dir='/home/ayaan/projects/emerald-world-research') as tmp:
            state = Path(tmp)
            paths = launcher.profile_paths(state, 'alice')
            paths['profile'].mkdir(parents=True)
            paths['config'].write_text('original')
            seed = state/'seed'; seed.write_bytes(b'seed')
            with launcher.ProfileLock(state, 'alice'):
                with patch('world.server.create_identity') as identity:
                    with self.assertRaises(ValueError):
                        launcher.prepare_profile(state, 'alice', seed)
                    identity.assert_not_called()
                with patch('world.launcher.subprocess.Popen') as spawn:
                    with self.assertRaises(ValueError):
                        launcher.main(['--state-dir', tmp, 'join', 'alice', '--seed-save', str(seed)])
                    spawn.assert_not_called()
                self.assertFalse(paths['save'].exists())
                self.assertEqual(paths['config'].read_text(), 'original')

    def test_lock_paths_fail_closed_and_stay_outside_game_mounts(self):
        import os
        from world import launcher
        with tempfile.TemporaryDirectory(dir='/home/ayaan/projects/emerald-world-research') as tmp:
            state = Path(tmp)
            with launcher.ProfileLock(state, 'alice'):
                pass
            lock = state/'.profile-locks/alice.lock'
            for kind in ('symlink', 'directory', 'fifo'):
                lock.unlink()
                if kind == 'symlink': lock.symlink_to(state/'outside')
                elif kind == 'directory': lock.mkdir()
                else: os.mkfifo(lock)
                with self.assertRaises((OSError, ValueError)):
                    launcher.ProfileLock(state, 'alice')
                if kind == 'directory':
                    lock.rmdir(); lock.touch()
            lock.unlink()
            paths = launcher.profile_paths(state, 'alice')
            command = launcher.game_command('/usr/bin/false', state, paths)
            self.assertNotIn(str(lock.parent), command)
            self.assertNotIn('--preserve-fds', command)

    def test_cli_holds_lock_through_real_child_and_releases_after_failure(self):
        import subprocess
        from unittest.mock import patch
        from world import launcher
        with tempfile.TemporaryDirectory(dir='/home/ayaan/projects/emerald-world-research') as tmp:
            state = Path(tmp)
            def command(binary, state, paths, display):
                with self.assertRaises(ValueError):
                    launcher.ProfileLock(state, 'alice')
                return ['/usr/bin/false']
            with patch('world.server.create_identity', return_value='a'*64), patch.object(launcher, 'game_command', command):
                self.assertEqual(launcher.main(['--state-dir', tmp, 'join', 'alice']), 1)
            with launcher.ProfileLock(state, 'alice'):
                pass
            with patch('world.server.create_identity', return_value='a'*64), patch.object(launcher, 'game_command', return_value=['/missing/game']):
                with self.assertRaises(OSError):
                    launcher.main(['--state-dir', tmp, 'join', 'alice'])
            with launcher.ProfileLock(state, 'alice'):
                pass

    def test_real_cli_child_blocks_desktop_until_exit(self):
        import subprocess
        import sys
        from unittest.mock import patch
        from world import launcher, session
        code = '''
import sys
from world import launcher, server
server.create_identity = lambda *args: 'a' * 64
launcher.game_command = lambda *args: [sys.executable, '-c', 'import sys; sys.stdin.read()']
original = launcher.subprocess.Popen
def spawn(*args, **kwargs):
    process = original(*args, **kwargs)
    print('started', flush=True)
    return process
launcher.subprocess.Popen = spawn
raise SystemExit(launcher.main(['--state-dir', sys.argv[1], 'join', 'alice']))
'''
        with tempfile.TemporaryDirectory(dir='/home/ayaan/projects/emerald-world-research') as tmp:
            state = Path(tmp)
            process = subprocess.Popen([sys.executable, '-c', code, tmp], stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, text=True, cwd=ROOT)
            try:
                self.assertEqual(process.stdout.readline().strip(), 'started')
                with session.DesktopSession(state) as desktop:
                    desktop.state = state
                    paths = launcher.profile_paths(state, 'alice')
                    with patch('world.session.game_command', return_value=['/usr/bin/false']):
                        with self.assertRaises(ValueError):
                            desktop.launch(paths, '/usr/bin/false', None)
                    with self.assertRaises(ValueError): desktop.local_profile('alice')
                process.stdin.close()
                self.assertEqual(process.wait(timeout=3), 0)
                with launcher.ProfileLock(state, 'alice'):
                    pass
            finally:
                if not process.stdin.closed: process.stdin.close()
                if process.poll() is None: process.kill()
                process.wait(timeout=3)
                process.stdout.close()

    def test_agent_command_scopes_control_to_own_profile_only(self):
        mod = self.load()
        with tempfile.TemporaryDirectory(dir='/home/ayaan/projects/emerald-world-research') as tmp:
            state = Path(tmp)
            alice = mod.profile_paths(state, 'alice')
            bob = mod.profile_paths(state, 'bob')
            human = mod.game_command('/usr/bin/true', state, alice)
            ai = mod.game_command('/usr/bin/true', state, bob, agent_control=True)
            self.assertNotIn('--player-control', human)
            self.assertEqual(ai[-2:], ['--player-control', str(bob['profile']/'player.sock')])
            self.assertNotIn(str(alice['profile']), ai)
            self.assertNotIn(str(state/'.profile-locks'), ai)
            self.assertNotIn(str(state/'world.sqlite3'), ai)
            (bob['profile']).mkdir(parents=True)
            (bob['profile']/'player.sock').symlink_to(alice['profile']/'player.sock')
            with self.assertRaisesRegex(ValueError, 'symlink'):
                mod.game_command('/usr/bin/true', state, bob, agent_control=True)

    def test_agent_endpoint_rejects_unix_path_byte_overflow(self):
        mod = self.load()
        state = Path('/tmp') / ('é' * 44)
        paths = mod.profile_paths(state, 'alice')
        self.assertLess(len(str(paths['profile']/'player.sock')), 108)
        with self.assertRaisesRegex(ValueError, '107|108|long'):
            mod.game_command('/usr/bin/true', state, paths, agent_control=True)
        mod.game_command('/usr/bin/true', state, paths)

    def test_real_cli_agent_control_prints_native_argument_and_honors_lock(self):
        import json
        import subprocess
        import sys
        from world.session import DesktopSession
        from world.launcher import ProfileLock
        with tempfile.TemporaryDirectory(dir='/home/ayaan/projects/emerald-world-research') as tmp:
            with DesktopSession(Path(tmp)) as host:
                host.create_world('w'); host.host('w')
                command = [sys.executable, '-m', 'world.launcher', '--state-dir', str(host.state),
                           'join', 'hermes', '--agent-control', '--print-command']
                result = subprocess.run(command, capture_output=True, text=True, cwd=ROOT, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)[-2:],
                                 ['--player-control', str(host.state/'trainers/hermes/player.sock')])
                with ProfileLock(host.state, 'hermes'):
                    blocked = subprocess.run(command, capture_output=True, text=True, cwd=ROOT, timeout=5)
                self.assertEqual(blocked.returncode, 1)
                self.assertIn('in use', blocked.stderr)

    def test_real_cli_remote_ai_uses_invitation_tls_without_host_admin(self):
        import hashlib
        import json
        import ssl
        import subprocess
        import sys
        from world.session import DesktopSession
        with tempfile.TemporaryDirectory(dir='/home/ayaan/projects/emerald-world-research') as tmp:
            root = Path(tmp)
            with DesktopSession(root) as host:
                host.create_world('h'); host.host('h')
                cert, key = host.tls_material()
                address = host.share(cert, key, ('127.0.0.1', 0))
                pin = hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text())).hexdigest()
                invitation = root/'invite.json'; host.invite('hermes', invitation)
                argv = [sys.executable, '-m', 'world.launcher', '--state-dir', str(root/'g'),
                        'join', 'hermes', '--agent-control', '--invitation', str(invitation),
                        '--remote', f'{address[0]}:{address[1]}', '--pin', pin, '--print-command']
                result = subprocess.run(argv, capture_output=True, text=True, cwd=ROOT, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                command = json.loads(result.stdout)
                self.assertEqual(command[-2:], ['--player-control', str(root/'g/trainers/hermes/player.sock')])
                self.assertFalse((root/'g/world.sqlite3').exists())
                self.assertNotIn(str(invitation), command)
                self.assertNotIn(str(key), command)
                self.assertNotIn(json.loads(invitation.read_text())['token'], result.stdout)
                self.assertFalse((root/'g/transport/world.sock').exists())
                wrong_pin = list(argv); wrong_pin[wrong_pin.index('--pin')+1] = '0'*64
                failed = subprocess.run(wrong_pin, capture_output=True, text=True, cwd=ROOT, timeout=10)
                self.assertEqual(failed.returncode, 1)

    def test_cli_ai_launch_prints_endpoint_sdk_without_claiming_ready(self):
        import contextlib
        import io
        from unittest.mock import patch
        from world import launcher
        with tempfile.TemporaryDirectory(dir='/home/ayaan/projects/emerald-world-research') as tmp:
            output = io.StringIO()
            with patch('world.server.create_identity', return_value='a'*64), \
                 patch.object(launcher, 'game_command', return_value=['/usr/bin/false']), \
                 contextlib.redirect_stderr(output):
                self.assertEqual(launcher.main(['--state-dir', tmp, 'join', 'hermes', '--agent-control']), 1)
            self.assertIn('AI control starting', output.getvalue())
            self.assertIn(str(Path(tmp)/'trainers/hermes/player.sock'), output.getvalue())
            self.assertIn('PlayerClient', output.getvalue())
            self.assertNotIn('ready', output.getvalue())
            self.assertNotIn('a'*64, output.getvalue())

    def test_cli_agent_resume_checks_stale_endpoint_under_lock_before_preparation(self):
        import socket
        import subprocess
        from unittest.mock import patch
        from world import launcher
        with tempfile.TemporaryDirectory(dir='/home/ayaan/projects/emerald-world-research') as tmp:
            state = Path(tmp)
            paths = launcher.profile_paths(state, 'hermes')
            paths['profile'].mkdir(parents=True, mode=0o700)
            paths['save'].write_bytes(b'existing save')
            paths['config'].write_text('original config')
            paths['settings'].write_text('original settings')
            endpoint = paths['profile']/'player.sock'
            with socket.socket(socket.AF_UNIX) as stale:
                stale.bind(str(endpoint))
            endpoint.chmod(0o600)
            inode = endpoint.stat().st_ino
            native_spawn = subprocess.Popen
            original_check = launcher.check_player_endpoint
            checked = []
            commands = []
            def check(checked_paths):
                with self.assertRaisesRegex(ValueError, 'in use'):
                    launcher.ProfileLock(state, 'hermes')
                self.assertEqual(paths['config'].read_text(), 'original config')
                checked.append(checked_paths)
                return original_check(checked_paths)
            def identity(*args):
                self.assertEqual(checked, [paths], 'endpoint must be checked before identity/config mutation')
                return 'a'*64
            def spawn(command, **kwargs):
                commands.append(command)
                self.assertEqual(endpoint.stat().st_ino, inode)
                with self.assertRaisesRegex(ValueError, 'in use'):
                    launcher.ProfileLock(state, 'hermes')
                return native_spawn(['/usr/bin/true'], **kwargs)
            with patch('world.server.create_identity', side_effect=identity), \
                 patch.object(launcher, 'check_player_endpoint', side_effect=check), \
                 patch.object(launcher.subprocess, 'Popen', side_effect=spawn):
                self.assertEqual(launcher.main(['--state-dir', tmp, 'join', 'hermes',
                                                '--binary', '/usr/bin/true', '--agent-control']), 0)
            self.assertEqual(commands[0][-2:], ['--player-control', str(endpoint)])
            self.assertIn('--unshare-all', commands[0])
            self.assertEqual(endpoint.stat().st_ino, inode)
            self.assertEqual(paths['save'].read_bytes(), b'existing save')
            self.assertEqual(paths['settings'].read_text(), 'original settings')
            with launcher.ProfileLock(state, 'hermes'):
                pass

    def test_agent_spawn_paths_reject_live_and_unsafe_endpoints_without_mutation(self):
        import os
        import socket
        from contextlib import ExitStack
        from unittest.mock import patch
        from world import launcher, session
        for launch in ('cli', 'cli-remote', 'desktop'):
            for kind in ('live', 'regular', 'directory', 'fifo', 'symlink', 'hardlink', 'public-socket'):
                with self.subTest(launch=launch, kind=kind), \
                     tempfile.TemporaryDirectory(dir='/home/ayaan/projects/emerald-world-research') as tmp, \
                     ExitStack() as stack:
                    state = Path(tmp)
                    paths = launcher.profile_paths(state, 'hermes')
                    paths['profile'].mkdir(parents=True, mode=0o700)
                    for name in ('save', 'config', 'settings', 'telemetry'):
                        paths[name].write_text('original '+name)
                    logfile = paths['profile']/'native.log'
                    logfile.write_text('original log')
                    endpoint = paths['profile']/'player.sock'
                    target = state/'outside'; target.write_text('untouched')
                    if kind in ('live', 'hardlink', 'public-socket'):
                        listener = stack.enter_context(socket.socket(socket.AF_UNIX))
                        listener.bind(str(endpoint))
                        endpoint.chmod(0o600)
                        if kind == 'live': listener.listen(1)
                        if kind == 'hardlink': os.link(endpoint, state/'socket-link')
                        if kind == 'public-socket': endpoint.chmod(0o666)
                    elif kind == 'regular': endpoint.write_text('not a socket')
                    elif kind == 'directory': endpoint.mkdir()
                    elif kind == 'fifo': os.mkfifo(endpoint)
                    else: endpoint.symlink_to(target)
                    before = endpoint.lstat()
                    with patch('world.server.create_identity') as identity, \
                         patch('world.launcher.subprocess.Popen') as spawn:
                        if launch.startswith('cli'):
                            argv = ['--state-dir', tmp, 'join', 'hermes', '--agent-control']
                            if launch == 'cli-remote':
                                argv += ['--remote', 'localhost:443', '--invitation', str(state/'invite.json'),
                                         '--pin', '0'*64]
                            with patch.object(session.DesktopSession, 'connect_remote',
                                              side_effect=AssertionError('endpoint must be checked before remote profile mutation')) as connect:
                                with self.assertRaises(ValueError):
                                    launcher.main(argv)
                                connect.assert_not_called()
                        else:
                            desktop = stack.enter_context(session.DesktopSession(state))
                            desktop.state = state
                            with self.assertRaises(ValueError):
                                desktop.launch(paths, '/usr/bin/true', None, agent_control=True)
                        identity.assert_not_called()
                        spawn.assert_not_called()
                    after = endpoint.lstat()
                    self.assertEqual((after.st_dev, after.st_ino, after.st_mode, after.st_nlink),
                                     (before.st_dev, before.st_ino, before.st_mode, before.st_nlink))
                    for name in ('save', 'config', 'settings', 'telemetry'):
                        self.assertEqual(paths[name].read_text(), 'original '+name)
                    self.assertEqual(logfile.read_text(), 'original log')
                    self.assertEqual(target.read_text(), 'untouched')
                    with launcher.ProfileLock(state, 'hermes'):
                        pass

    def test_author_response_rejects_extra_or_missing_source(self):
        mod=self.load()
        self.assertEqual(mod.parse_author_response('{"source":"def update(c,s): return {}","tests":""}')['tests'],'')
        with self.assertRaises(ValueError): mod.parse_author_response('{"instructions":"run shell"}')
        with self.assertRaises(ValueError): mod.parse_author_response('{"source":"x","tests":"","shell":"oops"}')

if __name__=='__main__': unittest.main()
