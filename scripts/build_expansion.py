#!/usr/bin/env python3
"""Build the candidate's pinned full native Expansion engine with its presence adapter.

Only existing development/sysroot inputs are used. No installs or downloads.
The engine is a separate checkout and no vanilla Pokemon/save ABI is imported.
"""
import argparse
from pathlib import Path
import shlex
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PIN = '511e4e8e7382f8868ae567653139f1ca0e298f61'
UPSTREAM_PIN = '79dd436920845ebc145577649de624f65298c209'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true',
                        help='check the pin and sandboxed toolchain without building or changing source files')
    parser.add_argument('--sysroot', type=Path)
    parser.add_argument('--multilib-sysroot', '--multilib-root', type=Path,
                        help='existing extracted libc/GCC multilib root for mandatory ABI probes')
    parser.add_argument('--development', action='store_true',
                        help='build explicit local candidate integration changes on top of the verified engine pin')
    parser.add_argument('--experimental-tower-records', action='store_true', help='enable experimental explicit Tower record imports; requires --development')
    parser.add_argument('--experimental-starter-offers', action='store_true', help='enable experimental optional fresh-save starters; requires --development')
    parser.add_argument('--experimental-field-moves', action='store_true', help='enable learned moves on shared props; requires --development')
    parser.add_argument('--experimental-floorplans', action='store_true', help='enable opt-in native owned-furniture guidance; requires --development')
    parser.add_argument('--experimental-native-trades', action='store_true', help='enable local opt-in authored trade templates; requires --development')
    parser.add_argument('--experimental-nature-challenges', action='store_true', help='enable local opt-in nature-driven NPC singles; requires --development')
    parser.add_argument('--experimental-party-practice', action='store_true', help='enable local native egg-move practice; requires --development')
    parser.add_argument('--experimental-maze-courses', action='store_true', help='enable experimental generated Trainer Hill mazes; requires --development')
    parser.add_argument('--experimental-pyramid-courses', action='store_true', help='enable experimental authored Pyramid courses; requires --development')
    parser.add_argument('--experimental-secret-bases', action='store_true', help='enable unverified own-base sharing; requires --development')
    parser.add_argument('--experimental-npc-coop', action='store_true',
                        help='enable unverified dynamic NPC co-op wire (requires --development; both clients must match)')
    parser.add_argument('--generated-regions', action='store_true',
                        help='enable selectable generated places (independent of regional saves/Kanto)')
    parser.add_argument('--regional-state', action='store_true',
                        help='enable experimental regional saves (requires --development)')
    parser.add_argument('--experimental-regional-starters', action='store_true', help='enable experimental isolated Kanto starter choices; requires existing regional readers; linked QA pending')
    parser.add_argument('--experimental-kanto-rematches', action='store_true', help='enable experimental separate Kanto rematches; requires custody/completion readers; linked QA pending')
    parser.add_argument('--experimental-route5-custody', action='store_true', help='enable experimental separate Route 5 daycare; requires regional completion migration; linked QA pending')
    parser.add_argument('--experimental-regional-completion', action='store_true', help='enable explicit regional championship migration; requires experimental regional badges; linked QA pending')
    parser.add_argument('--experimental-regional-badges', action='store_true', help='enable explicit personal regional badge migration; requires --kanto-content')
    parser.add_argument('--experimental-combined-presence', action='store_true', help='negotiate the fixed combined-world authority profile; requires --kanto-content')
    parser.add_argument('--kanto-content', action='store_true',
                        help='enable combined Hoenn/Kanto content (requires --regional-state)')
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    if args.experimental_field_moves and not args.development:
        parser.error('--experimental-field-moves requires --development; native object UI QA pending')
    if args.experimental_party_practice and not args.development:
        parser.error('--experimental-party-practice requires --development; native UI/save QA pending')
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    if args.experimental_tower_records and not args.development:
        parser.error('--experimental-tower-records requires --development; native save/appearance QA pending')
    if args.experimental_floorplans and not args.development:
        parser.error('--experimental-floorplans requires --development; native decoration QA pending')
    if args.experimental_native_trades and not args.development:
        parser.error('--experimental-native-trades requires --development; native trade QA pending')
    if args.experimental_nature_challenges and not args.development:
        parser.error('--experimental-nature-challenges requires --development; linked battle QA pending')
    if args.experimental_starter_offers and not args.development:
        parser.error('--experimental-starter-offers requires --development; intro/save QA pending')
    if args.experimental_maze_courses and not args.development:
        parser.error('--experimental-maze-courses requires --development; native layout/save QA pending')
    if args.experimental_pyramid_courses and not args.development:
        parser.error('--experimental-pyramid-courses requires --development; linked suspend/save QA pending')
    if args.experimental_secret_bases and not args.development:
        parser.error('--experimental-secret-bases requires --development; linked save QA pending')
    if args.experimental_npc_coop and not args.development:
        parser.error('--experimental-npc-coop requires --development; linked two-client QA pending')
    if args.regional_state and not args.development:
        parser.error('--regional-state requires --development and is not a release cohort')
    if args.experimental_regional_starters and not args.experimental_kanto_rematches:
        parser.error('--experimental-regional-starters requires --experimental-kanto-rematches and all regional reader prerequisites')
    if args.experimental_kanto_rematches and not args.experimental_route5_custody:
        parser.error('--experimental-kanto-rematches requires --experimental-route5-custody and regional completion prerequisites')
    if args.experimental_route5_custody and not args.experimental_regional_completion:
        parser.error('--experimental-route5-custody requires --experimental-regional-completion and its development prerequisites')
    if args.experimental_regional_completion and not args.experimental_regional_badges:
        parser.error('--experimental-regional-completion requires --experimental-regional-badges and its development prerequisites')
    if args.experimental_regional_badges and not args.kanto_content:
        parser.error('--experimental-regional-badges requires --kanto-content, --regional-state and --development')
    if args.experimental_combined_presence and not args.kanto_content:
        parser.error('--experimental-combined-presence requires --kanto-content, --regional-state and --development')
    if args.kanto_content and not args.regional_state:
        parser.error('--kanto-content requires --regional-state')
    for flag, path in (('--sysroot', args.sysroot), ('--multilib-sysroot', args.multilib_sysroot)):
        if path is not None and not path.is_dir():
            parser.error(f'{flag} must name an existing directory: {path}')
    source = ROOT / 'engines/expansion-native'
    if not (source / 'Makefile.native').is_file() or not (source / '.git').exists():
        parser.error('Expansion engine is not initialized. From the checkout root run: '
                     'git submodule sync --recursive && git submodule update --init --recursive')
    head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True).strip()
    if not args.development and (head != PIN or dirty):
        parser.error(f'engine must be the clean engines/expansion-native submodule at {PIN}. '
                     'Preserve any local engine changes, then run: '
                     'git submodule sync --recursive && git submodule update --init --recursive. '
                     'Use --development only for deliberate local engine integration work.')
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
                   PKG_CONFIG_LIBDIR=f'{sysroot}/usr/lib/x86_64-linux-gnu/pkgconfig:/usr/lib/x86_64-linux-gnu/pkgconfig:/usr/share/pkgconfig',
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
    # Probe inside the same sandbox and sysroots as make. In particular, the
    # mandatory layout checks compile AND run a 32-bit reference executable.
    probe = r'''
import shlex, shutil, subprocess, sys
missing = []
for tool in ('gcc', 'g++', 'make', 'git', 'pkg-config', 'as', 'objcopy', 'nm'):
    if not shutil.which(tool):
        missing.append(tool + ' (build-essential, binutils, git, pkg-config)')
if shutil.which('pkg-config'):
    for package, hint in (('sdl2', 'libsdl2-dev'), ('libpng', 'libpng-dev')):
        if subprocess.run(['pkg-config', '--exists', package]).returncode:
            missing.append(package + ' headers/libraries (' + hint + ')')
if shutil.which('gcc'):
    for bits in ('32', '64'):
        output = '/tmp/ew-abi' + bits
        result = subprocess.run(shlex.split(sys.argv[1]) + ['-m' + bits, '-x', 'c', '-o', output, '-'],
                                input='#include <stdio.h>\nint main(void) { return 0; }\n',
                                text=True, capture_output=True)
        try:
            ready = result.returncode == 0 and subprocess.run([output], capture_output=True).returncode == 0
        except OSError:
            ready = False
        if not ready:
            missing.append(bits + '-bit C compile/run ABI probe (gcc-multilib, libc6-dev-i386 for 32-bit; or --multilib-sysroot)')
if missing:
    print('Missing build prerequisites. See INSTALL_PC.md. Nothing was installed.', file=sys.stderr)
    for item in missing:
        print('  ' + item, file=sys.stderr)
    sys.exit(1)
print('OK pinned Expansion engine and sandboxed native toolchain (including 32-bit ABI probe).')
'''
    result = subprocess.run(command + ['--', 'python3', '-c', probe, compiler])
    if result.returncode:
        parser.error('Build preflight failed. Resolve the missing prerequisites above. '
                     'If Bubblewrap failed, check that unprivileged user namespaces are permitted.')
    if args.check:
        return 0
    # Feature CPPFLAGS are not represented in native object prerequisites. Rebuild
    # intermediates so toggling selectable regions cannot reuse a stale cohort.
    command += ['--', 'make', '-B', '-f', str(ROOT / 'engines/expansion.mk'), f'-j{args.jobs}',
                f'GENERATED_WORLD_REGIONS={int(args.generated_regions)}',
                f'WORLD_NATURE_CHALLENGES={int(args.experimental_nature_challenges)}',
                f'WORLD_TRADE_OFFERS={int(args.experimental_native_trades)}',
                f'WORLD_COMBINED_PRESENCE={int(args.experimental_combined_presence)}',
                f'WORLD_FLOORPLANS={int(args.experimental_floorplans)}',
                f'WORLD_CHARACTER_COOP_EXPERIMENT={int(args.experimental_npc_coop)}',
                f'WORLD_BASE_SHARE_EXPERIMENT={int(args.experimental_secret_bases)}',
                f'WORLD_TOWER_RECORD_EXPERIMENT={int(args.experimental_tower_records)}',
                f'WORLD_STARTER_OFFER_EXPERIMENT={int(args.experimental_starter_offers)}',
                f'WORLD_FIELD_MOVES_EXPERIMENT={int(args.experimental_field_moves)}',
                f'WORLD_PARTY_PRACTICE_EXPERIMENT={int(args.experimental_party_practice)}',
                f'WORLD_MAZE_COURSE_EXPERIMENT={int(args.experimental_maze_courses)}',
                f'WORLD_PYRAMID_COURSES_EXPERIMENT={int(args.experimental_pyramid_courses)}',
                f'EW_REGIONAL_BADGES={int(args.experimental_regional_badges)}',
                f'EW_REGIONAL_STARTERS={int(args.experimental_regional_starters)}',
                f'EW_KANTO_REMATCHES={int(args.experimental_kanto_rematches)}',
                f'EW_ROUTE5_CUSTODY={int(args.experimental_route5_custody)}',
                f'EW_REGIONAL_COMPLETION={int(args.experimental_regional_completion)}',
                f'EW_REGION_STATE={int(args.regional_state)}',
                f'EW_KANTO_CONTENT={int(args.kanto_content)}',
                *(['MAP_VERSION=combined'] if args.kanto_content else []),
                'native', 'BITS=64', f'TARGET_CC={compiler}', f'NATIVE_VERSION={PIN[:12]}-rc12-candidate',
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
    # Make generates headers such as map_groups.h needed by global.h. A fresh
    # clone cannot preprocess species metadata before that generation step.
    import sys
    sys.path.insert(0, str(ROOT))
    from scripts.export_expansion_species_catalogue import export_catalogue
    catalogue_path = ROOT / 'build/species-cohort/expansion-species.json'
    export_catalogue(source, catalogue_path)
    shutil.copy2(catalogue_path, ROOT / 'world/expansion_species.json')
    destination = ROOT / 'build/expansion-native'
    destination.mkdir(parents=True, exist_ok=True)
    binary = source / 'build/native64/pokeemerald-native'
    for name in ('pokeemerald-native', 'pokeemerald-native.symbols'):
        shutil.copy2(binary.parent / name, destination / name)
    print(f'Built {destination / binary.name}', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
