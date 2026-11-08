#!/usr/bin/env python3
"""Build RC10's pinned full native Expansion engine with its presence adapter.

Only existing development/sysroot inputs are used. No installs or downloads.
The engine is a separate checkout and no vanilla Pokemon/save ABI is imported.
"""
import argparse
from pathlib import Path
import shlex
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PIN = '89cff0d3ca70747c865def7e77a9941b42c9eff5'
UPSTREAM_PIN = '79dd436920845ebc145577649de624f65298c209'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sysroot', type=Path)
    parser.add_argument('--multilib-sysroot', '--multilib-root', type=Path,
                        help='existing extracted libc/GCC multilib root for mandatory ABI probes')
    parser.add_argument('--development', action='store_true',
                        help='build explicit local RC10 integration changes on top of the verified engine pin')
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    source = ROOT / 'engines/expansion-native'
    import sys
    sys.path.insert(0, str(ROOT))
    from scripts.export_expansion_species_catalogue import export_catalogue
    catalogue_path = ROOT / 'build/species-cohort/expansion-species.json'
    export_catalogue(source, catalogue_path)
    shutil.copy2(catalogue_path, ROOT / 'world/expansion_species.json')
    head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True).strip()
    if not args.development and (head != PIN or dirty):
        parser.error('engine must be the clean pinned engines/expansion-native submodule')
    subprocess.run(['git', '-C', str(source), 'merge-base', '--is-ancestor', PIN, head], check=True)
    if dirty:
        print('Building explicitly requested uncommitted integration sources; not a release artifact.', flush=True)
    subprocess.run(['git', '-C', str(source), 'merge-base', '--is-ancestor', UPSTREAM_PIN, PIN], check=True)
    if not shutil.which('bwrap'):
        parser.error('Bubblewrap is required to isolate the build')
    command = ['bwrap', '--unshare-all', '--die-with-parent', '--new-session',
               '--cap-drop', 'ALL', '--clearenv']
    for directory in ('/usr', '/lib', '/lib64'):
        command += ['--ro-bind', directory, directory]
    command += ['--ro-bind', '/etc/alternatives', '/etc/alternatives',
                '--symlink', 'usr/bin', '/bin', '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
                '--dir', '/home/sandbox', '--bind', str(ROOT), str(ROOT),
                '--ro-bind', str(ROOT / '.git'), str(ROOT / '.git'), '--chdir', str(source)]
    env = dict(CC='gcc', CXX='g++', HOME='/home/sandbox', PATH='/usr/bin:/bin',
               LANG='C.UTF-8', LC_ALL='C.UTF-8', TZ='UTC', GITHUB_ACTION='1',
               PYTHONDONTWRITEBYTECODE='1')
    if args.sysroot:
        sysroot = args.sysroot.resolve(strict=True)
        command += ['--ro-bind', str(sysroot), str(sysroot)]
        env.update(C_INCLUDE_PATH=f'{sysroot}/usr/include:{sysroot}/usr/include/x86_64-linux-gnu:/usr/include/x86_64-linux-gnu:/usr/include',
                   LIBRARY_PATH=f'{sysroot}/usr/lib/x86_64-linux-gnu',
                   PKG_CONFIG_LIBDIR=f'{sysroot}/usr/lib/x86_64-linux-gnu/pkgconfig',
                   PKG_CONFIG_SYSROOT_DIR=str(sysroot))
    compiler = 'gcc'
    if args.multilib_sysroot:
        multilib = args.multilib_sysroot.resolve(strict=True)
        gcc_dirs = sorted((multilib / 'usr/lib/gcc/x86_64-linux-gnu').glob('*/32'))
        if not gcc_dirs:
            parser.error('multilib sysroot lacks GCC 32-bit startup files')
        command += ['--ro-bind', str(multilib), str(multilib),
                    '--ro-bind', str(multilib / 'lib32'), '/lib32',
                    '--ro-bind', str(multilib / 'lib32/ld-linux.so.2'), '/lib/ld-linux.so.2']
        compiler = f'gcc --sysroot={shlex.quote(str(multilib))} -B{shlex.quote(str(gcc_dirs[-1].parent) + "/")}'
        env['C_INCLUDE_PATH'] = ':'.join((str(multilib / 'usr/include'),
                                         str(multilib / 'usr/include/x86_64-linux-gnu'),
                                         env.get('C_INCLUDE_PATH', '/usr/include/x86_64-linux-gnu:/usr/include')))
    for key, value in env.items():
        command += ['--setenv', key, value]
    command += ['--', 'make', '-f', str(ROOT / 'engines/expansion.mk'), f'-j{args.jobs}',
                'native', 'BITS=64', f'TARGET_CC={compiler}', f'NATIVE_VERSION={PIN[:12]}-rc10',
                'build/native64/data_relocations.checked', 'build/native64/data_layout.checked',
                'build/native64/battle_script_operands.checked']
    print(shlex.join(command), flush=True)
    # Makefile.native marks intermediates secondary. A formerly linked binary
    # must not hide newly added world objects just because those objects are absent.
    (source / 'build/native64/pokeemerald-native').unlink(missing_ok=True)
    # Pointer4 reference objects encode CPPFLAGS (including the RC10 script
    # cohort) in their assembled contents, but make cannot see flag changes as
    # prerequisites. Recreate only this generated reference tree each build so
    # relocation/layout comparisons always use the current feature cohort.
    shutil.rmtree(source / 'build/native64/pointer4', ignore_errors=True)
    (source / 'build/native64/pointer4.built').unlink(missing_ok=True)
    result = subprocess.run(command)
    if result.returncode:
        return result.returncode
    destination = ROOT / 'build/expansion-native'
    destination.mkdir(parents=True, exist_ok=True)
    binary = source / 'build/native64/pokeemerald-native'
    for name in ('pokeemerald-native', 'pokeemerald-native.symbols'):
        shutil.copy2(binary.parent / name, destination / name)
    print(f'Built {destination / binary.name}', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
