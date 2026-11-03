"""Persistent local world authority. Client reports never mutate trainer saves."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import secrets
import sqlite3
import selectors
import socket
import threading
import time
import os
import fcntl
import stat
import errno
import hashlib

from .build_catalog import validate_coords, validate_tile
from .mechanics import validate_objects
from .link_protocol import LinkProtocol

MAX_QUEUE = 65536
MAX_LINE = 1024
MAX_CONTROL_LINE = 16384
MAX_PEERS = 8
MAX_TILES = 128
STATE_FLUSH_INTERVAL = .5


def bounded(value, low, high):
    if not value.isascii() or not value.isdecimal() or len(value) > 20:
        raise ValueError('invalid integer')
    number = int(value)
    if not low <= number <= high:
        raise ValueError('integer out of bounds')
    return number

ID = re.compile(r'[A-Za-z0-9_-]{1,24}\Z')
HEX = re.compile(r'[0-9a-fA-F]{64}\Z')
HASH = re.compile(r'[0-9a-fA-F]{16}\Z')


class MeetingUnavailable(ValueError):
    """An expected presence race, not a malformed/authentication failure."""


class WorldServer:
    def __init__(self, socket_path, state_dir, mechanics=None, admin_path=None):
        from .world_library import WorldActivityLock
        # Direct CLI/SDK constructors must participate too, before mkdir or
        # opening SQLite. Session-only locking leaves a deletion race here.
        self.activity = WorldActivityLock(state_dir)
        try:
            self._initialize(socket_path, state_dir, mechanics, admin_path)
        except BaseException:
            try:
                for name in ('executor', 'control_executor'):
                    executor = getattr(self, name, None)
                    if executor is not None:
                        executor.shutdown(wait=True, cancel_futures=True)
                database = getattr(self, 'db', None)
                if database is not None:
                    database.close()
            finally:
                self.activity.close()
            raise

    def _initialize(self, socket_path, state_dir, mechanics, admin_path):
        # Refuse incomplete deployments at startup, not on a player's first STATE.
        from .build_catalog import catalog_maps
        catalog_maps()
        self.socket_path = str(socket_path)
        self.root = Path(state_dir).resolve()
        if admin_path is None:
            admin_path = (self.root / 'admin.sock' if Path(socket_path).parent.name == 'transport'
                          else self.socket_path + '.admin')
        self.admin_path = str(admin_path)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / 'world.sqlite3', check_same_thread=False)
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS identities (
                id TEXT PRIMARY KEY, token TEXT NOT NULL, save_path TEXT NOT NULL,
                party_hash TEXT, bag_hash TEXT);
            CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, data TEXT);
            CREATE INDEX IF NOT EXISTS events_kind_seq ON events(kind,seq);
        ''')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS module (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1), source TEXT,
                sha256 TEXT, state TEXT NOT NULL, tiles TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS status (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1), error TEXT);
        ''')
        columns = {row[1] for row in self.db.execute('PRAGMA table_info(module)')}
        if 'objects' not in columns:
            self.db.execute("ALTER TABLE module ADD COLUMN objects TEXT NOT NULL DEFAULT '[]'")
        if 'interaction_cursor' not in columns:
            self.db.execute('ALTER TABLE module ADD COLUMN interaction_cursor INTEGER NOT NULL DEFAULT 0')
        self.db.commit()
        os.chmod(self.root / 'world.sqlite3', 0o600)
        from .host_controls import HostControls
        self.host_controls = HostControls(self.db)
        self.runtime = mechanics
        if self.runtime is None:
            from .mechanics import MechanicRuntime
            self.runtime = MechanicRuntime(self.root)
        (self.root / 'candidates').mkdir(mode=0o700, exist_ok=True)
        self.candidate = None
        self.module_state = {}
        self.module_error = None
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='world-mechanics')
        # Control persistence may contend with the GM database. It never blocks
        # the game selector or shares the mechanic worker's execution queue.
        self.control_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='world-intents')
        self.control_jobs = []
        self.job = None
        self.deployment = None
        self.next_tick = time.monotonic() + 0.1
        self.tick = 0
        self.lock = threading.RLock()
        self.selector = None
        self.authority_lock = None
        self.thread = None
        self.stopping = threading.Event()
        self.connections = {}
        self.peers = {}
        self.link_channels = {}
        self.link_protocol = LinkProtocol()
        self.tiles = []
        self.objects = []
        self.interaction_cursor = 0
        self.revision = self.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0]
        # Presence is a latest-value snapshot, not authoritative game progress.
        # Bound it by trainer count and time without holding SQLite's write lock
        # between packets. Changed inventory hashes still commit immediately.
        self.pending_states = {}
        self.next_state_flush = time.monotonic() + STATE_FLUSH_INTERVAL
        row = self.db.execute('SELECT error FROM status WHERE singleton=1').fetchone()
        if row:
            self.module_error = row[0]
        row = self.db.execute('SELECT source,sha256,state,tiles,objects,interaction_cursor FROM module WHERE singleton=1').fetchone()
        if row:
            from .mechanics import Candidate
            try:
                stored = json.loads(row[3])
                if type(stored) is not list or any(type(t) is not list or len(t) != 6 for t in stored):
                    raise ValueError('invalid stored tile shape')
                keys = ('group', 'num', 'x', 'y', 'metatile', 'collision')
                state_json, tiles = self._validated(dict(state=json.loads(row[2]),
                    tiles=[dict(zip(keys, tile)) for tile in stored]))
                objects = validate_objects(json.loads(row[4]))
                if type(row[5]) is not int or row[5] < 0:
                    raise ValueError('invalid interaction cursor')
                self.module_state, self.tiles, self.objects = json.loads(state_json), tiles, objects
                self.interaction_cursor = row[5]
                self.candidate = Candidate(row[0], row[1])
            except (ValueError, TypeError, RecursionError) as exc:
                # Preserve the durable row for diagnosis but never broadcast or
                # execute an overlay written under an obsolete validation policy.
                self._record_error(ValueError('invalid persisted module: ' + str(exc)))

    def create_identity(self, trainer_id, token=None):
        with self.lock:
            return self._create_identity(trainer_id, token)

    def _create_identity(self, trainer_id, token):
        if not isinstance(trainer_id, str) or not ID.fullmatch(trainer_id):
            raise ValueError('invalid trainer id')
        if token is not None and (not isinstance(token, str) or not HEX.fullmatch(token)):
            raise ValueError('invalid token')
        row = self.db.execute('SELECT token,save_path FROM identities WHERE id=?', (trainer_id,)).fetchone()
        if row is not None and token is not None and not secrets.compare_digest(row[0], token):
            raise ValueError('identity already registered with different token')
        if row is None:
            # pathlib's parents=True applies mode only to the leaf. Create the
            # private trainer container explicitly, independent of the umask.
            (self.root / 'trainers').mkdir(mode=0o700, exist_ok=True)
            directory = self.root / 'trainers' / trainer_id
            directory.mkdir(mode=0o700, exist_ok=True)
            row = (token if token is not None else secrets.token_hex(32), str(directory / 'game.sav'))
            with self.db:
                self.db.execute('INSERT INTO identities(id,token,save_path) VALUES(?,?,?)', (trainer_id, *row))
        return dict(id=trainer_id, token=row[0], save_path=row[1])

    def start(self):
        if self.thread is not None:
            raise RuntimeError('already started')
        self.authority_lock = (self.root / 'world.lock').open('a+b')
        os.chmod(self.root / 'world.lock', 0o600)
        try:
            fcntl.flock(self.authority_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.authority_lock.close()
            self.authority_lock = None
            raise RuntimeError('world state already in use') from None
        Path(self.socket_path).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        Path(self.admin_path).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._remove_stale_socket(self.socket_path)
        self._remove_stale_socket(self.admin_path)
        self.selector = selectors.DefaultSelector()
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            listener.bind(self.socket_path)
            os.chmod(self.socket_path, 0o600)
            listener.listen(16)
            listener.setblocking(False)
            self.selector.register(listener, selectors.EVENT_READ, 'listener')
        except BaseException:
            listener.close()
            self.selector.close()
            self.selector = None
            raise
        admin_listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            admin_listener.bind(self.admin_path)
            os.chmod(self.admin_path, 0o600)
            admin_listener.listen(8)
            admin_listener.setblocking(False)
            self.selector.register(admin_listener, selectors.EVENT_READ, 'admin_listener')
        except BaseException:
            admin_listener.close()
            for key in list(self.selector.get_map().values()):
                key.fileobj.close()
            self.selector.close()
            self.selector = None
            Path(self.socket_path).unlink(missing_ok=True)
            raise
        self.thread = threading.Thread(target=self._loop, name='emerald-world', daemon=True)
        self.thread.start()
        return self

    @staticmethod
    def _remove_stale_socket(path):
        try:
            info = Path(path).lstat()
        except FileNotFoundError:
            return
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
            raise RuntimeError('refusing to remove non-owned socket path')
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.1)
            try:
                probe.connect(path)
            except OSError as exc:
                if exc.errno != errno.ECONNREFUSED:
                    raise RuntimeError('socket path is in use') from exc
            else:
                raise RuntimeError('socket path is in use')
        Path(path).unlink()

    def serve_forever(self):
        self.start()
        try:
            while self.thread.is_alive():
                self.thread.join(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            self.close()

    def _event(self, kind, data):
        cursor = self.db.execute('INSERT INTO events(kind,data) VALUES(?,?)', (kind, json.dumps(data)))
        self.revision = cursor.lastrowid

    def _flush_states(self, *, force=True):
        now = time.monotonic()
        if not force and now < self.next_state_flush:
            return
        if self.pending_states:
            revision = self.revision
            try:
                with self.db:
                    for data in self.pending_states.values():
                        self._event('state', data)
            except sqlite3.Error:
                self.revision = revision
                raise
            # Only acknowledge the batch after COMMIT succeeds.
            self.pending_states.clear()
        self.next_state_flush = time.monotonic() + STATE_FLUSH_INTERVAL

    def _queue(self, conn, text):
        data = text.encode('ascii')
        if len(conn['out']) + len(data) > MAX_QUEUE:
            self._drop(conn)
            return
        conn['out'].extend(data)
        if conn['sock'] in self.connections:
            self.selector.modify(conn['sock'], selectors.EVENT_READ | selectors.EVENT_WRITE, conn)

    def _error(self, conn, code):
        conn['closing'] = True
        self._queue(conn, 'ERROR ' + code + '\n')

    def _drop(self, conn):
        sock = conn['sock']
        conn['closing'] = True
        if sock not in self.connections:
            return
        self.selector.unregister(sock)
        del self.connections[sock]
        sock.close()
        if self.link_channels.get(conn['id']) is conn:
            del self.link_channels[conn['id']]
            self._deliver_links(self.link_protocol.disconnect(conn['id']))
        if conn['id'] and self.peers.get(conn['id']) is conn:
            self._flush_states()
            del self.peers[conn['id']]
            channel = self.link_channels.get(conn['id'])
            if channel is not None:
                self._drop(channel)
            for peer in self.peers.values():
                meeting = peer.get('meeting')
                if meeting and conn['id'] in (meeting['player'], meeting['target']):
                    peer['meeting'] = None
            with self.db:
                self._event('leave', conn['id'])
            self._broadcast()

    def _snapshot(self, conn):
        lines = ['BEGIN ' + str(self.revision)]
        for name, peer in sorted(self.peers.items()):
            if name != conn['id'] and peer['state'] is not None and peer['state'][6]:
                lines.append('PEER ' + name + ' ' + ' '.join(map(str, peer['state'])))
        lines += ['TILE ' + ' '.join(map(str, tile)) for tile in self.tiles]
        for obj in self.objects:
            lines.append('OBJECT ' + obj['id'] + ' ' + ' '.join(str(obj[k]) for k in ('group','num','x','y','gfx'))
                         + ' ' + obj['text'].encode('ascii').hex())
        meeting = conn.get('meeting')
        if conn.get('social') and meeting:
            lines.append('MEET ' + ' '.join(str(meeting[k]) for k in
                ('seq','player','target','group','num','x','y','signal')))
        return '\n'.join(lines + ['END', ''])

    def _broadcast(self):
        for conn in list(self.peers.values()):
            if not conn['closing']:
                self._queue(conn, self._snapshot(conn))

    def _line(self, conn, raw):
        try:
            fields = raw.decode('ascii').split()
            if conn['id'] is None:
                control = len(fields) == 5 and fields[4] == 'CONTROL'
                social = len(fields) == 5 and fields[4] == 'SOCIAL'
                link = len(fields) == 5 and fields[4] == 'LINK'
                if (len(fields) != 4 and not control and not social and not link) or fields[:2] != ['HELLO', '1']:
                    self._error(conn, 'AUTH')
                    return
                name, token = fields[2:4]
                if not ID.fullmatch(name) or not HEX.fullmatch(token):
                    self._error(conn, 'AUTH')
                    return
                row = self.db.execute('SELECT token FROM identities WHERE id=?', (name,)).fetchone()
                if row is None or not secrets.compare_digest(row[0], token):
                    self._error(conn, 'AUTH')
                    return
                if link:
                    presence = self.peers.get(name)
                    if presence is None or presence.get('closing'):
                        self._error(conn, 'PRESENCE')
                        return
                    if name in self.link_channels:
                        self._error(conn, 'DUPLICATE')
                        return
                    # Bind the exact live presence object, not just its reusable
                    # trainer ID. Closing/replacing presence closes this channel.
                    conn['id'], conn['link'], conn['presence'] = name, True, presence
                    self.link_channels[name] = conn
                    self._queue(conn, f'WELCOME 1 {name} {self.revision} LINK\n')
                    return
                rejection = self.host_controls.rejection(name)
                if rejection:
                    self._error(conn, rejection)
                    return
                if control:
                    controls = [c for c in self.connections.values() if c.get('control')]
                    if len(controls) >= 16 or sum(c['id'] == name for c in controls) >= 2:
                        self._error(conn, 'FULL')
                        return
                    conn['id'], conn['control'], conn['busy'] = name, True, False
                    self._queue(conn, f'WELCOME 1 {name} {self.revision} CONTROL\n')
                    return
                if name in self.peers:
                    self._error(conn, 'DUPLICATE')
                    return
                if len(self.peers) >= MAX_PEERS:
                    self._error(conn, 'FULL')
                    return
                conn['id'] = name
                conn['social'] = social
                self.peers[name] = conn
                with self.db:
                    self._event('join', name)
                self._queue(conn, f'WELCOME 1 {name} {self.revision}\n')
                self._broadcast()
                return
            if conn.get('link'):
                self._link_line(conn, raw)
                return
            if conn.get('control'):
                self._control_line(conn, raw)
                return
            if fields and fields[0] == 'INTERACT':
                self._interact(conn, fields)
                return
            if fields and fields[0] == 'MEET':
                try:
                    self._meet(conn, fields)
                except MeetingUnavailable:
                    # Consume the request sequence, but keep presence alive if
                    # the peer moved, opened a menu, or received a recent signal.
                    conn['seq'] = int(fields[1])
                    self._queue(conn, self._snapshot(conn))
                return
            if len(fields) != 11 or fields[0] != 'STATE':
                raise ValueError('state shape')
            seq = bounded(fields[1], 0, 2**63 - 1)
            if seq <= conn['seq']:
                self._error(conn, 'STALE')
                return
            limits = [255, 255, 32767, 32767, 4, 65535, 1]
            state = [bounded(v, 0, limit) for v, limit in zip(fields[2:9], limits)]
            validate_coords(*state[:4])
            if not 1 <= state[4] <= 4 or state[5] > 255:
                raise ValueError('invalid peer facing or graphics')
            if state[6] == 0 and state != [0, 0, 0, 0, 1, 7, 0]:
                raise ValueError('noncanonical unready state')
            if not all(HASH.fullmatch(h) for h in fields[9:]):
                raise ValueError('hash')
            data = dict(id=conn['id'], seq=seq, state=state, party_hash=fields[9], bag_hash=fields[10])
            hashes = tuple(fields[9:])
            previous = self.db.execute('SELECT party_hash,bag_hash FROM identities WHERE id=?', (conn['id'],)).fetchone()
            if hashes != previous:
                with self.db:
                    self.db.execute('UPDATE identities SET party_hash=?,bag_hash=? WHERE id=?', (*hashes, conn['id']))
                    self._event('state', data)
                self.pending_states.pop(conn['id'], None)
            else:
                self.pending_states[conn['id']] = data
            self._flush_states(force=False)
            conn['seq'], conn['state'] = seq, state
            self._broadcast()
        except (UnicodeError, ValueError):
            self._error(conn, 'MALFORMED')

    def _deliver_links(self, messages):
        for trainer, line in messages:
            channel = self.link_channels.get(trainer)
            if (channel is not None and not channel.get('closing')
                    and self.link_protocol.delivery_current(trainer, line)):
                self._queue(channel, line)

    def _link_line(self, conn, raw):
        if (conn.get('closing') or self.link_channels.get(conn['id']) is not conn
                or conn['sock'] not in self.connections):
            return
        if (self.peers.get(conn['id']) is not conn['presence']
                or conn['presence'].get('closing')):
            self._error(conn, 'PRESENCE')
            return
        # Only connected native link peers may be invited. CONTROL connections
        # neither approve requests nor contribute native engine rounds.
        fields = raw.split(b' ')
        if len(fields) == 4 and fields[:2] == [b'L', b'OFFER']:
            try:
                target = fields[3].decode('ascii')
            except UnicodeError:
                target = None
            other = self.link_channels.get(target)
            if (other is None or other.get('closing')
                    or self.peers.get(target) is not other.get('presence')):
                self._queue(conn, 'L ERROR UNAVAILABLE\n')
                return
        presence = {name: peer['state'] for name, peer in self.peers.items()
                    if peer['state'] is not None and not peer.get('closing')}
        self._deliver_links(self.link_protocol.process(conn['id'], bytes(raw), presence))

    def _meet(self, conn, fields):
        """One fixed cooperative signal, authenticated and ordered like STATE.

        SOCIAL is opt-in so legacy v1 snapshot parsers see no new records.
        A peer cannot choose text, scripts, another actor, or private state.
        """
        if len(fields) != 3 or not ID.fullmatch(fields[2]) or not conn.get('social'):
            raise ValueError('invalid trainer interaction')
        seq = bounded(fields[1], 0, 2**63-1)
        if seq <= conn['seq']:
            self._error(conn, 'STALE')
            return
        target = self.peers.get(fields[2])
        state = conn['state']
        other = target.get('state') if target else None
        if (target is conn or not target or not target.get('social') or target.get('closing')
                or not state or not other or not state[6] or not other[6] or state[:2] != other[:2]):
            raise MeetingUnavailable('trainer unavailable')
        dx, dy = {1:(0,1),2:(0,-1),3:(-1,0),4:(1,0)}[state[4]]
        if [state[2]+dx, state[3]+dy] != other[2:4]:
            raise MeetingUnavailable('trainer must be adjacent and facing')
        now = time.monotonic()
        if now - conn.get('last_interaction', -10) < 1 or now - target.get('last_meeting', -10) < 1:
            raise MeetingUnavailable('trainer interaction rate exceeded')
        data = dict(kind='trainer', player=conn['id'], target=target['id'],
                    signal='explore', group=other[0], num=other[1], x=other[2], y=other[3])
        with self.db:
            self._event('interaction', data)
        meeting = dict(data, seq=self.revision)
        conn['seq'], conn['last_interaction'] = seq, now
        conn['last_meeting'] = target['last_meeting'] = now
        conn['meeting'] = target['meeting'] = meeting
        self._broadcast()

    def _interact(self, conn, fields):
        if len(fields) != 3 or not ID.fullmatch(fields[2]):
            raise ValueError('invalid interaction')
        seq = bounded(fields[1], 0, 2**63 - 1)
        if seq <= conn['seq']:
            self._error(conn, 'STALE')
            return
        state = conn['state']
        obj = next((o for o in self.objects if o['id'] == fields[2]), None)
        if not state or not state[6] or not obj or state[:2] != [obj['group'], obj['num']]:
            raise ValueError('interaction unavailable')
        dx, dy = {1:(0,1), 2:(0,-1), 3:(-1,0), 4:(1,0)}[state[4]]
        if (state[2]+dx, state[3]+dy) != (obj['x'], obj['y']):
            raise ValueError('interaction requires adjacent facing object')
        now = time.monotonic()
        if now - conn.get('last_interaction', -1) < .2:
            raise ValueError('interaction rate exceeded')
        with self.db:
            self._event('interaction', dict(player=conn['id'], object=obj['id'],
                group=obj['group'], num=obj['num'], x=obj['x'], y=obj['y']))
        conn['seq'], conn['last_interaction'] = seq, now
        self._broadcast()

    def _control_line(self, conn, raw):
        if conn.get('busy'):
            self._error(conn, 'BUSY')
            return
        try:
            request = json.loads(raw)
            if type(request) is not dict:
                raise ValueError('control request must be an object')
            if request.get('command') == 'intent':
                if set(request) != {'command', 'request_id', 'text'}:
                    raise ValueError('invalid intent fields')
                key, text = request['request_id'], request['text']
                if type(key) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', key):
                    raise ValueError('invalid idempotency key')
                if type(text) is not str or not text.strip() or len(text.encode('utf-8')) > 2048:
                    raise ValueError('intent must be nonempty and at most 2048 UTF-8 bytes')
            elif request.get('command') == 'intent_status':
                if set(request) != {'command', 'id'} or type(request['id']) is not str or not re.fullmatch(r'net-[0-9a-f]{64}', request['id']):
                    raise ValueError('invalid intent status fields')
            else:
                raise ValueError('unknown control command')
            if len(self.control_jobs) >= 16:
                raise ValueError('intent service busy')
            conn['busy'] = True
            self.control_jobs.append((self.control_executor.submit(self._control_request, conn['id'], request), conn))
        except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
            self._queue(conn, json.dumps(dict(ok=False, error=str(exc)), ensure_ascii=True) + '\n')

    def _control_request(self, trainer, request):
        """Trainer is always taken from the authenticated connection, not JSON."""
        from .runtime_gm import IntentQueue
        queue = None
        try:
            if (self.root / 'gm').resolve() != self.root / 'gm':
                raise ValueError('GM state must not be a symlink')
            queue = IntentQueue(self.root)
            if request['command'] == 'intent':
                identifier = 'net-' + hashlib.sha256((trainer + '\0' + request['request_id']).encode()).hexdigest()
                existing = queue.db.execute('SELECT player,text FROM requests WHERE id=?', (identifier,)).fetchone()
                if existing is None:
                    pending = queue.db.execute("SELECT count(*) FROM requests WHERE status IN ('queued','running')").fetchone()[0]
                    own_pending = queue.db.execute("SELECT count(*) FROM requests WHERE player=? AND status IN ('queued','running')", (trainer,)).fetchone()[0]
                    latest = queue.db.execute("SELECT max(created) FROM requests WHERE player=? AND kind='intent'", (trainer,)).fetchone()[0]
                    if pending >= 64 or own_pending >= 8:
                        raise ValueError('intent queue is full')
                    if latest is not None and time.time() - latest < 2:
                        raise ValueError('wait two seconds between new intentions')
                queue.submit(trainer, request['text'], identifier)
            else:
                identifier = request['id']
            row = queue.db.execute('SELECT id,player,text,status,created,started,finished FROM requests WHERE id=? AND player=?',
                                   (identifier, trainer)).fetchone()
            if row is None:
                raise ValueError('intent not found')
            # Never expose host paths, source, provider errors, other players'
            # purposes, or the trusted runtime's full deployment report.
            return dict(ok=True, id=identifier, request=dict(row))
        except ValueError as exc:
            return dict(ok=False, error=str(exc))
        except Exception:
            return dict(ok=False, error='intent service unavailable')
        finally:
            if queue is not None:
                queue.close()

    def _poll_controls(self):
        remaining = []
        for future, conn in self.control_jobs:
            if not future.done():
                remaining.append((future, conn))
                continue
            conn['busy'] = False
            if conn['sock'] in self.connections and not conn['closing']:
                self._queue(conn, json.dumps(future.result(), ensure_ascii=True) + '\n')
        self.control_jobs = remaining

    def _admin_line(self, conn, raw):
        conn['closing'] = True
        try:
            request = json.loads(raw)
            if request.get('command') == 'inspect':
                result = self.inspect()
            elif request.get('command') == 'host_controls':
                try:
                    result = self.host_controls.request(request, self)
                except ValueError as exc:
                    # A busy activity or refused host action is not a failing
                    # mechanic module. Do not replace its persisted status.
                    result = dict(ok=False, error=str(exc))
            elif request.get('command') == 'events_since':
                cursor, limit = request.get('cursor', 0), request.get('limit', 64)
                if type(cursor) is not int or not 0 <= cursor <= 2**63-1 or type(limit) is not int or not 1 <= limit <= 64:
                    raise ValueError('invalid event cursor or limit')
                rows = self.db.execute("SELECT seq,kind,data FROM events WHERE kind='interaction' AND seq>? ORDER BY seq LIMIT ?",
                                       (cursor, limit+1)).fetchall()
                events = [dict(seq=seq, kind=kind, data=json.loads(data)) for seq, kind, data in rows[:limit]]
                result = dict(ok=True, events=events, cursor=events[-1]['seq'] if events else cursor, has_more=len(rows)>limit)
            elif request.get('command') == 'deploy':
                if self.deployment is not None or (self.job and self.job[1] == 'deploy'):
                    raise ValueError('deployment busy')
                source = self._candidate_path(request['source_path'])
                tests = request.get('tests_path')
                tests = self._candidate_path(tests) if tests is not None else None
                self.deployment = (conn, source, tests)
                return
            else:
                raise ValueError('unknown command')
        except (ValueError, TypeError, KeyError, OSError, AttributeError, RecursionError) as exc:
            self._record_error(exc)
            result = dict(ok=False, error=str(exc))
        self._queue(conn, json.dumps(result, ensure_ascii=True) + '\n')

    def inspect(self):
        with self.lock:
            players = []
            for name, conn in sorted(self.peers.items()):
                row = self.db.execute('SELECT party_hash,bag_hash,save_path FROM identities WHERE id=?', (name,)).fetchone()
                player = dict(id=name, party_hash=row[0], bag_hash=row[1], save_path=row[2])
                if conn['state'] is not None:
                    player.update(zip(('group','num','x','y','facing','gfx','ready'), conn['state']))
                player['meeting'] = conn.get('meeting')
                players.append(player)
            return dict(ok=True, revision=self.revision, players=players,
                        tiles=json.loads(json.dumps(self.tiles)), objects=json.loads(json.dumps(self.objects)),
                        state=json.loads(json.dumps(self.module_state)),
                        module_hash=self.candidate.sha256 if self.candidate else None,
                        error=self.module_error)

    def _candidate_path(self, path):
        directory = (self.root / 'candidates').resolve()
        source = Path(path)
        if not source.is_absolute():
            source = directory / source
        try:
            source = source.resolve(strict=True)
        except OSError as exc:
            raise ValueError('source must be an existing file confined to candidates directory') from exc
        if not source.is_relative_to(directory) or not source.is_file():
            raise ValueError('source must be confined to candidates directory')
        return source

    def _record_error(self, exc):
        self.module_error = str(exc)[:2048]
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO status VALUES(1,?)', (self.module_error,))

    def _context(self):
        # Batches are acknowledged atomically with successful mechanic state.
        # Failed candidates retry these same durable event IDs, never lose them.
        rows = self.db.execute("SELECT seq,data FROM events WHERE kind='interaction' AND seq>? ORDER BY seq LIMIT 64",
                               (self.interaction_cursor,)).fetchall()
        return dict(players=self.inspect()['players'], revision=self.revision, tick=self.tick,
                    interactions=[dict(json.loads(data), seq=seq) for seq, data in rows])

    def _deploy(self, source, tests, context, state):
        candidate = self.runtime.stage(source, tests)
        return candidate, self.runtime.run(candidate, context, state)

    @staticmethod
    def _validated(result):
        if type(result) is not dict or not {'state', 'tiles'} <= set(result) or set(result) - {'state', 'tiles', 'objects'}:
            raise ValueError('result must contain state and tiles')
        state = json.dumps(result['state'], allow_nan=False, separators=(',', ':'))
        if len(state.encode()) > 32768:
            raise ValueError('state too large')
        tiles = result['tiles']
        validate_objects(result.get('objects', []))
        if type(tiles) is not list or len(tiles) > MAX_TILES:
            raise ValueError('invalid tiles')
        keys = ('group', 'num', 'x', 'y', 'metatile', 'collision')
        limits = (255, 255, 1023, 1023, 1023, 1)
        normalized, seen = [], set()
        for tile in tiles:
            if type(tile) is not dict or set(tile) != set(keys):
                raise ValueError('invalid tile fields')
            values = [tile[k] for k in keys]
            if any(type(v) is not int or not 0 <= v <= limit for v, limit in zip(values, limits)):
                raise ValueError('tile out of bounds')
            validate_tile(values)
            location = tuple(values[:4])
            if location in seen:
                raise ValueError('duplicate tile')
            seen.add(location)
            normalized.append(values)
        normalized.sort()
        return state, normalized

    def _poll_mechanics(self):
        if self.job is not None and self.job[0].done():
            future, kind, conn, cursor = self.job
            self.job = None
            try:
                candidate, result = future.result()
                state_json, tiles = self._validated(result)
                objects = result.get('objects', [])
                changed = (kind == 'deploy' or result['state'] != self.module_state or tiles != self.tiles
                           or objects != self.objects or cursor != self.interaction_cursor)
                if changed:
                    with self.db:
                        self.db.execute('INSERT OR REPLACE INTO module(singleton,source,sha256,state,tiles,objects,interaction_cursor) VALUES(1,?,?,?,?,?,?)',
                                        (candidate.source, candidate.sha256, state_json, json.dumps(tiles), json.dumps(objects), cursor))
                        self._event(kind, dict(module_hash=candidate.sha256, tiles=tiles))
                        if kind == 'deploy':
                            self.db.execute('INSERT OR REPLACE INTO status VALUES(1,NULL)')
                    self.candidate, self.module_state, self.tiles = candidate, json.loads(state_json), tiles
                    self.objects, self.interaction_cursor = objects, cursor
                    if kind == 'deploy':
                        self.module_error = None
                    self._broadcast()
                response = dict(ok=True, revision=self.revision, module_hash=candidate.sha256)
            except Exception as exc:
                self._record_error(exc)
                response = dict(ok=False, error=self.module_error)
            if conn is not None and conn['sock'] in self.connections:
                self._queue(conn, json.dumps(response, ensure_ascii=True) + '\n')
            self.next_tick = time.monotonic() + 0.1
        if self.job is not None:
            return
        if self.deployment is not None:
            conn, source, tests = self.deployment
            self.deployment = None
            context = self._context()
            cursor = context['interactions'][-1]['seq'] if context['interactions'] else self.interaction_cursor
            future = self.executor.submit(self._deploy, source, tests, context, json.loads(json.dumps(self.module_state)))
            self.job = (future, 'deploy', conn, cursor)
        elif self.candidate is not None and time.monotonic() >= self.next_tick:
            self.tick += 1
            candidate = self.candidate
            context, state = self._context(), json.loads(json.dumps(self.module_state))
            def run_tick():
                return candidate, self.runtime.run(candidate, context, state)
            cursor = context['interactions'][-1]['seq'] if context['interactions'] else self.interaction_cursor
            self.job = (self.executor.submit(run_tick), 'tick', None, cursor)

    def _loop(self):
        while not self.stopping.is_set():
            for key, mask in self.selector.select(0.025):
                with self.lock:
                    if key.data in ('listener', 'admin_listener'):
                        sock, _ = key.fileobj.accept()
                        sock.setblocking(False)
                        if len(self.connections) >= 32:
                            sock.close()
                            continue
                        conn = dict(sock=sock, id=None, seq=-1, state=None, incoming=bytearray(), out=bytearray(), closing=False, born=time.monotonic())
                        conn['admin'] = key.data == 'admin_listener'
                        self.connections[sock] = conn
                        self.selector.register(sock, selectors.EVENT_READ, conn)
                        continue
                    conn = key.data
                    try:
                        if mask & selectors.EVENT_READ and not conn['closing']:
                            data = conn['sock'].recv(4096)
                            if not data:
                                self._drop(conn)
                                continue
                            conn['incoming'].extend(data)
                            while b'\n' in conn['incoming'] and not conn['closing']:
                                raw, _, rest = conn['incoming'].partition(b'\n')
                                conn['incoming'] = bytearray(rest)
                                limit = MAX_CONTROL_LINE if conn.get('control') else MAX_LINE
                                if len(raw) > limit:
                                    self._error(conn, 'OVERSIZE')
                                else:
                                    if conn['admin']:
                                        self._admin_line(conn, raw)
                                    else:
                                        self._line(conn, raw)
                            limit = MAX_CONTROL_LINE if conn.get('control') else MAX_LINE
                            if len(conn['incoming']) > limit:
                                conn['incoming'].clear()
                                self._error(conn, 'OVERSIZE')
                        if mask & selectors.EVENT_WRITE and conn['sock'] in self.connections:
                            sent = conn['sock'].send(conn['out'])
                            del conn['out'][:sent]
                            if not conn['out']:
                                if conn['closing']:
                                    self._drop(conn)
                                else:
                                    self.selector.modify(conn['sock'], selectors.EVENT_READ, conn)
                    except (OSError, KeyError):
                        self._drop(conn)
            for conn in list(self.connections.values()):
                if conn['id'] is None and not conn['admin'] and time.monotonic() - conn['born'] > 5:
                    self._drop(conn)
            with self.lock:
                self._flush_states(force=False)
                self._deliver_links(self.link_protocol.tick())
                self._poll_controls()
                self._poll_mechanics()

    def close(self):
        self.stopping.set()
        if self.thread is not None:
            self.thread.join()
        if self.selector is not None:
            for key in list(self.selector.get_map().values()):
                key.fileobj.close()
            self.selector.close()
            self.selector = None
            Path(self.socket_path).unlink(missing_ok=True)
            Path(self.admin_path).unlink(missing_ok=True)
        self.executor.shutdown(wait=True, cancel_futures=True)
        self.control_executor.shutdown(wait=True, cancel_futures=True)
        with self.lock:
            self._flush_states()
        if self.authority_lock is not None:
            self.authority_lock.close()
            self.authority_lock = None
        self.db.close()
        self.activity.close()


def create_identity(state_dir, trainer_id, token=None):
    """Provision a trainer or return its existing token. Never rotates credentials."""
    server = WorldServer('/unused', state_dir)
    try:
        return server.create_identity(trainer_id, token)['token']
    finally:
        server.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--socket')
    parser.add_argument('--admin-socket')
    parser.add_argument('--state-dir', required=True)
    parser.add_argument('--create-identity', metavar='ID')
    args = parser.parse_args(argv)
    if args.create_identity is not None:
        token = create_identity(args.state_dir, args.create_identity)
        print(json.dumps(dict(id=args.create_identity, token=token)))
    else:
        if args.socket is None:
            parser.error('--socket is required when serving')
        WorldServer(args.socket, args.state_dir, admin_path=args.admin_socket).serve_forever()


if __name__ == '__main__':
    main()
