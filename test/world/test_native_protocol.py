"""Native bridge acceptance tests. No compilation or third-party dependencies.

Run with EMERALD_WORLD_BINARY=/absolute/path/to/new/binary python3 this_file.
EMERALD_WORLD_SAVE may name a NEW acceptance-run save to exercise engine effects.
Scratch files stay in emerald-world-research, never the source checkout.
"""
import json
import os
from pathlib import Path
import re
import select
import socket
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRATCH = ROOT.parent / "emerald-world-research"


class BridgeContract(unittest.TestCase):
    def test_real_engine_hooks_exist(self):
        path = ROOT / "src/platform/world_bridge.c"
        self.assertTrue(path.exists(), "native world bridge is not implemented")
        source = path.read_text()
        for hook in ("SpawnSpecialObjectEventParameterized", "MoveObjectEventToMapCoords",
                     "RemoveObjectEventByLocalIdAndMap", "MapGridSetMetatileIdAt",
                     "MapGridSetMetatileEntryAt", "CurrentMapDrawMetatileAt"):
            self.assertIn(hook, source)


@unittest.skipUnless(os.environ.get("EMERALD_WORLD_BINARY"), "set EMERALD_WORLD_BINARY; never builds")
class NativeProtocol(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix="native-protocol-", dir=SCRATCH)
        self.path = Path(self.tmp.name)
        self.listener = socket.socket(socket.AF_UNIX)
        self.listener.bind(str(self.path / "sock"))
        self.listener.listen()
        self.listener.settimeout(3)
        self.token = "ab" * 32
        self.config = self.path / "world.conf"
        self.config.write_text(f"socket {self.path / 'sock'}\ntrainer alice\ntoken {self.token}\ntelemetry {self.path / 'world.json'}\n")
        self.proc = None
        self.conn = None
        self.readbuf = b""

    def tearDown(self):
        if self.proc:
            self.proc.stdin.close()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
            self.proc.stdout.close()
            self.proc.stderr.close()
        if self.conn:
            self.conn.close()
        self.listener.close()
        self.tmp.cleanup()

    def launch(self, enabled=True):
        save = self.path / "game.sav"
        if os.environ.get("EMERALD_WORLD_SAVE"):
            save.write_bytes(Path(os.environ["EMERALD_WORLD_SAVE"]).read_bytes())
        args = [os.environ["EMERALD_WORLD_BINARY"], "--save", str(save),
                "--test-input", "-", "--test-state", "-"]
        if enabled:
            args += ["--world-config", str(self.config)]
        self.proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, bufsize=1)
        return self.state()

    def state(self):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            while b"\n" in self.readbuf:
                line, self.readbuf = self.readbuf.split(b"\n", 1)
                if line.startswith(b"{"):
                    return json.loads(line)
            if not select.select([self.proc.stdout], [], [], max(0, deadline - time.monotonic()))[0]:
                break
            chunk = os.read(self.proc.stdout.fileno(), 65536)
            if not chunk:
                self.fail(f"native process exited: {self.proc.poll()}")
            self.readbuf += chunk
        self.fail("native process did not return test state")

    def step(self, frames=6, buttons="-"):
        self.proc.stdin.write(f"{frames} {buttons}\n")
        self.proc.stdin.flush()
        return self.state()

    def connect(self):
        self.launch()
        self.step()
        # Presence and virtual cable intentionally use separate sockets. This
        # fixture exercises only presence, so explicitly reject the LINK role
        # rather than assuming connection arrival order identifies the role.
        for _ in range(3):
            try:
                candidate, _ = self.listener.accept()
            except TimeoutError:
                self.fail("native bridge did not connect and send HELLO")
            candidate.settimeout(3)
            hello = b""
            while b"\n" not in hello and len(hello) <= 1024:
                chunk = candidate.recv(1024)
                if not chunk:
                    break
                hello += chunk
            if hello == f"HELLO 1 alice {self.token} LINK\n".encode():
                candidate.sendall(b"ERROR AUTH\n")
                candidate.close()
                continue
            self.assertEqual(hello.decode(), f"HELLO 1 alice {self.token} SOCIAL\n")
            self.conn = candidate
            break
        assert self.conn is not None, 'presence role never connected'
        self.conn.sendall(b"WELCOME 1 alice 0\n")
        self.assertTrue(self.step()["world"]["connected"])

    def test_bad_config_fails_before_save_open(self):
        self.config.write_text(f"socket {self.path / 'sock'}\ntrainer bad!id\ntoken {self.token}\ntelemetry {self.path / 'world.json'}\n")
        result = subprocess.run([os.environ["EMERALD_WORLD_BINARY"], "--world-config", str(self.config),
                                 "--save", str(self.path / "untouched.sav"), "--test-input", "-"],
                                input="", capture_output=True, text=True, timeout=8)
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.path / "untouched.sav").exists())

    def test_bootstrap_requires_world_config(self):
        result = subprocess.run([os.environ["EMERALD_WORLD_BINARY"], "--world-input", str(self.path / "input.txt")],
                                input="", capture_output=True, text=True, timeout=8)
        self.assertEqual(result.returncode, 1)
        self.assertIn("World bootstrap requires", result.stderr)

    def test_disabled_state_is_unchanged(self):
        self.assertNotIn("world", self.launch(False))

    def test_fragmented_snapshot_is_atomic(self):
        self.connect()
        self.conn.sendall(b"BEGIN 7\nPEER bob 0 9 5 5 1 0 1\n")
        self.assertEqual(self.step()["world"]["revision"], 0)
        self.conn.sendall(b"EN")
        self.assertEqual(self.step()["world"]["revision"], 0)
        self.conn.sendall(b"D\n")
        state = self.step()["world"]
        self.assertEqual(state["revision"], 7)
        self.assertEqual(json.loads((self.path / "world.json").read_text())["revision"], 7)
        self.conn.recv(4096)

    def test_object_snapshot_is_atomic_and_literal_text_is_validated(self):
        self.connect()
        text = 'Hello trainer!'.encode().hex()
        self.conn.sendall(f'BEGIN 8\nOBJECT guide 0 1 10 12 7 {text}\n'.encode())
        self.assertEqual(self.step()['world']['revision'], 0)
        self.conn.sendall(b'END\n')
        self.assertEqual(self.step()['world']['revision'], 8)
        self.conn.sendall(b'BEGIN 9\nOBJECT guide 0 1 10 12 7 24626164\nEND\n')
        self.assertFalse(self.step()['world']['connected'])
        self.assertEqual(self.step()['world']['revision'], 8)

    @unittest.skipUnless(os.environ.get('EMERALD_WORLD_SAVE'), 'needs fresh acceptance save')
    def test_shared_object_a_opens_native_dialogue_and_sends_event(self):
        self.connect()
        for frames, key in [(300, '-'), (2, 'START'), (140, '-'), (2, 'START'),
                            (220, '-'), (2, 'A'), (220, '-'), (2, 'A')]:
            self.step(frames, key)
        for _ in range(150):
            state = self.step(10)
            if state['world']['ready']:
                break
        self.assertTrue(state['world']['ready'])
        self.step(1, 'DOWN')
        state = self.step(20)
        group, num = state['map']
        x, y = state['pos']
        text = 'Welcome trainer!'.encode().hex()
        self.conn.sendall(f'BEGIN 9\nOBJECT guide {group} {num} {x} {y+1} 7 {text}\nEND\n'.encode())
        world = self.step()['world']
        self.assertEqual(world['objects'][0]['id'], 'guide')
        self.assertEqual(world['object_count'], 1)
        self.assertTrue(world['objects'][0]['visible'])
        self.assertEqual(world['objects'][0]['pos'], [x, y+1])
        state = self.step(1, 'A')
        world = self.step(100)['world']
        self.assertTrue(world['dialogue_active'])
        self.assertFalse(world['ready'])
        self.assertEqual(world['dialogue_object'], 'guide')
        self.assertEqual(world['dialogue_text'], 'Welcome trainer!')
        self.assertGreater(world['interaction_seq'], 0)
        wire = self.conn.recv(16384).decode()
        self.assertRegex(wire, r'INTERACT \d+ guide\n')
        world = self.step(1, 'A')['world']
        self.assertFalse(world['dialogue_active'])
        self.step(2)
        self.assertTrue(self.step()['world']['ready'])
        self.conn.sendall(b'BEGIN 10\nEND\n')
        self.assertEqual(self.step()['world']['objects'], [])

    def test_malformed_snapshot_disconnects(self):
        self.connect()
        self.conn.sendall(b"BEGIN 8\nTILE 0 9 -1 2 1024 2\nEND\n")
        state = self.step()["world"]
        self.assertFalse(state["connected"])
        self.assertEqual(state["revision"], 0)

    @unittest.skipUnless(os.environ.get('EMERALD_WORLD_SAVE'), 'needs fresh acceptance save')
    def test_trainer_a_waits_for_committed_signal_then_opens_native_ui(self):
        self.connect()
        for frames,key in [(300,'-'),(2,'START'),(140,'-'),(2,'START'),
                           (220,'-'),(2,'A'),(220,'-'),(2,'A')]:
            self.step(frames,key)
        for _ in range(150):
            state=self.step(10)
            if state['world']['ready']: break
        self.assertTrue(state['world']['ready'])
        self.step(1,'DOWN');state=self.step(20)
        group,num=state['map'];x,y=state['pos']
        self.conn.sendall(f'BEGIN 9\nPEER bob {group} {num} {x} {y+1} 1 7 1\nEND\n'.encode())
        self.assertEqual(self.step()['world']['peers'][0]['trainer'],'bob')
        world=self.step(1,'A')['world']
        self.assertFalse(world['dialogue_active'])
        self.assertRegex(self.conn.recv(32768).decode(), r'MEET \d+ bob\n')
        self.conn.sendall(f'BEGIN 10\nPEER bob {group} {num} {x} {y+1} 1 7 1\nMEET 10 alice bob {group} {num} {x} {y+1} explore\n'.encode())
        self.assertFalse(self.step()['world']['dialogue_active'])
        self.conn.sendall(b'END\n')
        # Native messages use the trainer's normal text speed. Let the longer
        # two-line greeting finish so A dismisses rather than accelerates it.
        world=self.step(240)['world']
        self.assertTrue(world['dialogue_active'])
        self.assertEqual(world['dialogue_kind'],'trainer')
        self.assertEqual(world['dialogue_text'],"bob\nLet's explore together!")
        self.assertEqual(world['meeting']['seq'],10)
        self.assertFalse(world['ready'])
        self.assertFalse(self.step(1,'A')['world']['dialogue_active'])
        self.step(2)
        self.assertTrue(self.step()['world']['ready'])
        self.conn.sendall(b'BEGIN 11\nEND\n')
        self.assertIsNone(self.step()['world']['meeting'])

    def test_peer_bound_is_enforced(self):
        self.connect()
        rows = "".join(f"PEER peer{i} 0 9 5 5 1 0 1\n" for i in range(9))
        self.conn.sendall(("BEGIN 5\n" + rows + "END\n").encode())
        self.assertFalse(self.step()["world"]["connected"])

    def test_tile_bound_is_enforced(self):
        self.connect()
        # Route 110 is large enough for 129 unique, in-bounds cells.
        rows = "".join(f"TILE 0 25 {i % 10} {i // 10} 1 1\n" for i in range(129))
        self.conn.sendall(("BEGIN 5\n" + rows + "END\n").encode())
        self.assertFalse(self.step()["world"]["connected"])

    def test_state_hashes_and_reconnect(self):
        self.connect()
        wire = self.conn.recv(4096).decode()
        states = [s for s in wire.splitlines() if s.startswith("STATE ")]
        self.assertTrue(states)
        self.assertRegex(states[-1], r"^STATE \d+ -?\d+ -?\d+ -?\d+ -?\d+ \d+ \d+ [01] [0-9a-f]{16} [0-9a-f]{16}$")
        self.conn.close()
        self.conn = None
        self.step(120)
        self.conn, _ = self.listener.accept()
        self.conn.settimeout(3)
        self.assertEqual(self.conn.recv(1024).decode(), f"HELLO 1 alice {self.token} SOCIAL\n")

    @unittest.skipUnless(os.environ.get("EMERALD_WORLD_SAVE"), "needs fresh acceptance save")
    def test_engine_sprite_and_tile_restore(self):
        self.connect()
        # The existing headless driver's continue-game sequence.
        for frames, key in [(300, "-"), (2, "START"), (140, "-"), (2, "START"),
                            (220, "-"), (2, "A"), (220, "-"), (2, "A")]:
            self.step(frames, key)
        for _ in range(150):
            state = self.step(10)
            if state["world"]["ready"]:
                break
        self.assertTrue(state["world"]["ready"])
        group, num = state["map"]
        x, y = state["pos"]
        # Adjacent cell on the fresh acceptance map, provided by parent.
        x += 1
        self.conn.sendall(f"BEGIN 9\nPEER bob {group} {num} {x} {y} 2 0 1\nTILE {group} {num} {x} {y} 1 1\nEND\n".encode())
        world = self.step()["world"]
        self.assertEqual(len(world["peers"]), 1)
        peer = world["peers"][0]
        self.assertEqual(peer["pos"], [x, y])
        self.assertLess(peer["object_id"], 16)
        self.assertLess(peer["sprite_id"], 64)
        self.assertEqual(world["tiles"][0]["raw"] & 0xFFF, 0xC01)
        self.conn.sendall(b"BEGIN 10\nEND\n")
        world = self.step()["world"]
        self.assertEqual(world["peers"], [])
        self.assertEqual(world["tiles"], [])
        self.assertEqual(world["restored_tiles"][0]["raw"], world["restored_tiles"][0]["original"])


if __name__ == "__main__":
    unittest.main()
