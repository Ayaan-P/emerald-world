"""Opt-in real native saved-world rejoin. Only explicit disposable seed copies.

EW_NATIVE_BINARY=/absolute/pokeemerald64 EW_NATIVE_SEED=/generated/first_battle/game.sav
python3 -m unittest test.world.test_saved_friend_native -v
"""
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from world.launcher import ProfileLock, game_command
from world.session import DesktopSession

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'test/headless'))
import driver


class Native(driver.Game):
    def __init__(self, binary, state, paths):
        self.paths = paths
        self.out_dir = str(paths['profile'])
        self.frames, self.steps, self.max_frames = 0, [], 40000
        self.states = (paths['profile']/'states.jsonl').open('w')
        self.stderr = (paths['profile']/'stderr.txt').open('w')
        self.lock = ProfileLock(state, paths['profile'].name)
        command = game_command(binary, state, paths)
        command += ['--test-input', '-', '--test-state', '-']
        try:
            self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=self.stderr, text=True, bufsize=1)
            self.state = self._read_state()
        except BaseException:
            self.stop()
            raise

    def _read_state(self):
        ready, _, _ = select.select([self.proc.stdout], [], [], 15)
        if not ready:
            raise RuntimeError('native state deadline')
        return super()._read_state()

    def stop(self):
        process = getattr(self, 'proc', None)
        if process:
            if process.poll() is None:
                process.stdin.close()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            for stream in (process.stdin, process.stdout):
                if stream and not stream.closed:
                    stream.close()
        self.states.close()
        self.stderr.close()
        self.lock.close()


class SavedFriendNativeTests(unittest.TestCase):
    def test_two_native_clients_and_rejoined_guest_retain_private_saves(self):
        binary, seed = os.getenv('EW_NATIVE_BINARY'), os.getenv('EW_NATIVE_SEED')
        if not binary or not seed:
            self.skipTest('explicit native binary and generated disposable seed required')
        if not shutil.which('bwrap') or not shutil.which('openssl'):
            self.skipTest('native isolation and local TLS tools required')
        seed = Path(seed).resolve()
        initial_seed = hashlib.sha256(seed.read_bytes()).hexdigest()
        games = []
        with tempfile.TemporaryDirectory(prefix='ew-native-') as tmp:
            root = Path(tmp)
            host_root, guest_root = root/'host', root/'guest'
            host_root.mkdir(mode=0o700)
            guest_root.mkdir(mode=0o700)
            with DesktopSession(host_root) as host, DesktopSession(guest_root) as guest:
                host.create_world('world')
                host.host('world')
                cert, key = host.tls_material()
                address = host.share(cert, key, ('127.0.0.1', 0))
                invitation = root/'invitation.json'
                host.export_invitation('bob', invitation, address)
                pin = json.loads(invitation.read_text())['pin']
                alice = host.local_profile('alice', seed)
                bob = guest.connect_remote('visited', invitation, address, pin)
                shutil.copyfile(seed, bob['save'])
                from test.world.native_acceptance import fixture
                fixture(seed, alice['save'], 'alice')
                fixture(seed, bob['save'], 'bob')
                originals = {name: paths['save'].read_bytes() for name, paths in [('alice', alice), ('bob', bob)]}
                try:
                    for session, paths in ((host, alice), (guest, bob)):
                        game = Native(Path(binary).resolve(), session.state, paths)
                        games.append(game)
                        driver.continue_game(game)
                    def converge():
                        deadline = time.monotonic()+8
                        while time.monotonic() < deadline:
                            for game in games:
                                game.wait(12)
                            states = [json.loads(p['telemetry'].read_text()) for p in (alice, bob)]
                            if all(any(peer['visible'] for peer in state.get('peers', [])) for state in states):
                                return states
                            time.sleep(.02)
                        self.fail('two actual native peer sprites never converged')
                    # Move away from the same seeded tile before requiring visibility.
                    games[0].press('LEFT', 16)
                    games[1].press('RIGHT', 16)
                    states = converge()
                    self.assertEqual(states[0]['peers'][0]['trainer'], 'bob')
                    self.assertEqual(states[1]['peers'][0]['trainer'], 'alice')
                    # Ordinary native menu save, only while free in the overworld.
                    # The generated first_battle fixture has no Pokedex yet.
                    self.assertTrue(games[1].state.free)
                    driver.save_game(games[1], 3)
                    import savecheck
                    saved = savecheck.Save(bob['save'])
                    self.assertGreater(saved.counter, savecheck.Save(seed).counter)
                    self.assertEqual(saved.party_count, 1)
                    committed_bob = bob['save'].read_bytes()
                    self.assertNotEqual(committed_bob, originals['bob'])
                    self.assertEqual(alice['save'].read_bytes(), originals['alice'])
                    games.pop().stop()
                    guest.close()
                    # Restart actual authority + TLS listener with persistent host
                    # identity and the same explicit endpoint, not a new trust pin.
                    games.pop().stop()
                    host.close()
                    host.host('world')
                    host.share(cert, key, address)
                    alice_returned = Native(Path(binary).resolve(), host.state, alice)
                    games.append(alice_returned)
                    driver.continue_game(alice_returned)
                    alice_returned.press('LEFT', 16)
                    invitation.unlink()
                    bob = guest.rejoin_friend('visited')
                    self.assertEqual(bob['save'].read_bytes(), committed_bob)
                    returned = Native(Path(binary).resolve(), guest.state, bob)
                    games.append(returned)
                    driver.continue_game(returned)
                    returned.press('RIGHT', 16)
                    states = converge()
                    self.assertEqual(states[0]['peers'][0]['trainer'], 'bob')
                    self.assertEqual(alice['save'].read_bytes(), originals['alice'])
                    self.assertEqual(bob['save'].read_bytes(), committed_bob)
                    games.pop().stop()
                    guest.close()
                    guest.forget_friend('visited')
                    self.assertEqual(guest.friend_worlds(), [])
                    self.assertEqual(bob['save'].read_bytes(), committed_bob)
                    print('PASS actual isolated native peers visible before and after host restart + saved TLS rejoin; newly menu-saved progress retained; Forget retains progress')
                finally:
                    for game in reversed(games):
                        game.stop()
        self.assertEqual(hashlib.sha256(seed.read_bytes()).hexdigest(), initial_seed)


if __name__ == '__main__':
    unittest.main()
