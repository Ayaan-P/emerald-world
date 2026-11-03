"""Private world labels and recoverable library operations on explicit roots.

Save contents are never guessed: this view has no validated Emerald save parser.
"""
import contextlib
import datetime
import json
import os
from pathlib import Path
import re
import stat
import uuid

CAPACITY = 32
KEY = re.compile(r'[A-Za-z0-9_-]{1,48}')
METADATA = '.library.json'


def _directory(path):
    path = Path(path)
    if not path.is_absolute() or path.resolve() != path:
        raise ValueError('Library directories cannot contain symlinks.')
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o022:
        raise ValueError('Library directories must be owned and not writable by others.')
    return path


class WorldActivityLock:
    """Shared world lifetime / exclusive move barrier, before any mutation.

    The inode lives outside the world and is never unlinked, so moving a world
    cannot split the barrier or let a late starter recreate its old pathname.
    Independent shared holders allow different trainers and the host to run.
    Callers creating a new world must hold this before mkdir, not afterwards.
    """
    def __init__(self, state_dir, exclusive=False):
        import fcntl
        import hashlib
        import threading
        self.fd = None
        self._guard = threading.Lock()
        path = Path(state_dir).absolute()
        if path.resolve() != path:
            raise ValueError('World activity paths cannot contain symlinks.')
        # The parent can be a sticky temporary directory in disposable callers.
        # Only our private lock directory is used for opening lock files.
        directory = path.parent/'.world-lifecycle-locks'
        directory.mkdir(mode=0o700, exist_ok=True)
        _directory(directory)
        parent = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            name = hashlib.sha256(os.fsencode(path.name)).hexdigest() + '.lock'
            fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW |
                         os.O_NONBLOCK | os.O_CLOEXEC, 0o600, dir_fd=parent)
            try:
                info = os.fstat(fd)
                if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                        or info.st_uid != os.geteuid() or info.st_mode & 0o077):
                    raise ValueError('Unsafe world lifecycle lock.')
                try:
                    fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise ValueError('World is active or moving. Stop it first or retry after the move.') from None
                if path.resolve() != path:
                    raise ValueError('World activity paths cannot contain symlinks.')
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

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def _world(root, key):
    root = _directory(root)
    if not isinstance(key, str) or not KEY.fullmatch(key) or key == 'Deleted':
        raise ValueError('Choose a valid stable world key, not Deleted.')
    return _directory(root/key)


def _read_metadata(path):
    try:
        fd = os.open(path/METADATA, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return {'display_name': path.name, 'tags': []}
    with os.fdopen(fd) as source:
        info = os.fstat(source.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_nlink != 1 or info.st_mode & 0o077 or info.st_size > 8192):
            raise ValueError('World label metadata is unsafe.')
        value = json.loads(source.read(8193))
    _labels(value['display_name'], value['tags'])
    return {'display_name': value['display_name'], 'tags': value['tags']}


def _labels(display_name, tags):
    if (not isinstance(display_name, str) or not 1 <= len(display_name.strip()) <= 80
            or any(ord(c) < 32 for c in display_name)
            or not isinstance(tags, list) or len(tags) > 12
            or any(not isinstance(t, str) or not 1 <= len(t) <= 24
                   or any(ord(c) < 32 for c in t) for t in tags)):
        raise ValueError('Use a name up to 80 characters and up to 12 short tags.')


def rename(root, key, display_name, tags):
    _labels(display_name, tags)
    path = _world(root, key)
    with WorldActivityLock(path):
        _read_metadata(path)  # Refuse unsafe existing targets rather than replacing them.
        parent = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        temporary = '.library-' + uuid.uuid4().hex
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=parent)
            with os.fdopen(fd, 'w') as output:
                json.dump({'display_name': display_name.strip(), 'tags': tags}, output)
                output.flush()
                os.fsync(output.fileno())
            _world(root, key)
            _read_metadata(path)
            os.replace(temporary, METADATA, src_dir_fd=parent, dst_dir_fd=parent)
            os.fsync(parent)
        finally:
            try:
                os.unlink(temporary, dir_fd=parent)
            except FileNotFoundError:
                pass
            os.close(parent)


def _move(source, destination):
    """Linux atomic RENAME_NOREPLACE. Fail closed when unavailable."""
    import ctypes
    import errno
    source_parent = os.open(_directory(source.parent), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    destination_parent = os.open(_directory(destination.parent), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = getattr(libc, 'renameat2', None)
        if renameat2 is None:
            raise ValueError('Atomic no-overwrite recovery is unavailable on this platform.')
        if renameat2(source_parent, os.fsencode(source.name), destination_parent,
                     os.fsencode(destination.name), 1) != 0:
            code = ctypes.get_errno()
            if code in (errno.EEXIST, errno.ENOTEMPTY):
                raise ValueError('Destination already exists. Nothing was replaced.')
            raise OSError(code, 'Atomic world move failed')
        os.fsync(source_parent)
        os.fsync(destination_parent)
    finally:
        os.close(source_parent)
        os.close(destination_parent)


def _deleted(root, create=False):
    root = _directory(root)
    path = root/'Deleted'
    if create:
        path.mkdir(mode=0o700, exist_ok=True)
    return _directory(path)


def _token(token):
    if not isinstance(token, str) or '--' not in token:
        raise ValueError('Choose a deleted world from this library.')
    key, suffix = token.rsplit('--', 1)
    if not KEY.fullmatch(key) or key == 'Deleted' or not re.fullmatch('[0-9a-f]{32}', suffix):
        raise ValueError('Choose a deleted world from this library.')
    return key


def deleted(root):
    _directory(root)
    if not (Path(root)/'Deleted').exists() and not (Path(root)/'Deleted').is_symlink():
        return []
    result = []
    for path in sorted(_deleted(root).iterdir()):
        try:
            key = _token(path.name)
        except ValueError:
            continue
        _directory(path)
        result.append({'token': path.name, 'key': key, **_read_metadata(path)})
    return result


@contextlib.contextmanager
def _inactive(path):
    """Hold every existing authority and game lifetime lock through the move."""
    import fcntl
    activity = WorldActivityLock(path, exclusive=True)
    descriptors = []
    try:
        # Reject links anywhere in the moved tree, including lock ancestors.
        # No save or credential contents are read.
        count = 0
        def scan_error(error):
            raise ValueError('World tree could not be checked. No files were moved.') from error
        for directory, directories, files in os.walk(path, followlinks=False, onerror=scan_error):
            _directory(Path(directory))
            for name in directories + files:
                entry = Path(directory)/name
                info = entry.lstat()
                count += 1
                if count > 10000 or stat.S_ISLNK(info.st_mode) or info.st_uid != os.geteuid():
                    raise ValueError('Unsafe world tree. No files were moved.')
        locks = [path/'world.lock', path/'gm/.lock', path/'gm/.runtime.lock']
        if (path/'.profile-locks').exists():
            locks += list((path/'.profile-locks').iterdir())
        for lock in locks:
            if not lock.exists():
                continue
            fd = os.open(lock, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
            descriptors.append(fd)
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid():
                raise ValueError('Unsafe world activity lock.')
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError('World is active in a host, native game or GM. Stop it first.') from None
        yield
    finally:
        for fd in reversed(descriptors):
            os.close(fd)
        activity.close()


def delete(root, key):
    path = _world(root, key)
    destination = _deleted(root, create=True)/(key + '--' + uuid.uuid4().hex)
    with _inactive(path):
        _world(root, key)
        _move(path, destination)
    return destination.name


def restore(root, token, count):
    key = _token(token)
    if count >= CAPACITY:
        raise ValueError('The library holds 32 worlds. Move an inactive world to Deleted first.')
    source = _directory(_deleted(root)/token)
    destination = _directory(root)/key
    with WorldActivityLock(destination, exclusive=True), _inactive(source):
        _move(source, destination)
    return destination


def cards(root, worlds):
    _directory(root)
    result = []
    for item in worlds:
        path = _world(root, item['name'])
        value = {'key': item['name'], 'path': str(path), **_read_metadata(path), 'trainers': []}
        directory = path/'trainers'
        if directory.exists() or directory.is_symlink():
            _directory(directory)
            for trainer in sorted(directory.iterdir()):
                if not re.fullmatch(r'[A-Za-z0-9_-]{1,24}', trainer.name):
                    continue
                _directory(trainer)
                saved = 'Unavailable (no save)'
                try:
                    info = (trainer/'game.sav').lstat()
                    if stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid():
                        saved = datetime.datetime.fromtimestamp(info.st_mtime).astimezone().isoformat(timespec='seconds')
                except FileNotFoundError:
                    pass
                value['trainers'].append({'name': trainer.name, 'saved_at': saved,
                    'party': 'Unavailable (save parser not available)',
                    'badges': 'Unavailable (save parser not available)',
                    'playtime': 'Unavailable (save parser not available)'})
        result.append(value)
    return result
