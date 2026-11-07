"""Exercise actual matching Expansion runtimes using disposable private profiles.

Run with --coop --save-reload for shared win, restored private EXP, isolated
saves and cold Continue. Map geometry is read only from this source checkout
for input planning; --runtime-root can select an extracted player package.
No Pokemon or save structures are decoded, injected or rewritten.
"""
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import json
import re
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--single', action='store_true')
parser.add_argument('--coop', action='store_true')
parser.add_argument('--save-reload', action='store_true')
parser.add_argument('--label', default='expansion-release')
parser.add_argument('--disposable-seed', required=True, type=Path,
                    help='Read-only seed from the actual Expansion opening replay, never a human save')
parser.add_argument('--runtime-root', type=Path, default=ROOT,
                    help='Runtime checkout or extracted package whose world modules and binary are exercised')
parser.add_argument('--output', type=Path, required=True, help='Fresh evidence directory')
args = parser.parse_args()
RUNTIME_ROOT = args.runtime_root.resolve(strict=True)
sys.path.insert(0, str(RUNTIME_ROOT))
from world.expansion import ExpansionSession, ENGINE
from world.launcher import ProfileLock, _prepare_profile, game_command, player_endpoint
from world.player import PlayerClient
from world.server import WorldServer
BINARY = RUNTIME_ROOT / 'build/expansion-native/pokeemerald-native'
SEED = args.disposable_seed.resolve(strict=True)
args.debug_fault = False
args.debug_link = False
BATTLE_SINGLE = args.single
DEBUG_LINK = args.debug_link
label = args.label
if re.fullmatch(r'[a-z][a-z0-9-]{0,63}', label) is None:
    parser.error('--label must be a simple lowercase artifact name')
OUT = args.output.resolve()
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.mkdir(mode=0o700, exist_ok=False)
base = Path(tempfile.mkdtemp(prefix='ew-expansion-release-'))
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
report = {'ok': False, 'scope': 'real two-client connection, observed movement and rendered peer visibility only; no battle/trade/persistence acceptance', 'binary_sha256': sha(BINARY), 'seed_sha256': sha(SEED), 'seed_provenance': 'prior disposable Expansion opening replay; not a human save', 'base': str(base), 'milestones': []}
locks, procs, logs, clients, paths = [], [], [], {}, {}
server = None
start = time.monotonic()
def record(label, states):
    with (OUT / 'trace.jsonl').open('a') as stream:
        stream.write(json.dumps({'label': label, 'elapsed': time.monotonic() - start, 'states': states}) + '\n')
def observe():
    return {name: client.observe()['state'] for name, client in clients.items()}
def ready(states):
    return all(s.get('world', {}).get('connected') and s.get('world', {}).get('ready') for s in states.values())
def press_all(buttons, frames):
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda client: client.press(buttons, frames), clients.values()))
def healthy():
    assert all(p.poll() is None for p in procs), 'owned native client exited; inspect its log'
def progress(text):
    return {k: int(v) for k, v in (part.split('=') for part in text.split())}
try:
    sessions = {name: ExpansionSession(base, name) for name in ('alice', 'bob')}
    state = sessions['alice'].state
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    for name, session in sessions.items():
        lock = ProfileLock(base, name, engine=ENGINE)
        lock.__enter__()
        locks.append(lock)
        paths[name] = session.paths
        _prepare_profile(state, name, None, session.paths)
        shutil.copyfile(SEED, session.paths['save'])
        os.chmod(session.paths['save'], 0o600)
    server = WorldServer(state / 'transport/world.sock', state)
    original_queue = server._queue
    report['link_events'] = []
    def traced_queue(conn, text):
        if text.startswith(('L ERROR ', 'L END ', 'L ADMIT ', 'L PAIR ', 'L READY ')):
            report['link_events'].append({'elapsed': time.monotonic() - start, 'line': text.strip()})
        return original_queue(conn, text)
    server._queue = traced_queue
    server.start()
    commands = {}
    for name in sessions:
        command = game_command(BINARY, base, paths[name], agent_control=True, engine=ENGINE)
        commands[name] = command
        log = (OUT / (name + '.log')).open('wb')
        logs.append(log)
        procs.append(subprocess.Popen(command, cwd=RUNTIME_ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True))
    (OUT / 'commands.json').write_text(json.dumps(commands, indent=2))
    deadline = time.monotonic() + 15
    while not all(player_endpoint(p).is_socket() for p in paths.values()):
        healthy()
        if time.monotonic() > deadline:
            raise TimeoutError('native control endpoint startup')
        time.sleep(0.1)
    clients = {name: PlayerClient(player_endpoint(p), timeout=8) for name, p in paths.items()}
    record('endpoints connected', observe())
    report['milestones'].append('both real native control endpoints connected')
    for _ in range(3):
        press_all([], 120)
    press_all(['START'], 2)
    press_all([], 90)
    states = observe()
    for attempt in range(8):
        record('continue bootstrap ' + str(attempt), states)
        if ready(states):
            break
        healthy()
        press_all(['A'], 2)
        press_all([], 120)
        states = observe()
    assert ready(states), 'both clients did not reach online field readiness'
    report['milestones'].append('both clients connected to the disposable authority and reached ready overworld')
    before = states['bob']['world']['pos']
    moved = False
    for direction in ('RIGHT', 'DOWN', 'LEFT', 'UP'):
        clients['bob'].press([direction], 16)
        clients['bob'].press([], 24)
        states = observe()
        record('bob movement ' + direction, states)
        if states['bob']['world']['pos'] != before:
            moved = True
            break
    assert moved, 'no observed native movement from executed control input'
    report['milestones'].append('native Bob position changed after actual GBA input')
    deadline = time.monotonic() + 15
    while True:
        healthy()
        states = observe()
        matches = all(any(p.get('trainer') == other and p.get('visible') is True and p.get('pos') == states[other]['world']['pos'] for p in states[name]['world'].get('peers', [])) for name, other in [('alice', 'bob'), ('bob', 'alice')])
        if matches:
            break
        if time.monotonic() > deadline:
            record('peer convergence timeout', states)
            raise TimeoutError('both native clients did not render the matching current peer position')
        time.sleep(0.1)
    record('mutual rendered peer visibility', states)
    report['milestones'].append('both native renderers report visible peer sprites at the other current position')
    if args.coop:
        from expansion_coop_journey import run as run_coop
        before_coop = {name: state.get('party0_progress') for name, state in states.items()}
        run_coop(clients, observe, record, report, healthy, press_all, ROOT)
        states = observe()
        report['private_reward_progress'] = {}
        for name, state in states.items():
            before, after = progress(before_coop[name]), progress(state['party0_progress'])
            for key in ('species', 'personality', 'ot'):
                assert after[key] == before[key], name + ' private Pokemon identity changed'
            assert after['outcome'] == 1, name + ' did not win the shared battle'
            assert after['exp'] > before['exp'], name + ' owned Pokemon did not receive experience'
            assert after['exp'] - before['exp'] < 100 and after['level'] <= before['level'] + 1, name + ' excessive EXP for this low-level Route101 fixture'
            report['private_reward_progress'][name] = {'before': before, 'after': after}
        report['milestones'].append('both restored private Pokemon retained identity and independently gained experience from the shared win')
        report['scope'] = 'real shared tagged wild battle win, private restored Pokemon identity and EXP; no capture/medicine acceptance'
    if args.save_reload:
        assert not (BATTLE_SINGLE or DEBUG_LINK or args.debug_fault)
        report['scope'] = ('real shared tagged wild battle win and owner-private EXP followed by separate normal saves and cold Continue; no capture/medicine acceptance' if args.coop else 'real two-client presence/movement plus independent in-game saves and cold Continue of distinct positions/party counts; no battle/trade reward acceptance')
        expected = {name: {'pos': state['world']['pos'], 'map': state['world']['map'], 'party_count': state['party_count'], 'party0_progress': state.get('party0_progress')} for name, state in states.items()}
        saved_hashes = {name: sha(p['save']) for name, p in paths.items()}
        for name, other in [('alice', 'bob'), ('bob', 'alice')]:
            client = clients[name]
            own_before, other_before = sha(paths[name]['save']), sha(paths[other]['save'])
            client.press(['START'], 2)
            client.press([], 24)
            # First start-menu cursor is zero. Normal menu ends SAVE, OPTION,
            # WORLD, EXIT irrespective of optional Dex/Nav rows: wrap up four.
            for _ in range(4):
                client.press(['UP'], 2)
                client.press([], 8)
            client.press(['A'], 2)
            client.press([], 60)
            for attempt in range(10):
                client.press(['A'], 2)
                client.press([], 60)
                current = observe()
                record(name + ' ordinary save confirmation ' + str(attempt), current)
                if sha(paths[name]['save']) != own_before and ready(current):
                    break
            # Save completion closes on neutral frames; extra A presses can
            # reopen interactions before the completion callback has returned.
            for tail_wait in range(5):
                client.press([], 120)
                current = observe()
                record(name + ' neutral save-return wait ' + str(tail_wait), current)
                if ready(current):
                    break
            assert sha(paths[name]['save']) != own_before, name + ' normal save never wrote its private file'
            assert sha(paths[other]['save']) == other_before, name + ' save modified the other profile'
            assert ready(observe()), name + ' did not return to ready field after save'
            saved_hashes[name] = sha(paths[name]['save'])
        assert saved_hashes['alice'] != saved_hashes['bob'], 'independently saved different positions must differ'
        report['milestones'].append('both normal in-game saves changed only their own distinct private files')
        for client in clients.values():
            client.close()
        clients.clear()
        for process in procs:
            process.terminate()
            process.wait(timeout=3)
        procs.clear()
        for name, p in paths.items():
            endpoint = player_endpoint(p)
            if endpoint.exists():
                endpoint.unlink()
            log = (OUT / ('cold-' + name + '.log')).open('wb')
            logs.append(log)
            procs.append(subprocess.Popen(commands[name], cwd=RUNTIME_ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True))
        deadline = time.monotonic() + 15
        while not all(player_endpoint(p).is_socket() for p in paths.values()):
            healthy()
            if time.monotonic() > deadline:
                raise TimeoutError('cold native control startup')
            time.sleep(0.1)
        clients = {name: PlayerClient(player_endpoint(p), timeout=8) for name, p in paths.items()}
        for _ in range(3):
            press_all([], 120)
        press_all(['START'], 2)
        press_all([], 90)
        states = observe()
        for attempt in range(8):
            if ready(states):
                break
            healthy()
            press_all(['A'], 2)
            press_all([], 120)
            states = observe()
        record('cold Continue states', states)
        assert ready(states), 'both saved games did not cold Continue into ready world'
        for name, state in states.items():
            assert {key: state['world'][key] for key in ('pos', 'map')} == {key: expected[name][key] for key in ('pos', 'map')}, name + ' cold-loaded the wrong saved location'
            assert state['party_count'] == expected[name]['party_count'], name + ' party count changed on cold load'
            if args.coop:
                wanted = progress(expected[name]['party0_progress'])
                loaded = progress(state['party0_progress'])
                for key in ('species', 'personality', 'ot', 'exp', 'level'):
                    assert loaded[key] == wanted[key], name + ' lost private reward/identity on cold Continue: ' + key
            assert sha(paths[name]['save']) == saved_hashes[name], name + ' cold load unexpectedly rewrote the save'
        report['saved_hashes'] = saved_hashes
        report['cold_saved_state'] = expected
        report['milestones'].append('both independent native saves cold-Continued at their own distinct locations with matching party counts')
    if BATTLE_SINGLE:
        report['scope'] = 'real two-client ordinary single battle through peer menus and bilateral consent; no co-op/trade acceptance'
        def phase(state):
            return state.get('activity', {}).get('phase')
        def wait_for(label, predicate, seconds=25):
            deadline = time.monotonic() + seconds
            while True:
                healthy()
                current = observe()
                if predicate(current):
                    record(label, current)
                    report['milestones'].append(label)
                    return current
                if time.monotonic() > deadline:
                    record('timeout: ' + label, current)
                    raise TimeoutError(label)
                time.sleep(0.1)
        def tap(name, buttons):
            clients[name].press(buttons, 1)
            clients[name].press([], 24)
        assert states['alice']['world']['pos'] == [6, 5] and states['bob']['world']['pos'] == [7, 5], 'expected adjacent disposable fixture positions'
        tap('alice', ['RIGHT'])
        tap('alice', ['A'])
        wait_for('real peer menu opened', lambda s: phase(s['alice']) == 'menu')
        tap('alice', ['DOWN'])  # Talk -> Single battle in existing WorldActivity menu.
        tap('alice', ['A'])
        wait_for('real native invitation received', lambda s: phase(s['bob']) == 'invitation')
        tap('bob', ['UP'])
        tap('bob', ['A'])
        wait_for('both clients entered native battle', lambda s: all(v.get('battle') and phase(v) == 'native' for v in s.values()), 45)
        for name, client in clients.items():
            client.screenshot()
            shutil.copyfile(paths[name]['profile'] / 'screenshot.ppm', OUT / (name + '-battle.ppm'))
        deadline = time.monotonic() + 120
        while True:
            healthy()
            states = observe()
            if all(not v.get('battle') and v.get('overworld') and not v.get('locked') and phase(v) == 'idle' for v in states.values()):
                record('both trainers returned after actual single battle', states)
                report['milestones'].append('both trainers returned after actual single battle')
                break
            if time.monotonic() > deadline:
                record('battle completion timeout', states)
                raise TimeoutError('actual single battle did not complete and return both trainers')
            press_all(['A'], 1)
            press_all([], 24)
    for name, client in clients.items():
        client.screenshot()
        shutil.copyfile(paths[name]['profile'] / 'screenshot.ppm', OUT / (name + '.ppm'))
    assert paths['alice']['save'] != paths['bob']['save']
    assert sha(SEED) == report['seed_sha256'], 'disposable source seed changed'
    report['final_states'] = states
    report['private_save_paths'] = {name: str(p['save']) for name, p in paths.items()}
    report['ok'] = True
except Exception as exc:
    report['error'] = type(exc).__name__ + ': ' + str(exc)
    report['traceback'] = traceback.format_exc()
    for name, client in clients.items():
        try:
            client.screenshot()
            shutil.copyfile(paths[name]['profile'] / 'screenshot.ppm', OUT / ('failure-' + name + '.ppm'))
        except Exception as capture_error:
            report.setdefault('capture_errors', {})[name] = str(capture_error)
finally:
    report['process_exit_before_cleanup'] = [{'pid': process.pid, 'returncode': process.poll()} for process in procs]
    for client in clients.values():
        client.close()
    for process in procs:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    if server is not None:
        server.close()
    for lock in reversed(locks):
        lock.__exit__(None, None, None)
    for log in logs:
        log.close()
    report['elapsed_seconds'] = time.monotonic() - start
    (OUT / 'acceptance.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'ok': report['ok'], 'milestones': report['milestones'], 'error': report.get('error'), 'report': str(OUT / 'acceptance.json')}))
sys.exit(0 if report['ok'] else 1)
