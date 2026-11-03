#!/usr/bin/env python3
"""Automated native player acceptance, NOT an LLM playing or a human playtest.

Runs two real-time native clients through production Session/game_command APIs.
The human-designated client has no controller endpoint. No display is created.
Default SDL dummy still runs the normal native clock and CPU framebuffer.
Only NEW directories below emerald-world-research are accepted.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import struct
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT.parent / 'emerald-world-research'
sys.path[:0] = [str(ROOT), str(ROOT / 'test/world'), str(ROOT / 'test/headless')]
from native_acceptance import fixture
from session_acceptance import save_readback
from world.launcher import ProfileLock, game_command, player_endpoint
from world.session import DesktopSession
from world.player import PlayerClient
from world.server import WorldServer
import savecheck

REQUIRED = (
    'native_control_supported', 'isolated_realtime_commands', 'profile_locks',
    'distinct_native_ownership', 'separate_bootstrapped_positions',
    'sdk_observes_own_trainer', 'human_has_no_endpoint',
    'realtime_while_controller_idle', 'bounded_sdk_movement', 'human_sees_peer_change',
    'native_screenshot', 'sdk_input_validation', 'native_unsafe_inputs_rejected',
    'authority_and_saves_unchanged', 'disconnect_releases_hold',
    'controller_reconnect_presence', 'seed_unchanged', 'owned_process_cleanup',
)


def require(value, message):
    if not value:
        raise AssertionError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def picture(path):
    """Validate actual P6 payload, without PIL or trusting response metadata."""
    data = path.read_bytes()
    match = re.match(rb'P6\s+(\d+)\s+(\d+)\s+255\s', data)
    require(match is not None, 'native screenshot is not binary PPM P6/255')
    width, height = map(int, match.groups())
    pixels = data[match.end():]
    require((width, height) == (240, 160), 'unexpected native framebuffer dimensions')
    require(len(pixels) == width * height * 3, 'truncated/oversized native framebuffer')
    require(len(set(pixels)) > 8, 'blank or implausible native framebuffer')
    return dict(path=str(path), format='P6', header=data[:match.end()].decode('ascii'),
                width=width, height=height, bytes=len(data), sha256=sha(path))


def process_group(group):
    """Inspect owned sandbox descendants across bwrap's new session, read-only."""
    rows = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            # comm may contain spaces or parentheses, so split after its final ')'.
            fields = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
            rows.append(dict(pid=int(entry.name), parent=int(fields[1]), group=int(fields[2]),
                             state=fields[0], start_ticks=fields[19]))
        except (OSError, ValueError, IndexError):
            continue
    owned = {row['pid'] for row in rows if row['group'] == group or row['pid'] == group}
    while True:
        expanded = owned | {row['pid'] for row in rows if row['parent'] in owned}
        if expanded == owned:
            break
        owned = expanded
    result = []
    for row in rows:
        if row['pid'] not in owned:
            continue
        try:
            command = (Path('/proc') / str(row['pid']) / 'cmdline').read_bytes().split(b'\0')
            row['argv'] = [part.decode(errors='replace') for part in command if part]
            result.append(row)
        except OSError:
            continue
    return result


def remaining_owned(entries):
    result = []
    for entry in entries:
        try:
            fields = (Path('/proc') / str(entry['pid']) / 'stat').read_text().rsplit(')', 1)[1].split()
            if fields[19] == entry['start_ticks'] and fields[0] != 'Z':
                result.append(entry)
        except (OSError, IndexError):
            pass
    return result


def raw_request(endpoint, payload, timeout):
    """Probe native validation, bypassing SDK validation but never world admin."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(timeout)
        conn.connect(str(endpoint))
        conn.sendall(payload)
        data = bytearray()
        while b'\n' not in data:
            chunk = conn.recv(4096)
            require(chunk, 'native silently closed request instead of rejecting it')
            data.extend(chunk)
            require(len(data) <= 65536, 'unbounded native error response')
        response = json.loads(data.split(b'\n', 1)[0])
        require(response.get('ok') is False and response.get('error'),
                'unsafe request was not explicitly rejected: ' + repr(response))
        return response


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--binary', type=Path, default=ROOT / 'build/pokeemerald64')
    parser.add_argument('--display', help='existing dedicated :90..:199 display; never started here')
    parser.add_argument('--seed-save', type=Path, default=RESEARCH / 'baseline/fixture-firstbattle.sav')
    parser.add_argument('--timeout', type=float, default=45, help='startup/convergence deadline in seconds')
    parser.add_argument('--restart-server', action='store_true', help='also require identity-preserving world restart')
    args = parser.parse_args(argv)
    out = args.out.absolute()
    require(out.resolve() == out and out.is_relative_to(RESEARCH.resolve()),
            '--out must be a NEW non-symlink directory below emerald-world-research')
    require(len(os.fsencode(out / 'w/trainers/alice/player.sock')) < 108, '--out too long for Unix sockets')
    require(0 < args.timeout <= 180, '--timeout must be in (0, 180]')
    out.mkdir(parents=True, mode=0o700, exist_ok=False)
    binary, seed = args.binary.resolve(), args.seed_save.resolve()
    names = list(REQUIRED) + (['server_restart_identity'] if args.restart_server else [])
    report = dict(ok=False, scope='automated acceptance; NOT an LLM playing; NOT human playtest',
                  rendering='existing dedicated X display' if args.display else 'SDL dummy, normal real-time native loop',
                  binary=str(binary), seed=str(seed), required=names,
                  checks={name: dict(ok=False, status='not_run') for name in names},
                  processes=[], images=[], observations=[], verifier_only=True)
    host = None
    client = None
    paths = {}
    processes = []
    logs = []
    profile_locks = []

    def flush():
        (out / 'acceptance.json').write_text(json.dumps(report, indent=2))

    def record(name, evidence):
        report['checks'][name] = dict(ok=True, status='passed', evidence=evidence)
        flush()
        print('PASS ' + name, flush=True)

    def wait_for(label, function):
        deadline = time.monotonic() + args.timeout
        last = None
        while time.monotonic() < deadline:
            for proc in processes:
                require(proc.poll() is None, 'owned native join exited early: ' + str(proc.returncode))
            last = function()
            if last:
                return last
            time.sleep(.05)
        raise AssertionError(label + ' deadline expired; last=' + repr(last))

    def telemetry(trainer):
        return read_json(paths[trainer]['telemetry'])

    def two_ready():
        snapshot = host.server.inspect()
        rows = snapshot['players']
        return snapshot if ({p['id'] for p in rows} == {'alice', 'bob'}
                            and all(p.get('ready') for p in rows)) else None

    def observation():
        result = client.observe()
        require(result.get('ok') is True and isinstance(result.get('state'), dict), 'missing actual native state')
        report['observations'].append(result)
        return result['state']

    def peers_visible():
        values = [telemetry(t) for t in ('alice', 'bob')]
        if not all(values):
            return None
        for own, other in ((values[0], values[1]), (values[1], values[0])):
            matches = [p for p in own.get('peers', []) if p.get('trainer') == other['trainer']]
            if not (own.get('ready') and own.get('connected') and len(matches) == 1):
                return None
            peer = matches[0]
            if not (peer.get('visible') and peer['pos'] == other['pos'] and peer['map'] == other['map']
                    and 0 <= peer['object_id'] < 16 and 0 <= peer['sprite_id'] < 64):
                return None
        return values

    def authority(snapshot):
        return {key: snapshot[key] for key in ('module_hash', 'state', 'tiles', 'objects', 'error')}

    def no_secrets(value):
        if isinstance(value, dict):
            require(not ({'token', 'admin', 'admin_token', 'world_config', 'config', 'secret'} & set(value)),
                    'native observation exposed authority/credentials')
            for item in value.values():
                no_secrets(item)
        elif isinstance(value, list):
            for item in value:
                no_secrets(item)

    try:
        report.update(binary_sha256=sha(binary), original_seed_sha256=sha(seed))
        flush()
        require(b'--player-control' in binary.read_bytes(),
                'binary predates native --player-control; parent must build current C sources first')
        record('native_control_supported', dict(binary_sha256=report['binary_sha256']))
        host = DesktopSession(out)
        state = host.create_world('w')
        host.host('w')
        for trainer, direction, trainer_id in (('alice', 'LEFT', 1001), ('bob', 'RIGHT', 1002)):
            paths[trainer] = host.local_profile(trainer, seed)
            fixture(seed, paths[trainer]['save'], trainer)
            # Distinct test-only identity, party nickname and bag, with valid GBA checksums.
            saved = savecheck.Save(paths[trainer]['save'])
            data = bytearray(paths[trainer]['save'].read_bytes())
            for sector in range(saved.slot * 14, (saved.slot + 1) * 14):
                offset = sector * 0x1000
                if struct.unpack_from('<H', data, offset + 0xFF4)[0] == 0:
                    struct.pack_into('<I', data, offset + 0x0A, trainer_id)
                    struct.pack_into('<H', data, offset + 0xFF6,
                                     savecheck.checksum(data[offset:offset+0x1000], savecheck.chunk_sizes()[0]))
            paths[trainer]['save'].write_bytes(data)
            # Finite real-time startup input, not --test-input and not a state teleport.
            bootstrap = out / (trainer + '-startup.txt')
            bootstrap.write_text('300 -\n2 START\n140 -\n2 START\n220 -\n2 A\n220 -\n2 A\n240 -\n'
                                 + '16 ' + direction + '\n24 -\n1 DOWN\n24 -\n')
            command = [sys.executable, '-m', 'world.launcher', '--state-dir', str(state),
                       'join', trainer, '--binary', str(binary), '--bootstrap', str(bootstrap)]
            if args.display:
                command += ['--display', args.display]
            if trainer == 'bob':
                command += ['--agent-control']
            native_command = game_command(binary, state, paths[trainer], args.display,
                                          agent_control=trainer == 'bob')
            own_bootstrap = paths[trainer]['profile'] / 'bootstrap.txt'
            own_bootstrap.write_bytes(bootstrap.read_bytes())
            native_command += ['--world-input', str(own_bootstrap), '--world-shot',
                               str(paths[trainer]['profile'] / 'bootstrap.ppm')]
            require('--unshare-all' in native_command and '--cap-drop' in native_command
                    and '--share-net' not in native_command, 'native not isolated')
            require('--test-input' not in native_command and '--test-state' not in native_command,
                    'frame-stepping protocol must never drive these clients')
            require(str(state) not in native_command and str(state / 'admin.sock') not in native_command,
                    'world authority mounted in player sandbox')
            require(str(paths['alice']['profile']) not in native_command if trainer == 'bob' else True,
                    'agent sandbox mounts human profile')
            logfile = out / (trainer + '-join.log')
            log = logfile.open('wb')
            logs.append(log)
            # Use the production game_command API directly so this process owns and
            # reaps the sandbox, with its real exit code, rather than a CLI wrapper.
            profile_locks.append(ProfileLock(state, trainer))
            proc = subprocess.Popen(native_command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log,
                                    stderr=subprocess.STDOUT, start_new_session=True)
            processes.append(proc)
            report['processes'].append(dict(trainer=trainer, pid=proc.pid, process_group=proc.pid,
                                            argv=native_command, production_cli_equivalent=command,
                                            cli_equivalent_executed=False, log=str(logfile), exitcode=None))
            flush()
        record('isolated_realtime_commands', report['processes'])
        # Independent production lifetime locks remain held while each child runs.
        def locked():
            result = []
            for trainer in ('alice', 'bob'):
                try:
                    lock = ProfileLock(state, trainer)
                except ValueError as exc:
                    result.append(dict(trainer=trainer, rejected=str(exc)))
                else:
                    lock.close()
                    return None
            return result
        record('profile_locks', wait_for('both profile locks held', locked))
        snapshot = wait_for('two real native players continued save', two_ready)
        # Wait for finite bootstrap EOF, well after both ready states first appear.
        wait_for('both bootstrap sequences complete', lambda: all(
            (telemetry(t) or {}).get('frame', 0) > 1200 for t in ('alice', 'bob')))
        snapshot = wait_for('bootstrapped peers visible', peers_visible)
        require(snapshot[0]['pos'] != snapshot[1]['pos'], 'bootstrap did not separate native positions')
        record('separate_bootstrapped_positions', snapshot)
        for entry in report['processes']:
            entry['live_process_group'] = process_group(entry['pid'])
        for trainer in ('alice', 'bob'):
            report['images'].append(picture(paths[trainer]['profile'] / 'bootstrap.ppm'))
        owned = host.server.inspect()
        ownership = {p['id']: [p['party_hash'], p['bag_hash']] for p in owned['players']}
        require(len({v[0] for v in ownership.values()}) == 2
                and len({v[1] for v in ownership.values()}) == 2, 'native party/bag ownership not distinct')
        report['initial_saves'] = {t: save_readback(p['save']) for t, p in paths.items()}
        record('distinct_native_ownership', dict(ownership=ownership, saves=report['initial_saves']))
        endpoint = player_endpoint(paths['bob'])
        wait_for('private agent endpoint', lambda: endpoint.is_socket())
        require(endpoint.stat().st_mode & 0o777 == 0o600, 'player socket not private 0600')
        require(not player_endpoint(paths['alice']).exists(), 'human unexpectedly has player endpoint')
        record('human_has_no_endpoint', dict(human=str(player_endpoint(paths['alice'])), exists=False,
                                            agent=str(endpoint), agent_mode=oct(endpoint.stat().st_mode & 0o777)))
        client = PlayerClient(endpoint, timeout=5)
        own = observation()
        no_secrets(own)
        require(own['world']['trainer'] == 'bob' and own['world']['ready'], 'SDK observes wrong/unready trainer')
        require(own['pos'] == telemetry('bob')['pos'] and own['map'] == telemetry('bob')['map'],
                'SDK own state does not match actual agent native telemetry')
        require(own['pos'] != telemetry('alice')['pos'], 'SDK state indistinguishable from human')
        record('sdk_observes_own_trainer', own)
        before = dict(human=telemetry('alice'), agent=own)
        time.sleep(1.0)  # No presses, pumping or polling native control during this interval.
        after = dict(human=telemetry('alice'), agent=observation())
        require(after['human']['frame'] - before['human']['frame'] >= 20,
                'human clock stalled while agent was idle')
        require(after['agent']['frame'] - before['agent']['frame'] >= 20,
                'agent game incorrectly waits for controller frame steps')
        require(after['human']['pos'] == before['human']['pos'], 'uncommanded human movement')
        record('realtime_while_controller_idle', dict(before=before, after=after))
        human_pos = telemetry('alice')['pos']
        start = observation()
        moved = None
        for direction in ('RIGHT', 'DOWN', 'UP', 'LEFT'):
            start = observation()
            tick = time.monotonic()
            reply = client.press([direction], 16)
            elapsed = time.monotonic() - tick
            no_secrets(reply)
            end = reply['state']
            report['observations'].append(reply)
            require(16 <= end['frame'] - start['frame'] < 120, 'press did not execute bounded native frames')
            require(elapsed < 4, 'bounded press blocked too long')
            time.sleep(.25)
            end = observation()
            require(telemetry('alice')['pos'] == human_pos, 'agent input moved human')
            if end['pos'] != start['pos']:
                moved = dict(direction=direction, before=start, after=end, elapsed=elapsed, reply=reply)
                break
        require(moved, 'bounded SDK input could not move the actual agent')
        record('bounded_sdk_movement', moved)
        record('human_sees_peer_change', wait_for('human rendered updated agent sprite', peers_visible))
        shot = client.screenshot()
        no_secrets(shot)
        image = Path(shot['screenshot'])
        require(image == paths['bob']['profile'] / 'screenshot.ppm' and not image.is_symlink(),
                'native screenshot did not use its fixed own-profile path')
        metadata = picture(image)
        # Keep immutable evidence as later screenshot calls replace the native fixed output.
        copy = out / 'agent-native.ppm'
        copy.write_bytes(image.read_bytes())
        metadata['evidence_copy'] = str(copy)
        report['images'].append(metadata)
        record('native_screenshot', dict(response=shot, image=metadata))
        invalid = []
        for buttons, frames in ((['RIGHT'], 0), (['RIGHT'], 121), (['RIGHT'], True),
                                (['TELEPORT'], 1), (['A', 'A'], 1), (['A'] * 10000, 1)):
            try:
                client.press(buttons, frames)
            except ValueError as exc:
                invalid.append(dict(button_count=len(buttons), frames=frames, error=str(exc)))
            else:
                raise AssertionError('SDK accepted invalid/oversized input')
        record('sdk_input_validation', invalid)
        protected_saves = {t: sha(p['save']) for t, p in paths.items()}
        protected_authority = authority(host.server.inspect())
        client.close()
        time.sleep(.1)
        errors = []
        requests = [dict(id=501, op='teleport', x=0, y=0), dict(id=502, op='deploy', source='pass'),
                    dict(id=503, op='admin', command='inspect'), dict(id=504, op='screenshot', path='/tmp/escape.ppm'),
                    dict(id=505, op='press', buttons=['RIGHT'], frames=121),
                    dict(id=506, op='press', buttons=['INVALID'], frames=1),
                    dict(id=507, op='observe', token='not-a-world-admin')]
        for request in requests:
            response = raw_request(endpoint, (json.dumps(request) + '\n').encode(), 5)
            errors.append(dict(request=request, response=response))
            time.sleep(.05)
        errors.append(dict(request='16384 bytes without newline',
                           response=raw_request(endpoint, b'X' * 16384, 5)))
        time.sleep(.1)
        record('native_unsafe_inputs_rejected', errors)
        require(authority(host.server.inspect()) == protected_authority, 'unsafe player input changed world authority')
        require({t: sha(p['save']) for t, p in paths.items()} == protected_saves, 'unsafe input changed saves')
        require(not player_endpoint(paths['alice']).exists(), 'unsafe request created human endpoint')
        record('authority_and_saves_unchanged', dict(authority=protected_authority,
               saves={t: save_readback(p['save']) for t, p in paths.items()}))
        # Disconnect during a real held direction. Observe stability BEFORE its 120-frame
        # expiry, then prove another tile in that direction remains traversable, not a wall.
        reverse = {'RIGHT': 'LEFT', 'LEFT': 'RIGHT', 'UP': 'DOWN', 'DOWN': 'UP'}[moved['direction']]
        before_hold = observation()
        client.close()
        time.sleep(.08)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(5)
            conn.connect(str(endpoint))
            conn.sendall((json.dumps(dict(id=601, op='press', buttons=[reverse], frames=120)) + '\n').encode())
            time.sleep(.14)
            during_hold = telemetry('bob')
            require(during_hold['pos'] != before_hold['pos'], 'disconnect probe did not start actual held movement')
        time.sleep(.30)
        settled = observation()
        time.sleep(.40)
        stopped = observation()
        require(stopped['frame'] - before_hold['frame'] < 110, 'hold expired naturally before release was tested')
        require(stopped['pos'] == settled['pos'], 'controller disconnect left a held movement button')
        probe = client.press([reverse], 16)
        time.sleep(.25)
        traversable = observation()
        require(traversable['pos'] != stopped['pos'], 'stability could be a wall, not a released held button')
        require(telemetry('alice')['pos'] == human_pos, 'disconnect/reconnect moved human')
        record('disconnect_releases_hold', dict(before=before_hold, during=during_hold, settled=settled,
                                               stopped=stopped, next_press=probe, traversable=traversable))
        current = wait_for('world presence survives controller reconnect', two_ready)
        require({p['id']: [p['party_hash'], p['bag_hash']] for p in current['players']} == ownership,
                'controller reconnect changed native identity or ownership')
        record('controller_reconnect_presence', dict(world=current, native=wait_for('peer retained', peers_visible)))
        if args.restart_server:
            host.server.close()
            host.server = WorldServer(state / 'transport/world.sock', state).start()
            current = wait_for('native reconnect after server restart', two_ready)
            require({p['id']: [p['party_hash'], p['bag_hash']] for p in current['players']} == ownership,
                    'world restart changed identity/ownership')
            require(authority(current) == protected_authority, 'world restart changed authority state')
            record('server_restart_identity', dict(world=current, peers=wait_for('restart native peers', peers_visible)))
        require(sha(seed) == report['original_seed_sha256'], 'original seed changed')
        record('seed_unchanged', dict(sha256=sha(seed)))
    except BaseException as exc:
        report['error'] = repr(exc)
        report['traceback'] = traceback.format_exc()
        print('FAIL ' + repr(exc), file=sys.stderr, flush=True)
    finally:
        if client is not None:
            client.close()
        cleanup = []
        for proc, entry in zip(processes, report['processes']):
            descendants = process_group(proc.pid)
            entry['pre_cleanup_processes'] = descendants
            entry['pre_cleanup_exitcode'] = proc.poll()
            if proc.poll() is None:
                # Each sandbox was started in its own session. Its native descendants
                # are bounded by --die-with-parent, never kill by name or touch a display.
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            try:
                entry['exitcode'] = proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                entry['forced_kill'] = True
                entry['exitcode'] = proc.wait(timeout=5)
            deadline = time.monotonic() + 3
            survivors = remaining_owned(descendants)
            while survivors and time.monotonic() < deadline:
                time.sleep(.05)
                survivors = remaining_owned(descendants)
            cleanup.append(dict(pid=proc.pid, sandbox_exitcode=entry['exitcode'],
                                remaining_native_processes=survivors,
                                expected_termination=entry['pre_cleanup_exitcode'] is None,
                                forced_kill=entry.get('forced_kill', False)))
        for log in logs:
            log.close()
        for lock in profile_locks:
            lock.close()
        if host is not None:
            host.close()
        if processes:
            clean = all(p.poll() is not None for p in processes)
            clean = clean and all(row['expected_termination'] and not row['forced_kill']
                                  and not row['remaining_native_processes'] for row in cleanup)
            report['checks']['owned_process_cleanup'] = dict(ok=clean, status='passed' if clean else 'failed', evidence=cleanup)
        if seed.exists() and 'original_seed_sha256' in report:
            unchanged = sha(seed) == report['original_seed_sha256']
            report['checks']['seed_unchanged'] = dict(ok=unchanged, status='passed' if unchanged else 'failed',
                                                     evidence=dict(sha256=sha(seed)))
        report['missing_criteria'] = [name for name in names if not report['checks'][name]['ok']]
        report['ok'] = not report.get('error') and not report['missing_criteria']
        flush()
    print(json.dumps(dict(ok=report['ok'], report=str(out / 'acceptance.json'),
                          missing=report['missing_criteria'])), flush=True)
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
