"""Exercise an actual Windows game PE against a local protocol fixture.

Not a production authority or WAN test. Uses only copied CI-generated saves.
The outer windows_verify.py deadline is mandatory in CI.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import queue
import secrets
import shutil
import socket
import subprocess
import tempfile
import threading
import time


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def wait_until(read, predicate, timeout=6):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            value = read()
            if predicate(value):
                return value
        except (FileNotFoundError, json.JSONDecodeError, PermissionError):
            pass
        time.sleep(.025)
    raise AssertionError('Timed out waiting for native fixture state')


class Fixture:
    def __init__(self, binary, save, root):
        self.root = root
        root.mkdir()
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen(1)
        self.listener.settimeout(6)
        self.local_key = secrets.token_hex(32)
        self.token = secrets.token_hex(32)
        self.telemetry = root / 'world state.json'
        self.save = root / 'own game.sav'
        shutil.copyfile(save, self.save)
        self.config = root / 'world.conf'
        self.config.write_text(f'loopback_port {self.listener.getsockname()[1]}\n'
            f'loopback_token {self.local_key}\ntrainer alice\ntoken {self.token}\n'
            f'telemetry {self.telemetry}\n', encoding='utf-8')
        self.binary = binary
        self.proc = None
        self.conn = None
        self.log = (root / 'private.log').open('wb')

    def launch(self, headless):
        command = [str(self.binary), '--save', str(self.save), '--world-config', str(self.config)]
        if headless:
            command += ['--test-input', '-', '--test-state', '-']
        else:
            input_path = self.root / 'bootstrap.txt'
            input_path.write_text('1 A\n', encoding='ascii')
            command += ['--world-input', str(input_path), '--world-shot', str(self.root / 'eof.ppm')]
        env = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
        self.proc = subprocess.Popen(command, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE if headless else self.log, stderr=self.log,
            text=True, bufsize=1, env=env, cwd=self.root)
        if headless:
            self.states = queue.Queue(maxsize=32)
            def read_states():
                for line in self.proc.stdout:
                    if line.startswith('{'):
                        self.states.put(json.loads(line), timeout=3)
            self.reader = threading.Thread(target=read_states, daemon=True)
            self.reader.start()
            return self.state()

    def state(self):
        try:
            return self.states.get(timeout=6)
        except queue.Empty:
            raise AssertionError('Native process did not return state') from None

    def step(self, frames=6, buttons='-'):
        self.proc.stdin.write(f'{frames} {buttons}\n')
        self.proc.stdin.flush()
        return self.state()

    def connect(self):
        self.conn, _ = self.listener.accept()
        self.conn.settimeout(6)
        received = bytearray()
        while received.count(b'\n') < 2 and len(received) <= 512:
            data = self.conn.recv(512)
            require(bool(data), 'Native peer closed before authentication')
            received.extend(data)
        expected = f'EWLOCAL1 {self.local_key}\nHELLO 1 alice {self.token} SOCIAL\n'.encode()
        require(bytes(received) == expected, 'Native handshake mismatch')
        self.conn.sendall(b'WELCOME 1 alice 0\n')

    def telemetry_state(self):
        return json.loads(self.telemetry.read_text(encoding='utf-8'))

    def close(self):
        if self.proc:
            if self.proc.poll() is None:
                self.proc.kill()
            self.proc.wait(timeout=6)
            if self.proc.stdin:
                self.proc.stdin.close()
            if self.proc.stdout:
                self.proc.stdout.close()
        if self.conn:
            self.conn.close()
        self.listener.close()
        self.log.close()


def cpu_seconds(proc):
    from ctypes import wintypes
    values = [wintypes.FILETIME() for _ in range(4)]
    function = ctypes.windll.kernel32.GetProcessTimes
    function.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    function.restype = wintypes.BOOL
    require(function(wintypes.HANDLE(int(proc._handle)), *[ctypes.byref(v) for v in values]),
            'GetProcessTimes failed')
    return sum((v.dwHighDateTime << 32) | v.dwLowDateTime for v in values[2:]) / 10000000


def verify(binary, save, root):
    checks = []
    fixture = Fixture(binary, save, root / 'headless profile')
    try:
        fixture.launch(True)
        fixture.step()
        fixture.connect()
        connection = fixture.conn
        assert connection is not None
        require(fixture.step()['world']['connected'], 'WELCOME was not accepted')
        # Continue the copied starter save using ordinary native input. This
        # also proves the Unicode profile's save path was read correctly.
        for frames, buttons in [(480, '-'), (2, 'START'), (120, '-'),
                                (2, 'START'), (120, '-'), (2, 'A'), (180, '-')]:
            state = fixture.step(frames, buttons)
        require(state['overworld'] and state['world']['ready'], 'Copied save did not enter the overworld')
        require(state['map'] == [1, 4] and state['pos'] == [6, 5], 'Copied Unicode-path save was not loaded')
        connection.sendall(b'BEGIN 7\nPEER bob 1 4 7 5 1 0 1\n')
        require(fixture.step()['world']['revision'] == 0, 'Partial snapshot was published')
        connection.sendall(b'EN')
        require(fixture.step()['world']['revision'] == 0, 'Fragment was published')
        connection.sendall(b'D\n')
        require(fixture.step()['world']['revision'] == 7, 'Complete snapshot not published')
        require(fixture.telemetry_state()['revision'] == 7, 'Telemetry was not replaced')
        state = fixture.step()
        peers = state['world']['peers']
        require(any(peer['trainer'] == 'bob' and peer['visible'] for peer in peers), 'Native peer sprite was not visible')
        fixture.step(16, 'RIGHT')
        require(fixture.step(8)['pos'] == [6, 5], 'Remote trainer did not block normal movement')
        fixture.step(16, 'DOWN')
        require(fixture.step(16)['pos'] == [6, 6], 'Normal native movement did not work')
        checks += ['native_loopback_capability_and_hello', 'fragmented_snapshot_atomic', 'telemetry_replace',
                   'unicode_profile_save_loaded', 'native_peer_visible', 'native_peer_collision', 'native_player_movement']
        fixture.proc.stdin.close()
        require(fixture.proc.wait(timeout=6) == 0, 'Headless input EOF did not exit normally')
        checks.append('headless_eof_exit')
    finally:
        fixture.close()
    fixture = Fixture(binary, save, root / 'realtime profile')
    try:
        fixture.launch(False)
        fixture.connect()
        initial = wait_until(fixture.telemetry_state, lambda value: value['connected'])
        wait_until(lambda: (fixture.root / 'eof.ppm').is_file(), bool)
        first_cpu = cpu_seconds(fixture.proc)
        started = time.monotonic()
        time.sleep(2)
        later = fixture.telemetry_state()
        elapsed = time.monotonic() - started
        cpu = cpu_seconds(fixture.proc) - first_cpu
        frames = later['frame'] - initial['frame']
        require(fixture.proc.poll() is None, 'Realtime bootstrap EOF stopped the game')
        require(30 <= frames <= 240, 'Realtime frame cadence froze or ran unbounded')
        require(cpu / elapsed < .90, 'Realtime dummy client appears to busy-spin')
        checks += ['sdl_dummy_realtime', 'bootstrap_eof_continues', 'realtime_cpu_bounded', 'separate_save_profile']
        return {'scope': 'Windows native PE with local fixture; not WAN or production authority',
                'passed': True, 'checks': checks, 'realtime_frames': frames,
                'cpu_seconds': round(cpu, 3), 'wall_seconds': round(elapsed, 3)}
    finally:
        fixture.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--save', type=Path, required=True, help='fresh smoke-generated save, copied into own profiles')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('An actual Windows runner is required. No simulated Windows pass is supported.')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='emerald Windows é 中 fixture ') as tmp:
        report = verify(args.binary.resolve(), args.save.resolve(), Path(tmp))
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('Actual Windows native fixture checks passed. No WAN claim.')


if __name__ == '__main__':
    main()
