#!/usr/bin/env python3
"""Build the experimental React launcher and optionally add a user shortcut.

This never installs operating-system packages or builds the native game. See
INSTALL_PC.md for those prerequisites. npm ci replaces launcher-web/node_modules
using the committed lockfile; it does not modify saves or hosted-world state.
"""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def node_supported(text):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', text.strip())
    if not match:
        return False
    major, minor, _ = map(int, match.groups())
    return (major == 20 and minor >= 19) or (major == 22 and minor >= 12) or major >= 24


def check_node():
    node, npm = shutil.which('node'), shutil.which('npm')
    if not node or not npm:
        raise ValueError('Node.js and npm are required. Install Node 20.19+, 22.12+, or 24+.')
    try:
        result = subprocess.run([node, '--version'], check=True, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        raise ValueError('Could not determine the installed Node.js version.') from None
    if not node_supported(result.stdout):
        raise ValueError('Use Node 20.19+, 22.12+, or 24+ (LTS versions recommended).')
    return npm


def report_native():
    from scripts.linux_client import discover_binary, prerequisites
    checks = [(name, ready, help_text) for name, ready, help_text in prerequisites(discover_binary())
              if name != 'tkinter']
    print('\nNative game prerequisites:')
    for name, ready, help_text in checks:
        print(f'  {"OK" if ready else "NEEDED"}: {name}' + ('' if ready else f': {help_text}'))
    if not all(ready for _, ready, _ in checks):
        print('Follow INSTALL_PC.md to build the game and install missing system prerequisites.')
    else:
        print('Basic checks passed; a graphical desktop and actual game launch still need verification.')
    return all(ready for _, ready, _ in checks)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='check prerequisites without building or installing')
    parser.add_argument('--install-shortcut', action='store_true', help='after building, add a separate user application shortcut')
    args = parser.parse_args(argv)
    if args.check and args.install_shortcut:
        parser.error('--check cannot install a shortcut')
    if sys.platform != 'linux':
        parser.exit(1, 'This experimental launcher setup currently supports Linux only.\n')
    try:
        npm = check_node()
        print('Node.js and npm: OK')
        if args.check:
            return 0 if report_native() else 1
        project = REPO / 'launcher-web'
        if not (project / 'package-lock.json').is_file():
            raise ValueError('The launcher lockfile is missing. Use a complete project checkout.')
        print('Installing locked launcher dependencies (replaces launcher-web/node_modules)…', flush=True)
        subprocess.run([npm, 'ci', '--no-audit', '--no-fund'], cwd=project, check=True)
        print('Building the launcher…', flush=True)
        subprocess.run([npm, 'run', 'build'], cwd=project, check=True)
        if not (project / 'dist/index.html').is_file():
            raise ValueError('The launcher build did not produce its entry point.')
        if args.install_shortcut:
            from world.web_launcher import install_shortcut
            install_shortcut()
            print('Added the separate experimental launcher shortcut for this user.')
        print('\nLauncher built. Start it with: python3 -m world.web_launcher')
        report_native()
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        # Fixed wording for subprocess errors; never print process environment.
        detail = str(exc) if isinstance(exc, ValueError) else 'A launcher setup command failed.'
        parser.exit(1, detail + '\n')


if __name__ == '__main__':
    sys.exit(main())
