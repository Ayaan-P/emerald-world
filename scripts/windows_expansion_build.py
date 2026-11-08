#!/usr/bin/env python3
"""Build the pinned Expansion Windows PE on Linux using existing tools only.

No tool/SDK installation, downloads, remote execution, or artifact uploads.
Uses a dedicated clean engine checkout, never a shared parent's build tree.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

from windows_expansion_package import (FLAGS, check_pe, git, plain_path,
                                       sha256, verify_checkout)

TOOLS = ('gcc', 'g++', 'clang', 'make', 'git', 'pkg-config', 'as', 'objcopy', 'nm',
         'bwrap', 'x86_64-w64-mingw32-gcc', 'x86_64-w64-mingw32-as',
         'x86_64-w64-mingw32-ar', 'x86_64-w64-mingw32-nm',
         'x86_64-w64-mingw32-objcopy', 'x86_64-w64-mingw32-objdump',
         'x86_64-w64-mingw32-windres')


def wrapper_text(app):
    # Avoid Makefile.native's second native invocation, which would bypass the
    # app integration. Both passes explicitly use this wrapper instead.
    return (f'include {app}/engines/expansion.mk\n'
            'EW_LINUX_RPATH := -Wl,-rpath-link,/usr/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu/pulseaudio\n'
            'ifeq ($(TARGET_OS),windows)\n'
            'NATIVE_LDFLAGS := $(filter-out $(EW_LINUX_RPATH),$(NATIVE_LDFLAGS))\n'
            'NATIVE_LDLIBS += -lws2_32\n'
            'endif\n')


def preflight(app, app_pin, engine_pin):
    if platform.system() != 'Linux' or platform.machine().lower() not in ('x86_64', 'amd64'):
        raise ValueError('Supported builder is Linux x86_64 with MinGW-w64, not native Windows/MSVC or macOS')
    missing = [name for name in TOOLS if not shutil.which(name)]
    if missing:
        raise ValueError('Missing existing build tools: ' + ', '.join(missing))
    app = plain_path(app)
    if any(c in str(app) for c in ' \t\n#$'):
        raise ValueError('Build checkout path cannot contain Make metacharacters or whitespace')
    engine = plain_path(app/'engines/expansion-native')
    if not (engine/'Makefile.native').is_file():
        raise ValueError('Initialize the pinned Expansion submodule separately; this script never fetches sources')
    verify_checkout(app, app_pin)
    verify_checkout(engine, engine_pin)
    if not git(app, 'ls-tree', app_pin, 'engines/expansion-native').decode().startswith('160000 commit '+engine_pin+'\t'):
        raise ValueError('App gitlink must pin the selected engine before building')
    sdk = engine/'build/sdl2-mingw'
    required = ['SDL2-devel-2.30.12-mingw.tar.gz.unpacked',
                'x86_64-w64-mingw32/include/SDL2/SDL.h',
                'x86_64-w64-mingw32/lib/libSDL2.dll.a',
                'x86_64-w64-mingw32/bin/SDL2.dll']
    for name in required:
        if not plain_path(sdk/name).is_file():
            raise ValueError('Missing existing SDL2 2.30.12 MinGW SDK input: '+name+'; no automatic download is permitted')
    check_pe((sdk/required[-1]).read_bytes(), dll=True)
    for package in ('sdl2', 'libpng'):
        if subprocess.run(['pkg-config', '--exists', package]).returncode:
            raise ValueError('Missing existing host development package: '+package)
    return engine, sdk


def sandbox(engine, multilib=None):
    # No network and no inherited credential environment. Only the dedicated
    # engine checkout is writable. Build tools and app sources are read-only.
    mounts = []
    if multilib is not None:
        multilib = plain_path(multilib)
        mounts = ['--ro-bind', str(multilib/'lib32'), '/lib32',
                  '--ro-bind', str(multilib/'lib32/ld-linux.so.2'), '/lib/ld-linux.so.2']
    return ['bwrap', '--unshare-net', '--die-with-parent', '--new-session',
            '--ro-bind', '/', '/', *mounts, '--bind', str(engine), str(engine),
            '--tmpfs', '/tmp', '--dir', '/tmp/expansion-build-home',
            '--dev', '/dev', '--proc', '/proc', '--clearenv',
            '--setenv', 'PATH', os.environ.get('PATH', '/usr/bin:/bin'),
            '--setenv', 'HOME', '/tmp/expansion-build-home',
            '--setenv', 'LANG', 'C.UTF-8', '--setenv', 'LC_ALL', 'C.UTF-8',
            '--setenv', 'TZ', 'UTC', '--chdir', str(engine), '--']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--app-pin', required=True)
    parser.add_argument('--engine-pin', required=True)
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--multilib-sysroot', type=Path, help='existing private multilib loader root; compiler wrappers on PATH must use it')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.jobs < 1:
            raise ValueError('--jobs must be positive')
        app = plain_path(args.app)
        engine, sdk = preflight(app, args.app_pin, args.engine_pin)
        isolated = sandbox(engine, args.multilib_sysroot)
        subprocess.run(isolated + ['true'], check=True)
        # The data checks run a 32-bit reference program even for a 64-bit PE.
        subprocess.run(isolated + ['bash', '-c',
            'printf "int main(void){return 0;}" | gcc -m32 -x c - -o /tmp/abi32 && /tmp/abi32'], check=True)
        if args.check:
            print(json.dumps({'preflight': 'passed', 'target': 'Expansion Windows x64', 'downloaded': False}))
            return 0
        # Refuse unknown/stale object cohorts rather than relabeling cached
        # binaries or deleting someone else's engine build output.
        for name in ('build/native64', 'build/native64-windows', 'platform/build/64-windows',
                     'platform/build/64-nosan', 'platform/m4a/build/64', 'platform/m4a/build/64-windows'):
            if (engine/name).exists():
                raise ValueError('Fresh dedicated engine object tree required; existing '+name)
        build = engine/'build'
        build.mkdir(exist_ok=True)
        wrapper = plain_path(build/'windows-expansion-wrapper.mk')
        text = wrapper_text(app)
        wrapper.write_text(text, encoding='utf-8')
        common = ['make', '-f', str(wrapper), '-j'+str(args.jobs),
                  *[k+'='+v for k, v in FLAGS.items() if k != 'TARGET_OS'],
                  'SANITIZE=0', 'TEST=0', 'NATIVE_VERSION='+args.engine_pin[:12]+'-rc12-windows']
        # First pass retains the matching cohort for ELF/data validation and
        # conversion. Second pass never re-enters the donor's unwrapped make.
        commands = [common + ['check-flat', 'TARGET=coff-x86_64', 'TARGET_OS=Linux'],
                    common + ['native', 'TARGET_OS=windows', 'WINDOWS_DATA_CHECKED=1',
                              '-o', 'build/sdl2-mingw/SDL2-devel-2.30.12-mingw.tar.gz.unpacked']]
        for command in commands:
            subprocess.run(isolated + command, check=True)
        binary = engine/'build/native64-windows/pokeemerald-native.exe'
        data = plain_path(binary).read_bytes()
        check_pe(data)
        verify_checkout(app, args.app_pin)
        verify_checkout(engine, args.engine_pin)
        tools = {name: {'path': shutil.which(name), 'version': subprocess.check_output(
                    [name, '--version'], text=True, stderr=subprocess.STDOUT).splitlines()[0]} for name in TOOLS}
        from windows_expansion_package import pinned_sources
        catalogue = engine/'build/windows-expansion-species.json'
        subprocess.run(isolated + ['python3', str(app/'scripts/export_expansion_species_catalogue.py'),
                                  str(engine), str(catalogue)], check=True)
        expected_catalogue = git(app, 'show', args.app_pin+':world/expansion_species.json')
        if catalogue.read_bytes() != expected_catalogue:
            raise ValueError('Pinned app species catalogue differs from selected engine. Regenerate and commit the app cohort before rebuilding')
        source_hashes = {name: sha256(data) for name, data in pinned_sources(app, args.app_pin).items()}
        receipt = {'schema': 1, 'engine': 'expansion-native', 'app_commit': args.app_pin,
                   'engine_commit': args.engine_pin, 'flags': FLAGS, 'command': commands,
                   'tools': tools, 'binary_sha256': sha256(data), 'source_sha256': source_hashes,
                   'catalogue_sha256': sha256(expected_catalogue),
                   'integration_sha256': sha256(git(app, 'show', args.app_pin+':engines/expansion.mk')),
                   'wrapper': text, 'wrapper_sha256': sha256(text.encode()),
                   'sdk_files': {p.relative_to(sdk).as_posix(): sha256(p.read_bytes())
                                 for p in sdk.rglob('*') if p.is_file()},
                   'windows_device_accepted': False}
        destination = plain_path(binary.with_name('windows-expansion-build.json'))
        destination.write_text(json.dumps(receipt, indent=2, sort_keys=True)+'\n', encoding='utf-8')
        print(json.dumps({'binary_sha256': sha256(data), 'receipt': str(destination),
                          'windows_device_accepted': False}))
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(2, 'Expansion Windows build unavailable: '+str(exc)+
                    '\nNothing was installed or downloaded. No binary was packaged or uploaded.\n')


if __name__ == '__main__':
    raise SystemExit(main())
