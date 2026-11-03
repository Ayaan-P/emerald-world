#!/usr/bin/env python3
"""Exercise the Center peer-menu storage shortcut with two disposable natives.

Requires a built Linux binary and a generated headless smoke save. Fixtures are
explicitly relocated, not evidence of walking to a Center. No live service,
operator profile, invitation or human graphical acceptance is involved.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import tempfile
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'test/world'), str(ROOT / 'test/headless')]
import savecheck
from native_acceptance import fixture
from world.launcher import ProfileLock, game_command, player_endpoint
from world.player import PlayerClient
from world.session import DesktopSession


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def center_fixture(seed, destination, trainer):
    fixture(seed, destination, trainer)
    groups = json.loads((ROOT / 'data/maps/map_groups.json').read_text())
    for group, name in enumerate(groups['group_order']):
        if 'OldaleTown_PokemonCenter_1F' in groups[name]:
            number = groups[name].index('OldaleTown_PokemonCenter_1F')
            break
    else:
        raise AssertionError('Center map absent')
    current = savecheck.Save(destination)
    data = bytearray(destination.read_bytes())
    sizes = savecheck.chunk_sizes()
    for index in range(current.slot * 14, (current.slot + 1) * 14):
        start = index * 0x1000
        sector = struct.unpack_from('<H', data, start + 0xFF4)[0]
        if sector == 1:
            struct.pack_into('<hh', data, start, 6, 5)
            data[start + 4:start + 7] = bytes([group, number, 255])
            checksum = savecheck.checksum(data[start:start + 0x1000], sizes[sector])
            struct.pack_into('<H', data, start + 0xFF6, checksum)
    destination.write_bytes(data)
    savecheck.Save(destination)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--seed', type=Path, required=True)
    args = parser.parse_args(argv)
    seed = args.seed.resolve()
    original = digest(seed)
    # Private parent and short path satisfy profile and AF_UNIX boundaries.
    parent = Path(tempfile.mkdtemp(prefix='ew-gpc-'))
    out = parent / 'run'
    out.mkdir(mode=0o700)
    host = DesktopSession(out)
    clients, paths, processes, logs, locks = {}, {}, [], [], []
    report = {'ok': False, 'out': str(out), 'scope': 'automated two-native Center storage UI, not human/WAN trade acceptance',
              'milestones': []}

    def states():
        return {name: client.observe()['state'] for name, client in clients.items()}

    def wait(label, predicate):
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if any(p.poll() is not None for p in processes):
                raise AssertionError('native process exited: ' + label)
            current = states()
            if predicate(current):
                report['milestones'].append(label)
                return current
            time.sleep(.1)
        raise AssertionError('timeout: ' + label)

    def press(name, buttons, frames=1):
        result = clients[name].press(buttons, frames)['state']
        clients[name].press([], 12)
        return result

    def free(state):
        return state['overworld'] and not state['locked'] and not state['script'] and not state['fade']

    try:
        world = host.create_world('w')
        host.host('w')
        for name, direction in [('alice', 'LEFT'), ('bob', 'RIGHT')]:
            paths[name] = host.local_profile(name, seed)
            center_fixture(seed, paths[name]['save'], name)
            locks.append(ProfileLock(world, name))
            startup = paths[name]['profile'] / 'bootstrap.txt'
            startup.write_text('300 -\n2 START\n140 -\n2 START\n220 -\n2 A\n220 -\n2 A\n240 -\n16 '
                               + direction + '\n24 -\n1 DOWN\n24 -\n')
            log = (out / (name + '.log')).open('wb')
            logs.append(log)
            command = game_command(args.binary.resolve(), world, paths[name], None, agent_control=True)
            command += ['--world-input', str(startup)]
            processes.append(subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                                              stdout=log, stderr=subprocess.STDOUT, start_new_session=True))
        deadline = time.monotonic() + 45
        while not all(player_endpoint(p).is_socket() for p in paths.values()):
            if time.monotonic() > deadline or any(p.poll() is not None for p in processes):
                raise AssertionError('native startup failed')
            time.sleep(.1)
        clients = {n: PlayerClient(player_endpoint(p)) for n, p in paths.items()}
        wait('both trainers ready', lambda s: all(v['frame'] > 1250 and v['world']['ready'] and free(v)
                                                 for v in s.values()))
        wait('peer positions converged', lambda s: all(any(
            p['trainer'] == other and p['visible'] and p['pos'] == s[other]['pos']
            for p in s[name]['world']['peers']) for name, other in [('alice', 'bob'), ('bob', 'alice')]))
        press('alice', ['RIGHT'], 16)
        wait('adjacent peers', lambda s: s['alice']['pos'] == [6, 5] and s['bob']['pos'] == [7, 5])
        before = {n: digest(p['save']) for n, p in paths.items()}
        press('alice', ['A'])
        wait('peer menu open', lambda s: s['alice']['activity']['phase'] == 'menu')
        for _ in range(6):
            press('alice', ['DOWN'])
        press('alice', ['A'])
        wait('local PC preparation without partner invitation', lambda s:
             s['alice']['activity']['phase'] == 'idle' and s['alice']['locked']
             and s['bob']['activity']['phase'] == 'idle' and free(s['bob']))
        # Default Withdraw opens the actual stock storage screen. No mon is moved.
        press('alice', ['A'])
        wait('stock storage screen entered', lambda s: not s['alice']['overworld'] and free(s['bob']))
        clients['alice'].press([], 120)
        clients['alice'].press([], 80)
        wait('storage rendering settled', lambda s: not s['alice']['overworld']
             and not s['alice']['fade'] and free(s['bob']))
        clients['alice'].screenshot()
        image = paths['alice']['profile'] / 'screenshot.ppm'
        (out / 'storage.ppm').write_bytes(image.read_bytes())
        old_bob = states()['bob']['pos']
        press('bob', ['UP'], 16)
        wait('partner can move during storage', lambda s: s['bob']['pos'] != old_bob and free(s['bob']))
        for _ in range(5):
            press('alice', ['B'])
            clients['alice'].press([], 80)
            if free(states()['alice']):
                break
        wait('both returned free without trade', lambda s: all(free(v) and v['activity']['phase'] == 'idle'
                                                             for v in s.values()))
        report['private_saves_unchanged'] = all(digest(p['save']) == before[n] for n, p in paths.items())
        report['ok'] = report['private_saves_unchanged']
    except BaseException:
        report['error'] = traceback.format_exc()
    finally:
        for client in clients.values():
            client.close()
        for process in processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
        for log in logs:
            log.close()
        for lock in locks:
            lock.close()
        host.close()
        report['seed_unchanged'] = digest(seed) == original
        report['processes_reaped'] = all(p.poll() is not None for p in processes)
        report['ok'] = bool(report['ok'] and report['seed_unchanged'] and report['processes_reaped'])
        (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
