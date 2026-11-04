"""Per-worlds-root launcher ownership. Permanent inode, no PID-based recovery."""
import fcntl
import http.client
import json
import os
from pathlib import Path
import re
import stat
import time


class InstanceError(ValueError):
    """Fixed public diagnostics, never discovery contents or capabilities."""


class LauncherInstance:
    def __init__(self, root):
        self.fd = None
        self.owner = False
        root = Path(root)
        try:
            info = root.lstat()
            if (not root.is_absolute() or root.resolve() != root
                    or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                    or info.st_mode & 0o022):
                raise ValueError
            parent = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                fd = os.open('.launcher-instance', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW |
                             os.O_NONBLOCK | os.O_CLOEXEC, 0o600, dir_fd=parent)
            finally:
                os.close(parent)
            self.fd = fd
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or info.st_nlink != 1 or info.st_mode & 0o077):
                raise ValueError
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            self.owner = True
            os.ftruncate(fd, 0)
        except (OSError, ValueError):
            self.close()
            raise InstanceError('Launcher state is unsafe. Check worlds-root ownership and permissions. '
                                'Do not delete files while a launcher is running.') from None

    def publish(self, port, capability):
        fd = self.fd
        if not self.owner or fd is None:
            raise InstanceError('Only the running launcher can publish its listener.')
        value = json.dumps({'port': port, 'capability': capability}).encode()
        os.ftruncate(fd, 0)
        os.pwrite(fd, value, 0)

    def existing_url(self, timeout=3):
        # A simultaneous shortcut may arrive between flock and publication.
        # An unresponsive owner is never evicted and its files are never removed.
        fd = self.fd
        assert fd is not None
        deadline = time.monotonic() + timeout
        while True:
            connection = None
            try:
                if os.fstat(fd).st_size > 1024:
                    raise ValueError
                value = json.loads(os.pread(fd, 1025, 0))
                port, capability = value['port'], value['capability']
                if (type(port) is not int or not 1 <= port <= 65535
                        or not isinstance(capability, str)
                        or re.fullmatch(r'[A-Za-z0-9_-]{43}', capability) is None):
                    raise ValueError
                connection = http.client.HTTPConnection('127.0.0.1', port, timeout=0.25)
                connection.request('GET', '/api/instance', headers={'Authorization': 'Bearer ' + capability})
                response = connection.getresponse()
                if response.status == 200 and response.read(65) == b'{"launcher": 1}':
                    return f'http://127.0.0.1:{port}/#{capability}'
            except (OSError, ValueError, TypeError, KeyError, http.client.HTTPException):
                pass
            finally:
                if connection is not None:
                    connection.close()
            if time.monotonic() >= deadline:
                raise InstanceError('Another launcher owns this worlds root but is not responding. '
                                    'Use Quit in that launcher or close its process, then retry. '
                                    'Do not delete socket or lock files.') from None
            time.sleep(0.05)

    def close(self):
        if self.fd is not None:
            try:
                if self.owner:
                    os.ftruncate(self.fd, 0)
            finally:
                os.close(self.fd)
                self.fd = None
