#!/usr/bin/env python3
"""Build the pinned native Expansion engine with Emerald World's presence seam.

No dependency downloads or installs. Optional --sysroot uses an already extracted
SDL2/libpng development tree. Only this checkout is writable in the sandbox.
"""
import argparse
import shlex
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PIN = 'bb3fd057061cdd7e6a9e79b76abb41924ee44ecc'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sysroot', type=Path)
    parser.add_argument('--multilib-sysroot', '--multilib-root', type=Path,
                        help='existing extracted libc and GCC multilib root for the donor ABI probe')
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    source = ROOT / 'engines/expansion-native'
    head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if head != PIN or subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True).strip():
        parser.error('initialize the clean pinned submodule with git submodule update --init engines/expansion-native')
    if not shutil.which('bwrap'):
        parser.error('Bubblewrap is required to isolate the build')
    cmd = ['bwrap', '--unshare-all', '--die-with-parent', '--new-session', '--cap-drop', 'ALL', '--clearenv']
    for directory in ('/usr', '/lib', '/lib64'):
        cmd += ['--ro-bind', directory, directory]
    cmd += ['--ro-bind', '/etc/alternatives', '/etc/alternatives']
    cmd += ['--symlink', 'usr/bin', '/bin', '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
            '--dir', '/home/sandbox', '--bind', str(ROOT), str(ROOT),
            '--ro-bind', str(ROOT / '.git'), str(ROOT / '.git'), '--chdir', str(source)]
    env = dict(CC='gcc', CXX='g++', HOME='/home/sandbox', PATH='/usr/bin:/bin', LANG='C.UTF-8', LC_ALL='C.UTF-8',
               TZ='UTC', GITHUB_ACTION='1', PYTHONDONTWRITEBYTECODE='1')
    if args.sysroot:
        sysroot = args.sysroot.resolve(strict=True)
        cmd += ['--ro-bind', str(sysroot), str(sysroot)]
        env.update(C_INCLUDE_PATH=f'{sysroot}/usr/include:{sysroot}/usr/include/x86_64-linux-gnu',
                   LIBRARY_PATH=f'{sysroot}/usr/lib/x86_64-linux-gnu',
                   PKG_CONFIG_LIBDIR=f'{sysroot}/usr/lib/x86_64-linux-gnu/pkgconfig',
                   PKG_CONFIG_SYSROOT_DIR=str(sysroot))
    compiler = 'gcc'
    if args.multilib_sysroot:
        multilib = args.multilib_sysroot.resolve(strict=True)
        gcc_dirs = sorted((multilib / 'usr/lib/gcc/x86_64-linux-gnu').glob('*/32'))
        if not gcc_dirs:
            parser.error('multilib sysroot lacks GCC 32-bit startup files')
        cmd += ['--ro-bind', str(multilib), str(multilib),
                '--ro-bind', str(multilib / 'lib32'), '/lib32',
                '--ro-bind', str(multilib / 'lib32/ld-linux.so.2'), '/lib/ld-linux.so.2']
        compiler = f'gcc --sysroot={shlex.quote(str(multilib))} -B{shlex.quote(str(gcc_dirs[-1].parent) + "/")}'
        env['C_INCLUDE_PATH'] = ':'.join((str(multilib / 'usr/include'),
                                         str(multilib / 'usr/include/x86_64-linux-gnu'),
                                         env.get('C_INCLUDE_PATH', '/usr/include'), '/usr/include'))
    for key, value in env.items():
        cmd += ['--setenv', key, value]
    cmd += ['--', 'make', '-f', '../expansion.mk', f'-j{args.jobs}', 'native', 'BITS=64',
            f'TARGET_CC={compiler}', f'NATIVE_VERSION={PIN[:12]}-emerald-world']
    result = subprocess.run(cmd)
    if result.returncode == 0:
        destination = ROOT / 'build/expansion-native'
        destination.mkdir(parents=True, exist_ok=True)
        binary = source / 'build/native64/pokeemerald-native'
        shutil.copy2(binary, destination / 'pokeemerald-native')
        shutil.copy2(str(binary)+'.symbols', destination / 'pokeemerald-native.symbols')
        print(f'Built {destination / "pokeemerald-native"}')
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
