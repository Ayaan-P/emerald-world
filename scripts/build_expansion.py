#!/usr/bin/env python3
"""Build the pinned combined Hoenn/Kanto Expansion release cohort.

Only existing development/sysroot inputs are used. No installs or downloads.
The engine is a separate checkout and no vanilla Pokemon/save ABI is imported.
"""
import argparse
from dataclasses import dataclass
from pathlib import Path
import shlex
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PIN = 'f58e825ba8ed5902c58281681b801748991ffc1c'
UPSTREAM_PIN = '79dd436920845ebc145577649de624f65298c209'


@dataclass(frozen=True)
class ReleaseConfig:
    map_version: str = 'combined'
    regional_state: int = 1
    kanto_content: int = 1
    generated_world_regions: int = 0
    version_suffix: str = 'rusturf-draft'


# Separate reconciled Rusturf candidate. Not an installed or validated release.
# The paired engine pin is explicit, never inferred from a moving branch.
RELEASE_CONFIG = ReleaseConfig()


def prepare_build_cohort(source, inputs):
    """Do not reuse native objects from an unknown or different feature cohort."""
    target = source / 'build/native64'
    stamp = target / 'ew-release-cohort.txt'
    value = '\n'.join(inputs) + '\n'
    if not stamp.is_file() or stamp.read_text() != value:
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)
        stamp.write_text(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true',
                        help='check the pin and sandboxed toolchain without building or changing source files')
    parser.add_argument('--sysroot', type=Path)
    parser.add_argument('--multilib-sysroot', '--multilib-root', type=Path,
                        help='existing extracted libc/GCC multilib root for mandatory ABI probes')
    parser.add_argument('--development', action='store_true',
                        help='build explicit local candidate integration changes on top of the verified engine pin')
    parser.add_argument('--experimental-shared-contest', action='store_true', help='Stock two-human Emerald contest (linked QA pending)')
    parser.add_argument('--experimental-shared-strength', action='store_true', help='Experimental Fiery Path boulder sharing (linked QA pending)')
    parser.add_argument('--experimental-coop-turn-plan', action='store_true',
                        help='default-off bilateral turn review; matching peers and --development; linked QA pending')
    parser.add_argument('--experimental-coop-hold-back', action='store_true',
                        help='default-off cooperative Hold back turn; matching peers and --development; linked QA pending')
    parser.add_argument('--experimental-dual-trainers', action='store_true',
                        help='Enable experimental two-opponent route co-op; matching peers and linked QA required')
    parser.add_argument('--experimental-coop-discovery', action='store_true',
                        help='Enable personal co-op opponent discovery after local presentation; linked QA pending')
    parser.add_argument('--experimental-coop-retreat', action='store_true',
                        help='Enable experimental coordinated wild retreat; matching peers and linked QA required')
    parser.add_argument('--experimental-shared-cut', action='store_true',
                        help='default-off tagged outdoor Hoenn Cut sharing; requires --development; linked QA pending')
    parser.add_argument('--experimental-coop-preparation', action='store_true',
                        help='default-off bilateral opening team preparation; requires --development; linked QA pending')
    parser.add_argument('--experimental-partner-medicine', action='store_true',
                        help='default-off active partner medicine; matching native peers and --development required; linked QA pending')
    parser.add_argument('--experimental-trainer-choice', action='store_true',
                        help='default-off trainer Team up / Face alone choice; requires matching authority and --development; linked QA pending')
    parser.add_argument('--experimental-woods-continuation', action='store_true',
                        help='default-off private Woods rescue; requires complete Roxanne/Rusturf reader cohort')
    parser.add_argument('--experimental-roxanne-continuation', action='store_true',
                        help='default-off synthetic-tested guest Gym continuation; requires experimental Rusturf readers')
    parser.add_argument('--experimental-rusturf-recovery', action='store_true',
                        help='enable unverified personal Rusturf recovery and all regional payload readers; requires --development --regional-state --kanto-content; synthetic saves only until linked QA')
    parser.add_argument('--experimental-secret-bases', action='store_true', help='enable unverified own-base sharing; requires --development')
    parser.add_argument('--experimental-npc-coop', action='store_true',
                        help='enable unverified dynamic NPC co-op wire (requires --development; both clients must match)')
    parser.add_argument('--generated-regions', action='store_true',
                        help='enable selectable generated places without changing the regional save/content cohort')
    parser.add_argument('--regional-state', action='store_true',
                        help='enable regional saves for a development build (already enabled for release)')
    parser.add_argument('--kanto-content', action='store_true',
                        help='enable Kanto in development (requires --regional-state; already enabled for release)')
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    if args.experimental_shared_contest and not args.development:
        parser.error('--experimental-shared-contest requires --development')
    if args.experimental_shared_strength and not args.development:
        parser.error('--experimental-shared-strength requires --development')
    if args.experimental_coop_turn_plan and not args.development:
        parser.error('--experimental-coop-turn-plan requires --development')
    if args.experimental_coop_hold_back and not args.development:
        parser.error('--experimental-coop-hold-back requires --development and matching native peers; linked QA pending')
    if args.experimental_dual_trainers and not args.development:
        parser.error('--experimental-dual-trainers requires --development and matching native peers; linked QA pending')
    if args.experimental_coop_discovery and not args.development:
        parser.error('--experimental-coop-discovery requires --development; linked QA pending')
    if args.experimental_coop_retreat and not args.development:
        parser.error('--experimental-coop-retreat requires --development and matching native peers; linked QA pending')
    if args.experimental_shared_cut and not args.development:
        parser.error('--experimental-shared-cut requires --development and matching native peers; linked QA pending')
    if args.experimental_coop_preparation and not args.development:
        parser.error('--experimental-coop-preparation requires --development and matching native peers; linked QA pending')
    if args.experimental_partner_medicine and not args.development:
        parser.error('--experimental-partner-medicine requires --development and matching native peers; linked QA pending')
    if args.experimental_trainer_choice and not args.development:
        parser.error('--experimental-trainer-choice requires --development and matching authority; linked QA pending')
    if args.experimental_woods_continuation and not args.experimental_roxanne_continuation:
        parser.error('--experimental-woods-continuation requires --experimental-roxanne-continuation')
    if args.experimental_roxanne_continuation and not args.experimental_rusturf_recovery:
        parser.error('--experimental-roxanne-continuation requires --experimental-rusturf-recovery')
    if args.experimental_rusturf_recovery and not (args.development and args.regional_state and args.kanto_content):
        parser.error('--experimental-rusturf-recovery requires --development --regional-state --kanto-content; linked rescue and save QA pending')
    if args.experimental_secret_bases and not args.development:
        parser.error('--experimental-secret-bases requires --development; linked save QA pending')
    if args.experimental_npc_coop and not args.development:
        parser.error('--experimental-npc-coop requires --development; linked two-client QA pending')
    if args.development and args.kanto_content and not args.regional_state:
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
    if not args.development:
        gitlink = subprocess.check_output(
            ['git', '-C', str(ROOT), 'rev-parse', 'HEAD:engines/expansion-native'], text=True).strip()
        if gitlink != PIN:
            parser.error('release pin mismatch: scripts/build_expansion.py:PIN must equal '
                         'the committed engines/expansion-native gitlink')
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
    regional_state = int(args.regional_state) if args.development else RELEASE_CONFIG.regional_state
    kanto_content = int(args.kanto_content) if args.development else RELEASE_CONFIG.kanto_content
    map_version = 'combined' if kanto_content else 'emerald'
    command += ['--', 'make', '-f', str(ROOT / 'engines/expansion.mk'), f'-j{args.jobs}',
                f'EW_RUSTURF_RECOVERY={int(args.experimental_rusturf_recovery)}',
                f'EW_SHARED_CONTEST={int(args.experimental_shared_contest)}',
                f'EW_SHARED_STRENGTH={int(args.experimental_shared_strength)}',
                f'EW_COOP_TURN_PLAN={int(args.experimental_coop_turn_plan)}',
        f'EW_COOP_HOLD_BACK={int(args.experimental_coop_hold_back)}',
                f'EW_DUAL_TRAINERS={int(args.experimental_dual_trainers)}',
                f'EW_COOP_DISCOVERY={int(args.experimental_coop_discovery)}',
                f'EW_COOP_RETREAT={int(args.experimental_coop_retreat)}',
                f'EW_SHARED_CUT={int(args.experimental_shared_cut)}',
                f'EW_COOP_PREPARATION={int(args.experimental_coop_preparation)}',
                f'EW_PARTNER_MEDICINE={int(args.experimental_partner_medicine)}',
                f'EW_TRAINER_CHOICE={int(args.experimental_trainer_choice)}',
                f'EW_WOODS_CONTINUATION={int(args.experimental_woods_continuation)}',
                f'EW_ROXANNE_CONTINUATION={int(args.experimental_roxanne_continuation)}',
                *[f'{name}={int(args.experimental_rusturf_recovery)}' for name in ('EW_REGIONAL_BADGES','EW_REGIONAL_COMPLETION','EW_ROUTE5_CUSTODY','EW_KANTO_REMATCHES','EW_REGIONAL_STARTERS')],
                f'EW_REGION_STATE={regional_state}', f'EW_KANTO_CONTENT={kanto_content}',
                f'MAP_VERSION={RELEASE_CONFIG.map_version if not args.development else map_version}',
                f'WORLD_CHARACTER_COOP_EXPERIMENT={int(args.experimental_npc_coop)}',
                f'WORLD_BASE_SHARE_EXPERIMENT={int(args.experimental_secret_bases)}',
                f'GENERATED_WORLD_REGIONS={int(args.generated_regions) or RELEASE_CONFIG.generated_world_regions}',
                'native', 'BITS=64', f'TARGET_CC={compiler}', f'NATIVE_VERSION={head[:12]}-{RELEASE_CONFIG.version_suffix}',
                'build/native64/data_relocations.checked', 'build/native64/data_layout.checked',
                'build/native64/battle_script_operands.checked']
    print(shlex.join(command), flush=True)
    prepare_build_cohort(source, [*command, (ROOT / 'engines/expansion.mk').read_text()])
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

