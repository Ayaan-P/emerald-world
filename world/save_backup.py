"""Create a private backup of one stopped trainer's local save.

This copies bytes only. It does not validate game progress, alter the source,
contact a server, or back up hosted-world state or account credentials.
"""
import argparse
import os
from pathlib import Path
import secrets
import stat
import sys

from .launcher import ProfileLock, profile_paths, require_online_state
from .offline import OfflineGameLock

MAX_SAVE = 131072  # The native Emerald flash buffer is 128 KiB.


def _owned_directory(path):
    path = Path(path).absolute()
    if path.resolve() != path:
        raise ValueError('Directory cannot contain symlinks.')
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    info = os.fstat(fd)
    if info.st_uid != os.geteuid() or info.st_mode & 0o022:
        os.close(fd)
        raise ValueError('Directory must be owned and not writable by others.')
    return fd


def backup_save(world, trainer, destination, *, offline=False, engine='vanilla'):
    """Copy one save while holding its existing nonblocking profile lock."""
    world = Path(world).absolute()
    destination = Path(destination).absolute()
    # Check the supplied world before constructing any paths or acquiring locks.
    check = _owned_directory(world)
    os.close(check)
    if not offline:
        require_online_state(world)
    state = world / '.offline' if offline else world
    if offline:
        marker = (state / '.offline-copy').lstat()
        if (not stat.S_ISREG(marker.st_mode) or marker.st_uid != os.geteuid()
                or marker.st_nlink != 1 or marker.st_mode & 0o077):
            raise ValueError('Choose a valid private offline profile.')
    paths = profile_paths(state, trainer, engine=engine)
    for directory in (state, paths['profile'].parent, paths['profile']):
        check = _owned_directory(directory)
        os.close(check)
    destination_fd = _owned_directory(destination.parent)
    lock = None
    temporary = None
    try:
        # OfflineGameLock also holds the parent world lifecycle barrier.
        lock = OfflineGameLock(world, trainer, engine=engine) if offline else ProfileLock(world, trainer, engine=engine)
        source_fd = os.open(paths['save'], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(source_fd, 'rb') as source:
            before = os.fstat(source.fileno())
            if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid()
                    or before.st_nlink != 1 or not 0 < before.st_size <= MAX_SAVE):
                raise ValueError('Save must be an owned, nonempty regular file no larger than 128 KiB.')
            data = source.read(MAX_SAVE + 1)
            after = os.fstat(source.fileno())
        stamp = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        if len(data) != before.st_size or stamp(before) != stamp(after):
            raise ValueError('Save changed while being copied. Close the game and retry.')
        temporary = '.emerald-save-' + secrets.token_hex(16) + '.tmp'
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=destination_fd)
        with os.fdopen(fd, 'wb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        # Linking publishes the complete inode atomically and never replaces a destination.
        os.link(temporary, destination.name, src_dir_fd=destination_fd,
                dst_dir_fd=destination_fd, follow_symlinks=False)
        os.unlink(temporary, dir_fd=destination_fd)
        temporary = None
        os.fsync(destination_fd)
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary, dir_fd=destination_fd)
            except OSError:
                pass
        if lock is not None:
            lock.close()
        os.close(destination_fd)
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path, required=True, help='explicit local world folder')
    parser.add_argument('--trainer', required=True, help='local trainer profile key')
    parser.add_argument('--destination', type=Path, required=True, help='new backup file path')
    parser.add_argument('--offline', action='store_true', help='back up the separate offline profile')
    parser.add_argument('--engine', choices=('vanilla', 'expansion-native'), default='vanilla')
    args = parser.parse_args(argv)
    try:
        backup_save(args.world, args.trainer, args.destination, offline=args.offline, engine=args.engine)
    except (OSError, ValueError, TypeError):
        parser.exit(1, 'Save backup failed. Close the game, check paths and permissions, and choose a new destination. A completed file may already exist if disk synchronization failed.\n')
    print('Private save backup created. The source was not modified. Save compatibility was not checked.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
