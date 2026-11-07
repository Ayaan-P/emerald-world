#!/usr/bin/env python3
"""Install or update a trusted extracted Emerald World Linux release for one user."""
import sys
sys.dont_write_bytecode = True
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile

VERSION = re.compile(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?')
MARKER = 'X-Emerald-World-Package=1\n'


def plain(path):
    path = Path(os.path.abspath(path))
    for part in (*reversed(path.parents), path):
        if part.is_symlink():
            raise ValueError(f'Symlink path is not allowed: {part}')
        if part.exists():
            mode = part.stat().st_mode
            if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                raise ValueError(f'Special path is not allowed: {part}')
            if stat.S_ISREG(mode) and part.stat().st_nlink != 1:
                raise ValueError(f'Hardlink is not allowed: {part}')
    return path


def verify(root):
    """Verify an extracted release, never run code from it during verification."""
    root = plain(root)
    manifest_path = plain(root / 'manifest.json')
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get('format') != 1 or manifest.get('architecture') != 'x86_64'
            or not isinstance(manifest.get('version'), str)
            or not VERSION.fullmatch(manifest['version'])):
        raise ValueError('Unsupported release manifest')
    files = manifest['files']
    engine = manifest.get('engine', 'vanilla')
    binary = manifest.get('binary', 'build/pokeemerald64')
    expected_binary = {'vanilla': 'build/pokeemerald64',
                       'expansion-native': 'build/expansion-native/pokeemerald-native'}.get(engine)
    if expected_binary is None or binary != expected_binary or binary not in files:
        raise ValueError('Release engine and native binary do not match')
    manifest['engine'], manifest['binary'] = engine, binary
    for name, metadata in files.items():
        relative = PurePosixPath(name)
        if (not relative.parts or relative.is_absolute() or '..' in relative.parts
                or relative.as_posix() != name or '\\' in name
                or name == 'manifest.json'):
            raise ValueError('Unsafe manifest path')
        path = plain(root / name)
        if (not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != metadata['sha256']
                or stat.S_IMODE(path.stat().st_mode) != metadata['mode']):
            raise ValueError(f'Release integrity check failed: {name}')
    actual = set()
    for path in root.rglob('*'):
        plain(path)
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    if actual != set(files) | {'manifest.json'}:
        raise ValueError('Unexpected files in release')
    return manifest


def interpreter(path):
    # Pin a standalone/base interpreter, never the caller's development venv.
    path = Path(path).resolve(strict=True)
    probe = subprocess.run([str(path), '-I', '-c',
        'import sys,ssl,sqlite3,ctypes,fcntl,http.server; '
        'assert sys.version_info >= (3,11), "Python 3.11+ required"; '
        'assert sys.prefix == sys.base_prefix, "Use a base interpreter, not a venv"'],
        capture_output=True, text=True)
    if probe.returncode:
        raise ValueError('Select a standalone Python 3.11+ with ssl, sqlite3, ctypes and the standard library using --python')
    return path


def token(value):
    value = str(value)
    if not re.fullmatch(r'[A-Za-z0-9_./ :+\-]+', value):
        raise ValueError('Use paths containing letters, numbers, spaces or ._/:+- only')
    return '"' + value + '"'


def install(source, prefix, applications, python):
    manifest = verify(source)
    python = interpreter(python)
    prefix, applications = map(plain, (prefix, applications))
    # Source may be deleted after install. Install state must never live inside it.
    if prefix.is_relative_to(source) or source.is_relative_to(prefix):
        raise ValueError('Install prefix and extracted release must be separate')
    command = token(python) + ' -I ' + token(prefix / 'current/entry.py')
    desktop = ('[Desktop Entry]\nType=Application\nName=Emerald World\n'
               'Comment=Open Emerald World\nExec=' + command + '\n'
               'Terminal=false\nCategories=Game;\n' + MARKER)
    shortcut = plain(applications / 'emerald-world-player.desktop')
    if shortcut.exists() and MARKER not in shortcut.read_text():
        raise ValueError('Existing unowned shortcut was left unchanged')
    prefix.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = plain(prefix / '.install.lock')
    with lock.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        releases = plain(prefix / 'releases')
        releases.mkdir(exist_ok=True, mode=0o700)
        target = plain(releases / manifest['version'])
        current = prefix / 'current'
        if current.is_symlink():
            destination = current.resolve(strict=True)
            if destination.parent != releases or not destination.is_dir():
                raise ValueError('Existing current link is not a managed release')
        elif current.exists():
            raise ValueError('Existing current path is not a managed link')
        if target.exists():
            if verify(target) != manifest:
                raise ValueError('Version already installed with different contents. Use a new version.')
        else:
            with tempfile.TemporaryDirectory(prefix='.stage-', dir=prefix) as temp:
                stage = Path(temp) / 'release'
                shutil.copytree(source, stage)
                verify(stage)
                stage.rename(target)
        # Commit pointer atomically. Old releases remain available for rollback.
        with tempfile.TemporaryDirectory(prefix='.switch-', dir=prefix) as temp:
            link = Path(temp) / 'current'
            link.symlink_to(Path('releases') / manifest['version'])
            link.replace(current)
        applications.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.NamedTemporaryFile(mode='w', dir=applications, delete=False) as temp:
            pending = Path(temp.name)
            try:
                temp.write(desktop)
                temp.flush()
                os.fchmod(temp.fileno(), 0o644)
                pending.replace(shortcut)
            finally:
                pending.unlink(missing_ok=True)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='verify release and standalone Python without installing or writing files')
    parser.add_argument('--prefix', type=Path, default=Path.home() / '.local/share/emerald-world-player')
    parser.add_argument('--applications-dir', type=Path, default=Path.home() / '.local/share/applications')
    parser.add_argument('--python', type=Path, default=Path(getattr(sys, '_base_executable', sys.executable)),
                        help='Standalone Python 3.11+ used by the installed shortcut, not a venv')
    args = parser.parse_args()
    try:
        if args.check:
            verify(Path(__file__).resolve().parent)
            selected = interpreter(args.python)
            print(f'Release and standalone Python verified: {selected}. Nothing was installed.')
            return
        result = install(Path(__file__).resolve().parent, args.prefix, args.applications_dir, args.python)
        print(f'Installed {result}. Saves in ~/.local/share/emerald-world/worlds were not touched.')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'Install refused: {exc}\n')


if __name__ == '__main__':
    main()
