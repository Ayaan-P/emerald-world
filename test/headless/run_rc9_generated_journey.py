#!/usr/bin/env python3
"""Bounded RC9 actual-Expansion generated-world acceptance, disposable fixtures only.

Adapted from rc8_shared_xl_playthrough.py / xl_durable_playthrough.py.
Uses production game_command, profile locks, WorldServer, PlayerClient, and encoders.
No memory writes, save decoding, save modification, debug warp, or model calls.
Opening fixture: unchanged prior disposable Expansion opening replay in Birch's
lab with a conscious starter. This does NOT test playing the opening itself.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import traceback


def free(state):
    # Missing instrumentation is a failure, not an implicit false/default value.
    return state['overworld'] and not any(state[key] for key in
                  ('locked', 'script', 'battle', 'fade', 'moving'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', '--app-root', required=True, type=Path)
    parser.add_argument('--binary', required=True, type=Path,
                        help='Explicit immutable Expansion snapshot, exact .symbols sibling required')
    parser.add_argument('--disposable-seed', '--seed-save', required=True, type=Path)
    parser.add_argument('--output', '--out', required=True, type=Path,
                        help='Must not already exist')
    parser.add_argument('--journey', choices=('shared', 'offline', 'both'), default='shared')
    parser.add_argument('--deadline-seconds', type=int, default=900)
    args = parser.parse_args(argv)
    if not 30 <= args.deadline_seconds <= 1800:
        parser.error('--deadline-seconds must be 30..1800')
    root = args.runtime_root.resolve(strict=True)
    binary = args.binary.resolve(strict=True)
    seed = args.disposable_seed.resolve(strict=True)
    if not os.access(binary, os.X_OK):
        parser.error('binary must be executable')
    symbols = Path(str(binary) + '.symbols')
    if not symbols.is_file():
        parser.error('matching exact .symbols sibling is required for map_name observations')
    out = args.output.resolve()
    out.mkdir(parents=True, mode=0o700, exist_ok=False)
    sys.path.insert(0, str(root))
    from world.expansion import ExpansionSession, ENGINE
    from world.launcher import ProfileLock, _prepare_profile, game_command, player_endpoint
    from world.player import PlayerClient
    from world.server import WorldServer
    from world.shared_cave import SharedCave
    from world.xl_wilds import encode as encode_xl
    from world.build_catalog import catalog_maps
    generated_wilds = next(list(key) for key, value in catalog_maps().items()
                           if value['name'] == 'GeneratedWorld_Wilds')
    # Reuse RC8's production flee helper via a tiny button/state facade.
    sys.path.insert(0, str(root / 'test/headless'))
    from large_cave_playthrough import flee

    started = time.monotonic()
    overall = started + args.deadline_seconds
    report = dict(ok=False, scope=('authored 127x127 geometry; '+args.journey+
                                  ' actual Expansion journey; no model generation/battle/trade acceptance'),
                  seed_provenance='OPENING SAVE FIXTURE: unchanged prior disposable Expansion opening replay in Birch lab, conscious starter; not a human save or an opening-playthrough test',
                  runtime_root=str(root), binary=str(binary), binary_sha256=sha(binary),
                  symbols_sha256=sha(symbols), seed_sha256=sha(seed), milestones=[])
    base = Path(tempfile.mkdtemp(prefix='rc9g-'))
    report['disposable_state_root'] = str(base)
    clients, procs, locks, paths, logs = {}, {}, [], {}, []
    commands = {}
    server = None

    def record(label, states):
        with (out / 'trace.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(label=label, elapsed=time.monotonic()-started,
                                         states=states)) + '\n')

    def healthy():
        if time.monotonic() >= overall:
            raise TimeoutError('overall acceptance deadline')
        for name, proc in procs.items():
            if proc.poll() is not None:
                raise RuntimeError(f'{name} native process exited {proc.returncode}')

    def observe():
        healthy()
        return {name: client.observe()['state'] for name, client in clients.items()}

    def milestone(label, states):
        record(label, states)
        report['milestones'].append(label)

    def press(name, buttons, frames):
        healthy()
        response = clients[name].press(buttons, frames)
        with (out/'inputs.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(name=name, buttons=buttons, frames=frames,
                                         native=response))+'\n')
        return response['state']

    def neutral(name, frames):
        while frames:
            n = min(frames, 120)
            press(name, [], n)
            frames -= n

    def tap(name, key, times=1, gap=12):
        for _ in range(times):
            press(name, [key], 2)
            neutral(name, gap)

    def wait(label, predicate, seconds=35):
        deadline = min(overall, time.monotonic()+seconds)
        while time.monotonic() < deadline:
            states = observe()
            if predicate(states):
                record(label, states)
                return states
            time.sleep(.05)
        record('timeout: '+label, observe())
        raise TimeoutError(label)

    class RC8State:
        def __init__(self, state):
            self.battle = state['battle']
            self.free = free(state)

    class RC8Game:
        def __init__(self, name):
            self.name = name
        @property
        def frames(self):
            return observe()[self.name]['frame']
        @property
        def state(self):
            return RC8State(observe()[self.name])
        def tap(self, key, times=1, gap=12):
            tap(self.name, key, times, gap)
        def wait(self, frames):
            neutral(self.name, frames)

    def field(name):
        if observe()[name]['battle']:
            flee(RC8Game(name))
        return wait(name+' free field', lambda s: free(s[name]))[name]

    def walk(name, target, limit=260):
        # All paths are authored clear corridors; no teleport/path-state mutation.
        for step in range(limit):
            s = field(name)
            x, y = s['pos']
            if (x, y) == target:
                record(name+' reached '+str(target), {name: s})
                return
            direction = 'RIGHT' if x < target[0] else 'LEFT' if x > target[0] else 'DOWN' if y < target[1] else 'UP'
            press(name, [direction], 8)
            neutral(name, 12)
            if step % 25 == 0:
                record(name+' walk '+str(target), observe())
        raise RuntimeError(f'bounded walking failed {name} -> {target}: {observe()[name]}')

    def launch(name, *, online, area=None, restart=False):
        session = ExpansionSession(base, name, online=online)
        if not restart:
            session.state.mkdir(parents=True, mode=0o700, exist_ok=True)
            lock = ProfileLock(session.base, name, engine=ENGINE)
            lock.__enter__()
            locks.append(lock)
            paths[name] = session.paths
            if online:
                # state-dir is the BASE, and engine explicitly selects namespace.
                _prepare_profile(base, name, None, session.paths, engine=ENGINE)
            else:
                session.paths['profile'].mkdir(parents=True, mode=0o700, exist_ok=True)
            shutil.copyfile(seed, session.paths['save'])
            os.chmod(session.paths['save'], 0o600)
            if area is not None:
                (session.paths['profile'] / 'area.bin').write_bytes(area)
        command = game_command(binary, session.base, paths[name], agent_control=True,
                               online=online, engine=ENGINE)
        if area is not None:
            command += ['--generated-map', str(paths[name]['profile'] / 'area.bin'),
                        '--generated-progress', 'on']
        command += ['--rtc-fixed', '1700000000']
        commands[name+('-restart' if restart else '')] = command
        log = (out / (name+('-restart' if restart else '')+'.log')).open('wb')
        logs.append(log)
        procs[name] = subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        endpoint = player_endpoint(paths[name])
        deadline = min(overall, time.monotonic()+15)
        while not endpoint.is_socket():
            healthy()
            if time.monotonic() > deadline:
                raise TimeoutError(name+' native control startup')
            time.sleep(.05)
        clients[name] = PlayerClient(endpoint, timeout=8)
        neutral(name, 360)
        tap(name, 'START', gap=90)
        for _ in range(8):
            if free(observe()[name]):
                break
            tap(name, 'A', gap=120)
        s = wait(name+' cold Continue free field', lambda s: free(s[name]))[name]
        if s['map_name'] != 'MAP_LITTLEROOT_TOWN_PROFESSOR_BIRCHS_LAB' or s['party_count'] < 1:
            raise RuntimeError('opening fixture is not the expected Expansion lab with starter: '+str(s))
        # Route around the starter-ball tile at (6,8), not through it.
        walk(name, (5, s['pos'][1]))
        walk(name, (5, 11))
        walk(name, (6, 11))
        origin_map = observe()[name]['map']
        for _ in range(8):
            press(name, ['DOWN'], 8)
            neutral(name, 24)
            if observe()[name]['map'] != origin_map:
                break
        s = wait(name+' outdoors', lambda s: free(s[name]) and
                 s[name]['map_name'] == 'MAP_LITTLEROOT_TOWN')[name]
        return dict(map=s['map'], pos=s['pos'])

    def enter(name):
        field(name)
        tap(name, 'START', gap=30)
        # First START cursor is zero. Normal menu tail is OPTION,WORLD,EXIT.
        tap(name, 'UP', times=2)
        tap(name, 'A', gap=60)
        # Native World menu starts on Story rally. DexNav then Explore area.
        tap(name, 'DOWN', times=2)
        tap(name, 'A', gap=90)
        s = wait(name+' entered XL', lambda s: free(s[name]) and
                 s[name]['map'] == generated_wilds)[name]
        if s['pos'] != [1, 1]:
            raise RuntimeError('unexpected XL spawn: '+str(s))

    def leave(name, origin):
        field(name)
        tap(name, 'START', gap=30)
        # WORLD cursor remembered, SAVE removed inside, so one UP selects WORLD.
        tap(name, 'UP')
        tap(name, 'A', gap=60)
        # Inside menu defaults Back (Story absent). UP selects Leave area.
        tap(name, 'UP')
        tap(name, 'A', gap=90)
        s = wait(name+' returned to private origin', lambda s:
                 free(s[name]) and s[name]['map'] == origin['map'])[name]
        if s['pos'] != origin['pos']:
            raise RuntimeError(f'{name} wrong return point: {s}')

    def stop(name):
        clients.pop(name).close()
        proc = procs.pop(name)
        if proc.poll() is not None:
            raise RuntimeError(name+' exited before owned cleanup')
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        report.setdefault('owned_cleanup_exits', []).append(dict(name=name, code=proc.returncode))

    def capture(name, label):
        clients[name].screenshot()
        shutil.copyfile(paths[name]['profile']/'screenshot.ppm', out/(label+'.ppm'))

    def alarm_handler(signum, frame):
        raise TimeoutError('hard acceptance wall-clock deadline')

    signal.signal(signal.SIGALRM, alarm_handler)
    signal.alarm(args.deadline_seconds)
    try:
        if args.journey in ('shared', 'both'):
            blob = encode_xl({'rows': ['#'*127]+['#'+'.'*125+'#']*125+['#'*127],
                              'spawn': [1, 1], 'exit': [125, 125]})
            (out/'shared-area.bin').write_bytes(blob)
            identity = SharedCave(blob).identity
            report['shared_area_identity'] = identity
            state = ExpansionSession(base, 'alice').state
            state.mkdir(parents=True, mode=0o700, exist_ok=True)
            server = WorldServer(state/'transport/world.sock', base, cave_template=blob)
            server.start()
            origins = {}
            for name in ('alice', 'bob'):
                origins[name] = launch(name, online=True)
                wait(name+' authority field readiness', lambda s, n=name:
                     s[n]['world']['connected'] and s[n]['world']['ready'])
                # Real authority admission/ACK must happen before the menu request.
                deadline = min(overall, time.monotonic()+30)
                while True:
                    healthy()
                    with server.lock:
                        admitted = any(p.get('id') == name and p.get('cave_ack') == identity
                                       for p in server.peers.values())
                    if admitted:
                        break
                    if time.monotonic() > deadline:
                        raise TimeoutError(name+' shared XL map ACK')
                    time.sleep(.05)
                enter(name)
            for name, x in (('alice', 70), ('bob', 71)):
                walk(name, (x, 1))
            def visible(states):
                return all(any(p['trainer'] == other and p['visible'] is True and
                               p['map'] == states[other]['map'] and p['pos'] == states[other]['pos']
                               for p in states[name]['world']['peers'])
                           for name, other in (('alice', 'bob'), ('bob', 'alice')))
            states = wait('mutual rendered XL peers beyond x63', visible)
            with server.lock:
                peers = {p['id']: {'state': p.get('state'), 'ack': p.get('cave_ack')}
                         for p in server.peers.values() if p.get('id')}
            if len(peers) != 2 or any(p['ack'] != identity or p['state'][2] < 70 for p in peers.values()):
                raise RuntimeError('authority XL cohort mismatch: '+str(peers))
            report['shared_authority_peers'] = peers
            milestone('two real clients admitted same XL identity, moved beyond x63, mutually rendered', states)
            for name in ('alice', 'bob'):
                capture(name, 'shared-xl-'+name)
                leave(name, origins[name])
            milestone('both shared clients returned to their exact private origins', observe())
            for name in ('alice', 'bob'):
                stop(name)
            server.close()
            server = None
        if args.journey in ('offline', 'both'):
            run_offline(launch, enter, leave, walk, tap, press, neutral, observe, field,
                        wait, stop, capture, milestone, record, paths, report, root, out)
        for name, p in paths.items():
            if sha(p['save']) != report['seed_sha256']:
                raise RuntimeError(name+' disposable native save changed without an ordinary save request')
        if sha(seed) != report['seed_sha256']:
            raise RuntimeError('read-only opening fixture changed')
        if sha(binary) != report['binary_sha256'] or sha(symbols) != report['symbols_sha256']:
            raise RuntimeError('binary/symbol snapshot changed during journey')
        report['private_save_hashes'] = {name: sha(p['save']) for name, p in paths.items()}
        report['ok'] = True
    except Exception as exc:
        report['error'] = type(exc).__name__+': '+str(exc)
        report['traceback'] = traceback.format_exc()
        for name in list(clients):
            try:
                capture(name, 'failure-'+name)
            except Exception as error:
                report.setdefault('capture_errors', {})[name] = str(error)
    finally:
        signal.alarm(0)
        for client in clients.values():
            client.close()
        for proc in procs.values():
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        if server is not None:
            server.close()
        for lock in reversed(locks):
            lock.__exit__(None, None, None)
        for log in logs:
            log.close()
        report['elapsed_seconds'] = time.monotonic()-started
        (out/'commands.json').write_text(json.dumps(commands, indent=2)+'\n')
        (out/'acceptance.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(dict(ok=report['ok'], error=report.get('error'), report=str(out/'acceptance.json'))))
    return 0 if report['ok'] else 1


def read_journal(path):
    """READ ONLY oracle from xl_progress_store.c:10-33 / generated_map.c:100-120.

    This inspects the native generated-story SIDECAR, never Pokemon/save bytes.
    Unit-test fixtures exercising this decoder are not gameplay evidence.
    """
    import struct
    data = Path(path).read_bytes()
    size = 12 + 1 + 64 * 70
    if len(data) != size * 2:
        raise ValueError('native journal must have two complete XLP2 snapshots')
    valid = []
    for index in range(2):
        slot = data[index*size:(index+1)*size]
        if slot[:4] != b'XLP2':
            continue
        checksum = 2166136261
        for i, byte in enumerate(slot):
            if i < 8 or i >= 12:
                checksum = ((checksum ^ byte) * 16777619) & 0xffffffff
        sequence, stored = struct.unpack_from('<II', slot, 4)
        if checksum == stored:
            valid.append((sequence, slot))
    if not valid:
        raise ValueError('native journal has no checksum-valid snapshot')
    sequence, slot = valid[0]
    for candidate, payload in valid[1:]:
        delta = (candidate - sequence) & 0xffffffff
        if 0 < delta < 0x80000000:
            sequence, slot = candidate, payload
    if slot[12] >= 64:
        raise ValueError('invalid next-slot cursor')
    entries = []
    for i in range(64):
        p = slot[13+i*70:13+(i+1)*70]
        if p[0] > 1 or p[5] > 15:
            raise ValueError('invalid native progress entry')
        if p[0]:
            identity = p[6:70].decode('ascii')
            if len(identity) != 64 or any(c not in '0123456789abcdef' for c in identity):
                raise ValueError('invalid native story identity')
            entries.append(dict(trainer=p[1:5].hex(), state=p[5], identity=identity))
    return dict(sequence=sequence, entries=entries, states=[e['state'] for e in entries],
                sha256=hashlib.sha256(data).hexdigest())


def run_offline(launch, enter, leave, walk, tap, press, neutral, observe, field,
                wait, stop, capture, milestone, record, paths, report, root, out):
    from world.author_cave import decode_blueprint_events
    from world.xl_painted_events import encode
    # Same RC8 painted outdoor map and three-step handoff. A fourth rule is
    # a restart witness: it can only fire after state 3 was restored in memory.
    doc = {'rooms': [[1, 1, 125, 125]], 'links': [], 'entrance_room': 0, 'exit_room': 0,
           'cast': [{'gfx': 'boy', 'x': 2, 'y': 1, 'text': 'Welcome, traveler!'},
                    {'gfx': 'girl', 'x': 75, 'y': 20, 'text': 'Far away!'}],
           'paint': [{'x': 10, 'y': 1, 'width': 30, 'height': 1, 'terrain': 'tall_grass'},
                     {'x': 80, 'y': 80, 'width': 8, 'height': 8, 'terrain': 'water'}],
           'events': {'initial': 0, 'rules': [
               {'state': 0, 'npc': 1, 'next': 1, 'text': 'Please ask my friend.'},
               {'state': 1, 'npc': 2, 'next': 2, 'text': 'Tell them I am well.'},
               {'state': 2, 'npc': 1, 'next': 3, 'text': 'Thank you!'},
               {'state': 3, 'npc': 1, 'next': 4, 'text': 'Progress survived.'}]}}
    (out/'offline-authored-blueprint.json').write_text(json.dumps(doc, indent=2)+'\n')
    wire = '\n'.join(json.dumps(x) for x in (
        {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(doc)}},
        {'type': 'turn.completed'})).encode()
    proposal, cast, events, paint = decode_blueprint_events(wire, large=True, xl=True,
                                                           cast=True, events=True, painted=True)
    blob = encode(proposal, paint, cast, events)
    (out/'offline-area.bin').write_bytes(blob)
    name = 'guide'
    origin = launch(name, online=False, area=blob)
    if observe()[name]['world']['connected']:
        raise RuntimeError('offline native client connected to an authority')
    enter(name)
    sidecar = Path(str(paths[name]['save'])+'.generated-story')
    report['offline_oracle'] = ('Read-only checksum-validated native XLP2 sidecar. Native socket does not expose '
                                'event_state or authored NPC list. Dialogue must lock/script and each interaction '
                                'must persist the expected state. Restart must execute state3-only rule into state4.')

    def journal(expected):
        result = read_journal(sidecar)
        if result['states'] != [expected]:
            raise RuntimeError(f'expected unique native story state {expected}: {result}')
        previous = report.setdefault('offline_journal_observations', [])
        if previous and result['entries'][0]['identity'] != previous[0]['entries'][0]['identity']:
            raise RuntimeError('offline story identity changed')
        previous.append(result)
        record('native sidecar state '+str(expected), result)
        shutil.copyfile(sidecar, out/('journal-state-'+str(expected)+'.bin'))
        return result

    def talk(expected):
        press(name, ['RIGHT'], 1)
        neutral(name, 12)
        tap(name, 'A', gap=20)
        s = observe()[name]
        if not (s['script'] or s['locked']):
            raise RuntimeError('authored NPC did not open actual dialogue')
        capture(name, 'offline-dialogue-state-'+str(expected))
        for _ in range(24):
            if free(observe()[name]):
                break
            tap(name, 'A', gap=20)
        field(name)
        journal(expected)

    talk(1)
    walk(name, (1, 2))
    walk(name, (74, 2))
    walk(name, (74, 20))
    talk(2)
    walk(name, (74, 2))
    walk(name, (1, 2))
    walk(name, (1, 1))
    talk(3)
    leave(name, origin)
    milestone('offline painted XL handoff advanced states 1,2,3 and returned exactly', observe())
    stop(name)
    before = journal(3)
    # Reuse the same private native save and journal. Never re-copy seed on restart.
    origin = launch(name, online=False, area=blob, restart=True)
    enter(name)
    restored = journal(3)
    if restored['sha256'] != before['sha256']:
        raise RuntimeError('restart/entry changed durable progress before any new dialogue')
    talk(4)
    leave(name, origin)
    milestone('cold process restored state3 and actual NPC rule advanced it to state4', observe())
    stop(name)


if __name__ == '__main__':
    raise SystemExit(main())
