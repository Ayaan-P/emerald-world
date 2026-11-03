"""Four disposable native clients. Requires an explicit generated smoke fixture.

Run with EMERALD_WORLD_BINARY and EMERALD_WORLD_SAVE. Never reads user saves.
"""
from contextlib import ExitStack
import hashlib
import os
import subprocess
from pathlib import Path
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'test/world'))
from native_acceptance import Engine as BaseEngine, driver
from world.server import WorldServer


class Engine(BaseEngine):
    """Own native children even when the initial state read fails."""
    def __init__(self, *args):
        try:
            super().__init__(*args)
        except BaseException:
            self._close(check=False)
            raise

    def _close(self, check):
        proc = getattr(self, 'proc', None)
        forced = False
        try:
            if proc is not None:
                if proc.stdin is not None:
                    try:
                        proc.stdin.close()
                    except OSError:
                        # A child that already exited may have broken its pipe.
                        pass
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    forced = True
                    proc.terminate()
                    try:
                        proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=2)
        finally:
            for stream in (getattr(proc, 'stdout', None), getattr(proc, 'stderr', None),
                           getattr(self, 'stderr', None), getattr(self, 'states', None)):
                if stream is not None:
                    stream.close()
        if check and proc is not None and (forced or proc.returncode != 0):
            raise AssertionError(f'native shutdown failed: forced={forced}, status={proc.returncode}')
        return proc.returncode if proc is not None else None

    def finish(self):
        return self._close(check=True)


@unittest.skipUnless(os.environ.get('EMERALD_WORLD_BINARY') and os.environ.get('EMERALD_WORLD_SAVE'),
                     'requires native binary and generated first_battle fixture')
class NativePresence(unittest.TestCase):
    def test_constructor_failure_reaps_native_process_and_closes_streams(self):
        class BrokenEngine(Engine):
            def _read_state(self):
                raise RuntimeError('deliberate initial-state failure')

        with tempfile.TemporaryDirectory(prefix='ewp-') as tmp:
            root = Path(tmp)/'world'
            root.mkdir(mode=0o700)
            (root/'transport').mkdir()
            engine = BrokenEngine.__new__(BrokenEngine)
            try:
                with self.assertRaisesRegex(RuntimeError, 'deliberate initial-state failure'):
                    engine.__init__(Path(os.environ['EMERALD_WORLD_BINARY']), root, 'alice',
                                    Path(os.environ['EMERALD_WORLD_SAVE']))
                self.assertIsNotNone(engine.proc.poll())
                for stream in (engine.proc.stdin, engine.proc.stdout, engine.stderr, engine.states):
                    self.assertTrue(stream.closed)
            finally:
                if engine.proc.poll() is None:
                    engine.proc.kill()
                engine.proc.wait(timeout=5)
                for stream in (engine.proc.stdin, engine.proc.stdout, engine.stderr, engine.states):
                    stream.close()

    def test_four_trainers_remain_visible_while_moving_and_using_menus(self):
        seed = Path(os.environ['EMERALD_WORLD_SAVE']).resolve()
        digest = hashlib.sha256(seed.read_bytes()).digest()
        with tempfile.TemporaryDirectory(prefix='ewp-') as tmp, ExitStack() as stack:
            root = Path(tmp)/'world'
            root.mkdir(mode=0o700)
            (root/'transport').mkdir()
            server = WorldServer(root/'transport/world.sock', root).start()
            stack.callback(server.close)
            games = []
            for name in ('alice', 'bob', 'carol', 'dave'):
                game = Engine(Path(os.environ['EMERALD_WORLD_BINARY']), root, name, seed)
                games.append(game)
                stack.callback(game.finish)
                driver.continue_game(game)

            def pump():
                for game in games:
                    if game.proc.poll() is None:
                        game.wait(6)
                time.sleep(.005)

            def expect_peers(game, names):
                peers = {}
                for _ in range(80):
                    pump()
                    peers = {p['trainer']: p for p in game.telemetry()['peers']}
                    if set(peers) == set(names):
                        self.assertTrue(all(p['visible'] for p in peers.values()))
                        self.assertEqual(len({p['object_id'] for p in peers.values()}), len(peers))
                        self.assertEqual(len({p['sprite_id'] for p in peers.values()}), len(peers))
                        return peers
                self.fail(f'expected {names}, got {peers}')

            for game in games:
                expect_peers(game, {g.telemetry()['trainer'] for g in games if g is not game})

            # Opening START must not make the trainer vanish on other screens.
            games[0].tap('START')
            self.assertFalse(games[0].state.free)
            peers = expect_peers(games[1], {'alice', 'carol', 'dave'})
            self.assertEqual(peers['alice']['pos'], list(games[0].state.pos))
            self.assertEqual({p['trainer'] for p in games[0].telemetry()['peers']}, {'bob', 'carol', 'dave'})
            alice = next(p for p in server.inspect()['players'] if p['id'] == 'alice')
            self.assertEqual(alice['ready'], 0)
            self.assertEqual([alice['x'], alice['y']], list(games[0].state.pos))
            # Opening POKEMON replaces the local sprite pool. The remote field
            # position must remain, without retaining stale local sprite handles.
            games[0].tap('A', gap=100)
            self.assertFalse(games[0].state.overworld)
            expect_peers(games[1], {'alice', 'carol', 'dave'})
            games[0].tap('B', gap=120)
            games[0].tap('B', gap=60)
            driver.wait_until(games[0], lambda s: s.free)
            expect_peers(games[0], {'bob', 'carol', 'dave'})

            # Native event scripts own the finite object pool. Visual peers
            # may not consume slots needed by a later scripted addobject.
            games[0].press('UP', 1)
            games[0].wait(20)
            games[0].tap('A')
            self.assertTrue(games[0].state.script)
            self.assertEqual(games[0].telemetry()['peers'], [])
            expect_peers(games[1], {'carol', 'dave'})
            driver.finish_dialog(games[0])
            expect_peers(games[0], {'bob', 'carol', 'dave'})

            # Inspect each movement sample, not just the settled endpoint.
            games[0].press('DOWN', 16)
            games[0].wait(24)
            before_walk = games[0].state.pos
            for _ in range(12):
                games[0].press('LEFT', 1)
                for other in games[1:]:
                    other.wait(6)
                time.sleep(.005)
                for observer in games[1:]:
                    peers = {p['trainer']: p for p in observer.telemetry()['peers']}
                    self.assertIn('alice', peers, 'walking trainer flickered out')
                    self.assertTrue(peers['alice']['visible'])
                alice = next(p for p in server.inspect()['players'] if p['id'] == 'alice')
                self.assertEqual(alice['ready'], 1, 'walking must retain authoritative presence readiness')
            games[0].wait(24)
            self.assertNotEqual(games[0].state.pos, before_walk, 'movement probe was blocked')
            peers = expect_peers(games[1], {'alice', 'carol', 'dave'})
            self.assertEqual(peers['alice']['pos'], list(games[0].state.pos))

            # Use Emerald's real doors and map connections. No state injection.
            for game in games[:2]:
                driver.walk_to(game, 6, 11)
                driver.leave_map(game, 'DOWN')
                self.assertEqual(game.state.map_name, 'LittlerootTown')
                if game is games[0]:
                    expect_peers(games[1], {'carol', 'dave'})
                driver.walk_to(game, 11, 0)
                driver.leave_map(game, 'UP')
                self.assertEqual(game.state.map_name, 'Route101')
                driver.walk_to(game, 10 if game is games[0] else 6,
                               19 if game is games[0] else 17)
            expect_peers(games[1], {'alice'})
            expect_peers(games[2], {'dave'})

            # Do not use finish_dialog's automatic battle handling while
            # seeking an encounter. Directional input cannot resolve a battle.
            driver.walk_to(games[0], 5, 17)
            for index in range(120):
                games[0].press('LEFT' if index % 2 == 0 else 'RIGHT', 16)
                if games[0].state.battle:
                    break
            self.assertTrue(games[0].state.battle, 'normal grass walking did not reach a wild battle')
            expect_peers(games[1], set())
            self.assertEqual(games[0].telemetry()['peers'], [])
            driver.fight_battle(games[0])
            self.assertEqual(games[0].state.map_name, 'Route101')
            expect_peers(games[1], {'alice'})
            driver.walk_to(games[0], 11, 19)
            driver.leave_map(games[0], 'DOWN')
            driver.walk_to(games[0], 7, 16)
            driver.wait_until(games[0], lambda s: s.free)
            self.assertEqual(games[0].state.map_name, 'LittlerootTown_ProfessorBirchsLab')
            expect_peers(games[2], {'alice', 'dave'})

            # A real client exit removes the object. Returning with its private
            # fixture save creates a fresh object, without duplicate handles.
            games[3].finish()
            expect_peers(games[2], {'alice'})
            replacement = Engine(Path(os.environ['EMERALD_WORLD_BINARY']), root, 'dave', None)
            games[3] = replacement
            stack.callback(replacement.finish)
            driver.continue_game(replacement)
            expect_peers(games[2], {'alice', 'dave'})
            expect_peers(replacement, {'alice', 'carol'})
        self.assertEqual(hashlib.sha256(seed.read_bytes()).digest(), digest)


if __name__ == '__main__':
    unittest.main()
