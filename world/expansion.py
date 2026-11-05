"""Opt-in native Expansion sessions and a read-only world presence adapter.

Expansion worlds use a separate authority and identity database as well as saves.
Presence is always busy: no native link, ownership payload or world mutation ABI
is claimed. The donor's scalar inspect facts are the only engine state we read.
"""
import json
from pathlib import Path
import subprocess
import threading
import time

from .launcher import REPO, ProfileLock, engine_state, game_command, profile_paths, _prepare_profile

ENGINE = 'expansion-native'
BINARY = REPO / 'build/expansion-native/pokeemerald-native'


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
        self.stop = threading.Event()
        self.error = None

    def _presence(self):
        from .client import WorldClient
        config = dict(line.split(' ', 1) for line in self.paths['config'].read_text().splitlines())
        try:
            with WorldClient(config['socket'], self.trainer, config['token'], timeout=1, social=True) as client:
                client.snapshot()
                seq = 0
                while not self.stop.wait(0.1):
                    path = self.paths['profile'] / 'presence.json'
                    try:
                        if time.time() - path.stat().st_mtime > 2:
                            raise ValueError('Expansion presence stopped advancing')
                        state = json.loads(path.read_text())
                    except FileNotFoundError:
                        continue
                    if state.get('schema') != 1 or state.get('engine') != ENGINE:
                        raise ValueError('unsupported Expansion presence schema')
                    seq += 1
                    if state.get('field'):
                        coordinates = [state[key] for key in ('group', 'num', 'x', 'y')]
                        if any(type(value) is not int or not 0 <= value <= limit
                               for value, limit in zip(coordinates, (255, 255, 32767, 32767))):
                            raise ValueError('invalid Expansion presence coordinates')
                        # FIELD is the SOCIAL protocol's visible-but-busy state.
                        # Zero hashes mean unavailable, not portable ownership.
                        values = [seq, *coordinates, 1, 0, 0]
                        message = 'FIELD ' + ' '.join(map(str, values)) + ' ' + '0'*16 + ' ' + '0'*16 + '\n'
                        client.sock.sendall(message.encode('ascii'))
                    else:
                        client.send_state(seq, 0, 0, 0, 0, 1, 7, 0, '0'*16, '0'*16)
                    snapshot = dict(client.snapshot(), engine=ENGINE, mode='presence-only', multiplayer=False)
                    temporary = self.paths['telemetry'].with_suffix('.tmp')
                    temporary.write_text(json.dumps(snapshot))
                    temporary.replace(self.paths['telemetry'])
        except (OSError, ValueError, KeyError) as exc:
            self.error = str(exc)

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
            command = game_command(binary, self.base, self.paths, display, online=False, engine=ENGINE)
            boundary = command.index('--')
            extra = []
            symbols = Path(str(Path(binary).resolve()) + '.symbols')
            if symbols.is_file():
                extra += ['--ro-bind', str(symbols), str(symbols)]
            if replay:
                replay = Path(replay).resolve(strict=True)
                extra += ['--ro-bind', str(replay.parent), str(replay.parent)]
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
            worker = None
            try:
                if self.online:
                    worker = threading.Thread(target=self._presence, daemon=True, name='expansion-presence')
                    worker.start()
                while process.poll() is None:
                    if self.error:
                        raise ValueError('Expansion presence bridge: ' + self.error)
                    time.sleep(0.1)
                code = process.wait()
                if self.error:
                    raise ValueError('Expansion presence bridge: ' + self.error)
                return code
            finally:
                self.stop.set()
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                if worker:
                    worker.join(timeout=2)


def run(args):
    if any(getattr(args, name, None) for name in
           ('seed_save', 'copy_online', 'agent_control', 'test_input', 'bootstrap', 'remote', 'invitation', 'pin')):
        raise ValueError('Expansion does not accept vanilla saves, controls, input scripts or invitations. Use --replay for donor replays.')
    session = ExpansionSession(args.state_dir, args.trainer, online=args.command == 'join')
    return session.run(args.binary or BINARY, args.display, replay=args.replay, frames=args.frames,
                       print_command=args.print_command)
