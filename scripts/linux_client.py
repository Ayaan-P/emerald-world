#!/usr/bin/env python3
"""Launch the existing isolated Linux desktop UI from a source checkout."""
import argparse
import ctypes
import os
from pathlib import Path
import shutil
import sys

REPO = Path(__file__).resolve().parents[1]


def discover_binary():
    """Only inspect the two documented checkout locations, in priority order."""
    for path in (REPO / 'build/pokeemerald64', REPO / 'pokeemerald64'):
        if path.exists() or path.is_symlink():
            return path
    return REPO / 'build/pokeemerald64'


def discover_display(directory=Path('/tmp')):
    for number in range(90, 200):
        if (not os.path.lexists(directory / '.X11-unix' / ('X' + str(number)))
                and not os.path.lexists(directory / ('.X' + str(number) + '-lock'))):
            return ':' + str(number)
    raise ValueError('No free dedicated game display. Close an unused game session first.')


def binary_ready(path):
    try:
        if not path.is_file() or not os.access(path, os.R_OK | os.X_OK):
            return False
        with path.open('rb') as stream:
            return stream.read(4) == b'\x7fELF'
    except OSError:
        return False


def prerequisites(binary):
    try:
        import tkinter  # noqa: F401. Import only, never create a window here.
        tkinter_ok = True
    except ImportError:
        tkinter_ok = False
    sdl_ok = False
    for name in ('libSDL2-2.0.so.0', 'libSDL2.so'):
        try:
            ctypes.CDLL(name)
            sdl_ok = True
            break
        except OSError:
            pass
    return [
        ('tkinter', tkinter_ok, 'Python must provide tkinter for the desktop UI.'),
        ('bwrap', bool(shutil.which('bwrap')), 'Bubblewrap must be executable on PATH.'),
        ('Xephyr', bool(shutil.which('Xephyr')), 'Xephyr must be executable on PATH.'),
        ('binary', binary_ready(binary), 'A readable, executable native ELF is required at build/pokeemerald64 or pokeemerald64.'),
        ('SDL2', sdl_ok, 'The system loader must provide the SDL2 runtime library.'),
    ]


def exec_token(value):
    """Quote a desktop Exec token, rejecting field codes and escape syntax."""
    import re
    value = str(value)
    if not value or not re.fullmatch(r'[A-Za-z0-9_./ :+\-]+', value):
        raise ValueError('Launcher paths contain unsupported characters. Use a checkout and interpreter path with plain letters, digits, spaces or ._/:+- characters.')
    return '"' + value + '"'


def install_user():
    import stat
    interpreter = Path(sys.executable).resolve()
    if not interpreter.is_file() or not os.access(interpreter, os.X_OK):
        raise ValueError('The current Python interpreter is not executable.')
    command = exec_token(interpreter) + ' ' + exec_token(Path(__file__).resolve())
    content = ('[Desktop Entry]\nType=Application\nName=Emerald World\n'
               'Comment=Open the Emerald World desktop client\n'
               'Exec=' + command + '\nTerminal=false\nCategories=Game;\n'
               'X-Emerald-World-Launcher=linux-client-v1\n')
    directory = Path.home() / '.local/share/applications'
    if not directory.is_absolute() or directory.resolve() != directory:
        raise ValueError('Launcher directory must be an absolute path without symlinks.')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = directory / 'emerald-world.desktop'
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    except FileExistsError:
        # Never replace even our own changed launcher. Identical installation is a no-op.
        fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stream.read(len(content.encode()) + 1) != content.encode()):
                raise ValueError('An existing launcher was left unchanged. Remove or rename it explicitly before installing.')
    else:
        with os.fdopen(fd, 'w') as stream:
            stream.write(content)
    print('User launcher installed. Keep this checkout and Python interpreter in place.')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='check prerequisites without opening a window or writing state')
    mode.add_argument('--install-user', action='store_true', help='install a menu entry pointing to this checkout, without copying a game binary')
    parser.add_argument('--invitation', type=Path, help='prefill a trusted friend invitation without connecting')
    args = parser.parse_args(argv)
    if args.invitation and args.install_user:
        parser.error('--invitation cannot be combined with --install-user')
    if args.invitation:
        sys.path.insert(0, str(REPO))
        from world.transport import read_invitation
        try:
            read_invitation(args.invitation)
        except (OSError, ValueError):
            print('Invalid friend invitation. No connection was started.', file=sys.stderr)
            return 1
    if args.install_user:
        try:
            return install_user()
        except (OSError, ValueError) as exc:
            print(str(exc) if isinstance(exc, ValueError) else 'Could not install the user launcher. Check the destination ownership and permissions.', file=sys.stderr)
            return 1
    binary = discover_binary()
    checks = prerequisites(binary)
    if args.check:
        for name, ready, detail in checks:
            print(('OK ' if ready else 'MISSING ') + name + ': ' + detail)
        print('No game or display was started. Runtime sandbox policy and desktop DISPLAY are not tested.')
        return 0 if all(ready for _, ready, _ in checks) else 1
    if not all(ready for _, ready, _ in checks):
        print('Prerequisites are missing. Run this script with --check.', file=sys.stderr)
        return 1
    sys.path.insert(0, str(REPO))
    from world import session
    original_app = session.DesktopApp
    if args.invitation:
        # run_desktop owns UI and session cleanup. Adapt only construction so its
        # existing validated import action runs before mainloop, without connecting.
        class InvitedDesktopApp(original_app):
            def __init__(self, *app_args, **app_kwargs):
                super().__init__(*app_args, **app_kwargs)
                try:
                    self.import_friend_invitation(args.invitation)
                except (OSError, ValueError):
                    # The file may change after preflight. Keep the constructed
                    # app alive so run_desktop still owns its normal cleanup.
                    self.message.set('Invalid friend invitation. No connection settings were changed.')
        session.DesktopApp = InvitedDesktopApp
    try:
        return session.run_desktop(Path.home() / '.local/share/emerald-world/worlds', binary=binary, display=discover_display())
    except (OSError, ValueError):
        print('Could not open Emerald World. Check desktop DISPLAY and the user-local worlds path. Run --check for prerequisites.', file=sys.stderr)
        return 1
    finally:
        session.DesktopApp = original_app


if __name__ == '__main__':
    raise SystemExit(main())
