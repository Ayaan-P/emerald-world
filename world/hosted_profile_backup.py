"""Copy an owner profile into a private backup or restore it without overwrite.

The profile is a bearer credential: anyone holding a copy can manage the owned
worlds. This tool never prints its contents and never sends it over the network.
It does not back up player saves or server-side world data.
"""
import argparse
import json
import os
import secrets
from pathlib import Path
import stat
import sys

from .hosting_client import HostingClient
from .hosting_protocol import _json_object

MAX_PROFILE = 4096


def _parent_fd(path):
    parent = path.parent
    if not path.name or parent.resolve() != parent:
        raise ValueError('Directory cannot contain symlinks.')
    fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    info = os.fstat(fd)
    if info.st_uid != os.geteuid() or info.st_mode & 0o022:
        os.close(fd)
        raise ValueError('Directory must be owned and not writable by others.')
    return fd


def read_profile(path):
    """Read and validate a private, owned, single-link host profile."""
    path = Path(path).absolute()
    parent_fd = _parent_fd(path)
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
        with os.fdopen(fd, 'rb') as source:
            info = os.fstat(source.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or info.st_nlink != 1 or info.st_mode & 0o077 or info.st_size > MAX_PROFILE):
                raise ValueError('Profile must be a private, owned regular file.')
            raw = source.read(MAX_PROFILE + 1)
    finally:
        os.close(parent_fd)
    if len(raw) > MAX_PROFILE:
        raise ValueError('Profile is too large.')
    value = _json_object(raw)
    HostingClient(value)  # Validate kind, endpoint, pin and bearer format without network.
    return value


def copy_profile(source, destination):
    """Create a 0600 copy at a new path; never replace any existing file."""
    value = read_profile(source)
    destination = Path(destination).absolute()
    parent_fd = _parent_fd(destination)
    temporary = None
    try:
        raw = (json.dumps(value, separators=(',', ':')) + '\n').encode('utf-8')
        temporary = '.emerald-owner-' + secrets.token_hex(16) + '.tmp'
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=parent_fd)
        with os.fdopen(fd, 'wb') as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        # Publish a complete inode without replacing an existing destination.
        os.link(temporary, destination.name, src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd, follow_symlinks=False)
        os.unlink(temporary, dir_fd=parent_fd)
        temporary = None
        os.fsync(parent_fd)
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary, dir_fd=parent_fd)
            except OSError:
                pass
        os.close(parent_fd)
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('backup', 'restore'))
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        copy_profile(args.source, args.destination)
    except (OSError, ValueError, TypeError, RecursionError):
        parser.exit(1, 'Profile copy failed. Check permissions and choose a new destination. A completed file may already exist if disk synchronization failed.\n')
    print('Private owner profile copied. Keep it secure; it grants control of your hosted worlds.')
    print('Player saves and world data are not included.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
