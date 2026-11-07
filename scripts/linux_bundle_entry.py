#!/usr/bin/env python3
"""Open the packaged React player launcher, or check it without opening a desktop."""
import sys
sys.dont_write_bytecode = True
import argparse
import ctypes
import os
from pathlib import Path
import platform
import shutil

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from install import verify


def checks(manifest):
    rows = [('Python', sys.version_info >= (3, 11), 'Python 3.11+ with the standard library'),
            ('architecture', platform.system() == 'Linux' and platform.machine() == 'x86_64', 'Linux x86_64')]
    try:
        import ssl, sqlite3, fcntl, http.server  # noqa: F401
        rows.append(('stdlib', True, 'ssl, sqlite3, ctypes, fcntl and http.server'))
    except ImportError:
        rows.append(('stdlib', False, 'Complete Python standard library required'))
    try:
        libc = ctypes.CDLL(None)
        libc.gnu_get_libc_version.restype = ctypes.c_char_p
        current = libc.gnu_get_libc_version().decode('ascii')
        required = manifest['runtime']['glibc_minimum'] or '2.35'
        ready = tuple(map(int, current.split('.'))) >= tuple(map(int, required.split('.')))
        rows.append(('glibc', ready, f'>={required}, found {current}'))
    except (AttributeError, OSError):
        rows.append(('glibc', False, 'glibc required, musl is not supported'))
    for library in manifest['runtime']['native_libraries']:
        try:
            ctypes.CDLL(library)
            ready = True
        except OSError:
            ready = False
        rows.append((library, ready, 'System loader must resolve this library and its dependencies'))
    from scripts.linux_client import prerequisites
    rows.extend(row for row in prerequisites(ROOT / manifest['binary']) if row[0] != 'tkinter')
    rows.append(('browser', bool(shutil.which('xdg-open') or shutil.which('firefox') or shutil.which('chromium')),
                 'A default desktop browser is required'))
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='verify files and runtime prerequisites, without starting a game or display')
    args = parser.parse_args(argv)
    try:
        manifest = verify(ROOT)
        rows = [('integrity', True, 'Release checksums and modes match')] + checks(manifest)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'Release check failed: {exc}', file=sys.stderr)
        return 1
    if args.check:
        for name, ready, detail in rows:
            print(('OK ' if ready else 'MISSING ') + name + ': ' + detail)
        print('No game or display was started. Sandbox namespace policy, browser launch and DISPLAY are not tested.')
        return 0 if all(ready for _, ready, _ in rows) else 1
    if not all(ready for _, ready, _ in rows):
        print('Runtime requirements are missing. Run this entry.py with --check.', file=sys.stderr)
        return 1
    # Keep child module lookup independent of the caller's current directory.
    os.chdir(ROOT)
    from world.web_launcher import main as launch
    return launch(['--binary', str(ROOT / manifest['binary']), '--engine', manifest['engine']])


if __name__ == '__main__':
    raise SystemExit(main())
