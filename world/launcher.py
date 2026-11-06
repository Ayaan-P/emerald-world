"""Local host/join entrypoint with private saves and isolated native clients.

python3 -m world.launcher --help
The service's Unix socket is local-only. No internet relay or account is used.
"""
from pathlib import Path
import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]


class ManagedDisplay:
    """Own only a newly started nested X server, never an existing display."""
    def __init__(self, display):
        if not re.fullmatch(r':(?:9[0-9]|1[0-9]{2})', display):
            raise ValueError('use a dedicated nested display :90..:199')
        self.display, self.process = display, None

    def start(self):
        import time
        socket = Path('/tmp/.X11-unix/X' + self.display[1:])
        lock = Path('/tmp/.X' + self.display[1:] + '-lock')
        if socket.exists() or lock.exists():
            raise ValueError('display already exists. Choose a free dedicated display or use the existing one explicitly.')
        if not shutil.which('Xephyr'):
            raise ValueError('Xephyr is unavailable. Ask the computer owner to provide it.')
        if not os.environ.get('DISPLAY'):
            raise ValueError('DISPLAY must name the desktop where the nested game window should open.')
        # TCP is disabled. Only this dedicated local socket is game-mounted.
        # The game uses SDL's software renderer. Do not initialize GLX drivers
        # in the nested display: host GPU plugins need not work in its sandbox.
        self.process = subprocess.Popen(['Xephyr', self.display, '-screen', '1100x760',
                                         '-ac', '-nolisten', 'tcp', '-noreset', '-extension', 'GLX'],
                                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.close()
                raise ValueError('Xephyr could not open a nested window. Check desktop DISPLAY and choose a free display.')
            if socket.is_socket():
                return self.display
            time.sleep(.05)
        self.close()
        raise ValueError('Xephyr did not become ready. Choose another dedicated display and retry.')

    def close(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None


def tk_environment(root):
    """Environment for one UI child only. Never forwarded into the game."""
    root = Path(root).resolve()
    if not (root/'usr/share/tcltk/tk8.6').is_dir():
        raise ValueError('Tk runtime root must contain an extracted Tk 8.6 runtime')
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join([str(root/'usr/lib/python3.10'),
                                       str(root/'usr/lib/python3.10/lib-dynload'), str(REPO)])
    env['LD_LIBRARY_PATH'] = os.pathsep.join([str(root/'usr/lib'), str(root/'usr/lib/x86_64-linux-gnu')])
    env['TK_LIBRARY'] = str(root/'usr/share/tcltk/tk8.6')
    return env


def engine_state(state_dir, engine='vanilla'):
    if engine not in ('vanilla', 'expansion-native'):
        raise ValueError('engine must be vanilla or expansion-native')
    state = Path(state_dir).resolve()
    return state if engine == 'vanilla' else state / 'engines' / engine


def profile_paths(state_dir, trainer, *, engine='vanilla'):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,24}', trainer):
        raise ValueError('trainer must be 1..24 ASCII letters, digits, _ or -')
    state_dir = Path(state_dir).resolve()
    profile = engine_state(state_dir, engine) / 'trainers' / trainer
    if profile.resolve() != profile:
        raise ValueError('trainer profile and its ancestors cannot be symlinks')
    paths = {'profile': profile, 'save': profile / 'game.sav',
             'config': profile / 'world.conf', 'telemetry': profile / 'telemetry.json',
             'settings': profile / 'pokeemerald.ini'}
    for key, path in paths.items():
        if path.is_symlink():
            raise ValueError(f'{key} cannot be a symlink')
    return paths


class ProfileLock:
    """Nonblocking lifetime flock, outside the native client's writable mount.

    Lock files are permanent: unlinking them would split the locking inode.
    No PID or timestamp is used to decide whether a profile is available.
    """
    def __init__(self, state_dir, trainer):
        from world.world_library import WorldActivityLock
        self.activity = WorldActivityLock(state_dir)
        try:
            self._acquire(state_dir, trainer)
        except BaseException:
            self.activity.close()
            raise

    def _acquire(self, state_dir, trainer):
        import fcntl
        import stat
        import threading
        self._guard = threading.Lock()
        self.fd = None
        self.paths = profile_paths(state_dir, trainer)
        directory = Path(state_dir).resolve() / '.profile-locks'
        if directory.resolve() != directory:
            raise ValueError('profile lock directory cannot be a symlink')
        directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        parent = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            fd = os.open(trainer + '.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW |
                         os.O_NONBLOCK | os.O_CLOEXEC, 0o600, dir_fd=parent)
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValueError('profile lock must be a single-link regular file')
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise ValueError('this trainer profile is already in use by a running game or launcher') from None
            except BaseException:
                os.close(fd)
                raise
            self.fd = fd
        finally:
            os.close(parent)

    def close(self):
        with self._guard:
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None
            self.activity.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def parse_author_response(text):
    value = json.loads(text)
    if (not isinstance(value, dict) or set(value) != {'source', 'tests'}
            or not all(isinstance(v, str) for v in value.values())
            or not value['source'].strip() or len(text.encode()) > 131072):
        raise ValueError('author must return exactly source and tests strings')
    return value


def player_endpoint(paths):
    """The native player controls belong only to this explicit trainer profile."""
    endpoint = paths['profile'] / 'player.sock'
    if endpoint.resolve() != endpoint or endpoint.is_symlink():
        raise ValueError('player control endpoint cannot be a symlink')
    if len(os.fsencode(endpoint)) >= 108:
        raise ValueError('player control endpoint is too long. Choose a shorter worlds root (107 bytes maximum).')
    return endpoint


def check_player_endpoint(paths):
    """Reject live/unsafe endpoints without deleting them. Native owns recovery."""
    import socket
    import stat
    endpoint = player_endpoint(paths)
    try:
        info = endpoint.lstat()
    except FileNotFoundError:
        return endpoint
    if (not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_nlink != 1 or info.st_mode & 0o077):
        raise ValueError('Refusing an unsafe existing player control endpoint.')
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.2)
        try:
            probe.connect(str(endpoint))
        except ConnectionRefusedError:
            # Do not unlink here. Native code rechecks owner/inode under its
            # private directory handle before recovering a stale socket.
            return endpoint
        except OSError:
            raise ValueError('Cannot verify existing player control endpoint is inactive.') from None
    raise ValueError('An existing player control endpoint is active. Stop its owner first.')


def game_command(binary, state_dir, paths, display=None, agent_control=False, *, online=True, engine='vanilla'):
    """Construct explicit allowlist mounts. Never mount whole HOME or /run."""
    engine_state(state_dir, engine)
    expanded = engine == 'expansion-native'
    if expanded:
        if agent_control:
            raise ValueError('Expansion does not implement the vanilla player-control ABI')
        if paths != profile_paths(state_dir, paths['profile'].name, engine=engine):
            raise ValueError('Expansion requires its own separate profile')
    binary = Path(binary).resolve()
    state_dir = Path(state_dir).resolve()
    if online:
        require_online_state(state_dir)
    transport = engine_state(state_dir, engine) / 'transport'
    expansion_link = expanded and online and os.environ.get('EW_EXPERIMENTAL_EXPANSION_LINK') == '1'
    mount_transport = online and (not expanded or expansion_link)
    if mount_transport:
        if transport.resolve() != transport:
            raise ValueError('transport cannot be a symlink')
        if transport.exists() and any(p.name != 'world.sock' for p in transport.iterdir()):
            raise ValueError('transport must contain only the public game socket, never admin or credentials')
    args = ['bwrap', '--unshare-all', '--die-with-parent', '--new-session',
            '--cap-drop', 'ALL', '--clearenv', '--ro-bind', '/usr', '/usr',
            '--ro-bind', '/lib', '/lib', '--ro-bind', '/lib64', '/lib64',
            '--symlink', 'usr/bin', '/bin', '--proc', '/proc', '--dev', '/dev',
            '--tmpfs', '/tmp', '--dir', '/home/sandbox',
            '--ro-bind', '/etc/ld.so.cache', '/etc/ld.so.cache',
            '--ro-bind', str(binary), str(binary),
            '--bind', str(paths['profile']), str(paths['profile']),
            '--chdir', str(paths['profile'])]
    if mount_transport:
        args += ['--ro-bind', str(transport), str(transport)]
    env = {'HOME': '/home/sandbox', 'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8',
           'SDL_AUDIODRIVER': 'dummy', 'SDL_RENDER_DRIVER': 'software'}
    if display:
        if not re.fullmatch(r':(?:9[0-9]|1[0-9]{2})', display):
            raise ValueError('use a dedicated nested display :90..:199, not the host display')
        number = display[1:]
        xsocket = '/tmp/.X11-unix/X' + number
        args += ['--ro-bind', xsocket, xsocket]
        env['DISPLAY'] = display
    else:
        env['SDL_VIDEODRIVER'] = 'dummy'
    if expanded:
        env['EW_EXPANSION_PRESENCE'] = str(paths['profile'] / 'presence.json')
        env['EW_EXPANSION_PEERS'] = str(paths['profile'] / 'peers.txt')
        if expansion_link:
            env['EW_EXPANSION_LINK_CONFIG'] = str(paths['config'])
        if os.environ.get('EW_EXPERIMENTAL_EXPANSION_PEERS') == '1':
            env['EW_EXPERIMENTAL_EXPANSION_PEERS'] = '1'
            if expansion_link and os.environ.get('EW_EXPERIMENTAL_EXPANSION_ACTIVITIES') == '1':
                env['EW_EXPERIMENTAL_EXPANSION_ACTIVITIES'] = '1'
                if os.environ.get('EW_EXPERIMENTAL_EXPANSION_TRADE') == '1':
                    env['EW_EXPERIMENTAL_EXPANSION_TRADE'] = '1'
    for key, value in env.items():
        args += ['--setenv', key, value]
    if expanded:
        return args + ['--', str(binary), '--data-dir', str(paths['profile']),
                       '--save', str(paths['save']), '--rtc-offset', str(paths['profile'] / 'clock.rtc')] + ([] if display else ['--headless', '--silent'])
    command = args + ['--', str(binary), '--save', str(paths['save']),
                      '--config', str(paths['settings'])]
    if online:
        command += ['--world-config', str(paths['config'])]
    if agent_control:
        # Construction only: launchers probe under their held profile lock.
        # A private stale socket must remain for native's inode-safe recovery.
        endpoint = player_endpoint(paths)
        command += ['--player-control', str(endpoint)]
    return command


def require_online_state(state_dir):
    """Offline provenance survives moving a copy to another directory name."""
    state = Path(state_dir)
    marker = state / '.offline-copy'
    if state.name == '.offline' or marker.exists() or marker.is_symlink():
        raise ValueError('Offline copies cannot connect to world services. Select the original online world.')


def prepare_profile(state_dir, trainer, seed_save=None):
    with ProfileLock(state_dir, trainer) as lock:
        return _prepare_profile(state_dir, trainer, seed_save, lock.paths)


def _prepare_profile(state_dir, trainer, seed_save, paths):
    """Prepare only while the caller owns the profile lock."""
    require_online_state(state_dir)
    from world.server import create_identity
    paths['profile'].parent.mkdir(exist_ok=True, mode=0o700)
    paths['profile'].mkdir(exist_ok=True, mode=0o700)
    os.chmod(paths['profile'], 0o700)
    token = create_identity(Path(state_dir), trainer)
    if isinstance(token, dict):
        token = token['token']
    if not isinstance(token, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', token):
        raise ValueError('identity service did not return a valid token')
    if seed_save:
        if paths['save'].exists():
            raise ValueError('refusing to overwrite an existing trainer save')
        seed = Path(seed_save).resolve()
        if seed == paths['save']:
            raise ValueError('seed must differ from profile save')
        shutil.copyfile(seed, paths['save'])
    socket_path = Path(state_dir).resolve() / 'transport/world.sock'
    paths['config'].write_text(f'socket {socket_path}\ntrainer {trainer}\ntoken {token}\ntelemetry {paths["telemetry"]}\n')
    os.chmod(paths['config'], 0o600)
    if not paths['settings'].exists():
        paths['settings'].write_text('[video]\nscale=2\n')
    return paths


def admin(socket_path, command):
    from world.client import admin_request
    return admin_request(str(socket_path), command)


def discover_worlds(worlds_root):
    """List valid immediate child worlds without following links or opening saves."""
    from urllib.parse import quote
    root = Path(worlds_root).expanduser()
    try:
        root.lstat()
    except OSError as exc:
        raise ValueError('worlds root must be an existing directory') from exc
    if root.is_symlink() or not root.is_dir():
        raise ValueError('worlds root must be a real directory')
    worlds = []
    for entry in sorted(root.iterdir(), key=lambda item: item.name):
        if entry.is_symlink() or not entry.is_dir():
            continue
        database = entry / 'world.sqlite3'
        if database.is_symlink() or not database.is_file():
            continue
        try:
            uri = 'file:' + quote(str(database.resolve()), safe='/') + '?mode=ro'
            connection = sqlite3.connect(uri, uri=True, timeout=0.2)
            try:
                tables = {row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
                if {'identities', 'events', 'module', 'status'} <= tables:
                    worlds.append({'name': entry.name, 'path': str(entry.resolve())})
            finally:
                connection.close()
        except sqlite3.Error:
            continue
    return worlds


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state-dir', type=Path, help='world state directory, not a personal save folder')
    sub = p.add_subparsers(dest='command', required=True)
    desktop = sub.add_parser('desktop', help='open the graphical host/join session launcher')
    desktop.add_argument('--worlds-root', type=Path, required=True, help='existing explicit directory for worlds and independent saves')
    desktop.add_argument('--binary', type=Path, default=REPO / 'build/pokeemerald64')
    desktop.add_argument('--display', default=':95', help='dedicated nested Xephyr display :90..:199')
    desktop.add_argument('--tk-runtime', type=Path, help='explicit extracted Tk sysroot for this UI process only')
    desktop.add_argument('--ui-python', type=Path, default=Path('/usr/bin/python3'), help='UI interpreter used with --tk-runtime')
    worlds = sub.add_parser('list-worlds', help='discover worlds under an explicit directory')
    worlds.add_argument('--worlds-root', type=Path, required=True, help='directory whose immediate child worlds to list')
    host = sub.add_parser('host', help='run persistent local world service in foreground')
    host.add_argument('--engine', choices=('vanilla', 'expansion-native'), default='vanilla')
    join = sub.add_parser('join', help='create/resume an independent trainer and launch the native game')
    join.add_argument('trainer')
    join.add_argument('--binary', type=Path)
    join.add_argument('--engine', choices=('vanilla', 'expansion-native'), default='vanilla')
    join.add_argument('--replay', type=Path, help='Expansion donor replay script')
    join.add_argument('--frames', type=int, help='Expansion frame limit')
    join.add_argument('--seed-save', type=Path, help='explicit copy into a new profile; never modifies original')
    join.add_argument('--display', help='dedicated nested Xephyr display :90..:199')
    join.add_argument('--test-input', type=Path, help='run upstream headless engine input instead of GUI')
    join.add_argument('--bootstrap', type=Path, help='graphical startup input, then return control to human')
    join.add_argument('--print-command', action='store_true')
    join.add_argument('--agent-control', action='store_true',
                      help='AI-controlled trainer with a private profile/player.sock endpoint')
    join.add_argument('--remote', help='remote host HOST:PORT, requires a trainer invitation and trusted TLS pin')
    join.add_argument('--invitation', type=Path, help='private trainer invitation, never administrator credentials')
    join.add_argument('--pin', help='trusted remote TLS certificate SHA256 pin')
    offline = sub.add_parser('offline', help='play a separate offline trainer copy without world services')
    offline.add_argument('trainer')
    offline.add_argument('--binary', type=Path)
    offline.add_argument('--engine', choices=('vanilla', 'expansion-native'), default='vanilla')
    offline.add_argument('--replay', type=Path, help='Expansion donor replay script')
    offline.add_argument('--frames', type=int, help='Expansion frame limit')
    seed = offline.add_mutually_exclusive_group()
    seed.add_argument('--seed-save', type=Path, help='copy an explicit disposable save once, never merge back')
    seed.add_argument('--copy-online', action='store_true', help='copy this trainer while its online game is stopped')
    offline.add_argument('--display', help='dedicated nested Xephyr display :90..:199')
    offline.add_argument('--test-input', type=Path, help='run upstream headless engine input instead of GUI')
    offline.add_argument('--print-command', action='store_true')
    sub.add_parser('inspect', help='show players, shared tiles, mechanic revision/errors')
    deploy = sub.add_parser('deploy', help='stage and deploy a source candidate under state-dir/candidates')
    deploy.add_argument('source', type=Path)
    deploy.add_argument('--tests', type=Path)
    listing = sub.add_parser('list', help='list trainer profiles in this world')
    args = p.parse_args(argv)
    if args.command == 'desktop':
        if args.tk_runtime:
            command = [str(args.ui_python), '-m', 'world.launcher', 'desktop',
                       '--worlds-root', str(args.worlds_root), '--binary', str(args.binary),
                       '--display', args.display]
            return subprocess.run(command, env=tk_environment(args.tk_runtime), cwd=REPO).returncode
        from world.session import run_desktop
        return run_desktop(args.worlds_root, args.binary, args.display)
    if args.command == 'list-worlds':
        print(json.dumps({'worlds': discover_worlds(args.worlds_root)}, indent=2))
        return 0
    if args.state_dir is None:
        p.error('--state-dir is required for this command')
    if args.command in ('join', 'offline'):
        if args.engine == 'expansion-native':
            from world.expansion import run
            return run(args)
        if args.replay or args.frames is not None:
            p.error('--replay and --frames require --engine expansion-native')
        args.binary = args.binary or REPO / 'build/pokeemerald64'
    if args.command == 'offline':
        from world.offline import run_offline
        return run_offline(args)
    state = args.state_dir.resolve()
    require_online_state(state)
    if args.command == 'host':
        state = engine_state(state, args.engine)
        if state.resolve() != state:
            raise ValueError('engine state cannot contain symlinks')
        state.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    from world.world_library import WorldActivityLock
    with WorldActivityLock(state):
        state.mkdir(parents=True, exist_ok=True, mode=0o700)
        transport = state / 'transport'; transport.mkdir(exist_ok=True, mode=0o700)
        socket_path = transport / 'world.sock'
        if args.command == 'host':
            from world.server import WorldServer
            server = WorldServer(str(socket_path), str(state))
            try:
                server.serve_forever()
            finally:
                server.close()
        elif args.command == 'join':
            from contextlib import ExitStack
            with ExitStack() as stack:
                if any((args.remote, args.invitation, args.pin)):
                    if not all((args.remote, args.invitation, args.pin)) or args.seed_save:
                        raise ValueError('remote join requires --remote, --invitation and --pin, without --seed-save')
                    from .session import DesktopSession
                    from .transport import _endpoint
                    remote_session = stack.enter_context(DesktopSession(state.parent))
                    if args.agent_control:
                        # connect_remote takes its own preparation lock. Reject an
                        # existing endpoint before it can rewrite profile config.
                        with ProfileLock(state, args.trainer) as preflight:
                            check_player_endpoint(preflight.paths)
                    paths = remote_session.connect_remote(state.name, args.invitation, _endpoint(args.remote), args.pin)
                    if paths['profile'].name != args.trainer:
                        raise ValueError('trainer must match the assigned invitation')
                    stack.enter_context(ProfileLock(state, args.trainer))
                    if args.agent_control:
                        check_player_endpoint(paths)
                else:
                    if (state/'remote.json').exists():
                        raise ValueError('remote trainer saves require their invitation and TLS connection')
                    lock = stack.enter_context(ProfileLock(state, args.trainer))
                    if args.agent_control:
                        check_player_endpoint(lock.paths)
                    paths = _prepare_profile(state, args.trainer, args.seed_save, lock.paths)
                cmd = (game_command(args.binary, state, paths, args.display, agent_control=True)
                       if args.agent_control else game_command(args.binary, state, paths, args.display))
                if args.test_input:
                    target = args.test_input.resolve()
                    if paths['profile'] not in target.parents:
                        copied = paths['profile'] / 'input.txt'; shutil.copyfile(target, copied); target = copied
                    cmd += ['--test-input', str(target)]
                if args.bootstrap:
                    target = paths['profile'] / 'bootstrap.txt'
                    shutil.copyfile(args.bootstrap.resolve(), target)
                    cmd += ['--world-input', str(target)]
                if args.print_command:
                    print(json.dumps(cmd, indent=2))
                    return 0
                process = subprocess.Popen(cmd)
                try:
                    if args.agent_control:
                        import shlex
                        endpoint = player_endpoint(paths)
                        print(f'AI control starting. Endpoint: {endpoint}', file=sys.stderr, flush=True)
                        print('Observe: ' + shlex.join(['env', f'PYTHONPATH={REPO}', 'python3', '-m',
                                                       'world.player', '--endpoint', str(endpoint), 'observe']),
                              file=sys.stderr, flush=True)
                        code = f'from world.player import PlayerClient; print(PlayerClient({str(endpoint)!r}).observe())'
                        print('SDK: ' + shlex.join(['env', f'PYTHONPATH={REPO}', 'python3', '-c', code]),
                              file=sys.stderr, flush=True)
                    return process.wait()
                finally:
                    # Never release the profile while an interrupted child can save.
                    if process.poll() is None:
                        process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
        elif args.command == 'inspect':
            print(json.dumps(admin(socket_path, {'command': 'inspect'}), indent=2))
        elif args.command == 'deploy':
            payload = {'command': 'deploy', 'source_path': str(args.source.resolve())}
            if args.tests: payload['tests_path'] = str(args.tests.resolve())
            value = admin(socket_path, payload); print(json.dumps(value, indent=2))
            return 0 if value.get('ok') else 1
        elif args.command == 'list':
            profiles = state / 'trainers'
            print(json.dumps({'world': str(state), 'trainers': sorted(x.name for x in profiles.iterdir() if x.is_dir() and not x.is_symlink()) if profiles.exists() else []}, indent=2))
        return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f'Emerald World: {error}', file=sys.stderr)
        raise SystemExit(1)

