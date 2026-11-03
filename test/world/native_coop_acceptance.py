#!/usr/bin/env python3
"""Local, disposable, SDK-only shared-wild native acceptance. Never injects battles.

Requires the parent's explicit matching coop-build-ready.json before any launch.
Evidence is not acceptance unless acceptance.json has ok=true. No personal saves.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = Path(os.environ.get('EMERALD_WORLD_RESEARCH', str(ROOT.parent / 'emerald-world-research')))
sys.path[:0] = [str(ROOT), str(ROOT / 'test/headless')]
import maps
import savecheck
from world.launcher import ProfileLock, game_command, player_endpoint
from world.player import PlayerClient
from world.session import DesktopSession


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_ready(marker, binary):
    value = json.loads(Path(marker).read_text())
    digest = sha(binary)
    if value.get('ok') is not True or value.get('binary_sha256') != digest:
        raise ValueError('build not ready: explicit ok=true and matching binary_sha256 required')
    return digest


def identity_fixture(seed, destination, trainer):
    """Only disposable trainer/mon display identity differs from the copied seed."""
    original = savecheck.Save(seed)
    data = bytearray(Path(seed).read_bytes())
    sizes = savecheck.chunk_sizes()
    def encoded(text, width):
        return bytes([0xBB + ord(c) - ord('A') for c in text[:width]] + [0xFF] * max(0, width-len(text)))
    for index in range(original.slot*14, (original.slot+1)*14):
        offset = index*0x1000
        sector = struct.unpack_from('<H', data, offset+0xFF4)[0]
        if sector == 0:
            data[offset:offset+8] = encoded(trainer.upper(), 8)
        elif sector == 1:
            data[offset+0x240:offset+0x24A] = encoded('START'+trainer.upper(), 10)
        struct.pack_into('<H', data, offset+0xFF6, savecheck.checksum(data[offset:offset+0x1000], sizes[sector]))
    Path(destination).write_bytes(data)
    return saved_party(destination)


def saved_party(path):
    """Independently decrypt the GBA party and validate every mon checksum."""
    save = savecheck.Save(path)
    permutations = ('GAEM','GAME','GEAM','GEMA','GMAE','GMEA',
                    'AGEM','AGME','AEGM','AEMG','AMGE','AMEG',
                    'EGAM','EGMA','EAGM','EAMG','EMGA','EMAG',
                    'MGAE','MGEA','MAGE','MAEG','MEGA','MEAG')
    result = []
    for slot in range(save.party_count):
        raw = save.saveblock1[0x238+100*slot:0x238+100*(slot+1)]
        personality, ot = struct.unpack_from('<II', raw)
        secure = struct.pack('<12I', *(x ^ personality ^ ot for x in struct.unpack_from('<12I', raw, 32)))
        assert sum(struct.unpack('<24H', secure)) & 0xFFFF == struct.unpack_from('<H', raw, 28)[0], 'Pokemon checksum invalid'
        order = permutations[personality % 24]
        growth = secure[12*order.index('G'):12*(order.index('G')+1)]
        attacks = secure[12*order.index('A'):12*(order.index('A')+1)]
        result.append({'slot': slot, 'name': savecheck.decode_text(raw[8:18]),
                       'species': struct.unpack_from('<H', growth)[0],
                       'exp': struct.unpack_from('<I', growth, 4)[0], 'level': raw[84],
                       'hp': struct.unpack_from('<H', raw, 86)[0],
                       'max_hp': struct.unpack_from('<H', raw, 88)[0],
                       'status': struct.unpack_from('<I', raw, 80)[0],
                       'moves': [{'id': struct.unpack_from('<H', attacks, i*2)[0], 'pp': attacks[8+i]} for i in range(4)]})
    return result


def field_free(state):
    # Matching world-bridge readiness matters: coordinates change before the
    # walking animation finishes, and a short A tap during that step is ignored.
    return state['overworld'] and not any(state[k] for k in ('locked', 'script', 'battle', 'fade', 'moving'))


def validate_shared_battle(states, counts):
    public = []
    for name, state in states.items():
        assert state['battle'] and state['activity']['coop'], name+' not native co-op'
        assert len(state['party']) == counts[name], name+' private party leaked'
        battle = state['battle_state']
        flags = battle['battle_type_flags']
        assert flags & 67 == 67 and not flags & 8, name+' wrong wild/multi/link/double flags'
        assert battle['battlers_count'] == 4, name+' wrong battler count'
        battlers = {b['battler']: b for b in battle['battlers']}
        assert all(i in battlers and battlers[i]['side'] == 0 for i in (0, 2)), name+' missing allied 0/2'
        wild = [b for b in battlers.values() if b['side'] == 1]
        assert len(wild) == 1 and wild[0]['battler'] in (1, 3), name+' missing single visible wild'
        public.append([(b['battler'], b['side'], b['species'], b['level']) for b in sorted(battlers.values(), key=lambda b: b['battler'])])
    assert public[0] == public[1], 'clients do not share the same visible wild and allied roles'


def debug_command(command, binary, *, stop_on_abort=False):
    """gdb is the inferior's parent INSIDE the existing allowlist sandbox."""
    at = command.index(str(binary), command.index('--')+1)
    expressions = ['thread apply all bt', 'p gMain.state', 'p gMain.callback1', 'p gMain.callback2',
                   'p gMain.savedCallback', 'p gBattleTypeFlags', 'p gBattleControllerExecFlags',
                   'p gBattlerControllerFuncs', 'p gBattlerPositions', 'p gActiveBattler',
                   'p gBattleMainFunc', 'p gBattleOutcome', 'p gBattleResults',
                   'p sCoop.state', 'p sCoop.phase', 'p sCoop.local', 'p sCoop.ownerPeer',
                   'p sCoop.count', 'p sCoop.originalCount', 'p sCoop.generation',
                   'p sCoop.seed', 'p sCoop.staged', 'p sCoop.readySent',
                   'p sCoop.commitSent', 'p sCoop.peerReady', 'p sCoop.peerCommit',
                   'p sCoop.wild.hp', 'p sCoop.wild.maxHP',
                   'p sCoop.publicValid', 'p sCoop.publicSlots', 'p sCoop.publicMons',
                   'p gHealthboxSpriteIds', 'p gBattlerSpriteIds',
                   'p gSprites[gHealthboxSpriteIds[0]]', 'p gSprites[gHealthboxSpriteIds[2]]',
                   'p gSprites[gBattlerSpriteIds[1]]',
                   'p gBattleSpritesDataPtr->animationData->introAnimActive',
                   'p gBattleSpritesDataPtr->animationData->wildMonInvisible',
                   'p gBattleSpritesDataPtr->healthBoxesData[1].ballAnimActive',
                   'p sLinkReceiveTaskId', 'p sLinkSendTaskId',
                   'p gTasks[sLinkReceiveTaskId]', 'p gTasks[sLinkSendTaskId]',
                   'p/x *(unsigned char (*)[24])gBlockRecvBuffer[0]',
                   'p/x *(unsigned char (*)[24])gBlockRecvBuffer[1]',
                   'p gSendCmd', 'p gRecvCmds',
                   'p gLastSendQueueCount', 'p gLastRecvQueueCount',
                   'p sActivity', 'p gReceivedRemoteLinkPlayers', 'p gLinkPlayers',
                   'p/x *(unsigned char (*)[8])gBattleBufferA[0]',
                   'p/x *(unsigned char (*)[8])gBattleBufferA[1]',
                   'p/x *(unsigned char (*)[8])gBattleBufferA[2]',
                   'p sNativeBattleRequestPending', 'p sNativeBattleRequest',
                   'p sNativeBattleReplyUsed', 'p sNativeBattlePayloadFailed',
                   'p gBattleMons', 'p gBattleSpritesDataPtr->battlerData[1]',
                   'p gAnimScriptCallback', 'p gAnimScriptActive',
                   'p gAnimVisualTaskCount', 'p gAnimSoundTaskCount',
                   'p *gBattleSpritesDataPtr->healthBoxesData@4',
                   'p *gBattleSpritesDataPtr->animationData', 'p *gTasks@16',
                   'p sBattleAnimScriptPtr', 'x/12bx sBattleAnimScriptPtr']
    wrapper = ['/usr/bin/gdb', '-q', '-batch', '-ex', 'set pagination off',
               '-ex', 'set confirm off', '-ex', 'handle SIGINT stop print nopass']
    if stop_on_abort:
        wrapper += ['-ex', "break NativeLink_Abort if 'native_link.c'::s.session != 0"]
    wrapper += ['-ex', 'run']
    for expression in expressions:
        wrapper += ['-ex', expression]
    command[at:at] = wrapper + ['--args']
    return command


def owned_native_processes(root, name, records):
    owned = {root}
    while True:
        expanded = owned | {pid for pid, (parent, _, _) in records.items() if parent in owned}
        if expanded == owned:
            break
        owned = expanded
    return sorted(pid for pid in owned if pid in records and records[pid][1] == name[:15])


def interrupt_native(root, binary):
    # Killing the outer bwrap group kills its monitor before gdb can print.
    # Interrupt only our ptraced native inferior (its separate process group),
    # retaining gdb and both namespace monitors to collect actual live state.
    records = {}
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():
            continue
        try:
            stat = (path/'stat').read_text()
            end = stat.rfind(')')
            fields = stat[end+2:].split()
            records[int(path.name)] = (int(fields[1]), stat[stat.find('(')+1:end], int(fields[2]))
        except (OSError, ValueError):
            continue
    targets = owned_native_processes(root, Path(binary).name, records)
    for pid in targets:
        group = os.getpgid(pid)
        if group == pid and not any(n in ('gdb', 'bwrap') for _, n, g in records.values() if g == group):
            os.killpg(group, signal.SIGINT)
        else:
            os.kill(pid, signal.SIGINT)
    return targets


def both_first_moves_executed(states, before):
    """Both chosen Growls consumed their owners' PP; wild targeting is separate.

    A single wild action need not damage both humans. Full completion, rewards
    and independent saves remain mandatory gates. Restart/rejoin requires a
    separate run before claiming reload behavior.
    """
    if len(states) != 2 or set(states) != set(before):
        return False
    return all(state['party'][0]['moves'][1]['pp']
               < before[name]['party'][0]['moves'][1]['pp']
               for name, state in states.items())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--binary', type=Path, default=ROOT/'build/pokeemerald64')
    parser.add_argument('--ready-file', type=Path, default=RESEARCH/'coop-build-ready.json')
    parser.add_argument('--debug-native', action='store_true')
    parser.add_argument('--debug-abort', action='store_true')
    args = parser.parse_args(argv)
    # Fail before even creating a world when the parent has not released the build.
    digest = require_ready(args.ready_file, args.binary)
    out = args.out.absolute()
    if out.resolve() != out or not out.is_relative_to(RESEARCH.resolve()):
        raise ValueError('--out must be a new non-symlink directory under external research')
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    seed = RESEARCH/'baseline/fixture-firstbattle.sav'
    seed_hash = sha(seed)
    report = {'ok': False, 'scope': 'local two native SDK trainers, genuine walking wild encounter',
              'binary_sha256': digest, 'seed_sha256': seed_hash, 'milestones': [], 'stage': 'setup'}
    session = DesktopSession(out)
    pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='coop-sdk')
    paths, clients, procs, logs, locks, initial = {}, {}, [], [], [], {}
    start = time.monotonic()
    overall = start + 420

    def persist():
        (out/'acceptance.json').write_text(json.dumps(report, indent=2))

    def trace(label, states=None):
        with (out/'trace.jsonl').open('a') as stream:
            stream.write(json.dumps({'label': label, 'elapsed': time.monotonic()-start, 'states': states})+'\n')

    def bounded():
        if time.monotonic() > overall:
            raise TimeoutError('overall 420 second acceptance deadline')
        if any(p.poll() is not None for p in procs):
            raise RuntimeError('owned native process exited '+str([p.poll() for p in procs]))

    def all_states():
        bounded()
        futures = {n: pool.submit(c.observe) for n,c in clients.items()}
        states = {n: f.result()['state'] for n,f in futures.items()}
        for n, v in states.items():
            if n in initial and v['party'] and len(v['party']) != len(initial[n]):
                raise AssertionError(n+' private party size changed/leaked')
        return states

    def press(name, buttons, frames=1):
        bounded()
        value = clients[name].press(buttons, frames)
        trace('press '+name+' '+str(buttons)+' '+str(frames), {name: value['state']})
        return value['state']

    def both(buttons, frames=1):
        bounded()
        futures = {n: pool.submit(press, n, buttons, frames) for n in clients}
        return {n: f.result() for n,f in futures.items()}

    def tap(name, buttons):
        press(name, buttons, 2)
        return press(name, [], 12)

    def both_tap(buttons):
        both(buttons, 2)
        return both([], 12)

    def wait(label, predicate, seconds=40):
        report['stage'] = label
        persist()
        deadline = min(overall, time.monotonic()+seconds)
        while time.monotonic() < deadline:
            states = all_states()
            trace('wait '+label, states)
            if predicate(states):
                report['milestones'].append(label)
                persist()
                return states
            time.sleep(.1)  # Poll actual live SDK state, never build readiness.
        raise TimeoutError('stage deadline: '+label)

    def capture(label):
        for name, client in clients.items():
            response = client.screenshot()
            trace('screenshot '+label+' '+name, {name: response})
            (out/(label+'-'+name+'.ppm')).write_bytes((paths[name]['profile']/'screenshot.ppm').read_bytes())

    def free(v):
        return field_free(v)

    def walk(name, goal, *, allow_battle=False):
        report['stage'] = 'walk '+name+' '+str(goal)
        persist()
        deadline = min(overall, time.monotonic()+35)
        blocked, attempts = set(), 0
        origin_map = None
        while time.monotonic() < deadline:
            state = all_states()[name]
            if origin_map is None:
                origin_map = state['map']
            if state['battle'] or state['activity'].get('coop'):
                if allow_battle:
                    return True
                raise AssertionError('unexpected battle before grass walk')
            if state['map'] != origin_map:
                wait('walk map transition '+name, lambda s: free(s[name]))
                return False
            if not free(state):
                press(name, [], 12)
                continue
            if tuple(state['pos']) == goal and not state['moving']:
                return False
            level = maps.load(maps.map_name(*state['map']))
            path = level.path(tuple(state['pos']), goal, blocked | {tuple(p) for p in state['objects']}, grass_cost=20)
            if path is None:
                raise AssertionError('no ordinary walk path '+str((name, state['pos'], goal, state['objects'])))
            if not path:
                press(name, [], 4)
                continue
            old = tuple(state['pos'])
            moved = press(name, [path[0]], 8)
            press(name, [], 8)
            if tuple(moved['pos']) == old:
                attempts += 1
                if attempts >= 5:
                    dx,dy = maps.DIRECTIONS[path[0]]
                    blocked.add((old[0]+dx, old[1]+dy))
                    attempts = 0
            else:
                attempts = 0
        raise TimeoutError(report['stage'])

    def advance(name, frames):
        while frames:
            count = min(120, frames)
            press(name, [], count)
            frames -= count

    try:
        world = session.create_world('w')
        session.host('w')
        for name in ('alice','bob'):
            paths[name] = session.local_profile(name, seed)
            initial[name] = identity_fixture(seed, paths[name]['save'], name)
            locks.append(ProfileLock(world, name))
            # Recheck immediately before every native process launch.
            assert require_ready(args.ready_file, args.binary) == digest
            command = game_command(args.binary.resolve(), world, paths[name], None, agent_control=True)
            if args.debug_native:
                command = debug_command(command, args.binary.resolve(), stop_on_abort=args.debug_abort)
            (out/(name+'-command.json')).write_text(json.dumps(command, indent=2))
            log = (out/(name+'.log')).open('wb')
            logs.append(log)
            procs.append(subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                                          stdout=log, stderr=subprocess.STDOUT, start_new_session=True))
        report['initial_saved_party'] = initial
        deadline = time.monotonic()+15
        while not all(player_endpoint(p).is_socket() for p in paths.values()):
            bounded()
            if time.monotonic() > deadline:
                raise TimeoutError('native player sockets')
            time.sleep(.1)
        clients = {n: PlayerClient(player_endpoint(p)) for n,p in paths.items()}
        # These are the same buttons as continue_game, through the ordinary SDK.
        for frames, button in ((300,None),(2,'START'),(140,None),(2,'START'),(220,None),
                               (2,'A'),(220,None),(2,'A'),(240,None)):
            if button:
                both([button], frames)
            else:
                while frames:
                    amount = min(120, frames)
                    both([], amount)
                    frames -= amount
        wait('both ordinary trainers ready in lab', lambda s: all(free(v) and v.get('world',{}).get('ready') for v in s.values()))
        for n, direction in (('alice','LEFT'),('bob','RIGHT')):
            press(n, [direction], 16)
            tap(n, ['DOWN'])
        wait('peer positions converged', lambda s: all(any(p['trainer'] == other and p['visible'] and p['pos'] == s[other]['pos']
            for p in s[n]['world'].get('peers',[])) for n,other in (('alice','bob'),('bob','alice'))))
        press('alice', ['RIGHT'], 16)
        ready = all_states()
        assert ready['alice']['pos'] == [6,5] and ready['bob']['pos'] == [7,5], 'unexpected fixture positions'
        report['before'] = ready
        capture('lab-before-consent')
        wait('both steps completed before peer interaction', lambda s: all(free(v) for v in s.values()))
        tap('alice', ['A'])
        wait('peer menu opened', lambda s: s['alice']['activity']['phase'] == 'menu')
        for _ in range(4):
            tap('alice', ['DOWN'])
        tap('alice', ['A'])
        wait('bilateral tag invitation', lambda s: s['bob']['activity']['phase'] == 'invitation')
        tap('bob', ['UP'])
        tap('bob', ['A'])
        wait('bilateral tag consent accepted', lambda s: all(s[n]['activity']['tag_peer'] == other
            for n,other in (('alice','bob'),('bob','alice'))))
        capture('tag-consented')
        # Leave the actual lab door and traverse town, never rewrite location.
        for n,door,destination in (('alice',(6,12),(8,18)),('bob',(7,12),(9,18))):
            walk(n,door)
            origin = all_states()[n]['map']
            # Arrow warps require pressing out of the doorway, not merely
            # arriving at the coordinate named by the map's warp event.
            for _ in range(6):
                press(n,['DOWN'],16)
                if all_states()[n]['map'] != origin:
                    break
            wait('walked out of lab '+n, lambda s,n=n: free(s[n]) and maps.map_name(*s[n]['map']) == 'LittlerootTown')
            walk(n,destination)
        for n,x in (('alice',10),('bob',11)):
            walk(n,(x,0))
            origin = all_states()[n]['map']
            for _ in range(6):
                press(n,['UP'],16)
                if all_states()[n]['map'] != origin:
                    break
            wait('walked into Route101 '+n, lambda s,n=n: free(s[n]) and maps.map_name(*s[n]['map']) == 'Route101')
        for n,goal in (('alice',(10,17)),('bob',(11,17)),('alice',(6,17)),('bob',(7,17))):
            walk(n,goal)
        wait('tag pair in Route101 encounter range', lambda s: all(v['activity']['tag_in_range'] for v in s.values()))
        report['pre_encounter'] = all_states()
        capture('route101-before-grass')
        report['stage'] = 'genuine grass-walking encounter'
        persist()
        encountered = False
        for _ in range(25):
            for goal in ((4,17),(3,17),(4,17),(5,17)):
                if walk('alice',goal,allow_battle=True):
                    encountered = True
                    break
            if encountered:
                break
        assert encountered, 'no genuine wild encounter from walking'
        battle = wait('both shared wild engines running', lambda s: all(v['battle'] and v['activity']['coop'] for v in s.values()), seconds=45)
        report['battle_entry'] = battle
        # Do not select a move until ordinary reveal animations publish the wild.
        visible = wait('both shared visible wild and allied 0/2', lambda s: all(v.get('battle_state') and
            len(v['battle_state']['battlers']) >= 3 for v in s.values()), seconds=30)
        validate_shared_battle(visible, {n: len(v) for n,v in initial.items()})
        report['shared_battle'] = visible
        capture('shared-wild-visible')
        # First choose the second (non-damaging baseline) move so both trainers
        # actually act before the weak Route101 wild can faint to two attacks.
        assert all(v['party'][0]['moves'][1]['id'] for v in visible.values()), 'baseline second move absent'
        both([], 120)  # Let the ordinary intro/action menu settle.
        both_tap(['A'])
        # Fight selection travels through the real link engine before the move
        # menu opens. Do not send RIGHT into the preceding action/ACK phase.
        both([], 120)
        capture('first-move-menu')
        both_tap(['RIGHT'])  # The move menu is 2x2: move slot 1 is top-right.
        both_tap(['A'])
        report['stage'] = 'both trainers execute their own first move'
        persist()
        first_move_deadline = min(overall, time.monotonic()+30)
        while time.monotonic() < first_move_deadline:
            first_moves = all_states()
            trace('first move completion', first_moves)
            if both_first_moves_executed(first_moves, report['pre_encounter']):
                report['first_move_damage_observed'] = {
                    n: v['party'][0]['hp'] < report['pre_encounter'][n]['party'][0]['hp']
                    for n,v in first_moves.items()}
                report['both_first_moves_completed'] = first_moves
                capture('both-moves-completed')
                break
            assert all(v['battle'] for v in first_moves.values()), 'battle ended before both trainers acted'
            both_tap(['A'])
        else:
            raise TimeoutError('both owned Growl PP consumptions not observed within 30 seconds')
        report['stage'] = 'complete actual shared battle'
        persist()
        deadline = min(overall, time.monotonic()+180)
        history = []
        while time.monotonic() < deadline:
            current = all_states()
            trace('battle progress',current)
            history.append(current)
            if all(free(v) and v['activity']['phase'] == 'idle' for v in current.values()):
                report['after'] = current
                break
            # Fight -> move selection is asynchronous across the two clients.
            # Use the same settled transition as the initial Growl selection;
            # otherwise LEFT can land in the old action/ACK phase forever.
            both_tap(['A'])
            both([], 120)
            both_tap(['LEFT'])  # Back to first move, not repeated Growl forever.
            both_tap(['UP'])
            both_tap(['A'])
        else:
            raise TimeoutError('actual shared battle failed to complete in 180 seconds')
        capture('returned-field')
        updates = {}
        for n,v in report['after'].items():
            before, after = report['pre_encounter'][n]['party'], v['party']
            assert len(after) == len(initial[n]), n+' own party count changed'
            assert [m['species'] for m in after] == [m['species'] for m in before], n+' own species changed'
            assert after[0]['exp'] > before[0]['exp'], n+' no own EXP reward'
            assert any(a['pp'] < b['pp'] for a,b in zip(after[0]['moves'],before[0]['moves'])), n+' no own move PP consumed'
            updates[n] = {'before': before, 'after': after,
                'hp_changed': after[0]['hp'] != before[0]['hp'],
                'hp_observed': sorted({s[n]['party'][0]['hp'] for s in history if s[n]['party']})}
        report['private_updates'] = updates
        # Save independently via the original start-menu path, then verify both
        # GBA sectors and decrypted own-mon numbers against final native state.
        counters = {n: savecheck.Save(p['save']).counter for n,p in paths.items()}
        report['stage'] = 'ordinary independent in-game SAVE'
        persist()
        for n in clients:
            other = 'bob' if n == 'alice' else 'alice'
            other_save_hash = sha(paths[other]['save'])
            tap(n,['START'])
            advance(n,30)
            for _ in range(3):
                tap(n,['DOWN'])
            tap(n,['A'])
            advance(n,90)
            for frames in (300,240,300):
                tap(n,['A'])
                advance(n,frames)
            tap(n,['B'])
            wait('returned after own SAVE '+n, lambda s,n=n: free(s[n]))
            disk = savecheck.Save(paths[n]['save'])
            assert sha(paths[other]['save']) == other_save_hash, n+' SAVE mutated peer private save'
            assert disk.name == n.upper(), n+' saved trainer identity changed/leaked'
            assert disk.counter > counters[n], n+' SAVE did not advance native checksum-valid counter'
            actual = saved_party(paths[n]['save'])
            assert [m['name'] for m in actual] == [m['name'] for m in initial[n]], n+' private names changed/leaked'
            assert len(actual) == len(initial[n]), n+' saved party count changed'
            for saved, live in zip(actual,report['after'][n]['party']):
                assert {k:saved[k] for k in live} == live, n+' saved private HP/PP/EXP differs from native state'
            report.setdefault('saved',{})[n] = {'counter':disk.counter,'sha256':sha(paths[n]['save']),
                'name':disk.name, 'party':actual, 'map':disk.map, 'position':disk.position}
        capture('independent-saves')
        report['milestones'].append('actual shared battle completed, private rewards persisted through ordinary independent SAVE')
        report['ok'] = True
    except BaseException:
        report['error'] = traceback.format_exc()
        print(report['error'],file=sys.stderr,flush=True)
        try:
            report['last_state'] = all_states()
        except Exception as exc:
            report['observation_error'] = repr(exc)
        try:
            capture('failed')
        except Exception as exc:
            report['screenshot_error'] = repr(exc)
        if args.debug_native:
            for proc in procs:
                if proc.poll() is None:
                    report.setdefault('debug_inferiors_interrupted', []).extend(interrupt_native(proc.pid, args.binary))
            for proc in procs:
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
    finally:
        for client in clients.values():
            client.close()
        pool.shutdown(wait=True, cancel_futures=True)
        for proc in procs:
            if proc.poll() is None:
                os.killpg(proc.pid,signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL)
                proc.wait(timeout=5)
        for log in logs:
            log.close()
        for lock in locks:
            lock.close()
        session.close()
        report['seed_unchanged'] = sha(seed) == seed_hash
        report['binary_unchanged'] = sha(args.binary) == digest
        report['processes_reaped'] = all(p.poll() is not None for p in procs)
        report['native_exit_codes'] = [p.returncode for p in procs]
        report['elapsed'] = time.monotonic()-start
        report['ok'] = bool(report['ok'] and report['seed_unchanged'] and report['binary_unchanged'] and report['processes_reaped'])
        persist()
        if args.debug_native and not report['ok']:
            for n in paths:
                print('LIVE NATIVE DEBUG '+n+'\n'+(out/(n+'.log')).read_text(errors='replace'),file=sys.stderr)
    print(json.dumps({'ok':report['ok'],'stage':report['stage'],'report':str(out/'acceptance.json')}),flush=True)
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
