"""Scripted real-native admission checks. Explicit generated fixture required.

This is headless multiplayer execution, not interactive human/GUI acceptance.
No personal save discovery, remote connections or new dependencies.
"""
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'test/world'))
from test_native_presence import Engine, driver
from world.client import admin_request
from world.server import WorldServer


@unittest.skipUnless(os.environ.get('EMERALD_WORLD_BINARY') and os.environ.get('EMERALD_WORLD_SAVE'),
                     'requires native binary and generated first_battle fixture')
class NativeHostControls(unittest.TestCase):
    def test_lock_remove_allow_and_split_preserve_private_native_games(self):
        binary = Path(os.environ['EMERALD_WORLD_BINARY']).resolve()
        seed = Path(os.environ['EMERALD_WORLD_SAVE']).resolve()
        original = hashlib.sha256(seed.read_bytes()).digest()
        with tempfile.TemporaryDirectory(prefix='ew-admit-') as directory, ExitStack() as stack:
            # WorldActivityLock deliberately refuses a world directly under
            # writable /tmp. Keep its parent owned and private as in the launcher.
            root = Path(directory) / 'world'
            (root / 'transport').mkdir(parents=True)
            sock = root / 'transport/world.sock'
            server = WorldServer(sock, root).start()
            stack.callback(server.close)
            games = []
            names = {'alice', 'bob', 'carol', 'dave'}
            for name in sorted(names):
                game = Engine(binary, root, name, seed)
                games.append(game)
                stack.callback(game.finish)
                driver.continue_game(game)

            def pump():
                for game in games:
                    self.assertIsNone(game.proc.poll(), 'admission action terminated a native game')
                    game.wait(6)
                time.sleep(.005)

            def await_condition(predicate, message):
                for _ in range(160):
                    pump()
                    snapshot = server.inspect()
                    if predicate(snapshot):
                        return snapshot
                self.fail(message + ': ' + repr(server.inspect()))

            def members(snapshot):
                return {p['id'] for p in snapshot['players']}

            def visible(game):
                return {p['trainer'] for p in game.telemetry()['peers'] if p['visible']}

            def action(value, **fields):
                result = admin_request(sock, dict(command='host_controls', action=value, **fields))
                self.assertTrue(result['ok'], result)
                return result

            joined = await_condition(
                lambda s: members(s) == names
                and all(visible(game) == names - {game.telemetry()['trainer']} for game in games),
                'native trainers did not become mutually visible')
            ownership = {p['id']: (p['party_hash'], p['bag_hash']) for p in joined['players']}
            self.assertNotEqual(ownership['alice'][0], ownership['bob'][0])
            self.assertNotEqual(ownership['alice'][1], ownership['bob'][1])
            saves = {name: (root / 'trainers' / name / 'game.sav').read_bytes()
                     for name in names}
            parties = {game.telemetry()['trainer']: json.loads(json.dumps(game.state.party))
                       for game in games}

            def assert_private():
                for name, data in saves.items():
                    self.assertEqual((root / 'trainers' / name / 'game.sav').read_bytes(), data)
                for game in games:
                    self.assertEqual(game.state.party, parties[game.telemetry()['trainer']])

            self.assertEqual(action('lock')['admission'], 'locked')
            # Existing clients continue moving under locked admission.
            before = games[0].state.pos
            games[0].press('DOWN', 16)
            games[0].wait(24)
            self.assertNotEqual(games[0].state.pos, before)
            await_condition(lambda s: members(s) == names
                            and all(visible(game) == names - {game.telemetry()['trainer']} for game in games),
                            'lock dropped existing trainers')
            assert_private()

            action('remove', trainer='bob')
            await_condition(lambda s: members(s) == names - {'bob'}
                            and all(visible(game) == names - {'bob', game.telemetry()['trainer']}
                                    for game in (games[0], games[2], games[3]))
                            and not games[1].telemetry()['connected'],
                            'removed native trainer retained its remote object')
            # Allow does not override the world lock. Native retry stays denied.
            action('allow', trainer='bob')
            for _ in range(45):
                pump()
            self.assertEqual(members(server.inspect()), names - {'bob'})
            self.assertFalse(games[1].telemetry()['connected'])
            assert_private()

            action('unlock')
            rejoined = await_condition(lambda s: members(s) == names
                                      and all(visible(game) == names - {game.telemetry()['trainer']}
                                              for game in games),
                                      'readmitted trainer did not reconnect without restarting its game')
            self.assertEqual({p['id']: (p['party_hash'], p['bag_hash']) for p in rejoined['players']},
                             ownership)
            assert_private()

            self.assertEqual(action('split')['admission'], 'stopped')
            await_condition(lambda s: members(s) == set()
                            and all(not game.telemetry()['connected']
                                    and not game.telemetry()['peers'] for game in games),
                            'split left native trainer sprites or connected sessions')
            for game in games:
                before = game.frames
                game.wait(12)
                self.assertGreater(game.frames, before)
                self.assertTrue(game.state.free, 'split prevented independent offline field play')
            assert_private()
        self.assertEqual(hashlib.sha256(seed.read_bytes()).digest(), original)


if __name__ == '__main__':
    unittest.main()
