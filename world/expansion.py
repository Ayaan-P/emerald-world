"""RC7 sessions running the full Expansion engine with native world integration.

The game owns its world/link connections and private ownership transactions.
Expansion profiles and authority remain isolated from vanilla save/protocol data.
"""
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess

from .launcher import (REPO, ProfileLock, check_player_endpoint, engine_state,
                       game_command, player_endpoint, profile_paths, _prepare_profile)

ENGINE = 'expansion-native'
BINARY = REPO / 'build/expansion-native/pokeemerald-native'


def stage_replay(source, profile):
    """Flatten bounded textual includes, never mount an input directory.

    Donor includes are textual before parsing, so cold-restart line numbers
    retain the same meaning. Includes must remain inside the selected directory.
    """
    import os
    import tempfile
    source = Path(source).resolve(strict=True)
    root = source.parent
    files = 0
    total = 0

    def expand(path, depth=0):
        nonlocal files, total
        path = path.resolve()
        if not path.is_relative_to(root) or depth > 4 or files >= 64:
            raise ValueError('replay include escapes its directory or exceeds donor limits')
        files += 1
        with path.open('rb') as stream:
            data = stream.read(1024*1024+1)
        total += len(data)
        if total > 1024*1024 or b'\0' in data:
            raise ValueError('replay exceeds donor size limits or contains NUL bytes')
        lines = []
        for line in data.splitlines():
            fields = line.partition(b'#')[0].split()
            if fields and fields[0] == b'include':
                if len(fields) != 2:
                    raise ValueError('replay include requires one relative filename')
                lines.append(expand(path.parent / fields[1].decode('utf-8'), depth+1))
            else:
                lines.append(line+b'\n')
        return b''.join(lines)

    data = expand(source)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=profile, prefix='.replay-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        target = profile / 'replay-input.replay'
        os.replace(temporary, target)
        return target
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


class ExpansionSession:
    def __init__(self, state_dir, trainer, *, online=True):
        from .launcher import require_online_state
        base = Path(state_dir).resolve()
        if online:
            require_online_state(base)
        self.base = base if online else base / '.offline'
        if self.base.resolve() != self.base:
            raise ValueError('Expansion state cannot contain symlinks')
        self.state = engine_state(self.base, ENGINE)
        self.paths = profile_paths(self.base, trainer, engine=ENGINE)
        self.trainer = trainer
        self.online = online

    def _verify_prepared_profile(self):
        """Validate host/join credentials already installed in this private profile."""
        import os

        path = self.paths['config']
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except OSError as exc:
            raise ValueError('Expansion profile has no safe prepared authority config') from exc
        with os.fdopen(fd, 'r') as source:
            info = os.fstat(source.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or info.st_uid != os.geteuid() or info.st_mode & 0o077):
                raise ValueError('Expansion authority config must be a private owned file')
            text = source.read(4097)
        if len(text.encode()) > 4096:
            raise ValueError('Expansion authority config is oversized')
        fields = {}
        for line in text.splitlines():
            key, separator, value = line.partition(' ')
            if not separator or key in fields:
                raise ValueError('Expansion authority config is invalid')
            fields[key] = value
        if (set(fields) != {'socket', 'trainer', 'token', 'telemetry'}
                or fields['socket'] != str(self.state/'transport/world.sock')
                or fields['trainer'] != self.trainer
                or fields['telemetry'] != str(self.paths['telemetry'])
                or not re.fullmatch(r'[0-9a-fA-F]{64}', fields['token'])):
            raise ValueError('Expansion profile is not prepared for this engine authority')

    def start(self, binary=BINARY, display=None, *, agent_control=False, provision_online=True, field_skills=False):
        """Start one browser-managed native client and return its held profile lock."""
        import shutil
        import subprocess

        if self.state.resolve() != self.state or self.base.resolve() != self.base:
            raise ValueError('Expansion state cannot contain symlinks')
        if self.online:
            self._require_authority()
        self.state.mkdir(parents=True, mode=0o700, exist_ok=True)
        if self.online:
            lock = ProfileLock(self.base, self.trainer, engine=ENGINE)
            profile_lock = lock
        else:
            from .offline import OfflineGameLock
            lock = OfflineGameLock(self.base.parent, self.trainer, engine=ENGINE)
            profile_lock = lock.profile
            if profile_lock is None:
                lock.close()
                raise ValueError('Expansion profile namespace mismatch')
        try:
            if profile_lock.paths != self.paths:
                raise ValueError('Expansion profile namespace mismatch')
            if self.online and provision_online:
                _prepare_profile(self.base, self.trainer, None, self.paths, engine=ENGINE)
            elif self.online:
                self._verify_prepared_profile()
            else:
                self.paths['profile'].mkdir(parents=True, mode=0o700, exist_ok=True)
            if agent_control:
                check_player_endpoint(self.paths)
            binary = Path(binary)
            if not binary.is_file() or not os.access(binary, os.X_OK):
                raise ValueError('Expansion native binary is missing or not executable')
            if not shutil.which('bwrap'):
                raise ValueError('Bubblewrap is required to isolate the Expansion client')
            if display and not Path('/tmp/.X11-unix/X' + display[1:]).is_socket():
                raise ValueError('Dedicated game display is missing')
            command = game_command(binary, self.base, self.paths, display,
                                   agent_control=agent_control, online=self.online, engine=ENGINE, field_skills=field_skills)
            symbols = Path(str(binary.resolve()) + '.symbols')
            if symbols.is_file():
                boundary = command.index('--')
                command[boundary:boundary] = ['--ro-bind', str(symbols), str(symbols)]
            for filename in ('presence.json', 'telemetry.json'):
                path = self.paths['profile'] / filename
                if path.is_symlink():
                    raise ValueError('Expansion telemetry cannot be a symlink')
                path.unlink(missing_ok=True)
            logfile = self.paths['profile'] / 'native.log'
            if logfile.is_symlink():
                raise ValueError('Native log cannot be a symlink')
            fd = os.open(logfile, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
            with os.fdopen(fd, 'wb') as output:
                info = os.fstat(output.fileno())
                if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                        or info.st_uid != os.geteuid()):
                    raise ValueError('Native log must be an owned single-link regular file')
                os.ftruncate(output.fileno(), 0)
                from .launcher import start_owned_process
                process = start_owned_process(command, stdin=subprocess.DEVNULL,
                                              stdout=output, stderr=subprocess.STDOUT)
            return process, lock
        except BaseException:
            lock.close()
            raise

    def _require_authority(self):
        """Fail before profile provisioning if the matching host is absent."""
        endpoint = self.state / 'transport' / 'world.sock'
        try:
            info = endpoint.lstat()
        except FileNotFoundError:
            raise ValueError('Expansion world authority is not running; start the expansion host first') from None
        if (not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_mode & 0o077):
            raise ValueError('Expansion world authority socket is unsafe or invalid')
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.2)
            try:
                probe.connect(str(endpoint))
            except OSError as exc:
                raise ValueError('Expansion world authority is not accepting connections; start the expansion host first') from exc

    def run(self, binary=BINARY, display=None, *, replay=None, frames=None, agent_control=False, print_command=False, field_skills=False):
        if self.state.resolve() != self.state:
            raise ValueError('Expansion state cannot contain symlinks')
        if self.online:
            self._require_authority()
        self.state.mkdir(parents=True, mode=0o700, exist_ok=True)
        with ProfileLock(self.base, self.trainer, engine=ENGINE) as lock:
            if lock.paths != self.paths:
                raise ValueError('Expansion profile namespace mismatch')
            if self.online:
                _prepare_profile(self.base, self.trainer, None, self.paths, engine=ENGINE)
            else:
                self.paths['profile'].mkdir(parents=True, mode=0o700, exist_ok=True)
            if agent_control:
                check_player_endpoint(self.paths)
            command = game_command(binary, self.base, self.paths, display, agent_control=agent_control,
                                  online=self.online, engine=ENGINE, field_skills=field_skills)
            boundary = command.index('--')
            extra = []
            symbols = Path(str(Path(binary).resolve()) + '.symbols')
            if symbols.is_file():
                extra += ['--ro-bind', str(symbols), str(symbols)]
            if replay:
                replay = stage_replay(replay, self.paths['profile'])
                command += ['--replay', str(replay), '--out', str(self.paths['profile'] / 'replay-out'),
                            '--unthrottled', '--rtc-fixed', '1700000000']
            if frames is not None:
                command += ['--frames', str(frames)]
            command[boundary:boundary] = extra
            if print_command:
                print(json.dumps(command, indent=2))
                return 0
            # Discard only our disposable telemetry, never any save or settings.
            for filename in ('presence.json', 'telemetry.json'):
                path = self.paths['profile'] / filename
                if path.is_symlink():
                    raise ValueError('Expansion telemetry cannot be a symlink')
                path.unlink(missing_ok=True)
            process = subprocess.Popen(command)
            try:
                if agent_control:
                    import shlex
                    endpoint = player_endpoint(self.paths)
                    print(f'AI control starting. Endpoint: {endpoint}', flush=True)
                    print('Observe: ' + shlex.join(['env', f'PYTHONPATH={REPO}', 'python3', '-m',
                                                   'world.player', '--endpoint', str(endpoint), 'observe']),
                          flush=True)
                    code = f'from world.player import PlayerClient; print(PlayerClient({str(endpoint)!r}).observe())'
                    print('SDK: ' + shlex.join(['env', f'PYTHONPATH={REPO}', 'python3', '-c', code]),
                          flush=True)
                return process.wait()
            finally:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def run(args):
    if any(getattr(args, name, None) for name in
           ('seed_save', 'copy_online', 'test_input', 'bootstrap', 'remote', 'invitation', 'pin')):
        raise ValueError('Expansion does not accept vanilla saves, input scripts or invitations. Use --replay for donor replays.')
    session = ExpansionSession(args.state_dir, args.trainer, online=args.command == 'join')
    return session.run(args.binary or BINARY, args.display, replay=args.replay, frames=args.frames,
                       agent_control=bool(getattr(args, 'agent_control', False)),
                       print_command=args.print_command, field_skills=bool(getattr(args, 'field_skills', False)))
