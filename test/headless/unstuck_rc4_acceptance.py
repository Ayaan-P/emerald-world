#!/usr/bin/env python3
"""RC4 native-input Unstuck acceptance. Requires the parent's wired binary.

Use a disposable first_battle scenario seed. No world server is launched.
The WORLD recovery row is zero-based and configurable after menu integration.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'test/headless'))
import driver
import savecheck


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--seed', type=Path, required=True)
    parser.add_argument('--world-row', type=int, default=8)
    parser.add_argument('--out', type=Path, default=ROOT / 'build/rc4-unstuck/native')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    seed = args.seed.resolve()
    digest = hashlib.sha256(seed.read_bytes()).hexdigest()
    data = savecheck.Save(seed).saveblock1
    group, num, warp, spawn_x, spawn_y = struct.unpack_from('<bbbxhh', data, 0x1C)
    assert group >= 0 and num >= 0 and warp == -1
    game = None
    result = {'native_acceptance': 'FAIL', 'world_row': args.world_row}
    try:
        # Driver copies the seed. Neither a launcher profile nor HOME is used.
        with tempfile.TemporaryDirectory(prefix='profile-', dir=args.out.resolve()) as tmp:
            game = driver.Game(str(args.binary.resolve()), str(Path(tmp)/'game'), save=str(seed))
            driver.continue_game(game)
            driver.walk_to(game, 6, 11)
            driver.leave_map(game, 'DOWN')
            driver.wait_until(game, lambda s: s.free)
            original = (tuple(game.state.map), game.state.pos)
            assert original[0] != (group, num), 'fixture must start away from its last heal map'
            saved_hash = hashlib.sha256(Path(game.save_path).read_bytes()).hexdigest()
            sidecar = Path(game.save_path + '.unstuck')

            opened = False
            def open_recovery():
                nonlocal opened
                # Start remembers WORLD after the first open. WORLD itself
                # clamps Up, so normalize its feature focus before selecting.
                game.tap('START'); game.wait(60)
                if not opened:
                    game.tap('UP', times=2)
                game.tap('A'); game.wait(80)
                game.tap('UP', times=20)
                game.tap('DOWN', times=args.world_row); game.tap('A'); game.wait(80)
                opened = True

            open_recovery()
            game.tap('B'); game.wait(60)  # explicit cancellation, never reserve
            assert not sidecar.exists()
            assert (tuple(game.state.map), game.state.pos) == original
            # Integration returns to WORLD features on cancellation.
            game.tap('A'); game.wait(80); game.tap('UP'); game.tap('A')
            driver.wait_until(game, lambda s: s.free and tuple(s.map)==(group,num), step=10, limit=5000)
            assert abs(game.state.pos[0]-spawn_x)+abs(game.state.pos[1]-spawn_y)<=2
            assert sidecar.is_file() and len(sidecar.read_bytes())==41
            assert sidecar.read_bytes().startswith(b'EWUNSTUCK2 ')
            assert hashlib.sha256(Path(game.save_path).read_bytes()).hexdigest()==saved_hash
            assert hashlib.sha256(seed.read_bytes()).hexdigest()==digest
            destination=(tuple(game.state.map),game.state.pos)
            open_recovery(); game.tap('UP'); game.tap('A'); game.wait(120)
            assert (tuple(game.state.map),game.state.pos)==destination
            game.tap('B'); game.wait(40); game.tap('B'); game.wait(40)
            assert hashlib.sha256(Path(game.save_path).read_bytes()).hexdigest()==saved_hash
            assert game.finish()==0
            game=None
            result.update(native_acceptance='PASS', arrival=list(destination[0])+list(destination[1]),
                          checked=['cancel','confirmed native warp','repeat request did not move','unchanged seed/save'],
                          limitation='This indoor seed does not isolate cooldown refusal from indoor-departure refusal.')
    except BaseException as error:
        result['error'] = str(error)
        if game is not None:
            result['last_state'] = repr(game.state)
        raise
    finally:
        if game is not None and game.proc.poll() is None:
            game.proc.kill(); game.proc.wait()
        (args.out / 'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
    return 0

if __name__ == '__main__':
    sys.exit(main())
