"""Two actual native processes, real world socket, authored XL map; no model calls."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import tempfile
import time
import driver
from world.session import DesktopSession
from world.xl_wilds import encode
from world.shared_cave import SharedCave


def run(binary, seed, out):
    binary, seed, out = [Path(p).resolve() for p in (binary, seed, out)]
    out.mkdir(parents=True, exist_ok=True)
    blob = encode({'rows': ['#'*127]+['#'+'.'*125+'#']*125+['#'*127], 'spawn': [1,1], 'exit': [125,125]})
    digest = hashlib.sha256(seed.read_bytes()).hexdigest()
    report = {'ok': False, 'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
              'seed_sha256': digest, 'area_identity': SharedCave(blob).identity,
              'scope': 'two native test-input processes with real authority sockets; authored geometry, no model generation or battle coverage'}
    games = []
    with tempfile.TemporaryDirectory(prefix='rc8xl-') as temp:
        root = Path(temp)
        session = DesktopSession(root)
        try:
            session.create_world('w')
            session.host('w')
            session.server._replace_cave(blob, label='RC8 socket acceptance')
            assert session.server.shared_cave.identity == report['area_identity']
            origins = []
            for name in ('Alice', 'Bob'):
                paths = session.local_profile(name, seed)
                wrapper = root/name
                wrapper.write_text('#!/bin/sh\nexec '+shlex.quote(str(binary))+' --world-config '+shlex.quote(str(paths['config']))+' "$@"\n')
                wrapper.chmod(0o700)
                game = driver.Game(str(wrapper), str(out/name), save=str(seed), max_frames=60000)
                games.append(game)
                driver.continue_game(game)
                driver.walk_to(game, 6, 11)
                driver.leave_map(game, 'DOWN')
                driver.wait_until(game, lambda s: s.free)
                origins.append((tuple(game.state.map), game.state.pos))
                # Let the actual client and authority exchange capabilities/map/admission.
                for _ in range(20):
                    game.wait(12)
                    time.sleep(.015)
                game.tap('START', gap=30)
                game.tap('DOWN', times=5)
                game.tap('A', gap=60)
                game.tap('DOWN', times=2)
                game.tap('A', gap=90)
                driver.wait_until(game, lambda s: s.map_name == 'GeneratedWorld_Wilds' and s.free)
            def pump():
                for game in games:
                    game.wait(12)
                time.sleep(.025)
            for _ in range(30):
                pump()
            # Use ordinary button movement; no teleporting or save injection.
            for game, target in zip(games, (70, 71)):
                for _ in range(160):
                    if game.state.pos == (target, 1):
                        break
                    driver.wait_until(game, lambda s: s.free or s.battle)
                    if game.state.battle:
                        from large_cave_playthrough import flee
                        flee(game)
                    game.press('RIGHT', 8)
                    game.wait(8)
                    for other in games:
                        if other is not game:
                            other.wait(16)
                    time.sleep(.005)
                assert game.state.pos == (target, 1), str(game.state)
                driver.wait_until(game, lambda s: s.free or s.battle)
                if game.state.battle:
                    from large_cave_playthrough import flee
                    flee(game)
                driver.wait_until(game, lambda s: s.free)
            for _ in range(30):
                pump()
            with session.server.lock:
                peers = {p['id']: {'state': p.get('state'), 'ack': p.get('cave_ack')} for p in session.server.peers.values() if p.get('id')}
            assert len(peers) == 2, peers
            for p in peers.values():
                assert p['ack'] == report['area_identity'] and p['state'][2] >= 70, peers
            a, b = games
            assert b.state.pos in a.state.objects and a.state.pos in b.state.objects, (a.state.objects, b.state.objects)
            report['two_native_positions'] = [g.state.pos for g in games]
            report['mutual_peer_objects'] = [g.state.objects for g in games]
            for game, origin in zip(games, origins):
                game.tap('START', gap=30)
                game.tap('UP')
                game.tap('A', gap=60)
                game.tap('UP')
                game.tap('A', gap=90)
                driver.wait_until(game, lambda s: tuple(s.map) == origin[0] and s.free)
                assert game.state.pos == origin[1], str(game.state)
            report['returned_to_private_origins'] = True
            report['ok'] = True
        finally:
            codes = [g.finish() for g in games]
            session.disconnect()
            report['exit_codes'] = codes
            report['save_hashes'] = [hashlib.sha256(Path(g.save_path).read_bytes()).hexdigest() for g in games]
            (out/'acceptance.json').write_text(json.dumps(report, indent=2)+'\n')
    assert all(code == 0 for code in codes), codes
    assert report['save_hashes'] == [digest, digest], report
    assert hashlib.sha256(seed.read_bytes()).hexdigest() == digest
    print('PASS: two real native clients admitted the same XL area, walked beyond x=63, rendered each other, and returned without changing saves')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True)
    parser.add_argument('--seed-save', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    run(args.binary, args.seed_save, args.out)
