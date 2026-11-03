#!/usr/bin/env python3
"""Real two-native-client peer menu/consent/engine acceptance, disposable only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import struct
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT.parent / 'emerald-world-research'
sys.path[:0] = [str(ROOT), str(ROOT / 'test/world'), str(ROOT / 'test/headless')]
import savecheck
from native_acceptance import fixture
from world.launcher import ProfileLock, game_command, player_endpoint
from world.player import PlayerClient
from world.session import DesktopSession


def trade_fixture(path):
    """Two valid copied mons, so the real last-usable-mon rule stays enabled.

    This is explicit fixture construction, not evidence of capturing a Pokemon.
    The encrypted baseline mon bytes remain intact. Nicknames are outside its
    encrypted substructure, matching native_acceptance.fixture's convention.
    """
    current = savecheck.Save(path)
    data = bytearray(path.read_bytes())
    sizes = savecheck.chunk_sizes()
    for index in range(current.slot * 14, (current.slot + 1) * 14):
        start = index * 0x1000
        if struct.unpack_from('<H', data, start + 0xFF4)[0] != 1:
            continue
        data[start + 0x234] = 2
        data[start + 0x238 + 100:start + 0x238 + 200] = data[start + 0x238:start + 0x238 + 100]
        nickname = bytes([0xBB + ord(c)-ord('A') for c in 'SPARE'] + [0xFF]*5)
        data[start + 0x238 + 108:start + 0x238 + 118] = nickname
        checksum = savecheck.checksum(data[start:start + 0x1000], sizes[1])
        struct.pack_into('<H', data, start + 0xFF6, checksum)
    path.write_bytes(data)
    if savecheck.Save(path).party_count != 2:
        raise AssertionError('invalid two-mon trade fixture')


def saved_party_names(path):
    saved = savecheck.Save(path)
    return [savecheck.decode_text(saved.saveblock1[0x238 + 100*i + 8:0x238 + 100*i + 18])
            for i in range(saved.party_count)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--binary', type=Path, default=ROOT / 'build/pokeemerald64')
    parser.add_argument('--mode', choices=['single', 'trade'], default='single')
    parser.add_argument('--debug-native', action='store_true')
    args = parser.parse_args(argv)
    out = args.out.absolute()
    if out.resolve() != out or not out.is_relative_to(RESEARCH.resolve()):
        raise ValueError('out must be a new non-symlink research directory')
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    seed = RESEARCH / 'baseline/fixture-firstbattle.sav'
    seed_hash = hashlib.sha256(seed.read_bytes()).hexdigest()
    report = {'ok': False, 'mode': args.mode, 'scope': 'ordinary native peer menus, bilateral consent, actual engine activity',
              'binary_sha256': hashlib.sha256(args.binary.read_bytes()).hexdigest(), 'milestones': []}
    host = DesktopSession(out)
    paths, clients, procs, logs, locks = {}, {}, [], [], []
    start = time.monotonic()

    def save():
        (out / 'acceptance.json').write_text(json.dumps(report, indent=2))

    def observe(name):
        return clients[name].observe()['state']

    def trace(label, states=None):
        with (out / 'trace.jsonl').open('a') as stream:
            stream.write(json.dumps({'label': label, 'elapsed': time.monotonic()-start, 'states': states})+'\n')

    def wait(label, predicate, seconds=40):
        deadline = time.monotonic()+seconds
        latest = {}
        while time.monotonic() < deadline:
            if any(p.poll() is not None for p in procs):
                raise AssertionError('owned native process exited: '+label)
            latest = {name: observe(name) for name in clients}
            if predicate(latest):
                report['milestones'].append(label)
                trace(label, latest)
                save()
                return latest
            time.sleep(.1)
        trace('timeout: '+label, latest)
        raise AssertionError('deadline: '+label)

    def press(name, buttons, frames=1):
        result = clients[name].press(buttons, frames)
        trace('press '+name+' '+','.join(buttons), {name: result['state']})
        clients[name].press([], 12)
        return result['state']

    def phase(state):
        return state.get('activity', {}).get('phase')

    def capture(label):
        for name, client in clients.items():
            client.screenshot()
            source = paths[name]['profile'] / 'screenshot.ppm'
            (out / (label+'-'+name+'.ppm')).write_bytes(source.read_bytes())

    def trade_phase(state):
        return state.get('activity', {}).get('trade_phase')

    try:
        world = host.create_world('w')
        host.host('w')
        for name, direction in [('alice', 'LEFT'), ('bob', 'RIGHT')]:
            paths[name] = host.local_profile(name, seed)
            fixture(seed, paths[name]['save'], name)
            if args.mode == 'trade':
                trade_fixture(paths[name]['save'])
            startup = paths[name]['profile'] / 'bootstrap.txt'
            startup.write_text('300 -\n2 START\n140 -\n2 START\n220 -\n2 A\n220 -\n2 A\n240 -\n16 '+direction+'\n24 -\n1 DOWN\n24 -\n')
            locks.append(ProfileLock(world, name))
            command = game_command(args.binary.resolve(), world, paths[name], None, agent_control=True)
            if args.debug_native:
                # Debug the disposable child inside its existing sandbox.
                executable = command.index(str(args.binary.resolve()), command.index('--chdir') + 2)
                command[executable:executable] = ['/usr/bin/gdb', '-batch', '-ex', 'run',
                    '-ex', 'thread apply all bt', '-ex', 'p sTradeAnim',
                    '-ex', 'p gMain.state', '-ex', 'p gMain.callback2', '--args']
            command += ['--world-input', str(startup)]
            log = (out / (name+'.log')).open('wb')
            logs.append(log)
            procs.append(subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True))
        deadline = time.monotonic()+45
        while time.monotonic() < deadline:
            if all(player_endpoint(p).is_socket() for p in paths.values()):
                break
            if any(p.poll() is not None for p in procs):
                raise AssertionError('native startup exited')
            time.sleep(.1)
        clients = {name: PlayerClient(player_endpoint(p)) for name,p in paths.items()}
        wait('both native trainers bootstrapped', lambda s: all(v['frame'] > 1250
            and v.get('world', {}).get('ready') for v in s.values()))
        # Wait for the actual current peer position before walking. A delayed
        # bootstrap snapshot can otherwise put Bob's solid ghost on (6,5).
        wait('current peer positions converged', lambda s: all(any(
            p['trainer'] == other and p['visible'] and p['pos'] == s[other]['pos']
            for p in s[name]['world'].get('peers', []))
            for name, other in [('alice', 'bob'), ('bob', 'alice')]))
        press('alice', ['RIGHT'], 16)
        ready = wait('adjacent peers visible with activity observation', lambda s: all(
            'activity' in v and any(p['visible'] for p in v['world'].get('peers', [])) for v in s.values()))
        if ready['alice']['pos'] != [6,5] or ready['bob']['pos'] != [7,5]:
            raise AssertionError('unexpected fixture positions')
        report['before'] = ready
        report['initial_saved_names'] = {n: saved_party_names(p['save']) for n,p in paths.items()}
        press('alice', ['A'])
        wait('native peer menu opened', lambda s: phase(s['alice']) == 'menu')
        for _ in range(1 if args.mode == 'single' else 3):
            press('alice', ['DOWN'])
        press('alice', ['A'])
        wait('native invitation received', lambda s: phase(s['bob']) == 'invitation')
        press('bob', ['UP'])
        press('bob', ['A'])
        launched = wait('both native engines entered activity', lambda s: all(
            phase(v) == 'native' for v in s.values()), seconds=60)
        report['launched'] = launched
        if args.mode == 'single':
            battle = wait('both native battle engines running', lambda s: all(v['battle'] for v in s.values()), seconds=30)
            report['battle_started'] = battle
            # These are ordinary trainer button inputs, never battle outcomes or
            # world authority commands. Repeated A selects the default move.
            deadline = time.monotonic()+180
            while time.monotonic() < deadline:
                current = {n: observe(n) for n in clients}
                if all(not v['battle'] and phase(v) == 'idle' and v['overworld'] for v in current.values()):
                    report['after'] = current
                    report['milestones'].append('both trainers returned after real battle')
                    report['ok'] = True
                    break
                for name in clients:
                    press(name, ['A'], 1)
                time.sleep(.1)
            if not report['ok']:
                raise AssertionError('battle did not complete and return both trainers')
        else:
            wait('both native trade menus choosing', lambda s: all(
                trade_phase(v) == 'choosing' for v in s.values()), seconds=60)
            capture('trade-choosing')
            for name in clients:
                press(name, ['A'])
            wait('own Pokemon action menus opened', lambda s: all(
                trade_phase(v) == 'selected' for v in s.values()))
            for name in clients:
                press(name, ['DOWN'])  # Summary -> Trade
                press(name, ['A'])
            wait('both native final trade confirmations', lambda s: all(
                trade_phase(v) == 'confirm' for v in s.values()), seconds=60)
            capture('trade-confirm')
            for name in clients:
                press(name, ['A'])
            # All exchange/evolution/save behavior runs inside the original
            # engine. A checksum-valid on-disk nickname swap is required.
            deadline = time.monotonic()+180
            exchanged = False
            trade_ready = False
            names = {}
            while time.monotonic() < deadline:
                current = {n: observe(n) for n in clients}
                try:
                    names = {n: saved_party_names(p['save']) for n,p in paths.items()}
                    exchanged = (names['alice'][0] == report['initial_saved_names']['bob'][0]
                        and names['bob'][0] == report['initial_saved_names']['alice'][0]
                        and names['alice'][1:] == report['initial_saved_names']['alice'][1:]
                        and names['bob'][1:] == report['initial_saved_names']['bob'][1:])
                except savecheck.SaveError:
                    exchanged = False  # A native multi-sector write can be in progress.
                if exchanged and all(trade_phase(v) == 'choosing' for v in current.values()):
                    trade_ready = True
                    report['exchanged_saved_names'] = names
                    report['milestones'].append('bilateral trade persisted with private reserve Pokemon unchanged')
                    break
                time.sleep(.1)
            if not trade_ready:
                raise AssertionError('bilateral native trade did not persist ownership and return to its menu')
            capture('trade-exchanged')
            # With two occupied top-row party slots, Down skips empty rows to
            # the actual Cancel button, preserving the engine's cancellation UI.
            for name in clients:
                press(name, ['DOWN'])
                press(name, ['A'])
            wait('both native cancel confirmations', lambda s: all(
                trade_phase(v) == 'cancel_confirm' for v in s.values()))
            for name in clients:
                press(name, ['A'])
            report['after'] = wait('both trainers returned after real trade', lambda s: all(
                phase(v) == 'idle' and v['overworld'] and not v['locked'] for v in s.values()), seconds=60)
            report['ok'] = True
    except BaseException:
        report['error'] = traceback.format_exc()
        print(report['error'], file=sys.stderr)
        try:
            report['last_state'] = {n: observe(n) for n in clients}
            capture('failed')
        except Exception:
            pass
    finally:
        for client in clients.values():
            client.close()
        for proc in procs:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=5)
        for log in logs:
            log.close()
        for lock in locks:
            lock.close()
        host.close()
        report['seed_unchanged'] = hashlib.sha256(seed.read_bytes()).hexdigest() == seed_hash
        report['processes_reaped'] = all(p.poll() is not None for p in procs)
        report['ok'] = bool(report['ok'] and report['seed_unchanged'] and report['processes_reaped'])
        save()
    print(json.dumps({'ok': report['ok'], 'report': str(out / 'acceptance.json')}))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
