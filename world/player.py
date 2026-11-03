"""Player-only Unix socket client. Responses are native envelopes, not inferred state."""
import argparse
import json
import math
import os
import socket
import sys
import threading
import time

MAX_REQUEST_BYTES = 8192
BUTTONS = ('UP', 'DOWN', 'LEFT', 'RIGHT', 'A', 'B', 'START', 'SELECT', 'L', 'R')
MAX_RESPONSE_BYTES = 1024 * 1024


class PlayerError(Exception):
    """A player operation failed. A timed out press must not be blindly retried."""


class PlayerProtocolError(PlayerError):
    pass


class PlayerTimeoutError(PlayerError):
    pass


class PlayerNativeError(PlayerError):
    def __init__(self, response):
        self.response = response
        super().__init__(str(response.get('error', 'native operation failed')))


def _json(data):
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError('duplicate JSON key')
            obj[key] = value
        return obj
    def constant(value):
        raise ValueError('non-finite JSON number')
    def number(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError('non-finite JSON number')
        return result
    try:
        return json.loads(data.decode('utf-8'), object_pairs_hook=pairs,
                          parse_constant=constant, parse_float=number)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise PlayerProtocolError('invalid JSON: ' + str(exc)) from exc


class PlayerClient:
    """One endpoint, one operation in flight, no retries or administrator actions.

    Each call returns the complete matching native response including its id/ok.
    timeout is a total connection/send/read deadline, in seconds.
    """
    def __init__(self, endpoint, *, timeout=5.0, max_response_bytes=MAX_RESPONSE_BYTES):
        self.endpoint = os.fspath(endpoint)
        if not isinstance(self.endpoint, str) or not self.endpoint or '\0' in self.endpoint:
            raise ValueError('endpoint must be a nonempty Unix socket path')
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('timeout must be finite and positive')
        if type(max_response_bytes) is not int or not 1 <= max_response_bytes <= MAX_RESPONSE_BYTES:
            raise ValueError('max_response_bytes must be 1..1048576')
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self._id = 0
        self._lock = threading.Lock()
        self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        conn = getattr(self, '_conn', None)
        if conn is not None:
            conn.close()

    def close(self):
        with self._lock:
            self._disconnect()

    def _disconnect(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def observe(self):
        return self._request('observe')

    def press(self, buttons, frames):
        """Hold exact uppercase GBA buttons for 1..120 executed native frames.

        An empty list advances without held buttons. No automatic retry occurs.
        Returns only after the native reply, never a synthetic acknowledgement.
        """
        if isinstance(buttons, str):
            buttons = [buttons]
        if not isinstance(buttons, (list, tuple)) or len(buttons) > len(BUTTONS):
            raise ValueError('buttons must be a list of uppercase GBA button names')
        if any(not isinstance(button, str) or button not in BUTTONS for button in buttons):
            raise ValueError('unknown button; expected ' + ', '.join(BUTTONS))
        if len(set(buttons)) != len(buttons):
            raise ValueError('duplicate buttons')
        if type(frames) is not int or not 1 <= frames <= 120:
            raise ValueError('frames must be an integer in 1..120')
        return self._request('press', buttons=list(buttons), frames=frames)

    def screenshot(self):
        """Ask native code for its fixed profile screenshot, with no path input.

        The response preserves the actual native screenshot path and state.
        This SDK does not open the path or infer visual game facts.
        """
        return self._request('screenshot')

    def _request(self, op, **fields):
        with self._lock:
            self._id = self._id % 2147483647 + 1
            request = {'id': self._id, 'op': op, **fields}
            payload = (json.dumps(request, separators=(',', ':'), allow_nan=False) + '\n').encode()
            if len(payload) > MAX_REQUEST_BYTES:
                raise ValueError('request exceeds 8192 bytes')
            deadline = time.monotonic() + self.timeout
            def remaining():
                value = deadline - time.monotonic()
                if value <= 0:
                    raise PlayerTimeoutError('player deadline expired; action completion is unknown')
                return value
            try:
                if self._conn is None:
                    self._conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    self._conn.settimeout(remaining())
                    self._conn.connect(self.endpoint)
                conn = self._conn
                conn.settimeout(remaining())
                conn.sendall(payload)
                data = bytearray()
                while True:
                    conn.settimeout(remaining())
                    chunk = conn.recv(min(4096, self.max_response_bytes + 1 - len(data)))
                    if not chunk:
                        raise PlayerProtocolError('native socket closed before complete JSONL response')
                    data.extend(chunk)
                    if len(data) > self.max_response_bytes:
                        raise PlayerProtocolError('native response exceeds byte limit')
                    if b'\n' in data:
                        line, extra = data.split(b'\n', 1)
                        if extra:
                            raise PlayerProtocolError('unexpected bytes after response')
                        response = _json(bytes(line))
                        break
                if not isinstance(response, dict) or type(response.get('id')) is not int or response['id'] != self._id:
                    raise PlayerProtocolError('missing or mismatched native response id')
                if type(response.get('ok')) is not bool:
                    raise PlayerProtocolError('native response ok must be boolean')
            except (socket.timeout, TimeoutError) as exc:
                self._disconnect()
                raise PlayerTimeoutError('player deadline expired; action completion is unknown') from exc
            except OSError as exc:
                self._disconnect()
                raise PlayerError('player socket: ' + str(exc)) from exc
            except PlayerError:
                self._disconnect()
                raise
            if not response['ok']:
                raise PlayerNativeError(response)
            return response


def capabilities():
    """Custom JSONL protocol description. This is not an MCP implementation."""
    empty = {'type': 'object', 'properties': {}, 'additionalProperties': False}
    return {
        'protocol': 'emerald-player-jsonl-v1',
        'description': 'Custom JSONL tools bound to one player endpoint. Not MCP.',
        'request': {'id': 'integer 0..2147483647', 'tool': 'one of tools[].name',
                    'arguments': 'object matching inputSchema, default {}'},
        'response': {'id': 'echoed request id', 'ok': 'boolean',
                     'result': 'unmodified native response on success',
                     'error': 'typed error on failure, including native envelope when available'},
        'limits': {'request_bytes': MAX_REQUEST_BYTES, 'response_bytes': MAX_RESPONSE_BYTES,
                   'frames': [1, 120], 'inflight': 1},
        'notes': ['No automatic retries. A timed out press may have executed.',
                  'Game continues in real time. State fields are only those supplied by the engine.',
                  'Screenshot paths come from native code, never from tool arguments.'],
        'tools': [
            {'name': 'observe', 'description': 'Read actual native game state.', 'inputSchema': empty},
            {'name': 'press', 'description': 'Hold GBA buttons until requested native frames complete.',
             'inputSchema': {'type': 'object', 'additionalProperties': False,
                             'required': ['buttons', 'frames'], 'properties': {
                                 'buttons': {'type': 'array', 'uniqueItems': True, 'maxItems': len(BUTTONS),
                                             'items': {'type': 'string', 'enum': list(BUTTONS)}},
                                 'frames': {'type': 'integer', 'minimum': 1, 'maximum': 120}}}},
            {'name': 'screenshot', 'description': 'Capture native fixed profile screenshot and return its path.',
             'inputSchema': empty},
        ],
    }


def _error(exc):
    error = {'type': type(exc).__name__, 'message': str(exc)}
    if isinstance(exc, PlayerNativeError):
        error['native'] = exc.response
    return error


def _emit(value):
    print(json.dumps(value, separators=(',', ':'), allow_nan=False), flush=True)


def serve(client):
    """Custom bounded JSONL stdio tools. Emits capabilities first, then replies.

    Example line: {"id":1,"tool":"press","arguments":{"buttons":["A"],"frames":1}}
    The endpoint is selected at startup only. No admin or file-reading tools exist.
    """
    _emit(capabilities())
    stream = sys.stdin.buffer
    while True:
        line = stream.readline(MAX_REQUEST_BYTES + 1)
        if not line:
            return 0
        request_id = None
        try:
            if len(line) > MAX_REQUEST_BYTES:
                while not line.endswith(b'\n'):
                    line = stream.readline(MAX_REQUEST_BYTES + 1)
                    if not line:
                        break
                raise PlayerProtocolError('tool request exceeds 8192 bytes')
            if not line.endswith(b'\n'):
                raise PlayerProtocolError('tool request must end with newline')
            request = _json(line)
            if not isinstance(request, dict):
                raise ValueError('tool request must be an object')
            candidate_id = request.get('id')
            if type(candidate_id) is not int or not 0 <= candidate_id <= 2147483647:
                raise ValueError('tool id must be an integer in 0..2147483647')
            request_id = candidate_id
            if set(request) - {'id', 'tool', 'arguments'}:
                raise ValueError('unknown request fields')
            arguments = request.get('arguments', {})
            if not isinstance(arguments, dict):
                raise ValueError('arguments must be an object')
            tool = request.get('tool')
            if tool in ('observe', 'screenshot'):
                if arguments:
                    raise ValueError(tool + ' accepts no arguments')
                result = client.observe() if tool == 'observe' else client.screenshot()
            elif tool == 'press':
                if set(arguments) != {'buttons', 'frames'}:
                    raise ValueError('press requires only buttons and frames')
                if not isinstance(arguments['buttons'], list):
                    raise ValueError('tool buttons must be an array')
                result = client.press(arguments['buttons'], arguments['frames'])
            else:
                raise ValueError('unknown tool; only observe, press, screenshot are available')
            _emit({'id': request_id, 'ok': True, 'result': result})
        except (PlayerError, ValueError) as exc:
            _emit({'id': request_id, 'ok': False, 'error': _error(exc)})


def main(argv=None):
    parser = argparse.ArgumentParser(description='Player-only native socket SDK and custom JSONL tools (not MCP).')
    parser.add_argument('--endpoint', required=True, help='One private player-control Unix socket path')
    parser.add_argument('--timeout', type=float, default=5.0, help='Total socket deadline in seconds (default 5)')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('observe', help='Print the actual native observation JSON')
    press = commands.add_parser('press', help='Wait for native completion of 1..120 input frames')
    press.add_argument('--buttons', nargs='*', default=[], choices=BUTTONS,
                       help='Exact uppercase GBA buttons; omit for no held buttons')
    press.add_argument('--frames', required=True, type=int)
    commands.add_parser('screenshot', help='Print native JSON including its fixed screenshot path')
    commands.add_parser('capabilities', help='Print the custom JSONL protocol and tool schemas')
    commands.add_parser('serve', help='Custom JSONL stdio server: capabilities first, then {id,tool,arguments} lines')
    args = parser.parse_args(argv)
    try:
        client = PlayerClient(args.endpoint, timeout=args.timeout)
        if args.command == 'serve':
            return serve(client)
        if args.command == 'capabilities':
            result = capabilities()
        elif args.command == 'observe':
            result = client.observe()
        elif args.command == 'screenshot':
            result = client.screenshot()
        else:
            result = client.press(args.buttons, args.frames)
        _emit(result)
        return 0
    except PlayerNativeError as exc:
        _emit(exc.response)
        return 1
    except (PlayerError, ValueError) as exc:
        _emit({'ok': False, 'error': _error(exc)})
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
