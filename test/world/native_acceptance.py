"""Exercise actual native Emerald clients, not simulated world clients.

Run only with disposable test saves. All evidence goes to --state-dir outside repo.
An external model response is requested AFTER both native clients are running.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'test/headless'))
import driver
import savecheck
from world.launcher import prepare_profile, game_command
from world.server import WorldServer
from world.client import admin_request, WorldClient


def fixture(seed, destination, trainer):
    """Checksum-correct copied fixtures differ in nickname and bag, not game code."""
    data = bytearray(Path(seed).read_bytes())
    save = savecheck.Save(seed)
    sizes = savecheck.chunk_sizes()
    for index in range(save.slot * 14, (save.slot + 1) * 14):
        start = index * 0x1000
        sector_id = struct.unpack_from('<H', data, start + 0xFF4)[0]
        if sector_id == 0:
            name = trainer.upper()[:7]
            data[start:start+8] = bytes([0xBB + ord(c)-ord('A') for c in name] + [0xFF] * (8-len(name)))
        if sector_id == 1:
            # Nickname is outside the Pokemon encrypted substructure checksum.
            name = ('START' + trainer.upper())[:10]
            data[start+0x238+8:start+0x238+18] = bytes([0xBB + ord(c)-ord('A') for c in name] + [0xFF] * (10-len(name)))
            key = struct.unpack_from('<I', save.saveblock2, 0xAC)[0] & 0xFFFF
            struct.pack_into('<HH', data, start+0x560, 13, (2 if trainer == 'alice' else 5) ^ key)
        chk = savecheck.checksum(data[start:start+0x1000], sizes[sector_id])
        struct.pack_into('<H', data, start+0xFF6, chk)
    Path(destination).write_bytes(data)
    savecheck.Save(destination)


class Engine(driver.Game):
    def __init__(self, binary, state_dir, trainer, seed):
        paths = prepare_profile(state_dir, trainer)
        if seed is not None:
            fixture(seed, paths['save'], trainer)
        self.paths = paths
        self.out_dir = str(paths['profile'])
        self.save_path = str(paths['save'])
        self.hashes_path = str(paths['profile']/'hashes.txt')
        self.max_frames = 200000
        self.stderr = (paths['profile']/'stderr.txt').open('w')
        self.states = (paths['profile']/'states.jsonl').open('w')
        self.steps = []; self.frames = 0
        command = game_command(binary, state_dir, paths)
        command += ['--test-input', '-', '--test-state', '-', '--test-hashes', self.hashes_path,
                    '--test-shots', str(paths['profile'])]
        (paths['profile']/'command.json').write_text(json.dumps(command, indent=2))
        self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=self.stderr, text=True, bufsize=1)
        self.state = self._read_state()

    def _read_state(self):
        ready, _, _ = select.select([self.proc.stdout], [], [], 20)
        if not ready:
            raise RuntimeError(f'native engine state timeout, status={self.proc.poll()}, stderr={self.out_dir}/stderr.txt')
        return super()._read_state()

    def telemetry(self):
        return json.loads(self.paths['telemetry'].read_text())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state-dir', type=Path, required=True)
    p.add_argument('--binary', type=Path, default=ROOT/'build/pokeemerald64')
    p.add_argument('--seed-save', type=Path, required=True)
    p.add_argument('--response-file', type=Path, required=True)
    p.add_argument('--author-wait', type=float, default=240)
    a = p.parse_args()
    state = a.state_dir.resolve()
    state.mkdir(parents=True, exist_ok=False)
    (state/'transport').mkdir()
    sock = state/'transport/world.sock'
    server = WorldServer(str(sock), str(state)).start()
    games = []
    evidence = {'binary': str(a.binary), 'binary_sha256': hashlib.sha256(a.binary.read_bytes()).hexdigest(),
                'seed_sha256': hashlib.sha256(a.seed_save.read_bytes()).hexdigest(), 'checks': []}
    def record(name, value):
        evidence['checks'].append({'name': name, 'value': value})
        (state/'acceptance.json').write_text(json.dumps(evidence, indent=2))
        print('PASS', name, flush=True)
    def pump(count=1):
        for _ in range(count):
            for game in games:
                if game.proc.poll() is None: game.wait(6)
            time.sleep(.01)
    def await_world(predicate, name, attempts=120):
        for _ in range(attempts):
            pump()
            snapshot = server.inspect()
            if predicate(snapshot):
                record(name, snapshot); return snapshot
        raise AssertionError(name + ': ' + json.dumps(server.inspect()))
    try:
        for trainer in ['alice','bob']:
            game = Engine(a.binary.resolve(), state, trainer, a.seed_save.resolve())
            games.append(game)
            driver.continue_game(game)
        games[0].press('LEFT', 16); games[0].wait(12)
        games[1].press('RIGHT', 16); games[1].wait(12)
        snapshot = await_world(lambda s: len(s['players']) == 2 and all(p.get('ready') for p in s['players']), 'independent native sessions authenticated')
        assert len({p['party_hash'] for p in snapshot['players']}) == 2
        assert len({p['bag_hash'] for p in snapshot['players']}) == 2
        ownership = {p['id']:(p['party_hash'],p['bag_hash']) for p in snapshot['players']}
        record('distinct party and bag ownership in actual native clients', ownership)
        for _ in range(100):
            pump()
            if all(g.telemetry().get('peers') for g in games): break
        for i,g in enumerate(games):
            t = g.telemetry(); peer = t['peers'][0]
            assert peer['trainer'] == ('bob' if i == 0 else 'alice')
            assert peer['visible']
            assert peer['pos'] == list(games[1-i].state.pos)
            assert peer['object_id'] != 0xFF and peer['sprite_id'] != 0xFF
        record('real remote object-event sprites visible both ways', [g.telemetry() for g in games])
        old = games[1].state.pos
        games[1].press('RIGHT',16); games[1].wait(12); pump(6)
        assert games[1].state.pos != old
        assert games[0].telemetry()['peers'][0]['pos'] == list(games[1].state.pos)
        record('independent native movement replicated', [g.telemetry() for g in games])
        # Both face south to start. Bob north later arms the newly authored gate.
        games[0].press('DOWN',1); games[0].wait(12)
        games[1].press('DOWN',1); games[1].wait(12); pump(4)
        x,y = games[0].state.pos
        challenge = {'request': f'Create a new persistent two-trainer north-signal gate in map 1.4. Tile ({x},{y+1}) must visibly use metatile 1 and block movement (collision=1) initially. When two ready trainers are on map 1.4 and trainer bob faces UP (facing=2), permanently latch this gate open (collision=0). Alice can then walk south across it. Preserve the latch through disconnect and service restart, including when zero players are present. Implement new executable logic, not a fixed command. Initial state may be empty. Return JSON source/tests. Tests must cover initial blocking, single trainer cannot open, two trainer north opening, and persistent latch. Tests have update injected; no import mechanic.',
                     'inspection': server.inspect(), 'target': [1,4,x,y+1], 'native_pids': [g.proc.pid for g in games]}
        (state/'author-request.json').write_text(json.dumps(challenge, indent=2))
        print('WORLD_AUTHOR_READY ' + str(state/'author-request.json'), flush=True)
        deadline = time.monotonic() + a.author_wait
        while True:
            try:
                response = json.loads(a.response_file.read_text())
                if (type(response) is dict and set(response) == {'source', 'tests'}
                        and all(type(v) is str and v.strip() for v in response.values())):
                    break
            except (OSError, ValueError):
                pass
            if time.monotonic() > deadline: raise TimeoutError('complete genuine model response not supplied before deadline')
            pump(2)
        from world.gm import author_and_deploy
        report = author_and_deploy(state, sock, challenge['request'], None, response_file=a.response_file)
        assert report.get('ok'), report
        revision = server.inspect()['module_hash']
        record('new model-authored code deployed while native clients stay alive', report)
        await_world(lambda s: bool(s['tiles']) and s['tiles'][0][-1] == 1, 'new gate starts blocked')
        pump(8)
        before = games[0].state.pos
        games[0].press('DOWN',32); games[0].wait(12); pump(8)
        assert games[0].state.pos == before, (games[0].state, before)
        assert all(g.telemetry()['tiles'][0]['collision']==1 for g in games)
        record('blocked tile affects actual native collision', [g.telemetry() for g in games])
        games[1].press('UP',1); games[1].wait(12)
        await_world(lambda s: bool(s['tiles']) and s['tiles'][0][-1] == 0, 'bob north signal opens new shared gate')
        pump(8)
        assert all(g.telemetry()['tiles'][0]['collision']==0 for g in games)
        games[0].press('DOWN',16); games[0].wait(12); pump(5)
        assert games[0].state.pos[1] > before[1], (games[0].state, before)
        record('new executable mechanic changes real traversal in both clients', [g.telemetry() for g in games])
        token = server.create_identity('badpeer')['token']
        offender = WorldClient(sock, 'badpeer', token)
        try:
            try:
                offender.send_state(1,255,255,0,0,0,65535,0,'0'*16,'0'*16)
            except (EOFError, ValueError, ConnectionError, OSError):
                pass
            pump(12)
            assert all(g.telemetry()['connected'] for g in games)
            assert {p['id'] for p in server.inspect()['players']} == {'alice','bob'}
        finally:
            offender.close()
        record('malformed authenticated peer cannot disconnect actual native clients', [g.telemetry() for g in games])
        for label,tile in [('nonexistent-map',(255,255,0,0,1,1)),('sparse-tileset',(1,0,0,0,511,1))]:
            invalid = state/f'candidates/rejected-{label}.py'
            invalid.write_text("def update(context,state):\n return {'state':state,'tiles':[dict(zip(('group','num','x','y','metatile','collision'),"+repr(tile)+"))]}\n")
            rejected = admin_request(sock, {'command':'deploy','source_path':str(invalid)})
            assert not rejected['ok'] and server.inspect()['module_hash']==revision, rejected
            pump(5)
            assert all(g.telemetry()['connected'] for g in games)
            record(label+' candidate rejected without breaking actual native clients', rejected)
        bad = state/'candidates/rejected.py'; bad.write_text('def update(context,state):\n raise RuntimeError("deliberate rejected candidate")\n')
        result = admin_request(sock, {'command':'deploy','source_path':str(bad)})
        assert not result['ok'] and server.inspect()['module_hash']==revision
        record('bad candidate rejected and last-good mechanic preserved', result)
        saved_state = server.inspect()['state']
        server.close(); server = WorldServer(str(sock),str(state)).start()
        await_world(lambda s: len(s['players'])==2 and s['module_hash']==revision and s['state']==saved_state, 'service restart reconnect preserves code and durable mechanic state')
        assert server.inspect()['tiles'][0][-1] == 0
        for p in server.inspect()['players']:
            assert (p['party_hash'],p['bag_hash'])==ownership[p['id']]
        record('ownership unchanged through live mechanic and restart', server.inspect())
        # Use the real Emerald start menu and flash writer, then inspect the GBA save.
        telemetry = games[0].telemetry()
        if telemetry['tiles']:
            overlay = telemetry['tiles'][0]
        else:
            restored = [tile for tile in telemetry['restored_tiles']
                        if tile['pos'] == [5, 6]]
            assert restored, telemetry
            overlay = {'pos': restored[0]['pos'], 'original': restored[0]['original']}
        driver.save_game(games[0],3)
        games[0].wait(120)
        saved = savecheck.Save(games[0].save_path)
        objects = [saved.saveblock1[0xA30+i*0x24:0xA30+(i+1)*0x24] for i in range(16)]
        assert not any(obj[0]&1 and 224 <= obj[8] < 255 for obj in objects), 'remote trainer leaked into GBA save'
        index = (overlay['pos'][1]+7-saved.position[1])*15 + (overlay['pos'][0]+7-saved.position[0])
        assert 0 <= index < 256
        raw = struct.unpack_from('<H',saved.saveblock1,0x34+index*2)[0]
        assert raw == overlay['original'], (raw,overlay)
        key = struct.unpack_from('<I',saved.saveblock2,0xAC)[0]&0xFFFF
        item,quantity = struct.unpack_from('<HH',saved.saveblock1,0x560)
        assert item==13 and quantity^key==2
        record('actual Emerald save excludes shared tiles and remote trainers and retains own bag',
               {'save':games[0].save_path,'map':saved.map,'pos':saved.position,'saved_gate_raw':raw,
                'original_gate_raw':overlay['original'],'potion_quantity':quantity^key})
        assert hashlib.sha256(a.seed_save.read_bytes()).hexdigest()==evidence['seed_sha256']
        evidence['ok']=True
    except BaseException as exc:
        evidence['ok']=False; evidence['error']=repr(exc)
        raise
    finally:
        for g in games:
            try:
                status=g.finish()
                evidence.setdefault('native_exit_codes',[]).append(status)
            except Exception:
                g.proc.kill(); g.proc.wait()
        server.close()
        (state/'acceptance.json').write_text(json.dumps(evidence,indent=2))
    print('ALL NATIVE WORLD ACCEPTANCE CHECKS PASSED',flush=True)

if __name__=='__main__': main()
