"""Disposable two-native-client Friends UI acceptance, without forced gameplay.

Uses an ordinary early-game headless save. This checks the visible menu and
rejection/cleanup path, not earned Fly gameplay or native WAN acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'test/headless'))
sys.path.insert(0, str(ROOT / 'test/world'))
import driver
from native_acceptance import Engine
from world.server import WorldServer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--seed-save', type=Path, required=True)
    args = parser.parse_args()
    seed_hash = hashlib.sha256(args.seed_save.read_bytes()).hexdigest()
    games = []
    with tempfile.TemporaryDirectory(prefix='ew-fly-') as directory:
        state = Path(directory)
        (state / 'transport').mkdir()
        server = WorldServer(str(state / 'transport/world.sock'), str(state)).start()
        try:
            for name in ('alice', 'bob'):
                game = Engine(args.binary.resolve(), state, name, args.seed_save.resolve())
                games.append(game)
                driver.continue_game(game)
            for _ in range(60):
                for game in games:
                    game.wait(6)
                time.sleep(.01)
                if len(server.inspect()['players']) == 2:
                    break
            alice, bob = games
            assert alice.telemetry()['travel']['phase'] == 'idle'
            before = [hashlib.sha256(g.paths['save'].read_bytes()).hexdigest() for g in games]
            alice.tap('START')
            # Friends is immediately above EXIT in the native pause menu.
            # Go to EXIT by wrapping UP from the first row, then one row UP.
            alice.tap('UP', times=2)
            alice.tap('A')
            assert alice.telemetry()['travel']['phase'] == 'friends', alice.telemetry()
            alice.tap('A')
            assert alice.telemetry()['travel']['phase'] == 'confirm', alice.telemetry()
            alice.tap('UP')  # confirmation defaults to Cancel
            alice.tap('A')
            travel = alice.telemetry()['travel']
            assert travel['phase'] == 'message', travel
            assert travel['status'] in ('You need the Feather Badge.', 'A Pokemon must know Fly.'), travel
            alice.tap('B')
            alice.tap('B')
            assert alice.telemetry()['travel']['phase'] == 'idle'
            # Closing restores ordinary field controls without saving either trainer.
            assert alice.state.free, alice.state
            alice.tap('START')
            alice.tap('A')  # pause cursor remains on Friends
            assert alice.telemetry()['travel']['phase'] == 'friends'
            alice.press('A+B+START+SELECT', 2)
            alice.wait(2)
            driver.continue_game(alice)
            assert alice.telemetry()['travel']['phase'] == 'idle'
            assert alice.state.free, alice.state
            assert [hashlib.sha256(g.paths['save'].read_bytes()).hexdigest() for g in games] == before
            for game in games:
                assert game.finish() == 0
            games.clear()
            assert hashlib.sha256(args.seed_save.read_bytes()).hexdigest() == seed_hash
            print(json.dumps({'ok': True, 'checks': ['two native clients', 'native pause Friends menu',
                'Fly confirmation', 'private eligibility rejection', 'cancel restores controls', 'menu soft reset/rejoin',
                'no save writes', 'fixture seed unchanged', 'all native processes reaped']}))
        finally:
            for game in games:
                if game.proc.poll() is None:
                    game.finish()
            server.close()


if __name__ == '__main__':
    main()
