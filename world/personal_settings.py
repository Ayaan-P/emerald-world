"""Edit supported Expansion startup settings without touching gameplay or saves.

The native contract is platform/settings.h, options.h and input.c: settings.ini
under --data-dir, scale 1..16, fullscreen auto/yes/no, and SDL key names.
Only explicit changed fields are rewritten. All other lines are preserved.
"""
from contextlib import ExitStack
import hashlib
import os
from pathlib import Path
import secrets
import stat

from .launcher import ProfileLock, profile_paths
from .offline import OfflineGameLock
from .world_library import WorldActivityLock

MAX_SIZE = 16384
KEYS = tuple('abcdefghijklmnopqrstuvwxyz0123456789') + (
    'up', 'down', 'left', 'right', 'return', 'backspace', 'space', 'tab',
    'left shift', 'right shift', 'left ctrl', 'right ctrl', 'left alt', 'right alt',
    'escape', 'home', 'end', 'pageup', 'pagedown', 'insert', 'delete') + tuple(
        f'keypad {number}' for number in range(10)) + tuple(f'f{number}' for number in range(2, 13))
DEFAULTS = {'scale': 3, 'fullscreen': 'auto', 'a': 'z', 'b': 'x', 'select': 'backspace',
            'start': 'return', 'right': 'right', 'left': 'left', 'up': 'up', 'down': 'down', 'r': 's', 'l': 'a'}


def _directory(path):
    path = Path(path).absolute()
    if path.resolve() != path:
        raise ValueError('Settings directories cannot contain symlinks.')
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    info = os.fstat(fd)
    if info.st_uid != os.geteuid() or info.st_mode & 0o022:
        os.close(fd)
        raise ValueError('Settings directories must be owned and not writable by others.')
    return fd


def _profile(world, trainer, offline):
    world = Path(world).absolute()
    state = world / '.offline' if offline else world
    paths = profile_paths(state, trainer, engine='expansion-native')
    # Inspect every ancestor under this library world, including the engine.
    directory = world
    directories = [directory]
    for part in paths['profile'].relative_to(world).parts[:-1]:
        directory = directory / part
        directories.append(directory)
    for directory in directories:
        fd = _directory(directory)
        os.close(fd)
    if offline:
        marker = (state / '.offline-copy').lstat()
        if (not stat.S_ISREG(marker.st_mode) or marker.st_uid != os.geteuid()
                or marker.st_nlink != 1 or marker.st_mode & 0o077):
            raise ValueError('Choose an existing offline profile.')
    return paths['profile']


def _read(directory):
    try:
        fd = os.open('settings.ini', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid()
                or before.st_nlink != 1 or before.st_mode & 0o022 or before.st_size > MAX_SIZE):
            raise ValueError('Settings must be an owned regular file no larger than 16 KiB.')
        data = stream.read(MAX_SIZE + 1)
        after = os.fstat(stream.fileno())
    stamp = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_ctime_ns)
    if len(data) > MAX_SIZE or stamp(before) != stamp(after) or len(data) != before.st_size:
        raise ValueError('Settings changed while being read. Reload them.')
    if b'\0' in data:
        raise ValueError('Settings contain invalid text. Check settings.ini before editing.')
    data.decode('utf-8-sig')
    return data


def _revision(data):
    return hashlib.sha256(b'missing' if data is None else b'file\0' + data).hexdigest()


def _line_key(line):
    name, separator, _ = line.partition('=')
    name = name.strip(' \t\r').lower()
    return name if separator and not name.startswith('#') else None


def _value(key, raw):
    raw = raw.strip(' \t\r').lower()
    if key == 'scale':
        return int(raw) if raw.isascii() and raw.isdecimal() and len(raw) < 20 and 1 <= int(raw) <= 16 else None
    if key == 'fullscreen':
        return raw if raw in ('auto', 'yes', 'no') else None
    return raw if raw in KEYS else None


def _snapshot(data):
    values = dict(DEFAULTS)
    custom = set()
    for line in (data or b'').decode('utf-8-sig').split('\n'):
        key = _line_key(line)
        if key not in DEFAULTS:
            continue
        value = _value(key, line.partition('=')[2])
        if value is None:
            # The SDL key vocabulary is wider than the editor. Do not pretend
            # an unknown binding is the default or overwrite it on another edit.
            custom.add(key)
            values[key] = None
        else:
            custom.discard(key)
            values[key] = value
    return {'revision': _revision(data), 'values': values, 'custom': sorted(custom), 'exists': data is not None}


def read_settings(world, trainer, *, offline=False):
    directory = _directory(_profile(world, trainer, offline))
    try:
        return _snapshot(_read(directory))
    finally:
        os.close(directory)


def write_settings(world, trainer, changes, expected_revision, *, offline=False):
    if (type(changes) is not dict or not changes or not set(changes) <= set(DEFAULTS)
            or not isinstance(expected_revision, str) or len(expected_revision) != 64):
        raise ValueError('Choose supported personal settings and reload the profile before saving.')
    for key, value in changes.items():
        if key == 'scale':
            valid = type(value) is int and 1 <= value <= 16
        else:
            valid = isinstance(value, str) and _value(key, value) == value
        if not valid:
            raise ValueError('Choose a supported setting value.')
    # The same lifetime/profile locks as game launch also protect other
    # launchers. Never stop a running game to acquire them.
    with ExitStack() as stack:
        world = Path(world).absolute()
        fd = _directory(world)
        os.close(fd)
        stack.enter_context(WorldActivityLock(world))
        profile = _profile(world, trainer, offline)
        lock = (OfflineGameLock(world, trainer, engine='expansion-native') if offline
                else ProfileLock(world, trainer, engine='expansion-native'))
        stack.callback(lock.close)
        directory = _directory(profile)
        stack.callback(os.close, directory)
        original = _read(directory)
        if _revision(original) != expected_revision:
            raise ValueError('Settings changed. Reload before saving your changes.')
        text = (original or b'').decode('utf-8-sig')
        newline = '\r\n' if '\r\n' in text else '\n'
        text = '\n'.join(line for line in text.split('\n') if _line_key(line) not in changes)
        if text and not text.endswith('\n'):
            text += newline
        text += ''.join(f'{key} = {value}{newline}' for key, value in changes.items())
        data = (b'\xef\xbb\xbf' if original and original.startswith(b'\xef\xbb\xbf') else b'') + text.encode()
        if len(data) > MAX_SIZE:
            raise ValueError('The settings file would exceed 16 KiB. No changes were saved.')
        temporary = '.settings-' + secrets.token_hex(16)
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if _revision(_read(directory)) != expected_revision:
                raise ValueError('Settings changed. Reload before saving your changes.')
            os.replace(temporary, 'settings.ini', src_dir_fd=directory, dst_dir_fd=directory)
            os.fsync(directory)
        finally:
            try:
                os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass
        return _snapshot(data)
