"""Ephemeral two-player consent coordinator (not a native command validator).

All actors are exact authenticated server IDs, never request-body identities.
Presence is a server-owned mapping ID -> [group,num,x,y,facing,gfx,ready].
Call serially on the server loop. Deliver every Result.events / LinkError.events
reliably and in order. On delivery failure call disconnect for that connection.
No saves, trade commits, automatic retransmits or durable recovery live here.
"""
from dataclasses import dataclass, field
from types import MappingProxyType
import math
import time
import inspect
from functools import wraps
from uuid import uuid4


def _operation(method):
    """Expire before validation, preserving abort events even on bad requests."""
    signature = inspect.signature(method)

    @wraps(method)
    def call(self, *args, **kwargs):
        bound = signature.bind(self, *args, **kwargs)
        now = self._time(bound.arguments.get('now'))
        bound.arguments['now'] = now
        expired = self._expire(now)
        try:
            result = method(*bound.args, **bound.kwargs)
        except LinkError as error:
            error.events = expired + error.events
            raise
        return Result(result.session_id, result.generation, expired + result.events)
    return call


class RegionPresence(dict):
    """Authority-only place scopes; native seven-field STATE remains unchanged."""
    def __init__(self, states, scopes):
        super().__init__(states)
        self.scopes = scopes


class LinkError(ValueError):
    def __init__(self, code, events=()):
        super().__init__(code)
        self.code = code
        self.events = tuple(events)


@dataclass(frozen=True)
class Event:
    recipient: str
    data: object


@dataclass(frozen=True)
class Result:
    session_id: str | None
    generation: int | None
    events: tuple = ()


@dataclass
class _NativeTail:
    step: int
    handshake: bool
    next_steps: dict
    rows: dict


@dataclass
class _Session:
    id: str
    generation: int
    proposer: str
    target: str
    kind: str
    participants: tuple
    deadline: float
    state: str = 'pending'
    ready: set = field(default_factory=set)
    step: int = 0
    pending: dict = field(default_factory=dict)
    previous: tuple | None = None
    link_generation: int = 0
    closed_generation: int | None = None
    link_type: int = 0
    opens: set = field(default_factory=set)
    native_open: bool = False
    handshake: bool = False
    native_pending: dict = field(default_factory=dict)
    native_history: dict = field(default_factory=dict)
    native_next: dict = field(default_factory=dict)
    native_tail: _NativeTail | None = None


class LinkSessions:
    """offer/accept/ready return Results; errors have stable .code and .events.

    Event data always includes type, session_id, generation, kind, participants,
    proposer, target, state, link_generation and link_type. Participants are
    immutable lexicographic native indices (0, 1). Session generation is stable
    and monotonic within this coordinator; IDs have a public restart namespace.
    Native mode: accept -> open from both -> pair -> slot-0 advance -> handshake
    -> submit. No overworld readiness check is made after native admission.
    Pair/handshake carry step=0 and zero 2x8 words. Frames carry step and words.
    Map step to native round and link_generation to native uint32 generation.
    close_generation preserves consent, resets step, and requires next OPEN
    generation. Do not map generation_closed to an activity ABORT.
    ready is an alternative non-native barrier; it is not used by native mode.
    Explicit ``now`` overrides the injected monotonic clock, never wall time.
    Timeouts are (0, 60] seconds. now is finite [0, 2**53-1], nondecreasing.
    tick must be called periodically even when no client sends requests.
    """
    KINDS = frozenset(('battle_single', 'battle_double', 'trade', 'coop_wild'))
    NATIVE_WINDOW = 16

    def __init__(self, *, clock=time.monotonic, consent_timeout=15,
                 step_timeout=10, max_steps=4294967296, max_sessions=8):
        for timeout in (consent_timeout, step_timeout):
            if type(timeout) not in (int, float) or not 0 < timeout <= 60 or not math.isfinite(timeout):
                raise LinkError('invalid_timeout')
        if type(max_steps) is not int or not 1 <= max_steps <= 4294967296:
            raise LinkError('invalid_max_steps')
        if type(max_sessions) is not int or not 1 <= max_sessions <= 64:
            raise LinkError('invalid_max_sessions')
        self.max_sessions = max_sessions
        self._clock = clock
        self._consent_timeout = consent_timeout
        self._step_timeout = step_timeout
        self._max_steps = max_steps
        self._instance = uuid4().hex
        self._last_now = None
        self._generation = 0
        self._sessions = {}
        self._locks = {}

    def _time(self, now):
        now = self._clock() if now is None else now
        if type(now) not in (int, float) or not 0 <= now <= 9007199254740991 or not math.isfinite(now):
            raise LinkError('invalid_time')
        if self._last_now is not None and now < self._last_now:
            raise LinkError('clock_regressed')
        self._last_now = now
        return now

    @staticmethod
    def _id(actor):
        if type(actor) is not str or not 1 <= len(actor) <= 64 or not all(c.isascii() and (c.isalnum() or c in '_-') for c in actor):
            raise LinkError('invalid_actor')

    @staticmethod
    def _near(presence, a, b, *, coop=False):
        if not isinstance(presence, dict):
            raise LinkError('invalid_presence')
        if isinstance(presence, RegionPresence) and presence.scopes.get(a) != presence.scopes.get(b):
            raise LinkError('different_region')
        states = []
        for actor in (a, b):
            s = presence.get(actor)
            if type(s) not in (list, tuple) or len(s) != 7 or any(type(v) is not int for v in s):
                raise LinkError('invalid_presence')
            if any(v < 0 or v > 65535 for v in s[:6]) or s[6] != 1:
                raise LinkError('not_ready')
            states.append(s)
        a, b = states
        if coop:
            if tuple(a[:2]) != tuple(b[:2]) or max(abs(a[2] - b[2]), abs(a[3] - b[3])) > 12:
                raise LinkError('not_in_range')
        elif tuple(a[:2]) != tuple(b[:2]) or abs(a[2] - b[2]) + abs(a[3] - b[3]) != 1:
            raise LinkError('not_adjacent')

    @staticmethod
    def _events(s, event_type, **extra):
        data = MappingProxyType(dict(type=event_type, session_id=s.id,
            generation=s.generation, kind=s.kind, participants=s.participants,
            proposer=s.proposer, target=s.target, state=s.state,
            link_generation=s.link_generation, link_type=s.link_type, **extra))
        return tuple(Event(actor, data) for actor in s.participants)

    def _result(self, s, events=()):
        return Result(s.id, s.generation, tuple(events))

    @_operation
    def offer(self, actor, target, kind, presence, now=None):
        now = self._time(now)
        self._id(actor)
        self._id(target)
        if actor == target:
            raise LinkError('self_offer')
        if type(kind) is not str or kind not in self.KINDS:
            raise LinkError('invalid_kind')
        if actor in self._locks or target in self._locks:
            raise LinkError('busy')
        if len(self._sessions) >= self.max_sessions:
            raise LinkError('capacity')
        self._near(presence, actor, target, coop=kind == 'coop_wild')
        self._generation += 1
        sid = 'link-' + self._instance + '-' + str(self._generation)
        s = _Session(sid, self._generation, actor, target, kind,
                     tuple(sorted((actor, target))), now + self._consent_timeout)
        self._sessions[sid] = s
        self._locks[actor] = self._locks[target] = sid
        return self._result(s, self._events(s, 'offer', deadline=s.deadline))

    def _member(self, actor, session_id):
        self._id(actor)
        if type(session_id) is not str:
            raise LinkError('invalid_session')
        s = self._sessions.get(session_id)
        if s is None:
            raise LinkError('unknown_session')
        if actor not in s.participants:
            raise LinkError('not_member')
        return s

    @_operation
    def accept(self, actor, session_id, presence, now=None):
        self._time(now)
        s = self._member(actor, session_id)
        if actor != s.target:
            raise LinkError('not_target')
        if s.state != 'pending':
            raise LinkError('invalid_state')
        self._near(presence, *s.participants, coop=s.kind == 'coop_wild')
        s.state = 'preparing'
        return self._result(s, self._events(s, 'accepted'))

    @_operation
    def ready(self, actor, session_id, presence, now=None):
        now = self._time(now)
        s = self._member(actor, session_id)
        if s.state != 'preparing' or s.link_generation:
            raise LinkError('invalid_state')
        self._near(presence, *s.participants, coop=s.kind == 'coop_wild')
        s.ready.add(actor)
        if len(s.ready) == 2:
            s.state = 'active'
            s.deadline = now + self._step_timeout
            return self._result(s, self._events(s, 'active', step=0))
        return self._result(s)

    def _end(self, s, reason):
        s.state = 'closed'
        del self._sessions[s.id]
        for actor in s.participants:
            del self._locks[actor]
        return self._events(s, 'closed', reason=reason)

    def _expire(self, now):
        events = ()
        for s in tuple(self._sessions.values()):
            if now >= s.deadline:
                reason = 'step_timeout' if s.state == 'active' or s.link_generation else 'consent_timeout'
                events += self._end(s, reason)
        return events

    @_operation
    def tick(self, now=None):
        return Result(None, None)

    @_operation
    def reject(self, actor, session_id, now=None):
        s = self._member(actor, session_id)
        if actor != s.target:
            raise LinkError('not_target')
        if s.state != 'pending':
            raise LinkError('invalid_state')
        return self._result(s, self._end(s, 'rejected'))

    @_operation
    def close(self, actor, session_id, now=None):
        s = self._member(actor, session_id)
        return self._result(s, self._end(s, 'closed'))

    @_operation
    def disconnect(self, actor, now=None):
        self._id(actor)
        sid = self._locks.get(actor)
        if sid is None:
            return Result(None, None)
        s = self._sessions[sid]
        return self._result(s, self._end(s, 'disconnect'))

    @_operation
    def submit(self, actor, session_id, generation, step, commands, now=None,
               *, link_generation=None):
        """Validate structural u16 envelope only, NOT native engine semantics.

        Native mode accepts sequential per-actor rounds in a 16-slot window,
        retains 16 committed matrices for exact duplicate checks, and never
        replays frames. Non-native mode remains strict stop-and-wait.
        Only completion by both peers extends the active deadline.
        """
        now = self._time(now)
        s = self._member(actor, session_id)
        if type(generation) is not int or generation != s.generation:
            raise LinkError('invalid_generation')
        old_native = (type(link_generation) is int
                      and link_generation == s.closed_generation)
        if not old_native:
            if s.native_open:
                self._link_generation(s, link_generation)
            elif link_generation is not None:
                raise LinkError('invalid_link_generation')
        if not old_native and s.state != 'active':
            raise LinkError('invalid_state')
        if type(step) is not int or not 0 <= step < self._max_steps:
            raise LinkError('invalid_step')
        if type(commands) not in (list, tuple) or len(commands) != 8:
            raise LinkError('invalid_commands')
        if any(type(word) is not int or not 0 <= word <= 65535 for word in commands):
            raise LinkError('invalid_commands')
        words = tuple(commands)
        if old_native:
            return self._submit_native_tail(s, actor, step, words)
        # Pairing gates full native ticks. The lobby needs empty committed
        # ticks to reach its host ADVANCE callback before gameplay commands.
        if s.native_open and not s.handshake and any(words):
            raise LinkError('invalid_state')
        if s.native_open:
            return self._submit_native(s, actor, step, words, now)
        if s.previous is not None and step == s.step - 1:
            if s.previous[s.participants.index(actor)] != words:
                raise LinkError('conflicting_duplicate')
            return self._result(s)
        if step != s.step:
            raise LinkError('invalid_step')
        if actor in s.pending:
            if s.pending[actor] != words:
                raise LinkError('conflicting_duplicate')
            return self._result(s)
        s.pending[actor] = words
        if len(s.pending) < 2:
            return self._result(s)
        frame = tuple(s.pending[p] for p in s.participants)
        events = self._events(s, 'frame', step=step, words=frame)
        s.previous = frame
        s.pending.clear()
        s.step += 1
        s.deadline = now + self._step_timeout
        if s.step == self._max_steps:
            events += self._end(s, 'step_limit')
        return self._result(s, events)

    def _submit_native_tail(self, s, actor, step, words):
        # A CLOSE on one socket can overtake another socket's pipelined rounds.
        # Only the last generation survives, with a fixed (never sliding) bound.
        # These vectors are swallowed, never committed into the next generation.
        tail = s.native_tail
        if tail is None:
            raise LinkError('invalid_link_generation')
        row = tail.rows.get(step, {})
        if actor in row:
            if row[actor] != words:
                raise LinkError('conflicting_duplicate')
            return self._result(s)
        if step != tail.next_steps.get(actor, 0) or not tail.step <= step < tail.step + self.NATIVE_WINDOW:
            raise LinkError('invalid_step')
        if not tail.handshake and any(words):
            raise LinkError('invalid_state')
        tail.rows.setdefault(step, {})[actor] = words
        tail.next_steps[actor] = step + 1
        return self._result(s)

    def _submit_native(self, s, actor, step, words, now):
        # A peer cannot skip even an idle round. Retain exact committed vectors
        # for one window so retransmission cannot replace engine contributions.
        row = s.native_history.get(step, s.native_pending.get(step, {}))
        if actor in row:
            if row[actor] != words:
                raise LinkError('conflicting_duplicate')
            return self._result(s)
        if step != s.native_next.get(actor, 0) or not s.step <= step < s.step + self.NATIVE_WINDOW:
            raise LinkError('invalid_step')
        s.native_pending.setdefault(step, {})[actor] = words
        s.native_next[actor] = step + 1
        events = ()
        while len(s.native_pending.get(s.step, {})) == 2:
            row = s.native_pending.pop(s.step)
            frame = tuple(row[p] for p in s.participants)
            events += self._events(s, 'frame', step=s.step, words=frame)
            s.native_history[s.step] = row
            s.step += 1
            s.native_history.pop(s.step - self.NATIVE_WINDOW - 1, None)
            s.deadline = now + self._step_timeout
            if s.step == self._max_steps:
                events += self._end(s, 'step_limit')
                break
        return self._result(s, events)

    @staticmethod
    def _link_generation(s, generation):
        if type(generation) is not int or not 1 <= generation <= 4294967295 or generation != s.link_generation:
            raise LinkError('invalid_link_generation')

    @_operation
    def open(self, actor, session_id, link_generation, link_type, now=None):
        """Authenticated native OPEN after consent; no overworld ready recheck.

        Exactly matching bilateral OPEN publishes PAIR. Generation starts at 1,
        advances only after close_generation, and cannot wrap or skip.
        """
        now = self._time(now)
        s = self._member(actor, session_id)
        if type(link_generation) is not int or not 1 <= link_generation <= 4294967295:
            raise LinkError('invalid_link_generation')
        if type(link_type) is not int or not 0 <= link_type <= 65535:
            raise LinkError('invalid_link_type')
        if s.state not in ('preparing', 'opening', 'active'):
            raise LinkError('invalid_state')
        if s.native_open:
            self._link_generation(s, link_generation)
            if link_type != s.link_type:
                raise LinkError('link_type_mismatch')
            if actor in s.opens:
                return self._result(s)
        else:
            if link_generation != s.link_generation + 1:
                raise LinkError('invalid_link_generation')
            s.link_generation = link_generation
            s.link_type = link_type
            s.native_open = True
            s.native_pending.clear()
            s.native_history.clear()
            s.native_next.clear()
            s.handshake = False
            s.opens.clear()
            s.ready.clear()
            s.pending.clear()
            s.previous = None
            s.step = 0
            s.state = 'opening'
            s.deadline = now + self._step_timeout
        s.opens.add(actor)
        if len(s.opens) < 2:
            return self._result(s)
        s.state = 'active'
        s.deadline = now + self._step_timeout
        return self._result(s, self._events(s, 'pair', step=0, words=((0,) * 8,) * 2))

    @_operation
    def advance(self, actor, session_id, link_generation, now=None):
        """Slot zero ADVANCE publishes exactly one HANDSHAKE per generation."""
        now = self._time(now)
        s = self._member(actor, session_id)
        self._link_generation(s, link_generation)
        if actor != s.participants[0]:
            raise LinkError('not_host')
        if not s.native_open or s.state != 'active' or len(s.opens) != 2:
            raise LinkError('invalid_state')
        if s.handshake:
            return self._result(s)
        s.handshake = True
        s.deadline = now + self._step_timeout
        return self._result(s, self._events(s, 'handshake', step=0, words=((0,) * 8,) * 2))

    @_operation
    def close_generation(self, actor, session_id, link_generation, now=None):
        """Close a native generation, not its bilateral activity reservation."""
        now = self._time(now)
        s = self._member(actor, session_id)
        # Independent sockets can deliver the other peer's CLOSE after the
        # first peer has already OPENed the next generation. It is a bounded
        # acknowledgment, never permission to reset the new state.
        if type(link_generation) is int and link_generation == s.closed_generation:
            return self._result(s)
        self._link_generation(s, link_generation)
        if not s.native_open:
            return self._result(s)
        s.native_tail = _NativeTail(s.step, s.handshake, s.native_next.copy(),
                                    {**s.native_history, **s.native_pending})
        s.native_pending.clear()
        s.native_history.clear()
        s.native_next.clear()
        s.native_open = False
        s.closed_generation = link_generation
        s.handshake = False
        s.state = 'preparing'
        s.opens.clear()
        s.ready.clear()
        s.pending.clear()
        s.previous = None
        s.step = 0
        s.deadline = now + self._step_timeout
        return self._result(s, self._events(s, 'generation_closed'))
