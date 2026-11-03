"""Read-only ordinary-player event pipe, not an agent runner or Hermes wakeup.

First observation and reconnection are baselines: no historic meeting/dialogue
triggers. Polling can miss intermediate native changes. Meeting seq is a monotonic
high-water mark for this observer's lifetime (restart it after a world reset).
Public dialogue is bounded, marked untrusted, and never host instructions.
No press, screenshot, admin endpoint, provider, or file access is used.
"""
import copy
import json
import math
from pathlib import Path
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from world.player import PlayerClient, PlayerError, PlayerProtocolError

MAX_OBSERVATION_BYTES = 65536
MAX_EVENT_BYTES = 4096
MAX_PEERS = 64
MAX_DIALOGUE_CHARS = 512
_NAME = re.compile(r'[A-Za-z0-9_-]{1,32}\Z')
_SENSITIVE = re.compile(
    r'(?i)(?:token|secret|password|api[_ -]?key|authorization|bearer|sk-)|'
    r'(?:[/\\]|[A-Za-z]:)|[A-Za-z0-9_+=-]{40,}')


class PlayerIdentityError(PlayerError):
    """The endpoint does not belong to the explicitly selected trainer."""


def _name(value, *, empty=False):
    if empty and value == '':
        return value
    if not isinstance(value, str) or not _NAME.fullmatch(value):
        raise ValueError('invalid public identifier')
    return value


def _integer(value, low=0, high=4294967295):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('invalid integer')
    return value


def _pair(value, low, high):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError('invalid coordinates')
    return [_integer(v, low, high) for v in value]


def _text(value):
    if not isinstance(value, str) or len(value) > 4096:
        raise ValueError('invalid dialogue')
    # Native public prose is the only free-form field admitted. Never copy an
    # envelope/error as prose. Defensive filtering is not a general DLP service.
    if _SENSITIVE.search(value):
        return {'text': '[redacted]', 'truncated': False, 'untrusted': True}
    safe = ''.join(c for c in value if c == '\n' or (c.isprintable() and not 0xD800 <= ord(c) <= 0xDFFF))
    bounded = safe[:MAX_DIALOGUE_CHARS]
    # ASCII JSON escapes astral characters as surrogate pairs. Bound the wire
    # representation too, leaving room for the event metadata and identifiers.
    while len(json.dumps(bounded, ensure_ascii=True)) > 2048:
        bounded = bounded[:-1]
    return {'text': bounded, 'truncated': len(bounded) < len(safe), 'untrusted': True}


def _snapshot(native, trainer):
    """Validate atomically and retain only explicit bounded public fields."""
    if not isinstance(native, dict) or native.get('ok') is not True:
        raise ValueError('invalid native envelope')
    state = native.get('state')
    if not isinstance(state, dict) or not isinstance(state.get('world'), dict):
        raise ValueError('missing native state')
    world = state['world']
    if world.get('trainer') != trainer:
        raise PlayerIdentityError('bound trainer identity mismatch')
    if len(json.dumps(native, ensure_ascii=True, allow_nan=False).encode()) > MAX_OBSERVATION_BYTES:
        raise ValueError('observation exceeds limit')
    if type(world.get('connected')) is not bool or type(world.get('dialogue_active')) is not bool:
        raise ValueError('invalid world flags')
    result = {'frame': _integer(state.get('frame')), 'map': _pair(state.get('map'), -1, 255),
              'battle': _integer(state.get('battle'), 0, 1), 'connected': world['connected']}
    peers = world.get('peers')
    if not isinstance(peers, list) or len(peers) > MAX_PEERS:
        raise ValueError('invalid peers')
    result['peers'] = {}
    for peer in peers:
        if not isinstance(peer, dict):
            raise ValueError('invalid peer')
        name = _name(peer.get('trainer'))
        if name == trainer or name in result['peers']:
            raise ValueError('invalid peer identity')
        result['peers'][name] = {'trainer': name, 'map': _pair(peer.get('map'), 0, 255),
                                  'pos': _pair(peer.get('pos'), -32768, 32767)}
    result['dialogue'] = None
    if world['dialogue_active']:
        result['dialogue'] = {'object': _name(world.get('dialogue_object')),
                              'interaction_seq': _integer(world.get('interaction_seq', 0)),
                              **_text(world.get('dialogue_text'))}
    meeting = world.get('meeting')
    result['meeting'] = None
    if meeting is not None:
        if not isinstance(meeting, dict) or meeting.get('signal') != 'explore':
            raise ValueError('invalid meeting')
        result['meeting'] = {'seq': _integer(meeting.get('seq')),
                              'player': _name(meeting.get('player')),
                              'target': _name(meeting.get('target')), 'signal': 'explore'}
    return result


class PlayerObserver:
    """Bounded synchronous subscription over one ordinary PlayerClient.

    poll() returns a bounded list, sleeping before every call after the first.
    Errors return a deduplicated disconnected event, close the transport, and
    schedule capped exponential backoff. Identity mismatch is fatal. Never use
    the same client concurrently for actions. close() owns and closes it.
    Inject sleep/clock for deterministic tests. Events contain only public
    projections, never raw native responses, exception messages or paths.
    """
    def __init__(self, client, *, trainer, interval=0.25, backoff_initial=0.5,
                 backoff_max=8.0, sleep=time.sleep, clock=time.monotonic):
        self.trainer = _name(trainer)
        for value in (interval, backoff_initial, backoff_max):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0.05 <= value <= 60:
                raise ValueError('polling delays must be finite and in 0.05..60 seconds')
        if backoff_max < backoff_initial or backoff_initial < interval:
            raise ValueError('backoff must be at least interval and initial backoff')
        self.client = client
        self.interval = interval
        self.backoff_initial = backoff_initial
        self.backoff_max = backoff_max
        self.sleep = sleep
        self.clock = clock
        self._delay = 0
        self._backoff = backoff_initial
        self._previous = None
        self._meeting_seq = 0
        self._disconnected = False
        self._closed = False
        self._seq = 0

    def close(self):
        if not self._closed:
            self._closed = True
            self._previous = None
            self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _event(self, kind, data, frame=None):
        self._seq += 1
        return {'type': kind, 'seq': self._seq, 'time': self.clock(),
                'trainer': self.trainer, 'frame': frame, 'data': copy.deepcopy(data)}

    def _offline(self, reason):
        self.client.close()
        self._previous = None
        self._delay = self._backoff
        self._backoff = min(self.backoff_max, self._backoff * 2)
        if self._disconnected:
            return []
        self._disconnected = True
        return [self._event('disconnected', {'reason': reason})]

    def poll(self):
        if self._closed:
            raise RuntimeError('observer is closed')
        if self._delay:
            self.sleep(self._delay)
        try:
            current = _snapshot(self.client.observe(), self.trainer)
        except PlayerIdentityError:
            self.close()
            raise
        except (PlayerError, OSError, ValueError, TypeError, RecursionError):
            return self._offline('observation_unavailable')
        if not current['connected']:
            return self._offline('world_disconnected')
        self._delay = self.interval
        self._backoff = self.backoff_initial
        events = []
        def emit(kind, data):
            events.append(self._event(kind, data, current['frame']))
        if self._disconnected:
            emit('reconnected', {})
            self._disconnected = False
        meeting = current['meeting']
        if meeting and meeting['seq'] > self._meeting_seq:
            if self._previous is not None and meeting['target'] == self.trainer and meeting['player'] != self.trainer:
                emit('meeting', dict(meeting))
            self._meeting_seq = meeting['seq']
        previous = self._previous
        if previous is not None:
            for field in ('map', 'battle'):
                if previous[field] != current[field]:
                    emit(field + '_changed', {'previous': previous[field], 'current': current[field]})
            dialogue, old = current['dialogue'], previous['dialogue']
            if dialogue is not None and dialogue != old:
                emit('dialogue_opened' if old is None else 'dialogue_changed', dict(dialogue))
            elif dialogue is None and old is not None:
                emit('dialogue_closed', {})
            old_peers, peers = previous['peers'], current['peers']
            for name in sorted(old_peers.keys() | peers.keys()):
                if name not in old_peers:
                    emit('peer_arrived', dict(peers[name]))
                elif name not in peers:
                    emit('peer_departed', dict(old_peers[name]))
                elif old_peers[name] != peers[name]:
                    emit('peer_moved', dict(peers[name]))
        self._previous = current
        return events

    def events(self, *, max_polls=None):
        """Yield changes without an unbounded queue. Close on exit/exhaustion.

        Close this generator explicitly when abandoning iteration, or use the
        observer as a context manager. max_polls bounds observations, not events.
        """
        if max_polls is not None:
            _integer(max_polls, 1, 1000000)
        count = 0
        try:
            while not self._closed and (max_polls is None or count < max_polls):
                count += 1
                yield from self.poll()
        finally:
            self.close()


def watch(observer, *, max_polls=None, stream=None):
    """Emit bounded JSONL event records with immediate flush, no raw errors."""
    stream = sys.stdout if stream is None else stream
    try:
        for event in observer.events(max_polls=max_polls):
            line = json.dumps(event, separators=(',', ':'), ensure_ascii=True, allow_nan=False)
            if len(line.encode()) + 1 > MAX_EVENT_BYTES:
                raise PlayerProtocolError('event exceeds limit')
            stream.write(line + '\n')
            stream.flush()
        return 0
    except KeyboardInterrupt:
        return 130
    except BrokenPipeError:
        return 0
    finally:
        observer.close()


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', required=True, help='Explicit own-player Unix socket')
    parser.add_argument('--trainer', required=True, help='Expected own trainer identity')
    parser.add_argument('--timeout', type=float, default=5.0)
    parser.add_argument('--interval', type=float, default=0.25)
    parser.add_argument('--backoff-initial', type=float, default=0.5)
    parser.add_argument('--backoff-max', type=float, default=8.0)
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('watch', help='Flush read-only public events as JSONL')
    command.add_argument('--max-polls', type=int, help='Stop after this many observations')
    args = parser.parse_args(argv)
    client = None
    observer = None
    try:
        _name(args.trainer)
        if args.max_polls is not None:
            _integer(args.max_polls, 1, 1000000)
        client = PlayerClient(args.endpoint, timeout=args.timeout,
                              max_response_bytes=MAX_OBSERVATION_BYTES)
        observer = PlayerObserver(client, trainer=args.trainer, interval=args.interval,
                                  backoff_initial=args.backoff_initial, backoff_max=args.backoff_max)
        return watch(observer, max_polls=args.max_polls)
    except PlayerIdentityError:
        print('{"type":"error","data":{"reason":"identity_mismatch"}}', flush=True)
        return 1
    except (PlayerError, ValueError):
        print('{"type":"error","data":{"reason":"invalid_configuration_or_event"}}', flush=True)
        return 1
    finally:
        if observer is not None:
            observer.close()
        elif client is not None:
            client.close()


if __name__ == '__main__':
    raise SystemExit(main())
