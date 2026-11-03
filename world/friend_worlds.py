"""Private bookmarks for authenticated friend worlds, separate from save data."""
import json
import os
import stat
import uuid

from .transport import validate_invitation
from .world_library import _directory, KEY, WorldActivityLock

BOOKMARK = '.friend.json'


def read(path):
    path = _directory(path)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Invalid saved friend connection.')
            result[key] = value
        return result
    try:
        fd = os.open(path/BOOKMARK, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as source:
            info = os.fstat(source.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or info.st_nlink != 1 or info.st_mode & 0o077 or info.st_size > 4096):
                raise ValueError('Invalid saved friend connection.')
            raw = source.read(4097)
            if len(raw) > 4096:
                raise ValueError('Invalid saved friend connection.')
            value = validate_invitation(json.loads(raw, object_pairs_hook=unique))
        if 'version' not in value:
            raise ValueError('Invalid saved friend connection.')
        return value
    except (OSError, ValueError, TypeError, RecursionError):
        raise ValueError('Saved friend connection is missing or unsafe.') from None


def remember(path, invitation):
    path = _directory(path)
    validate_invitation(invitation)
    target = path/BOOKMARK
    if target.exists() or target.is_symlink():
        read(path)  # Do not replace an unsafe existing capability file.
    parent = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = '.friend-' + uuid.uuid4().hex
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=parent)
        with os.fdopen(fd, 'w') as output:
            json.dump(invitation, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, BOOKMARK, src_dir_fd=parent, dst_dir_fd=parent)
        os.fsync(parent)
    finally:
        try:
            os.unlink(temporary, dir_fd=parent)
        except FileNotFoundError:
            pass
        os.close(parent)


def worlds(root):
    result = []
    for path in sorted(_directory(root).iterdir()):
        if not KEY.fullmatch(path.name) or path.name == 'Deleted' or not path.is_dir():
            continue
        if not (path/BOOKMARK).exists() and not (path/BOOKMARK).is_symlink():
            continue
        try:
            invitation = read(path)
        except ValueError:
            continue  # One corrupt bookmark must not prevent other worlds opening.
        result.append({'name': path.name, 'trainer': invitation['trainer']})
    return result


def forget(path):
    path = _directory(path)
    with WorldActivityLock(path):
        read(path)
        parent = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.unlink(BOOKMARK, dir_fd=parent)
            os.fsync(parent)
        finally:
            os.close(parent)
