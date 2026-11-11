"""Bounded native link wire codec backed by authoritative consent sessions.

This module relays native command rounds. It does not simulate a battle, mutate
saves, or certify the safety of engine-level command payloads. Call serially from
the authenticated server loop and deliver returned recipient/line pairs in order.
"""
from dataclasses import dataclass
import re
import secrets
import struct
import time

from .link_sessions import LinkError, LinkSessions

_NAME = re.compile(r'[A-Za-z0-9_-]{1,24}\Z')
_HEX = re.compile(r'[0-9a-f]{32}\Z')
_KINDS = {1: 'battle_single', 2: 'battle_double', 3: 'trade', 4: 'coop_wild', 5: 'contest'}
_LINK_TYPES = {1: frozenset((0x2211, 0x2233)),
               2: frozenset((0x2211, 0x2244)),
               3: frozenset((0x1111, 0x1122, 0x1133, 0x1144)),
               4: frozenset((0x2255, 0x2211)), 5: frozenset((0x6602,))}


@dataclass
class _Tag:
    id: int
    proposer: str
    target: str
    deadline: float
    active: bool = False
    in_range: int = 0
    next_keepalive: float = 0
    coop_wire: int | None = None

    @property
    def participants(self):
        return (self.proposer, self.target)


@dataclass(frozen=True)
class _WireSession:
    internal: str
    generation: int
    mode: int
    participants: tuple


def _uint(text, limit):
    if not text or len(text) > 20 or not text.isascii() or not text.isdecimal():
        raise ValueError('integer')
    value = int(text)
    if value > limit:
        raise ValueError('integer')
    return value


class LinkProtocol:
    def __init__(self, *, clock=time.monotonic, id_factory=None, max_players=8):
        if type(max_players) is not int or not 1 <= max_players <= 64:
            raise ValueError('max_players must be between 1 and 64')
        self.max_players = max_players
        self.sessions = LinkSessions(clock=clock, max_sessions=max_players // 2 or 1)
        self.id_factory = id_factory or (lambda: secrets.randbits(64))
        self._wire = {}
        self._internal = {}
        self._last_wire = None
        self._tags = {}
        self._tag_actor = {}
        self._encounters = {}  # connection-local tag/token; never save progress

    def admit_contest(self, members, presence):
        """Only called after both counter selections and native ACKs are verified."""
        actor,target=members
        wire=self._new_id()
        offered=self.sessions.offer(actor,target,'contest',presence)
        event=next(e for e in offered.events if e.data['type']=='offer')
        entry=_WireSession(offered.session_id,offered.generation,5,event.data['participants'])
        self._wire[wire]=entry;self._internal[entry.internal]=wire
        try:
            accepted=self.sessions.accept(target,entry.internal,presence)
        except Exception:
            self._deliver(self.sessions.disconnect(actor).events)
            raise
        return wire,self._deliver(accepted.events)

    def busy(self, actor):
        """Region selection must not carry an existing link/tag into a new place."""
        return actor in self.sessions._locks or actor in self._tag_actor

    def field_action_busy(self, actor):
        """A social tag is not a battle; retain the stricter relocation busy()."""
        if actor in self.sessions._locks or actor in self._encounters:
            return True
        identity = self._tag_actor.get(actor)
        if identity is None:
            return False
        tag = self._tags.get(identity)
        # An inconsistent tag cannot prove that field execution is safe.
        return tag is None or actor not in tag.participants or tag.coop_wire is not None

    def _end_tag(self, tag):
        del self._tags[tag.id]
        for actor in tag.participants:
            self._encounters.pop(actor, None)
        for actor in tag.participants:
            del self._tag_actor[actor]
        return [(actor, f'T END {tag.id}\n') for actor in tag.participants]

    def update_presence(self, presence):
        output = []
        for tag in self._tags.values():
            if not tag.active:
                continue
            try:
                self.sessions._near(presence, *tag.participants, coop=True)
                flag = 1
            except LinkError:
                flag = 0
            if flag != tag.in_range:
                tag.in_range = flag
                output.extend((actor, f'T RANGE {tag.id} {flag}\n') for actor in tag.participants)
        return output

    def _tag_request(self, actor, fields, presence, now):
        if len(fields) != 3:
            raise ValueError('tag shape')
        op, value = fields[1:]
        if op == 'OFFER':
            if not _NAME.fullmatch(value):
                raise ValueError('target')
            if actor == value:
                raise LinkError('self_offer')
            if actor in self._tag_actor or value in self._tag_actor:
                raise LinkError('busy')
            if len(self._tag_actor) + 2 > self.max_players:
                raise LinkError('capacity')
            self.sessions._near(presence, actor, value, coop=True)
            # Human consent includes reading the invitation and switching windows.
            # This deadline is authoritative for both client invitation views.
            tag = _Tag(self._new_id(), actor, value, now + 60, next_keepalive=now + 10)
            self._tags[tag.id] = tag
            self._tag_actor[actor] = self._tag_actor[value] = tag.id
            return [(value, f'T OFFER {tag.id} {actor}\n')]
        if op not in ('ACCEPT', 'REJECT', 'END'):
            raise ValueError('tag operation')
        tag = self._tags.get(_uint(value, 2**64-1))
        if tag is None:
            raise LinkError('unknown_session')
        if actor not in tag.participants:
            raise LinkError('not_member')
        if op == 'END':
            return self._end_tag(tag)
        if actor != tag.target:
            raise LinkError('not_target')
        if tag.active:
            raise LinkError('invalid_state')
        if op == 'REJECT':
            return self._end_tag(tag)
        self.sessions._near(presence, *tag.participants, coop=True)
        tag.active = True
        tag.in_range = 1
        tag.next_keepalive = now + 10
        return [(a, f'T ACTIVE {tag.id} {b} 1\n')
                for a, b in ((tag.proposer, tag.target), (tag.target, tag.proposer))]

    def _new_id(self):
        # A random process namespace followed by a counter avoids reuse without
        # keeping an unbounded tombstone set for every completed activity.
        value = self.id_factory() if self._last_wire is None else self._last_wire + 1
        if type(value) is not int or not 0 < value < 2**64:
            raise LinkError('capacity')
        self._last_wire = value
        return value

    def _entry(self, actor, wire):
        entry = self._wire.get(wire)
        if entry is None:
            raise LinkError('unknown_session')
        if actor not in entry.participants:
            raise LinkError('not_member')
        return entry

    def _deliver(self, events):
        output = []
        closed = set()
        for event in events:
            data = event.data
            wire = self._internal.get(data['session_id'])
            if wire is None:
                continue
            entry = self._wire[wire]
            kind = data['type']
            if kind == 'offer':
                if event.recipient != data['target']:
                    continue
                line = f'L OFFER {wire} {entry.mode} {data["proposer"]}\n'
            elif kind == 'accepted':
                slot = entry.participants.index(event.recipient)
                line = f'L ADMIT {wire} {entry.mode} {slot}\n'
            elif kind in ('pair', 'handshake', 'frame'):
                commit = {'pair': 1, 'handshake': 2, 'frame': 3}[kind]
                step = data['step'] if kind == 'frame' else 0
                words = [struct.pack('<8H', *row).hex() for row in data['words']]
                line = f'L COMMIT {commit} {wire} {data["link_generation"]} {step} {words[0]} {words[1]}\n'
            elif kind == 'closed':
                line = f'L ABORT {wire}\n'
                closed.add(wire)
            elif kind == 'generation_closed':
                continue
            else:
                raise RuntimeError('unexpected coordinator event')
            output.append((event.recipient, line))
        for wire in closed:
            entry = self._wire.pop(wire)
            del self._internal[entry.internal]
            for tag in self._tags.values():
                if tag.coop_wire == wire:
                    tag.coop_wire = None
        return output

    def tick(self, *, now=None):
        output = self._deliver(self.sessions.tick(now=now).events)
        now = self.sessions._last_now
        assert now is not None  # sessions.tick established the authority clock.
        for tag in tuple(self._tags.values()):
            if not tag.active and now >= tag.deadline:
                output.extend(self._end_tag(tag))
            elif not tag.active and now >= tag.next_keepalive:
                # Keep pending consent alive through the 30-second TLS idle
                # lease without renewing its deadline or granting admission.
                output.extend((actor, f'T WAIT {tag.id}\n') for actor in tag.participants)
                tag.next_keepalive = now + 10
            elif tag.active and now >= tag.next_keepalive:
                # Reassert only the existing authority range bit. A durable tag
                # otherwise leaves LINK silent until the TLS relay expires it.
                output.extend((actor, f'T RANGE {tag.id} {tag.in_range}\n')
                              for actor in tag.participants)
                tag.next_keepalive = now + 10
        return output

    def reserved(self, trainers):
        """Read-only host barrier, including offers and between generations.

        Call serially on the authority loop, like process and disconnect.
        """
        return any(trainer in entry.participants for trainer in trainers
                   for entry in self._wire.values())

    def disconnect(self, actor, *, now=None):
        output = self._deliver(self.sessions.disconnect(actor, now=now).events)
        tag = self._tags.get(self._tag_actor.get(actor))
        if tag is not None:
            output.extend(self._end_tag(tag))
        return output

    def delivery_current(self, actor, line):
        """Recheck after a queue callback may synchronously abort an activity."""
        fields = line.split()
        if fields[0] == 'T':
            if fields[1] in ('ERROR', 'END'):
                return True
            tag = self._tags.get(int(fields[2]))
            return tag is not None and actor in tag.participants
        if fields[1] in ('ERROR', 'ABORT', 'HELD', 'RELEASED'):
            return True
        index = 3 if fields[1] == 'COMMIT' else 2
        wire = int(fields[index])
        entry = self._wire.get(wire)
        return entry is not None and actor in entry.participants

    def encounter_target(self, actor, tag_text, token_text):
        """Resolve TEAM only for the current authenticated encounter hold.

        The server must apply its ordinary LINK/presence/region checks to this
        target before dispatch, exactly as it does for a literal L OFFER.
        """
        try:
            tag_id, token = _uint(tag_text, 2**64-1), _uint(token_text, 2**32-1)
        except ValueError:
            return None
        tag = self._tags.get(self._tag_actor.get(actor))
        if tag is None or not tag.active or tag.id != tag_id or self._encounters.get(actor) != (tag_id, token):
            return None
        return next(p for p in tag.participants if p != actor)

    def process(self, actor, raw, presence, *, now=None):
        """Input actor comes only from the authenticated LINK connection.

        Errors contain fixed codes only. A malformed operation by an admitted
        participant aborts its reservation; it never silently skips an engine
        round. Bad activity IDs from outsiders cannot abort another pair.
        """
        output = self.tick(now=now)
        channel = 'L'
        try:
            if not isinstance(actor, str) or not _NAME.fullmatch(actor):
                raise ValueError('actor')
            if type(raw) is not bytes or not 1 <= len(raw) <= 512 or b'\n' in raw or b'\r' in raw:
                raise ValueError('line')
            fields = raw.decode('ascii').split(' ')
            if fields[0] == 'T':
                channel = 'T'
                if any(not field for field in fields):
                    raise ValueError('shape')
                output.extend(self._tag_request(actor, fields, presence, self.sessions._last_now))
                return output
            if any(not field for field in fields) or fields[0] != 'L':
                raise ValueError('shape')
            if len(fields) == 5 and fields[1] == 'CHOICE':
                op, tag_id, token = fields[2], _uint(fields[3], 2**64-1), _uint(fields[4], 2**32-1)
                tag = self._tags.get(self._tag_actor.get(actor))
                if not token or tag is None or not tag.active or tag.id != tag_id:
                    raise LinkError('denied')
                previous = self._encounters.get(actor)
                if previous is not None and previous != (tag_id, token):
                    raise LinkError('conflict')
                if op == 'HOLD':
                    # Ordered barrier: withdraw any crossing/pre-battle admission
                    # before acknowledging. Tag consent is deliberately retained.
                    if tag.coop_wire is not None:
                        entry = self._entry(actor, tag.coop_wire)
                        output.extend(self._deliver(self.sessions.close(actor, entry.internal, now=now).events))
                    self._encounters[actor] = (tag_id, token)
                    output.append((actor, f'L HELD {tag_id} {token}\n'))
                    return output
                if previous != (tag_id, token):
                    raise LinkError('not_found')
                if op == 'RELEASE':
                    if tag.coop_wire is not None:
                        raise LinkError('busy')
                    del self._encounters[actor]
                    output.append((actor, f'L RELEASED {tag_id} {token}\n'))
                    return output
                if op != 'TEAM':
                    raise ValueError('choice')
                target = next(p for p in tag.participants if p != actor)
                # Two separately captured encounters must not borrow one another's
                # trainer callback or rewards. Neither target can be a guest here.
                if target in self._encounters:
                    raise LinkError('busy')
                fields = ['L', 'OFFER', '4', target]
            if len(fields) == 4 and fields[1] == 'OFFER':
                mode = _uint(fields[2], 4)
                target = fields[3]
                if mode not in _KINDS or not _NAME.fullmatch(target):
                    raise ValueError('offer')
                tag = None
                if mode == 4:
                    tag = self._tags.get(self._tag_actor.get(actor))
                    if tag is None or not tag.active or target not in tag.participants or actor == target:
                        raise LinkError('denied')
                    if target in self._encounters:
                        raise LinkError('busy')
                    if tag.coop_wire is not None:
                        entry = self._entry(actor, tag.coop_wire)
                        slot = entry.participants.index(actor)
                        output.append((actor, f'L ADMIT {tag.coop_wire} 4 {slot}\n'))
                        return output
                # Allocate public ID before reserving peers, so allocation failure
                # cannot strand a consent lock with no addressable wire session.
                wire = self._new_id()
                result = self.sessions.offer(actor, target, _KINDS[mode], presence, now=now)
                assert result.session_id is not None and result.generation is not None
                event = next(e for e in result.events if e.data['type'] == 'offer')
                entry = _WireSession(result.session_id, result.generation, mode, event.data['participants'])
                self._wire[wire] = entry
                self._internal[entry.internal] = wire
                if tag is not None:
                    tag.coop_wire = wire
                    accepted = self.sessions.accept(target, entry.internal, presence, now=now)
                    output.extend(self._deliver(result.events))
                    result = accepted
            elif len(fields) == 3 and fields[1] in ('ACCEPT', 'REJECT'):
                wire = _uint(fields[2], 2**64-1)
                entry = self._entry(actor, wire)
                if fields[1] == 'ACCEPT':
                    result = self.sessions.accept(actor, entry.internal, presence, now=now)
                else:
                    result = self.sessions.reject(actor, entry.internal, now=now)
            elif len(fields) == 10 and fields[1] == 'EVENT':
                kind = _uint(fields[2], 5)
                wire = _uint(fields[3], 2**64-1)
                mode = _uint(fields[4], 5)
                slot = _uint(fields[5], 1)
                generation = _uint(fields[6], 2**32-1)
                step = _uint(fields[7], 2**32-1)
                link_type = _uint(fields[8], 65535)
                if kind < 1 or not _HEX.fullmatch(fields[9]):
                    raise ValueError('event')
                words = struct.unpack('<8H', bytes.fromhex(fields[9]))
                entry = self._entry(actor, wire)
                if entry.mode != mode:
                    raise LinkError('mode')
                if entry.participants[slot] != actor:
                    raise LinkError('slot')
                if kind != 4 and any(words):
                    raise ValueError('control payload')
                if kind == 1:
                    if step != 0 or link_type not in _LINK_TYPES[mode]:
                        raise ValueError('open')
                    result = self.sessions.open(actor, entry.internal, generation, link_type, now=now)
                elif kind == 2:
                    result = self.sessions.close_generation(actor, entry.internal, generation, now=now)
                elif kind == 3:
                    result = self.sessions.advance(actor, entry.internal, generation, now=now)
                elif kind == 4:
                    result = self.sessions.submit(actor, entry.internal, entry.generation,
                        step, words, now=now, link_generation=generation)
                else:
                    result = self.sessions.close(actor, entry.internal, now=now)
            else:
                raise ValueError('shape')
            output.extend(self._deliver(result.events))
        except (ValueError, UnicodeError) as error:
            if isinstance(error, LinkError):
                output.extend(self._deliver(error.events))
                code = error.code.upper()
                if not re.fullmatch(r'[A-Z_]{1,40}', code):
                    code = 'MALFORMED'
            else:
                code = 'MALFORMED'
            output.append((actor, f'{channel} ERROR {code}\n'))
            if channel == 'L' and isinstance(actor, str) and _NAME.fullmatch(actor):
                output.extend(self._deliver(self.sessions.disconnect(actor, now=now).events))
        return output
