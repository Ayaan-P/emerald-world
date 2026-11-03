"""Player API tests use a real temporary Unix socket, not a game substitute."""
import json
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path


class NativeSocket:
    def __init__(self, handler, *, persistent=True):
        self.handler = handler
        self.persistent = persistent
        self.connections = 0
        self.active = None
        self.requests = []
        self.errors = []

    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / 'player.sock')
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(self.path)
        self.server.listen(8)
        self.server.settimeout(0.1)
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        return self

    def run(self):
        while not self.stop.is_set():
            try:
                conn, _ = self.server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            self.connections += 1
            self.active = conn
            with conn:
                conn.settimeout(0.1)
                try:
                    while not self.stop.is_set():
                        data = b''
                        while b'\n' not in data and not self.stop.is_set():
                            try:
                                chunk = conn.recv(4096)
                            except socket.timeout:
                                continue
                            if not chunk:
                                break
                            data += chunk
                        if not data or b'\n' not in data:
                            break
                        request = json.loads(data)
                        self.requests.append(request)
                        self.handler(conn, request)
                        if not self.persistent:
                            break
                except (BrokenPipeError, ConnectionResetError):
                    pass
                except Exception as exc:
                    self.errors.append(exc)
            self.active = None

    def __exit__(self, *args):
        self.stop.set()
        self.server.close()
        self.thread.join(2)
        self.temp.cleanup()
        if self.errors:
            raise self.errors[0]


def reply(conn, request, **fields):
    conn.sendall((json.dumps({'id': request['id'], 'ok': True, **fields}) + '\n').encode())


class PlayerTests(unittest.TestCase):
    def test_observe_preserves_real_native_state_and_fragmented_json(self):
        from world.player import PlayerClient
        state = {'frame': 812, 'map': {'name': 'LITTLEROOT_TOWN'}, 'inBattle': False}
        def handler(conn, request):
            data = (json.dumps({'id': request['id'], 'ok': True, 'state': state}) + '\n').encode()
            for chunk in (data[:2], data[2:13], data[13:]):
                conn.sendall(chunk)
        with NativeSocket(handler) as server:
            result = PlayerClient(server.path).observe()
            self.assertEqual(result['state'], state)
            self.assertNotIn('party', result['state'])
            self.assertEqual(server.requests[0]['op'], 'observe')
            self.assertIs(type(server.requests[0]['id']), int)

    def test_press_waits_for_native_completion_and_increments_ids(self):
        from world.player import PlayerClient
        completed = threading.Event()
        def handler(conn, req):
            if req['op'] == 'press':
                self.assertEqual(req['buttons'], ['UP', 'A'])
                self.assertEqual(req['frames'], 12)
                time.sleep(0.04)
                completed.set()
            reply(conn, req, state={'frame': 912})
        with NativeSocket(handler) as server:
            client = PlayerClient(server.path)
            first = client.observe()
            pressed = client.press(['UP', 'A'], 12)
            self.assertTrue(completed.is_set())
            self.assertEqual(pressed['state']['frame'], 912)
            self.assertNotEqual(first['id'], pressed['id'])

    def test_buttons_frames_and_configuration_are_validated_before_connect(self):
        from world.player import PlayerClient
        client = PlayerClient('/nonexistent-player-endpoint')
        for buttons in (['ADMIN'], ['a'], ['UP', 'UP'], [1], None, {'A': True}, ['A\n']):
            with self.subTest(buttons=buttons), self.assertRaises(ValueError):
                client.press(buttons, 1)
        for frames in (0, 121, True, 1.5, '2', None):
            with self.subTest(frames=frames), self.assertRaises(ValueError):
                client.press(['A'], frames)
        for options in ({'timeout': 0}, {'timeout': float('nan')}, {'timeout': True},
                        {'max_response_bytes': 0}, {'max_response_bytes': True},
                        {'max_response_bytes': 1048577}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                PlayerClient('/socket', **options)

    def test_screenshot_returns_actual_native_path_without_opening_files(self):
        from world.player import PlayerClient
        with NativeSocket(lambda conn, req: reply(conn, req, screenshot='/profile/screenshot.ppm',
                                                  state={'frame': 913})) as server:
            result = PlayerClient(server.path).screenshot()
            self.assertEqual(result['screenshot'], '/profile/screenshot.ppm')
            self.assertEqual(server.requests[0]['op'], 'screenshot')
            self.assertEqual(set(server.requests[0]), {'id', 'op'})

    def test_empty_buttons_wait_and_string_buttons(self):
        from world.player import PlayerClient
        with NativeSocket(lambda conn, req: reply(conn, req)) as server:
            client = PlayerClient(server.path)
            client.press([], 120)
            client.press('A', 1)
            self.assertEqual(server.requests[0]['buttons'], [])
            self.assertEqual(server.requests[1]['buttons'], ['A'])

    def test_cli_returns_actual_envelopes_for_each_player_action(self):
        def handler(conn, req):
            reply(conn, req, state={'frame': 74}, screenshot='/profile/screenshot.ppm')
        with NativeSocket(handler) as server:
            for command in (['observe'], ['press', '--buttons', 'UP', 'A', '--frames', '12'], ['screenshot']):
                result = subprocess.run([sys.executable, '-m', 'world.player', '--endpoint', server.path,
                                         *command], capture_output=True, text=True, timeout=3)
                self.assertEqual(result.returncode, 0, result.stderr)
                actual = json.loads(result.stdout)
                self.assertEqual(actual['state'], {'frame': 74})
                self.assertEqual(actual['screenshot'], '/profile/screenshot.ppm')
            self.assertEqual([r['op'] for r in server.requests], ['observe', 'press', 'screenshot'])

    def test_cli_native_error_exits_nonzero_and_preserves_native_json(self):
        def handler(conn, req):
            conn.sendall((json.dumps({'id': req['id'], 'ok': False, 'error': 'busy'}) + '\n').encode())
        with NativeSocket(handler) as server:
            result = subprocess.run([sys.executable, '-m', 'world.player', '--endpoint', server.path,
                                     'observe'], capture_output=True, text=True, timeout=3)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)['error'], 'busy')

    def test_custom_stdio_tools_are_bound_and_self_describing(self):
        requests = [
            {'id': 9, 'tool': 'observe'},
            {'id': 10, 'tool': 'press', 'arguments': {'buttons': ['A'], 'frames': 2}},
            {'id': 11, 'tool': 'screenshot'},
            {'id': 12, 'tool': 'deploy', 'arguments': {}},
            {'id': 13, 'tool': 'screenshot', 'arguments': {'path': '/etc/passwd'}},
            {'id': 14, 'tool': 'observe', 'arguments': {'endpoint': '/other'}},
            {'id': 15, 'tool': 'press', 'arguments': {'buttons': ['ADMIN'], 'frames': 1}},
        ]
        with NativeSocket(lambda conn, req: reply(conn, req, state={'frame': 10})) as server:
            result = subprocess.run([sys.executable, '-m', 'world.player', '--endpoint', server.path,
                                     'serve'], input=''.join(json.dumps(r) + '\n' for r in requests),
                                    capture_output=True, text=True, timeout=3)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = [json.loads(line) for line in result.stdout.splitlines()]
            capabilities = lines.pop(0)
            self.assertEqual(capabilities['protocol'], 'emerald-player-jsonl-v1')
            self.assertEqual({t['name'] for t in capabilities['tools']}, {'observe', 'press', 'screenshot'})
            self.assertEqual([r['id'] for r in lines], list(range(9, 16)))
            self.assertTrue(all(r['ok'] for r in lines[:3]))
            self.assertTrue(all(not r['ok'] for r in lines[3:]))
            self.assertEqual(lines[0]['result']['state'], {'frame': 10})
            self.assertEqual([r['op'] for r in server.requests], ['observe', 'press', 'screenshot'])

    def test_stdio_recovers_after_invalid_or_oversized_line(self):
        with NativeSocket(lambda conn, req: reply(conn, req)) as server:
            payload = b'x' * 9000 + b'\n' + b'not json\n' + b'{"id":1,"tool":"observe"}\n'
            result = subprocess.run([sys.executable, '-m', 'world.player', '--endpoint', server.path,
                                     'serve'], input=payload, capture_output=True, timeout=3)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual(len(lines), 4)
            self.assertFalse(lines[1]['ok'])
            self.assertFalse(lines[2]['ok'])
            self.assertTrue(lines[3]['ok'])
            self.assertEqual(len(server.requests), 1)

    def test_sequential_calls_reuse_one_connection_until_explicit_close(self):
        from world.player import PlayerClient
        with NativeSocket(lambda conn, req: reply(conn, req)) as server:
            client = PlayerClient(server.path)
            client.observe()
            client.screenshot()
            self.assertEqual(server.connections, 1)
            client.close()
            with client:
                client.observe()
            self.assertEqual(server.connections, 2)

    def test_rejects_wrong_id_and_malformed_envelopes(self):
        from world.player import PlayerClient, PlayerProtocolError
        cases = [b'{}\n', b'[]\n', b'not json\n', b'{"id":1,"id":1,"ok":true}\n',
                 b'{"id":true,"ok":true}\n', b'{"id":1,"ok":1}\n',
                 b'{"id":999,"ok":true}\n', b'{"id":1,"ok":true,"state":NaN}\n',
                 b'{"id":1,"ok":true,"state":1e999}\n',
                 b'{"id":1,"ok":true}\n{}\n', b'\xff\n', b'{"id":1']
        for data in cases:
            with self.subTest(data=data):
                with NativeSocket(lambda conn, req: conn.sendall(data), persistent=False) as server:
                    with self.assertRaises(PlayerProtocolError):
                        PlayerClient(server.path).observe()

    def test_native_error_envelope_is_preserved(self):
        from world.player import PlayerClient, PlayerNativeError
        def handler(conn, req):
            conn.sendall((json.dumps({'id': req['id'], 'ok': False,
                                     'error': 'busy', 'detail': 'press in progress'}) + '\n').encode())
        with NativeSocket(handler) as server:
            with self.assertRaises(PlayerNativeError) as caught:
                PlayerClient(server.path).observe()
            self.assertEqual(caught.exception.response['error'], 'busy')
            self.assertEqual(caught.exception.response['detail'], 'press in progress')

    def test_response_limit_and_socket_deadline(self):
        from world.player import PlayerClient, PlayerProtocolError, PlayerTimeoutError
        with NativeSocket(lambda conn, req: conn.sendall(b'x' * 129)) as server:
            with self.assertRaises(PlayerProtocolError):
                PlayerClient(server.path, max_response_bytes=128).observe()
        def slow(conn, req):
            for _ in range(30):
                conn.sendall(b' ')
                time.sleep(0.01)
        with NativeSocket(slow) as server:
            start = time.monotonic()
            with self.assertRaises(PlayerTimeoutError):
                PlayerClient(server.path, timeout=0.06).observe()
            self.assertLess(time.monotonic() - start, 0.3)


if __name__ == '__main__':
    unittest.main()
