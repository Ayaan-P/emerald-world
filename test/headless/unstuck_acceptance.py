#!/usr/bin/env python3
"""Exercise offline Unstuck on a disposable early-game native save.

Uses the ordinary headless input API, no world connection, no network and no
personal files. Does not claim online or graphical acceptance.
"""
import argparse
import hashlib
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
    args = parser.parse_args()
    seed = args.seed.resolve()
    digest = hashlib.sha256(seed.read_bytes()).hexdigest()
    data = savecheck.Save(seed).saveblock1
    group, num, warp, spawn_x, spawn_y = struct.unpack_from('<bbbxhh', data, 0x1C)
    assert group >= 0 and num >= 0 and warp == -1
    game = None
    with tempfile.TemporaryDirectory(prefix='ew-unstuck-') as tmp:
        try:
            game = driver.Game(str(args.binary.resolve()), str(Path(tmp)/'game'), save=str(seed))
            driver.continue_game(game)
            driver.walk_to(game, 6, 11)
            driver.leave_map(game, "DOWN")  # The lab itself is not an allowed departure.
            original = (tuple(game.state.map), game.state.pos)
            assert original[0] != (group,num), 'fixture must start away from last heal map'
            saved_hash = hashlib.sha256(Path(game.save_path).read_bytes()).hexdigest()
            sidecar = Path(game.save_path + '.unstuck')
            game.tap('START'); game.tap('UP',times=2); game.tap('A'); game.wait(120)
            game.tap('B'); game.wait(80)  # default No: return to the menu
            assert not sidecar.exists() and (tuple(game.state.map),game.state.pos)==original
            game.tap('A'); game.wait(120); game.tap('UP'); game.tap('A')
            driver.wait_until(game, lambda s: s.free and tuple(s.map)==(group,num), step=10, limit=5000)
            assert abs(game.state.pos[0]-spawn_x)+abs(game.state.pos[1]-spawn_y)<=2
            assert sidecar.is_file() and len(sidecar.read_bytes())==32
            assert hashlib.sha256(Path(game.save_path).read_bytes()).hexdigest()==saved_hash
            assert hashlib.sha256(seed.read_bytes()).hexdigest()==digest
            destination=(tuple(game.state.map),game.state.pos)
            game.tap('START'); game.tap('A'); game.wait(120); game.tap('UP'); game.tap('A'); game.wait(120)
            # The cooldown refusal leaves the player in place; dismiss the message and menu.
            game.tap('A'); game.wait(60); game.tap('B'); game.wait(60)
            assert (tuple(game.state.map),game.state.pos)==destination
            assert hashlib.sha256(Path(game.save_path).read_bytes()).hexdigest()==saved_hash
            assert game.finish()==0; game=None
            print('PASS: offline Unstuck cancel, confirmed return, cooldown and unchanged save/seed')
        finally:
            if game is not None and game.proc.poll() is None:
                game.proc.kill(); game.proc.wait()
    return 0

if __name__ == '__main__':
    sys.exit(main())
