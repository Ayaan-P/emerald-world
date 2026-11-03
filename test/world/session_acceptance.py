#!/usr/bin/env python3
"""Real native multiplayer session acceptance. No model, network account or GUI.

Run with /usr/bin/python3 and a NEW disposable research --out directory. Both
native endpoints use independently prepared saves and pinned TLS brokers. This
is not a substitute for graphical/manual acceptance or live GM authoring.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import ssl
import struct
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT.parent / 'emerald-world-research'
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'test/headless'))
sys.path.insert(0, str(ROOT / 'test/world'))
from native_acceptance import Engine, fixture
from world.launcher import game_command
from world.client import admin_request
from world.session import DesktopSession
import driver
import savecheck


REQUIRED = (
    'create_host', 'tls_independent_profiles', 'native_ownership',
    'remote_sprites', 'movement_both_ways', 'wrong_pin_isolated',
    'native_save_readback', 'guest_disconnect', 'guest_rejoin',
    'host_offline', 'host_restart_rebind', 'trainer_interaction',
    'seed_unchanged', 'native_exitcodes',
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    # Deliberately not Python assert: python -O must not disable acceptance.
    if not condition:
        raise AssertionError(message)


def save_readback(path):
    saved = savecheck.Save(path)
    key = struct.unpack_from('<I', saved.saveblock2, 0xAC)[0] & 0xFFFF
    item, quantity = struct.unpack_from('<HH', saved.saveblock1, 0x560)
    objects = [saved.saveblock1[0xA30+i*0x24:0xA30+(i+1)*0x24] for i in range(16)]
    require(not any(obj[0] & 1 and 224 <= obj[8] < 255 for obj in objects),
            'remote object leaked into the GBA save')
    return dict(path=str(path), sha256=sha(path), name=saved.name,
                trainer_id=saved.trainer_id, counter=saved.counter,
                map=list(saved.map), pos=list(saved.position),
                party_sha256=hashlib.sha256(saved.saveblock1[0x238:0x490]).hexdigest(),
                item=item, quantity=quantity ^ key)


class PreparedEngine(Engine):
    """Reuse the real driver's input/state protocol, never prepare local authority.

    Remote DesktopSession.connect_remote has already prepared these exact paths.
    Calling the original Engine constructor would create a different local world.
    """
    def __init__(self, binary, state, paths, generation):
        self.paths = paths
        logs = paths['profile'] / ('run-' + str(generation))
        logs.mkdir()
        self.out_dir = str(logs)
        self.save_path = str(paths['save'])
        self.hashes_path = str(logs / 'hashes.txt')
        self.max_frames = 200000
        self.stderr = (logs / 'stderr.txt').open('w')
        self.states = (logs / 'states.jsonl').open('w')
        self.steps, self.frames = [], 0
        self.closed = False
        command = game_command(binary, state, paths)
        require('--unshare-all' in command and '--share-net' not in command,
                'native game must not have direct network access')
        require(str(state) not in command and str(state / 'admin.sock') not in command,
                'native sandbox mounted world authority instead of just transport')
        require(not any('key.pem' in value or value.endswith('alice.json')
                        or value.endswith('bob.json') for value in command),
                'native sandbox exposes a TLS key or invitation')
        command += ['--test-input', '-', '--test-state', '-', '--test-hashes',
                    self.hashes_path, '--test-shots', str(logs)]
        (logs / 'command.json').write_text(json.dumps(command, indent=2))
        self.command = command
        self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=self.stderr, text=True, bufsize=1)
        try:
            self.state = self._read_state()
        except BaseException:
            self.stop()
            raise

    def _read_state(self):
        ready, _, _ = select.select([self.proc.stdout], [], [], 20)
        if not ready:
            raise RuntimeError(f'native state timeout: pid={self.proc.pid}, log={self.out_dir}')
        return driver.Game._read_state(self)

    def stop(self):
        if self.closed:
            return self.proc.returncode
        (Path(self.out_dir) / 'input.txt').write_text(''.join(f'{n} {b}\n' for n, b in self.steps))
        try:
            self.proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        try:
            code = self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()  # Only this harness-owned child, never a process-name kill.
            code = self.proc.wait(timeout=5)
        self.proc.stdout.close()
        self.stderr.close()
        self.states.close()
        self.closed = True
        return code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--binary', type=Path, default=ROOT / 'build/pokeemerald64')
    parser.add_argument('--seed-save', type=Path,
                        default=RESEARCH / 'baseline/fixture-firstbattle.sav')
    parser.add_argument('--timeout', type=float, default=20,
                        help='bounded transport convergence deadline, not an author wait')
    args = parser.parse_args(argv)
    out = args.out.absolute()
    require(out.resolve() == out and out.is_relative_to(RESEARCH.resolve()),
            '--out must be a new non-symlink directory below emerald-world-research')
    require(len(os.fsencode(out / 'h/transport/world.sock')) < 108,
            'use a shorter --out name (Unix sockets have a 108-byte limit)')
    require(args.timeout > 0, '--timeout must be positive')
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    binary, seed = args.binary.resolve(), args.seed_save.resolve()
    report = dict(ok=False, binary=str(binary), seed=str(seed), required=list(REQUIRED),
                  checks=[], native_processes=[], commands=[], scope='headless real C native clients over pinned TLS')
    sessions, engines, active = [], [], []

    def flush():
        (out / 'acceptance.json').write_text(json.dumps(report, indent=2))

    def record(name, evidence):
        report['checks'].append(dict(name=name, ok=True, evidence=evidence))
        flush()
        print('PASS ' + name, flush=True)

    def pump():
        for game in list(active):
            require(game.proc.poll() is None, f'native exited unexpectedly: {game.out_dir}')
            game.wait(6)
        time.sleep(.02)

    def wait_for(name, predicate):
        deadline = time.monotonic() + args.timeout
        last = None
        while time.monotonic() < deadline:
            pump()
            last = predicate()
            if last:
                return last
        raise AssertionError(f'{name}: convergence timeout; native=' + json.dumps(
            [g.telemetry() for g in active]))

    def start(session, paths, generation):
        game = PreparedEngine(binary, session.state, paths, generation)
        engines.append(game)
        active.append(game)
        report['native_processes'].append(dict(pid=game.proc.pid, trainer=paths['profile'].name,
                                               logs=game.out_dir, command=game.command))
        flush()
        driver.continue_game(game)
        return game

    def peers_match():
        if len(active) != 2:
            return False
        for index, game in enumerate(active):
            other = active[1-index]
            telemetry = game.telemetry()
            peers = telemetry.get('peers', [])
            if not telemetry.get('connected') or len(peers) != 1:
                return False
            peer = peers[0]
            if not (peer['trainer'] == other.paths['profile'].name and peer['visible']
                    and peer['pos'] == list(other.state.pos)
                    and peer['map'] == other.state.map
                    and 0 <= peer['object_id'] < 16 and 0 <= peer['sprite_id'] < 64):
                return False
        return [g.telemetry() for g in active]

    try:
        report.update(binary_sha256=sha(binary), seed_sha256=sha(seed))
        flush()
        host, alice_session, bob_session, bad = [DesktopSession(out) for _ in range(4)]
        sessions.extend([bad, bob_session, alice_session, host])
        state = host.create_world('h')
        require(host.worlds() == [dict(name='h', path=str(state))], 'world discovery readback')
        host.host('h')
        record('create_host', dict(worlds=host.worlds(), inspect=host.server.inspect()))
        cert, key = out / 'cert.pem', out / 'key.pem'
        command = ['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                   '-keyout', str(key), '-out', str(cert), '-days', '1', '-subj', '/CN=localhost']
        with (out / 'openssl.log').open('w') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=30)
        key.chmod(0o600)
        report['commands'].append(dict(argv=command, exitcode=result.returncode))
        require(result.returncode == 0, 'local certificate generation failed')
        pin = hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text())).hexdigest()
        address = host.share(cert, key, ('127.0.0.1', 0))
        paths = {}
        invitations = {}
        for trainer, session, name in [('alice', alice_session, 'a'), ('bob', bob_session, 'b')]:
            invitation = out / (trainer + '.json')
            host.invite(trainer, invitation)
            invitations[trainer] = invitation
            require(invitation.stat().st_mode & 0o777 == 0o600, 'private invitation permissions')
            paths[trainer] = session.connect_remote(name, invitation, address, pin)
            fixture(seed, paths[trainer]['save'], trainer)
            # The copied fixtures also have distinct in-game trainer IDs.
            data = bytearray(paths[trainer]['save'].read_bytes())
            saved = savecheck.Save(paths[trainer]['save'])
            for sector in range(saved.slot*14, (saved.slot+1)*14):
                offset = sector*0x1000
                if struct.unpack_from('<H', data, offset+0xFF4)[0] == 0:
                    struct.pack_into('<I', data, offset+0x0A, 1001 if trainer == 'alice' else 1002)
                    struct.pack_into('<H', data, offset+0xFF6,
                                     savecheck.checksum(data[offset:offset+0x1000], savecheck.chunk_sizes()[0]))
            paths[trainer]['save'].write_bytes(data)
            require(not (session.state / 'world.sqlite3').exists(), 'remote unexpectedly created local authority')
        record('tls_independent_profiles', dict(address=address, pin=pin,
               saves={t: save_readback(p['save']) for t, p in paths.items()}))
        alice = start(alice_session, paths['alice'], 0)
        bob = start(bob_session, paths['bob'], 0)
        # Separate the initially co-located copied fixtures using actual input.
        alice.press('LEFT', 16); alice.wait(12)
        bob.press('RIGHT', 16); bob.wait(12)
        def players_ready():
            snapshot = host.server.inspect()
            players = snapshot['players']
            return snapshot if ({p['id'] for p in players} == {'alice', 'bob'}
                                and all(p.get('ready') for p in players)) else False
        snapshot = wait_for('two native authenticated trainers', players_ready)
        ownership = {p['id']: [p['party_hash'], p['bag_hash']] for p in snapshot['players']}
        require(len({v[0] for v in ownership.values()}) == 2, 'party ownership not distinct')
        require(len({v[1] for v in ownership.values()}) == 2, 'bag ownership not distinct')
        record('native_ownership', snapshot)
        record('remote_sprites', wait_for('native remote sprites', peers_match))
        movement = []
        for game in (alice, bob):
            before = list(game.state.pos)
            game.press('LEFT' if game is alice else 'RIGHT', 16); game.wait(12)
            require(list(game.state.pos) != before, 'native movement blocked at fixture location')
            movement.append(dict(trainer=game.paths['profile'].name, before=before,
                                 after=list(game.state.pos), readback=wait_for('movement replication', peers_match)))
        record('movement_both_ways', movement)
        wrong = ('1' if pin[0] != '1' else '2') + pin[1:]
        try:
            bad.connect_remote('bad', invitations['bob'], address, wrong)
        except (OSError, ValueError) as error:
            rejection = dict(type=type(error).__name__, message=str(error))
        else:
            raise AssertionError('wrong TLS pin accepted')
        require(bad.state is None and bad.broker is None, 'failed connection retained authority')
        record('wrong_pin_isolated', dict(rejection=rejection,
               native=wait_for('host survives wrong pin', peers_match), host=host.server.inspect()))
        for game in (alice, bob):
            driver.save_game(game, 3)
            game.wait(120)
        saved_before = {t: save_readback(p['save']) for t, p in paths.items()}
        for trainer, quantity in [('alice', 2), ('bob', 5)]:
            saved = saved_before[trainer]
            require(saved['name'] == trainer.upper() and saved['quantity'] == quantity
                    and saved['item'] == 13, 'in-game save lost independent identity or bag')
        record('native_save_readback', saved_before)
        require(bob.stop() == 0, 'guest native did not exit cleanly')
        active.remove(bob)
        bob_session.close()
        def guest_gone():
            snap = host.server.inspect()
            return snap if ({p['id'] for p in snap['players']} == {'alice'}
                            and alice.telemetry()['connected'] and not alice.telemetry()['peers']) else False
        record('guest_disconnect', wait_for('guest absence without host disruption', guest_gone))
        old_config = sha(paths['bob']['config'])
        resumed = bob_session.connect_remote('b', invitations['bob'], address, pin)
        require(resumed == paths['bob'] and sha(resumed['config']) == old_config,
                'remote rejoin changed trainer profile binding')
        require(save_readback(resumed['save']) == saved_before['bob'], 'rejoin overwrote the native save')
        bob = start(bob_session, resumed, 1)
        wait_for('guest rejoin native ownership', players_ready)
        record('guest_rejoin', dict(native=wait_for('rejoined sprites', peers_match),
                                    save=save_readback(resumed['save']), host=host.server.inspect()))
        # Explicit public lifecycle: close invalidates inode-pinned HostBroker.
        # Re-host AND re-share are required, on the SAME address and certificate.
        old_host_inode = (state / 'transport/world.sock').stat().st_ino
        host.close()
        record('host_offline', wait_for('native observes host outage', lambda:
               [g.telemetry() for g in active] if all(not g.telemetry()['connected'] for g in active) else False))
        host.host('h')
        rebound = host.share(cert, key, address)
        require(rebound == address, 'host failed explicit TLS address rebind')
        snapshot = wait_for('native reconnect after host rebind', players_ready)
        require({p['id']: [p['party_hash'], p['bag_hash']] for p in snapshot['players']} == ownership,
                'host restart changed native ownership')
        record('host_restart_rebind', dict(policy='DesktopSession.close/host/share; fresh inode-pinned broker, same TLS address/pin',
               previous_inode=old_host_inode, current_inode=(state/'transport/world.sock').stat().st_ino,
               address=rebound, inspect=snapshot, native=wait_for('restart sprites', peers_match)))
        # Actual A input on an adjacent remote trainer. New bridge support is
        # mandatory: old binaries fail explicitly, never silently skip this check.
        # Position on the clear fixture map via driver input, not memory writes.
        bx, by = bob.state.pos
        driver.walk_to(alice, bx-1, by)
        alice.press('RIGHT', 1); alice.wait(12)
        wait_for('adjacent trainer sprites', peers_match)
        before_revision = host.server.inspect()['revision']
        alice.press('A', 1); alice.wait(12)
        # SOCIAL/MEET is committed on the first A. Only the authority's
        # acknowledgement opens the actual native modal on both clients.
        def meeting_received():
            snap = host.server.inspect()
            meetings = [p.get('meeting') for p in snap['players']]
            return snap if len(meetings) == 2 and all(
                m and m.get('player') == 'alice' and m.get('target') == 'bob'
                and m.get('signal') == 'explore' and m.get('seq', 0) > before_revision
                for m in meetings) else False
        interaction_host = wait_for('native trainer SOCIAL/MEET support (rebuild bridge if absent)', meeting_received)
        def native_dialogues():
            telemetry = [g.telemetry() for g in active]
            for value, game, other in zip(telemetry, active, ('bob', 'alice')):
                if not (value.get('dialogue_active') and value.get('dialogue_object') == other
                        and value.get('dialogue_text') == other + "\nLet's explore together!"
                        and game.state.locked):
                    return False
            return telemetry
        opened = wait_for('exact trainer dialogue and real native modal locks on both clients', native_dialogues)
        events = admin_request(state/'transport/world.sock',
                               dict(command='events_since', cursor=before_revision, limit=64))
        require(events.get('ok') and not events['has_more'] and len(events['events']) == 1,
                'trainer interaction must commit exactly one durable event')
        event = events['events'][0]
        require(event['kind'] == 'interaction' and event['data'] == dict(
            kind='trainer', player='alice', target='bob', signal='explore',
            group=bob.state.map[0], num=bob.state.map[1], x=bx, y=by),
            'durable trainer interaction event mismatch')
        # Held A cannot create a second event or retrigger the native modal.
        alice.press('A', 90)
        pump()
        repeated = admin_request(state/'transport/world.sock',
                                 dict(command='events_since', cursor=before_revision, limit=64))
        require(repeated == events, 'held A duplicated the trainer interaction')
        for game in active:
            game.wait(180)
            for _ in range(8):
                if not game.telemetry().get('dialogue_active'):
                    break
                game.tap('B', hold=1, gap=20)
        dismissed = wait_for('trainer dialogue closes and unlocks both native clients', lambda:
            [g.telemetry() for g in active] if all(
                not g.telemetry().get('dialogue_active') and g.state.free for g in active) else False)
        record('trainer_interaction', dict(opened=opened, host=interaction_host,
               durable_events=events, held_a_readback=repeated, dismissed=dismissed))
    except BaseException as error:
        report['error'] = dict(type=type(error).__name__, message=str(error), traceback=traceback.format_exc())
        print('FAIL ' + str(error), file=sys.stderr, flush=True)
    finally:
        for game in engines:
            try:
                code = game.stop()
                report.setdefault('native_exit_codes', []).append(dict(pid=game.proc.pid, logs=game.out_dir, exitcode=code))
            except BaseException as error:
                report.setdefault('cleanup_errors', []).append(repr(error))
        for session in sessions:
            try:
                session.close()
            except BaseException as error:
                report.setdefault('cleanup_errors', []).append(repr(error))
        if 'seed_sha256' in report and seed.is_file():
            unchanged = sha(seed) == report['seed_sha256']
            report['checks'].append(dict(name='seed_unchanged', ok=unchanged, evidence=dict(sha256=sha(seed))))
        exits = report.get('native_exit_codes', [])
        report['checks'].append(dict(name='native_exitcodes', ok=bool(exits) and all(e['exitcode'] == 0 for e in exits), evidence=exits))
        passed = {c['name'] for c in report['checks'] if c['ok']}
        report['missing_or_failed'] = [name for name in REQUIRED if name not in passed]
        report['ok'] = not report['missing_or_failed'] and 'error' not in report and not report.get('cleanup_errors')
        flush()
    print(json.dumps(dict(ok=report['ok'], evidence=str(out/'acceptance.json'),
                          missing_or_failed=report['missing_or_failed'])), flush=True)
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
