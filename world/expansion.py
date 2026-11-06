"""Opt-in native Expansion sessions and a read-only world presence adapter.

Expansion worlds use a separate authority and identity database as well as saves.
Presence is always busy: no native link, ownership payload or world mutation ABI
is claimed. The donor's scalar inspect facts are the only engine state we read.
"""
import json
import re
from pathlib import Path
import subprocess
import threading
import tempfile
import os
import time

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


def serialize_peers(snapshot):
    """Translate an authenticated server snapshot into a bounded engine input."""
    peers = snapshot.get('peers')
    if type(peers) is not dict or len(peers) > 8:
        raise ValueError('invalid Expansion peer snapshot')
    lines = ['EWPEERS 1']
    for name, peer in sorted(peers.items()):
        if (type(name) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,24}', name)
                or type(peer) is not dict):
            raise ValueError('invalid Expansion peer')
        keys = ('group', 'num', 'x', 'y', 'facing', 'gfx')
        values = [peer.get(k) for k in keys]
        if any(type(v) is not int or v < lo or v > hi for v, lo, hi in
               zip(values, (0, 0, 0, 0, 1, 0), (255, 255, 32767, 32767, 4, 255))):
            raise ValueError('invalid Expansion peer position')
        lines.append(' '.join([name, *(str(v) for v in values)]))
    return '\n'.join(lines) + '\n'


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

    def _receive_snapshots(self, client, finished):
        try:
            while not finished.is_set():
                snapshot = dict(client.snapshot(), engine=ENGINE, mode='presence-only', multiplayer=False)
                peer_path = self.paths['profile'] / 'peers.txt'
                temporary_peer = None
                try:
                    with tempfile.NamedTemporaryFile(mode='w', encoding='ascii',
                                                     dir=self.paths['profile'],
                                                     prefix='.peers-', delete=False) as stream:
                        temporary_peer = Path(stream.name)
                        stream.write(serialize_peers(snapshot))
                    os.replace(temporary_peer, peer_path)
                finally:
                    if temporary_peer is not None:
                        temporary_peer.unlink(missing_ok=True)
                temporary = self.paths['telemetry'].with_suffix('.tmp')
                temporary.write_text(json.dumps(snapshot))
                temporary.replace(self.paths['telemetry'])
        except (OSError, ValueError) as exc:
            if not finished.is_set() and not self.stop.is_set():
                self.error = str(exc)

    def _publish_presence(self, client):
        seq = 0
        started = time.monotonic()
        while not self.stop.wait(0.1):
            path = self.paths['profile'] / 'presence.json'
            try:
                if time.time() - path.stat().st_mtime > 2:
                    raise ValueError('Expansion presence stopped advancing')
                state = json.loads(path.read_text())
            except FileNotFoundError:
                if time.monotonic() - started > 5:
                    raise ValueError('Expansion binary did not publish presence')
                continue
            if state.get('schema') != 1 or state.get('engine') != ENGINE:
                raise ValueError('unsupported Expansion presence schema')
            seq += 1
            coordinates = None
            if state.get('field'):
                coordinates = [state[key] for key in ('group', 'num', 'x', 'y')]
                if any(type(value) is not int or not 0 <= value <= limit
                       for value, limit in zip(coordinates, (255, 255, 32767, 32767))):
                    raise ValueError('invalid Expansion presence coordinates')
                # Group 34 is generated worlds in the server's vanilla catalog,
                # but FRLG link rooms in Expansion. Never alias unrelated maps.
                from .build_catalog import validate_coords
                if coordinates[0] >= 34:
                    coordinates = None
                else:
                    try:
                        validate_coords(*coordinates)
                    except ValueError:
                        coordinates = None
            if coordinates is not None:
                # FIELD is the SOCIAL protocol's visible-but-busy state.
                # Zero hashes mean unavailable, not portable ownership.
                facing, gfx = state.get('facing', 1), state.get('gfx', 0)
                if type(facing) is not int or not 1 <= facing <= 4 or type(gfx) is not int or not 0 <= gfx <= 255:
                    raise ValueError('invalid Expansion avatar')
                values = [seq, *coordinates, facing, gfx, 0]
                message = 'FIELD ' + ' '.join(map(str, values)) + ' ' + '0'*16 + ' ' + '0'*16 + '\n'
                client.sock.sendall(message.encode('ascii'))
            else:
                client.send_state(seq, 0, 0, 0, 0, 1, 7, 0, '0'*16, '0'*16)

    def _presence(self):
        import socket
        from .client import WorldClient
        try:
            config = dict(line.split(' ', 1) for line in self.paths['config'].read_text().splitlines())
            with WorldClient(config['socket'], self.trainer, config['token'], timeout=1, social=True) as client:
                # One reader owns the buffered stream. It drains broadcasts even
                # before the engine starts and independently of our publish rate.
                client.sock.settimeout(None)
                finished = threading.Event()
                reader = threading.Thread(target=self._receive_snapshots, args=(client, finished),
                                          daemon=True, name='expansion-snapshots')
                reader.start()
                try:
                    self._publish_presence(client)
                finally:
                    finished.set()
                    try:
                        client.sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    reader.join(timeout=2)
        except (OSError, ValueError, KeyError) as exc:
            self.error = str(exc)

    def run(self, binary=BINARY, display=None, *, replay=None, frames=None, print_command=False, prepared_remote=False):
        if self.state.resolve() != self.state:
            raise ValueError('Expansion state cannot contain symlinks')
        self.state.mkdir(parents=True, mode=0o700, exist_ok=True)
        with ProfileLock(self.state, self.trainer) as lock:
            if lock.paths != self.paths:
                raise ValueError('Expansion profile namespace mismatch')
            if self.online:
                if prepared_remote:
                    # DesktopSession already authenticated and wrote this profile's
                    # invitation. Do not replace it with a local identity.
                    if not (self.state / 'remote.json').is_file() or not self.paths['config'].is_file():
                        raise ValueError('Expansion remote profile is not prepared')
                else:
                    if (self.state / 'remote.json').exists() or (self.state / 'remote.json').is_symlink():
                        raise ValueError('Remote Expansion saves require their invitation and TLS connection')
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
            for filename in ('presence.json', 'telemetry.json', 'peers.txt'):
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
           ('seed_save', 'copy_online', 'agent_control', 'test_input', 'bootstrap')):
        raise ValueError('Expansion does not accept vanilla saves, controls or input scripts. Use --replay for donor replays.')
    session = ExpansionSession(args.state_dir, args.trainer, online=args.command == 'join')
    options = dict(replay=args.replay, frames=args.frames, print_command=args.print_command)
    remote = tuple(getattr(args, name, None) for name in ('remote', 'invitation', 'pin'))
    if not any(remote):
        return session.run(args.binary or BINARY, args.display, **options)
    if args.command != 'join' or not all(remote):
        raise ValueError('Expansion remote join requires --remote, --invitation and --pin')
    from .transport import _endpoint, read_invitation
    identity = read_invitation(args.invitation)
    if identity['trainer'] != args.trainer:
        raise ValueError('trainer must match the assigned invitation')
    # Reuse the existing TLS broker in the Expansion engine namespace. Its
    # profile path is exactly the Expansion trainer path, not a vanilla save.
    if session.state.resolve() != session.state:
        raise ValueError('Expansion state cannot contain symlinks')
    session.state.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    from .session import DesktopSession
    with DesktopSession(session.state.parent) as broker:
        paths = broker.connect_remote(session.state.name, args.invitation, _endpoint(args.remote), args.pin)
        if paths != session.paths:
            raise ValueError('Expansion remote profile namespace mismatch')
        return session.run(args.binary or BINARY, args.display, prepared_remote=True, **options)
