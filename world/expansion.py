"""RC7 sessions running the full Expansion engine with native world integration.

The game owns its world/link connections and private ownership transactions.
Expansion profiles and authority remain isolated from vanilla save/protocol data.
"""
import json
from pathlib import Path
import subprocess

from .launcher import REPO, ProfileLock, engine_state, game_command, profile_paths, _prepare_profile

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

    def run(self, binary=BINARY, display=None, *, replay=None, frames=None, print_command=False):
        if self.state.resolve() != self.state:
            raise ValueError('Expansion state cannot contain symlinks')
        self.state.mkdir(parents=True, mode=0o700, exist_ok=True)
        with ProfileLock(self.state, self.trainer) as lock:
            if lock.paths != self.paths:
                raise ValueError('Expansion profile namespace mismatch')
            if self.online:
                _prepare_profile(self.state, self.trainer, None, self.paths)
            else:
                self.paths['profile'].mkdir(parents=True, mode=0o700, exist_ok=True)
            command = game_command(binary, self.base, self.paths, display, online=self.online, engine=ENGINE)
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
           ('seed_save', 'copy_online', 'agent_control', 'test_input', 'bootstrap', 'remote', 'invitation', 'pin')):
        raise ValueError('Expansion does not accept vanilla saves, controls, input scripts or invitations. Use --replay for donor replays.')
    session = ExpansionSession(args.state_dir, args.trainer, online=args.command == 'join')
    return session.run(args.binary or BINARY, args.display, replay=args.replay, frames=args.frames,
                       print_command=args.print_command)
