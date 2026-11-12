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
PIN = '8dea9e7f4ea77e22f3e1dd88da84b1b880ed7174'
UPSTREAM_PIN = '79dd436920845ebc145577649de624f65298c209'


@dataclass(frozen=True)
class ReleaseConfig:
    map_version: str = 'combined'
    regional_state: int = 1
    kanto_content: int = 1
    generated_world_regions: int = 0
    version_suffix: str = 'rc13'


# Frozen RC12/13 integration cohort. Candidate only: not an installed release.
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
    parser.add_argument('--experimental-tower-records', action='store_true', help='enable experimental explicit Tower record imports; requires --development')
    parser.add_argument('--experimental-starter-offers', action='store_true', help='enable experimental optional fresh-save starters; requires --development')
    parser.add_argument('--experimental-field-moves', action='store_true', help='enable learned moves on shared props; requires --development')
    parser.add_argument('--experimental-floorplans', action='store_true', help='enable opt-in native owned-furniture guidance; requires --development')
    parser.add_argument('--experimental-native-trades', action='store_true', help='enable local opt-in authored trade templates; requires --development')
    parser.add_argument('--experimental-nature-challenges', action='store_true', help='enable local opt-in nature-driven NPC singles; requires --development')
    parser.add_argument('--experimental-regional-starters', action='store_true', help='enable experimental isolated Kanto starter choices; linked QA pending')
    parser.add_argument('--experimental-kanto-rematches', action='store_true', help='enable experimental separate Kanto rematches; linked QA pending')
    parser.add_argument('--experimental-route5-custody', action='store_true', help='enable experimental separate Route 5 daycare; linked QA pending')
    parser.add_argument('--experimental-regional-completion', action='store_true', help='enable explicit regional championship migration; linked QA pending')
    parser.add_argument('--experimental-regional-badges', action='store_true', help='enable explicit personal regional badge migration; requires --kanto-content')
    parser.add_argument('--experimental-combined-presence', action='store_true', help='negotiate the fixed combined-world authority profile; requires --kanto-content')
    parser.add_argument('--experimental-party-practice', action='store_true', help='enable local native egg-move practice; requires --development')
    parser.add_argument('--experimental-maze-courses', action='store_true', help='enable experimental generated Trainer Hill mazes; requires --development')
    parser.add_argument('--experimental-pyramid-courses', action='store_true', help='enable experimental authored Pyramid courses; requires --development')
    parser.add_argument('--experimental-match-call-events', action='store_true', help='Temporary world rematches in original Match Call, linked QA pending')
    parser.add_argument('--experimental-field-concealment', action='store_true', help='private learned-move route concealment; requires --development')
    parser.add_argument('--experimental-persistent-cut', action='store_true', help='completed Cut changes archived shared outdoor grass; requires --development')
    parser.add_argument('--experimental-rematch-strategies', action='store_true', help='optional persistent native Hoenn rematch tactics; requires --development')
    parser.add_argument('--experimental-birch-studies', action='store_true', help='optional retained private field studies and local native tutoring; requires --development')
    parser.add_argument('--experimental-wally-invitation', action='store_true', help='enable optional native Wally invitation; requires --development')
    parser.add_argument('--experimental-map-offers', action='store_true', help='Read actual public settings on original Hoenn map, linked QA pending')
    parser.add_argument('--experimental-rydel-routes', action='store_true', help='Optional Rydel route board, linked QA pending')
    parser.add_argument('--experimental-birch-research', action='store_true', help='Living Birch after original lab Pokedex service (linked QA pending)')
    parser.add_argument('--experimental-apprentice-walking', action='store_true', help='enable transient on-foot apprentice sprite; requires --development --experimental-apprentice-outings; rendered QA pending')
    parser.add_argument('--experimental-apprentice-outings', action='store_true', help='enable RAM-only trained apprentice wild companions; requires --development; linked QA pending')
    parser.add_argument('--experimental-hoenn-markets', action='store_true', help='Optional visiting stock at original Hoenn marts (rendered QA pending)')
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
    parser.add_argument('--experimental-market-reactions', action='store_true', help='enable disclosed anonymous community purchase reports; requires --development --experimental-hoenn-markets')
    parser.add_argument('--experimental-base-rooms', action='store_true', help='enable unverified matching Secret Base rooms; requires --development')
    parser.add_argument('--experimental-dewford-trends', action='store_true', help='enable unverified opt-in public Dewford fishing patterns; requires --development')
    parser.add_argument('--experimental-safari-feeders', action='store_true', help='enable shared Safari feeder scents; requires --development')
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
    parser.add_argument("--experimental-field-support", action="store_true", help="private companion Heal Pulse on original Hoenn routes; requires --development")
    parser.add_argument("--experimental-route-trainers",action="store_true",help="voluntary authored Hoenn trainer sight behavior; development only")
    parser.add_argument("--experimental-shared-cave-light",action="store_true",help="opt-in runtime Granite Cave visibility; development only")
    args = parser.parse_args()
    if args.experimental_route_trainers and not args.development:
        parser.error("--experimental-route-trainers requires --development")
    if any((args.experimental_floorplans, args.experimental_native_trades, args.experimental_nature_challenges,
            args.experimental_regional_starters, args.experimental_kanto_rematches, args.experimental_route5_custody,
            args.experimental_regional_completion, args.experimental_regional_badges,
            args.experimental_combined_presence)) and not args.development:
        parser.error('each experimental option requires --development; linked native QA pending')
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
    if args.experimental_field_moves and not args.development:
        parser.error('--experimental-field-moves requires --development; native object UI QA pending')
    if args.experimental_party_practice and not args.development:
        parser.error('--experimental-party-practice requires --development; native UI/save QA pending')
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    if args.experimental_tower_records and not args.development:
        parser.error('--experimental-tower-records requires --development; native save/appearance QA pending')
    if args.experimental_starter_offers and not args.development:
        parser.error('--experimental-starter-offers requires --development; intro/save QA pending')
    if args.experimental_maze_courses and not args.development:
        parser.error('--experimental-maze-courses requires --development; native layout/save QA pending')
    if args.experimental_pyramid_courses and not args.development:
        parser.error('--experimental-pyramid-courses requires --development; linked suspend/save QA pending')
    if args.experimental_field_concealment and not args.development:
        parser.error('--experimental-field-concealment requires --development')
    if args.experimental_field_support and not args.development:
        parser.error("--experimental-field-support requires --development")
    if args.experimental_persistent_cut and not args.development:
        parser.error('--experimental-persistent-cut requires --development')
    if args.experimental_shared_cave_light and not args.development:
        parser.error("--experimental-shared-cave-light requires --development")
    if args.experimental_rematch_strategies and not args.development:
        parser.error('--experimental-rematch-strategies requires --development')
    if args.experimental_birch_studies and not args.development:
        parser.error('--experimental-birch-studies requires --development')
    if args.experimental_wally_invitation and not args.development:
        parser.error('--experimental-wally-invitation requires --development')
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    if args.experimental_match_call_events and not args.development:
        parser.error('--experimental-match-call-events requires --development')
    if args.experimental_map_offers and not args.development:
        parser.error('--experimental-map-offers requires --development')
    if args.experimental_rydel_routes and not args.development:
        parser.error('--experimental-rydel-routes requires --development')
    if args.experimental_birch_research and not args.development:
        parser.error('--experimental-birch-research requires --development')
    if args.experimental_apprentice_walking and not (args.development and args.experimental_apprentice_outings):
        parser.error('--experimental-apprentice-walking requires --development --experimental-apprentice-outings; rendered QA pending')
    if args.experimental_apprentice_outings and not args.development:
        parser.error('--experimental-apprentice-outings requires --development; linked QA pending')
    if args.experimental_hoenn_markets and not args.development:
        parser.error('--experimental-hoenn-markets requires --development')
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
    if args.experimental_market_reactions and not (args.development and args.experimental_hoenn_markets):
        parser.error('--experimental-market-reactions requires --development --experimental-hoenn-markets; linked shopping QA pending')
    if args.experimental_base_rooms and not args.development:
        parser.error('--experimental-base-rooms requires --development; linked room QA pending')
    if args.experimental_dewford_trends and not args.development:
        parser.error('--experimental-dewford-trends requires --development; linked gameplay QA pending')
    if args.experimental_safari_feeders and not args.development:
        parser.error('--experimental-safari-feeders requires --development; linked Safari QA pending')
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
                f'EW_BIRCH_RESEARCH={int(args.experimental_birch_research or args.experimental_birch_studies)}',
                f'EW_RYDEL_ROUTES={int(args.experimental_rydel_routes)}',
                f'EW_MAP_OFFERS={int(args.experimental_map_offers)}',
                f'EW_WALLY_INVITATION={int(args.experimental_wally_invitation)}',
                f'EW_FIELD_CONCEALMENT={int(args.experimental_field_concealment)}',
                f'EW_FIELD_SUPPORT={int(args.experimental_field_support)}',
                f'EW_PERSISTENT_CUT={int(args.experimental_persistent_cut)}',
                f'EW_SHARED_CAVE_LIGHT={int(args.experimental_shared_cave_light)}',
                f'EW_REMATCH_STRATEGIES={int(args.experimental_rematch_strategies)}',
                f'EW_BIRCH_STUDIES={int(args.experimental_birch_studies)}',
                f'EW_MATCH_CALL_EVENTS={int(args.experimental_match_call_events)}',
                f'EW_APPRENTICE_WALKING={int(args.experimental_apprentice_walking)}',
                f'EW_APPRENTICE_OUTINGS={int(args.experimental_apprentice_outings)}',
                f'EW_ROUTE_TRAINERS={int(args.experimental_route_trainers)}',
                f'EW_HOENN_MARKETS={int(args.experimental_hoenn_markets)}',
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
                f'EW_REGION_STATE={regional_state}', f'EW_KANTO_CONTENT={kanto_content}',
                f'MAP_VERSION={RELEASE_CONFIG.map_version if not args.development else map_version}',
                f'WORLD_NATURE_CHALLENGES={int(args.experimental_nature_challenges)}',
                f'WORLD_TRADE_OFFERS={int(args.experimental_native_trades)}',
                f'WORLD_COMBINED_PRESENCE={int(args.experimental_combined_presence)}',
                f'WORLD_FLOORPLANS={int(args.experimental_floorplans)}',
                f'EW_REGIONAL_BADGES={int(args.experimental_regional_badges or args.experimental_rusturf_recovery)}',
                f'EW_REGIONAL_STARTERS={int(args.experimental_regional_starters or args.experimental_rusturf_recovery)}',
                f'EW_KANTO_REMATCHES={int(args.experimental_kanto_rematches or args.experimental_rusturf_recovery)}',
                f'EW_ROUTE5_CUSTODY={int(args.experimental_route5_custody or args.experimental_rusturf_recovery)}',
                f'EW_REGIONAL_COMPLETION={int(args.experimental_regional_completion or args.experimental_rusturf_recovery)}',
                f'WORLD_CHARACTER_COOP_EXPERIMENT={int(args.experimental_npc_coop)}',
                f'EW_MARKET_REACTIONS={int(args.experimental_market_reactions)}',
                f'EW_SHARED_DEWFORD_TRENDS={int(args.experimental_dewford_trends)}',
                f'WORLD_BASE_SHARE_EXPERIMENT={int(args.experimental_secret_bases)}',
                f'EW_SHARED_BASE_ROOMS={int(args.experimental_base_rooms)}',
                f'EW_SHARED_SAFARI_FEEDERS={int(args.experimental_safari_feeders)}',
                f'GENERATED_WORLD_REGIONS={int(args.generated_regions) or RELEASE_CONFIG.generated_world_regions}',
                f'WORLD_TOWER_RECORD_EXPERIMENT={int(args.experimental_tower_records)}',
                f'WORLD_STARTER_OFFER_EXPERIMENT={int(args.experimental_starter_offers)}',
                f'WORLD_FIELD_MOVES_EXPERIMENT={int(args.experimental_field_moves)}',
                f'WORLD_PARTY_PRACTICE_EXPERIMENT={int(args.experimental_party_practice)}',
                f'WORLD_MAZE_COURSE_EXPERIMENT={int(args.experimental_maze_courses)}',
                f'WORLD_PYRAMID_COURSES_EXPERIMENT={int(args.experimental_pyramid_courses)}',
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
