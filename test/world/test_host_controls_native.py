"""Opt-in local graphical acceptance with real Human-mode native processes.

Set EMERALD_HOST_BINARY and EMERALD_HOST_SEED to a locally built binary and a
headless first_battle fixture. DISPLAY must be an isolated disposable X display.
No network other than private local sockets, no personal saves, no game-state
injection, and no player-control endpoint are used.
"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile
import time
import unittest


@unittest.skipUnless(os.environ.get('EMERALD_HOST_BINARY') and os.environ.get('EMERALD_HOST_SEED')
                     and os.environ.get('DISPLAY'), 'explicit isolated native acceptance fixtures required')
class NativeHostControlsTests(unittest.TestCase):
    def test_human_games_keep_private_progress_through_lock_remove_and_split(self):
        import tkinter as tk
        from world.session import DesktopApp, DesktopSession
        binary, seed = Path(os.environ['EMERALD_HOST_BINARY']), Path(os.environ['EMERALD_HOST_SEED'])
        seed_hash = hashlib.sha256(seed.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory(prefix='ew-host-native-') as tmp:
            session = DesktopSession(DesktopSession.create_root(Path(tmp) / 'worlds'))
            window = tk.Tk()
            app = DesktopApp(window, session, binary, os.environ['DISPLAY'])
            processes, profiles, windows = {}, {}, {}
            try:
                session.create_world('test')
                session.host('test')
                panel = app.host_controls
                app.notebook.select(panel.page)

                def state(name):
                    try:
                        return json.loads(profiles[name]['telemetry'].read_text())
                    except (OSError, ValueError):
                        return {}

                def wait(predicate, message, timeout=30):
                    deadline = time.monotonic() + timeout
                    while time.monotonic() < deadline:
                        window.update()
                        for name, proc in processes.items():
                            self.assertIsNone(proc.poll(), name + ' native process exited')
                        if predicate():
                            return
                        time.sleep(.02)
                    self.fail(message + '; telemetry=' + str({n: state(n) for n in profiles}))

                def frames(name, count):
                    start = state(name).get('frame', 0)
                    wait(lambda: state(name).get('frame', 0) >= start + count, name + ' stopped executing frames')

                def key(name, symbol, count=3):
                    subprocess.run(['xdotool', 'windowfocus', '--sync', windows[name]], check=True)
                    subprocess.run(['xdotool', 'keydown', symbol], check=True)
                    try:
                        frames(name, count)
                    finally:
                        subprocess.run(['xdotool', 'keyup', symbol], check=True)
                    frames(name, 15)

                def launch(name):
                    profiles[name] = session.local_profile(name, seed)
                    processes[name] = session.launch(profiles[name], binary, os.environ['DISPLAY'])
                    found = []
                    def find_window():
                        result = subprocess.run(['xdotool', 'search', '--name', '^Emerald World \\| ' + name + ' \\| Human$'],
                                                capture_output=True, text=True)
                        found[:] = result.stdout.split()
                        return bool(found)
                    wait(find_window, name + ' Human window did not appear')
                    windows[name] = found[0]
                    wait(lambda: state(name).get('frame', 0) >= 300, 'native boot stalled')
                    key(name, 'Return')
                    frames(name, 140)
                    key(name, 'Return')
                    frames(name, 220)
                    key(name, 'z')
                    frames(name, 220)
                    key(name, 'z')
                    wait(lambda: state(name).get('ready'), name + ' never reached the field')
                    self.assertFalse((profiles[name]['profile'] / 'player.sock').exists())

                def action(name, trainer=None, confirm=True):
                    if trainer is not None:
                        panel.trainer.set(trainer)
                    if name in ('remove', 'split'):
                        # Invoke the real confirmation dialog's actual button.
                        window.after(50, lambda: window.tk.call('.__tk__messagebox.' + ('yes' if confirm else 'no'), 'invoke'))
                    panel.buttons[name].invoke()
                    wait(lambda: panel.future is None, 'host action did not finish', timeout=10)

                launch('alice')
                action('lock')
                launch('bob')
                wait(lambda: state('alice').get('connected') and not state('bob').get('connected'),
                     'lock failed to retain Alice or block Bob')
                action('unlock')
                wait(lambda: state('bob').get('connected'), 'Bob did not join after unlock')
                key('alice', 'Left', 16)
                key('bob', 'Right', 16)
                wait(lambda: all(state(n).get('peers') for n in profiles), 'native trainers never saw each other')
                original = {n: hashlib.sha256(p['save'].read_bytes()).hexdigest() for n, p in profiles.items()}
                action('remove', 'bob')
                wait(lambda: not state('bob').get('connected') and not state('alice').get('peers'),
                     'removed Bob remained connected or visible')
                self.assertTrue(state('alice')['connected'])
                old = state('bob')['pos']
                key('bob', 'Left', 16)
                self.assertNotEqual(state('bob')['pos'], old, 'removed native game cannot keep playing alone')
                action('allow', 'bob')
                wait(lambda: state('bob').get('connected'), 'allowed Bob did not rejoin')
                action('stop')
                self.assertTrue(all(state(n).get('connected') for n in profiles))
                action('split', confirm=False)
                self.assertTrue(all(state(n).get('connected') for n in profiles))
                action('split')
                wait(lambda: all(not state(n).get('connected') and not state(n).get('peers') for n in profiles),
                     'split did not clear multiplayer presence')
                for name in profiles:
                    old = state(name)['pos']
                    key(name, 'Down', 16)
                    self.assertNotEqual(state(name)['pos'], old, name + ' cannot move after split')
                    self.assertEqual(hashlib.sha256(profiles[name]['save'].read_bytes()).hexdigest(), original[name])
                self.assertEqual(hashlib.sha256(seed.read_bytes()).hexdigest(), seed_hash)
                print('Native Human acceptance passed: lock, unlock, remove, solo movement, readmit, stop, cancel split, split, solo movement, unchanged private saves and seed.')
            finally:
                app.executor.shutdown(wait=True)
                session.close()
                window.destroy()
            for proc in processes.values():
                self.assertIsNotNone(proc.poll(), 'native process was not reaped')


@unittest.skipUnless(os.environ.get('EMERALD_HOST_BINARY') and os.environ.get('EMERALD_HOST_SEED'),
                     'explicit native binary and generated smoke fixture required')
class HeadlessHostControlsTests(unittest.TestCase):
    def test_native_clients_rejoin_and_keep_private_saves_after_host_actions(self):
        from contextlib import ExitStack
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from test_native_presence import Engine, driver
        from world.client import admin_request
        from world.server import WorldServer

        binary = Path(os.environ['EMERALD_HOST_BINARY']).resolve()
        seed = Path(os.environ['EMERALD_HOST_SEED']).resolve()
        seed_hash = hashlib.sha256(seed.read_bytes()).digest()
        with tempfile.TemporaryDirectory(prefix='ew-host-hl-') as tmp, ExitStack() as stack:
            root = Path(tmp) / 'world'
            root.mkdir(mode=0o700)
            (root / 'transport').mkdir(mode=0o700)
            socket = root / 'transport/world.sock'
            server = WorldServer(socket, root).start()
            stack.callback(server.close)
            games = []

            def action(name, trainer=None):
                request = dict(command='host_controls', action=name)
                if trainer is not None:
                    request['trainer'] = trainer
                result = admin_request(socket, request)
                self.assertTrue(result['ok'], result)
                return result

            def launch(name):
                game = Engine(binary, root, name, seed)
                games.append(game)
                stack.callback(game.finish)
                driver.continue_game(game)
                return game

            def wait_for(predicate, message):
                # Native bridges advance only with requested frames here. The
                # wall-clock bound detects failures, not simulated game time.
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    for game in games:
                        game.wait(6)
                    if predicate():
                        return
                    time.sleep(.005)
                self.fail(message)

            alice = launch('alice')
            wait_for(lambda: alice.telemetry()['connected'], 'Alice did not connect')
            action('lock')
            bob = launch('bob')
            self.assertTrue(alice.telemetry()['connected'])
            self.assertFalse(bob.telemetry()['connected'])
            action('unlock')
            wait_for(lambda: bob.telemetry()['connected'], 'Bob did not join after unlock')
            originals = [hashlib.sha256(game.paths['save'].read_bytes()).digest() for game in games]

            action('remove', 'bob')
            wait_for(lambda: not bob.telemetry()['connected'], 'Bob stayed connected after removal')
            self.assertTrue(alice.telemetry()['connected'])
            action('allow', 'bob')
            wait_for(lambda: bob.telemetry()['connected'], 'Bob did not rejoin after allow')
            action('stop')
            self.assertTrue(all(game.telemetry()['connected'] for game in games))
            action('split')
            wait_for(lambda: all(not game.telemetry()['connected'] for game in games),
                     'split left a native client connected')
            for game, digest in zip(games, originals):
                before = game.state.pos
                game.press('LEFT', 16)
                game.wait(60)
                self.assertNotEqual(game.state.pos, before, 'native movement stopped after split')
                self.assertTrue(game.state.free)
                self.assertEqual(hashlib.sha256(game.paths['save'].read_bytes()).digest(), digest)
            self.assertEqual(hashlib.sha256(seed.read_bytes()).digest(), seed_hash)


if __name__ == '__main__':
    unittest.main()
