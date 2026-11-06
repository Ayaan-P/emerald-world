"""Separate native offline copies. Never creates a world identity or connection.

The online save is only read, while its normal profile lock is held. There is
no merge/import-back operation. Native runs without a world-config argument or
transport mount, in the same network-isolated sandbox as an online client.
"""
from contextlib import contextmanager, ExitStack
import json
import os
from pathlib import Path
import stat
import subprocess

from .launcher import ProfileLock, game_command, profile_paths
from .world_library import WorldActivityLock


def _private_directory(path):
    if path.resolve() != path:
        raise ValueError('Offline directories cannot contain symlinks.')
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise ValueError('Offline directories must be private and owned by this user.')


def _regular(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or info.st_uid != os.geteuid()):
        raise ValueError('Offline files must be owned single-link regular files.')


def _copy_seed(source, destination):
    source = Path(source).absolute()
    if source.resolve() != source:
        raise ValueError('Offline seed cannot contain symlinks.')
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_uid != os.geteuid() or not 0 < info.st_size <= 1048576):
            raise ValueError('Choose an owned regular seed save no larger than 1 MiB.')
        data = stream.read(1048577)
        if len(data) != info.st_size:
            raise ValueError('Seed changed while it was being copied.')
    try:
        output = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        raise ValueError('Offline save already exists. Resume it without a seed instead of overwriting it.') from None
    try:
        with os.fdopen(output, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


class OfflineGameLock:
    """Keep the enclosing library world immovable while its offline child runs."""
    def __init__(self, state_dir, trainer):
        import threading
        self._guard = threading.Lock()
        self.activity = None
        self.profile = None
        state = Path(state_dir).absolute()
        try:
            self.activity = WorldActivityLock(state)
            if state.resolve() != state or not state.is_dir():
                raise ValueError('World moved before offline play started. Select it again.')
            self.profile = ProfileLock(state / '.offline', trainer)
        except BaseException:
            self.close()
            raise

    def close(self):
        with self._guard:
            if self.profile is not None:
                self.profile.close()
                self.profile = None
            if self.activity is not None:
                self.activity.close()
                self.activity = None


@contextmanager
def offline_profile(state_dir, trainer, seed_save=None, *, copy_online=False):
    """Hold the destination for play, and the optional source only while copying."""
    state = Path(state_dir).absolute()
    if state.resolve() != state:
        raise ValueError('World paths cannot contain symlinks.')
    # Validate trainer before creating any profile directories.
    profile_paths(state, trainer)
    if copy_online and seed_save is not None:
        raise ValueError('Choose either an online copy or an explicit seed.')
    with ExitStack() as stack:
        stack.enter_context(WorldActivityLock(state))
        state.mkdir(parents=True, mode=0o700, exist_ok=True)
        from .rules import read
        read(state, create=True)
        offline = state / '.offline'
        _private_directory(offline)
        marker = offline / '.offline-copy'
        # Do not relabel an existing online world or remote profile as offline.
        if any((offline / name).exists() or (offline / name).is_symlink()
               for name in ('world.sqlite3', 'remote.json', 'transport')):
            raise ValueError('An online world cannot be converted into an offline copy.')
        _regular(marker)
        if not marker.exists():
            fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'w') as stream:
                stream.write('Emerald offline copy v1\n')
        lock = stack.enter_context(ProfileLock(offline, trainer))
        paths = lock.paths
        _private_directory(paths['profile'].parent)
        _private_directory(paths['profile'])
        _regular(paths['save'])
        _regular(paths['settings'])
        if (copy_online or seed_save is not None) and paths['save'].exists():
            raise ValueError('Offline save already exists. Resume without a seed instead of overwriting it.')
        if copy_online:
            with ProfileLock(state, trainer) as source_lock:
                _copy_seed(source_lock.paths['save'], paths['save'])
        elif seed_save is not None:
            _copy_seed(seed_save, paths['save'])
        if not paths['settings'].exists():
            fd = os.open(paths['settings'], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'w') as stream:
                stream.write('scale = 2\n')
        yield paths


def run_offline(args):
    with offline_profile(args.state_dir, args.trainer, args.seed_save, copy_online=args.copy_online) as paths:
        command = game_command(args.binary, Path(args.state_dir) / '.offline', paths,
                               args.display, online=False)
        if args.test_input:
            source = Path(args.test_input).absolute()
            target = paths['profile'] / 'input.txt'
            if source != target:
                if target.exists() or target.is_symlink():
                    _regular(target)
                    target.unlink()
                _copy_seed(source, target)
            command += ['--test-input', str(target)]
        if args.print_command:
            print(json.dumps(command, indent=2))
            return 0
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
