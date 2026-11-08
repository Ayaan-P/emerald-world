"""Persistent local world authority. Client reports never mutate trainer saves."""
import argparse
import base64
import binascii
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
import sys

from .build_catalog import validate_coords, validate_tile, catalog_maps
from .mechanics import validate_objects
from .link_protocol import LinkProtocol
from .guilds import Guilds
from .guild_chat import GuildChat
from .world_rules import WorldRules
from .rally import RallyCoordinator
from .world_memory import object_content, overlay_places, terrain_delta

MAX_QUEUE = 65536
MAX_LINE = 1024
MAX_CONTROL_LINE = 16384
MAX_ADMIN_LINE = 24576  # Bounded base64 transport for one 127x127 template.
MAX_PEERS = 8
MAX_PEERS_EXTENDED = 32
MAX_PEERS_INTERMEDIATE = 16
MAX_TRAVEL_PEERS = 63  # The authority admits at most 64 authenticated trainers.
TRAVEL_FRESH_SECONDS = 3
MAX_TILES = 128
STATE_FLUSH_INTERVAL = .5
PRESENCE_BATCH_INTERVAL = .05
PRESENCE_HEARTBEAT_INTERVAL = 1.0


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
    def __init__(self, socket_path, state_dir, mechanics=None, admin_path=None, *,
                 max_players=32, max_controls=None, connection_headroom=8, cave_template=None,
                 persist_generated_cave=False, archive_generated_areas=False):
        from .build_catalog import catalog_maps
        from .shared_cave import SharedCave
        entries = [(group, num) for (group, num), item in catalog_maps().items()
                   if item.get('name') == 'GeneratedWorld_Cave']
        if len(entries) > 1:
            raise ValueError('ambiguous generated cave map')
        self.cave_map = entries[0] if entries else None
        wilds = [(group, num) for (group, num), item in catalog_maps().items() if item.get('name') == 'GeneratedWorld_Wilds']
        if len(wilds) > 1: raise ValueError('ambiguous generated wilds map')
        self.wilds_map = wilds[0] if wilds else None
        if type(persist_generated_cave) is not bool:
            raise ValueError('persist_generated_cave must be a bool')
        self.persist_generated_cave = persist_generated_cave
        if type(archive_generated_areas) is not bool or (archive_generated_areas and not persist_generated_cave):
            raise ValueError('generated area archive requires persistent generated caves')
        self.archive_generated_areas = archive_generated_areas
        self.shared_cave = SharedCave(cave_template) if cave_template is not None else None
        self._terrain_walk_cache = None
        if self.shared_cave and (self.wilds_map if self.shared_cave.version in (6, 7, 8, 9, 16) else self.cave_map) is None:
            raise ValueError('generated map missing from catalog')
        if type(max_players) is not int or not 1 <= max_players <= 64:
            raise ValueError('max_players must be between 1 and 64')
        if max_controls is None:
            max_controls = 2 * max_players
        if type(max_controls) is not int or not 0 <= max_controls <= 128:
            raise ValueError('max_controls must be between 0 and 128')
        if type(connection_headroom) is not int or not 2 <= connection_headroom <= 64:
            raise ValueError('connection_headroom must be between 2 and 64')
        self.max_players = max_players
        self.max_controls = max_controls
        self.connection_headroom = connection_headroom
        self.max_connections = 2 * max_players + max_controls + connection_headroom
        self._closed = False
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
        self.world_rules = WorldRules(self.db)
        from .world_memory import WorldMemory
        self.memory = WorldMemory(self.db)
        self.guilds = Guilds(self.db, catalog_maps(), record_outcome=self.memory.append)
        self.guild_chat = GuildChat(self, validate_coords, TRAVEL_FRESH_SECONDS)
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
        if self.persist_generated_cave:
            from .shared_cave import SharedCave
            self.db.execute('CREATE TABLE IF NOT EXISTS generated_cave (singleton INTEGER PRIMARY KEY CHECK(singleton=1), template BLOB NOT NULL)')
            row = self.db.execute('SELECT template FROM generated_cave WHERE singleton=1').fetchone()
            if row is not None:
                self.shared_cave = SharedCave(row[0])
                self.memory.place(self.shared_cave.identity)
                if (self.wilds_map if self.shared_cave.version in (6, 7, 8, 9, 16) else self.cave_map) is None:
                    raise ValueError('generated map missing from catalog')
            if self.archive_generated_areas:
                self.db.execute('CREATE TABLE IF NOT EXISTS generated_area_terrain (identity TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload BLOB NOT NULL)')
                self.db.execute('CREATE TABLE IF NOT EXISTS generated_area_archive (identity TEXT PRIMARY KEY, label TEXT NOT NULL, kind TEXT NOT NULL, template BLOB NOT NULL, created INTEGER NOT NULL)')
                if row is not None:
                    kind = 'wilds' if self.shared_cave.version in (6, 7, 8, 9, 16) else 'cave'
                    self.db.execute('INSERT OR IGNORE INTO generated_area_archive (identity,label,kind,template,created) VALUES (?,?,?,?,?)',
                                    (self.shared_cave.identity, 'Outdoor area' if kind == 'wilds' else 'Cave', kind, row[0], int(time.time())))
        if self.archive_generated_areas:
            self.db.execute('CREATE TABLE IF NOT EXISTS world_region_revisions (place_id TEXT PRIMARY KEY, revision TEXT NOT NULL UNIQUE)')
            for (identity,) in self.db.execute('SELECT identity FROM generated_area_archive').fetchall():
                self.memory.place(identity)
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
        self.presence_dirty = False
        self.presence_due = 0.0
        self.last_presence_broadcast = time.monotonic()
        self.tick = 0
        self.lock = threading.RLock()
        self.selector = None
        self.authority_lock = None
        self.thread = None
        self.stopping = threading.Event()
        self.connections = {}
        self.peers = {}
        self.rally = RallyCoordinator(self.peers)
        self.chat_serial = 0
        self.link_channels = {}
        self.sharing: dict | None = None
        self.sharing_listen = None
        self.link_protocol = LinkProtocol(max_players=self.max_players)
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
                if any((obj['group'], obj['num']) in (self.cave_map, self.wilds_map) for obj in objects):
                    raise ValueError('persisted object targets generated cave')
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
            self.rally.disconnect(conn)
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

    def _connection_cave(self, conn):
        return conn.get('region_cave') or self.shared_cave

    def _region_scope(self, conn):
        cave = self._connection_cave(conn)
        return cave.identity if cave and conn.get('cave_ack') == cave.identity else None

    def open_region(self, revision):
        """Owner pins one immutable plain-cave revision per logical place."""
        from .shared_cave import SharedCave
        with self.lock:
            if not self.archive_generated_areas or type(revision) is not str or not re.fullmatch('[0-9a-f]{64}',revision):
                raise ValueError('persistent archived revision required')
            row=self.db.execute('SELECT template,label FROM generated_area_archive WHERE identity=?',(revision,)).fetchone()
            if row is None or hashlib.sha256(row[0]).hexdigest()!=revision:
                raise ValueError('archived region unavailable')
            cave=SharedCave(row[0])
            if cave.version!=1:
                raise ValueError('REGION1 supports immutable plain caves only')
            place=self.memory.place(revision)
            existing=self.db.execute('SELECT revision FROM world_region_revisions WHERE place_id=?',(place,)).fetchone()
            if existing and existing[0]!=revision:
                raise ValueError('region already pins a different revision')
            if not existing:
                with self.db:
                    self.db.execute('INSERT INTO world_region_revisions VALUES (?,?)',(place,revision))
                    self.memory.append('region_opened',dict(place_id=place,revision=revision,label=row[1]))
                self.revision=self.db.execute('SELECT max(seq) FROM events').fetchone()[0]
            return dict(ok=True,place_id=place,revision=revision,changed=existing is None)

    def _select_region(self, conn, place):
        from .shared_cave import SharedCave
        with self.lock:
            if not conn.get('region_capable') or not self.archive_generated_areas:
                raise ValueError('region selection unavailable')
            state=conn.get('state')
            if (not state or not state[6] or conn.get('in_generated_cave')
                    or tuple(state[:2]) in (self.cave_map,self.wilds_map)
                    or time.monotonic()-conn.get('state_time',0)>5
                    or self.link_protocol.busy(conn['id']) or self.rally.current(conn) is not None):
                raise ValueError('leave generated areas and finish activities before selecting a region')
            row=self.db.execute("""SELECT a.template,r.revision FROM world_region_revisions r
                JOIN generated_area_archive a ON a.identity=r.revision WHERE r.place_id=?""",(place,)).fetchone()
            if row is None or hashlib.sha256(row[0]).hexdigest()!=row[1]:
                raise ValueError('region unavailable')
            cave=SharedCave(row[0])
            if cave.version!=1:
                raise ValueError('region format unavailable')
            conn['region_cave']=cave
            conn['region_place']=place
            conn['cave_offer']=conn['cave_ack']=None
            conn['cave_transfer_pending']=False
            conn['cave_revoked']=[]
            conn['cave_next']=0
            self._queue(conn,'REGION SELECTED '+place+' '+cave.identity+'\n')

    def _snapshot(self, conn):
        lines = ['BEGIN ' + str(self.revision)]
        # World population is not the fixed native render-array capacity.
        # Select deterministically by proximity; no extra wire fields are added.
        origin = conn.get('state')
        candidates = []
        for name, peer in self.peers.items():
            state = peer['state']
            if (name == conn['id'] or state is None or
                    not (state[6] or (conn.get('social') and peer.get('field')))):
                continue
            # A new or legacy connection with no field state must never see
            # generated-cave peers in its first generic snapshot.
            if tuple(state[:2]) in (self.cave_map, self.wilds_map):
                if (origin is None or tuple(origin[:2]) != tuple(state[:2])
                        or self._region_scope(conn) is None or self._region_scope(conn) != self._region_scope(peer)):
                    continue
            if origin is not None and state[:2] != origin[:2]:
                continue
            distance = abs(state[2]-origin[2]) + abs(state[3]-origin[3]) if origin else 0
            candidates.append((distance, name, state))
        for _, name, state in sorted(candidates)[:conn.get('peer_limit', MAX_PEERS)]:
            lines.append('PEER ' + name + ' ' + ' '.join(map(str, state)))
        if conn.get('travel'):
            # Separate from render relevance. Include every field occupant so
            # a ninth trainer cannot become an invisible occupied landing tile.
            # Remaining lifetime comes from THAT trainer's last accepted state,
            # never a broadcast caused by somebody else's movement or chat.
            now = time.monotonic()
            friends = []
            for name, peer in sorted(self.peers.items()):
                state = peer['state']
                if (name == conn['id'] or peer.get('closing') or state is None
                        or not (state[6] or peer.get('field'))):
                    continue
                # Fly-to-friend is not yet supported for ephemeral caves.
                if tuple(state[:2]) in (self.cave_map, self.wilds_map):
                    continue
                ttl = max(0, min(180, int((TRAVEL_FRESH_SECONDS
                    - (now - peer.get('state_time', now - TRAVEL_FRESH_SECONDS))) * 60)))
                friends.append('FRIEND ' + name + ' ' + ' '.join(map(str, state)) + ' ' + str(ttl))
            # Complete roster, never truncate occupancy. max_players <= 64.
            if len(friends) > MAX_TRAVEL_PEERS:
                raise ValueError('travel roster exceeds authority capacity')
            lines.append('TRAVEL ' + str(len(friends)))
            lines += friends
        lines += ['TILE ' + ' '.join(map(str, tile)) for tile in self.tiles
                  if tuple(tile[:2]) not in (self.cave_map, self.wilds_map)]
        for obj in self.objects:
            if (obj['group'], obj['num']) in (self.cave_map, self.wilds_map):
                continue
            lines.append('OBJECT ' + obj['id'] + ' ' + ' '.join(str(obj[k]) for k in ('group','num','x','y','gfx'))
                         + ' ' + obj['text'].encode('ascii').hex())
        meeting = conn.get('meeting')
        if conn.get('social') and meeting:
            lines.append('MEET ' + ' '.join(str(meeting[k]) for k in
                ('seq','player','target','group','num','x','y','signal')))
        if conn.get('chat'):
            lines += ['CHATMSG ' + ' '.join(map(str, message)) for message in conn['chat_history']]
            lines.append('CHATSTATUS ' + conn['chat_status'])
        lines += self.rally.snapshot(conn)
        return '\n'.join(lines + ['END', ''])

    def _broadcast(self):
        # Immediate event broadcasts also include the latest presence.
        self.presence_dirty = False
        self.last_presence_broadcast = time.monotonic()
        for conn in list(self.peers.values()):
            if not conn['closing']:
                self._queue(conn, self._snapshot(conn))

    def _link_presence(self):
        from .link_sessions import RegionPresence
        states={name:peer['state'] for name,peer in self.peers.items()
                if peer['state'] is not None and not peer.get('closing')
                and (tuple(peer['state'][:2]) not in (self.cave_map,self.wilds_map)
                     or self._region_scope(peer) is not None)}
        scopes={name:self._region_scope(self.peers[name])
                if tuple(state[:2]) in (self.cave_map,self.wilds_map) else None
                for name,state in states.items()}
        return RegionPresence(states,scopes)

    def _schedule_presence(self, now):
        if not self.presence_dirty:
            self.presence_dirty = True
            self.presence_due = now + PRESENCE_BATCH_INTERVAL

    def _poll_presence(self, now):
        if self.presence_dirty and now >= self.presence_due:
            self._broadcast()

    def _line(self, conn, raw):
        # Serialize admission with owner rule updates, including the capability check.
        if conn['id'] is None:
            with self.lock:
                return self._line_impl(conn, raw)
        return self._line_impl(conn, raw)

    def _line_impl(self, conn, raw):
        try:
            fields = raw.decode('ascii').split()
            if conn['id'] is None:
                role = fields[4] if len(fields) == 5 else ''
                rules_version = 3 if role.endswith('RULES3') else 2 if role.endswith('RULES2') else 1 if role.endswith('RULES1') else 0
                rules_capable = rules_version != 0
                if rules_capable:
                    role = role[:-6]
                region_capable = role.endswith('REGION1')
                if region_capable:
                    role = role[:-7]
                cave_xl = role.endswith('CAVE16')
                cave_expansion_large = cave_xl or role.endswith('CAVE11')
                cave_expansion = cave_expansion_large or role.endswith('CAVE10')
                cave_large_terrain = cave_xl or role.endswith('CAVE9H')
                cave_geometry = cave_large_terrain or role.endswith('CAVE9G')
                cave_terrain = cave_geometry or role.endswith('CAVE9T')
                cave_events = cave_expansion or cave_terrain or role.endswith('CAVE9')
                cave_cast = cave_events or role.endswith('CAVE8')
                cave_guide = cave_cast or role.endswith('CAVE7')
                cave_wilds = cave_guide or role.endswith('CAVE6')
                cave_large_wildlife = cave_wilds or role.endswith('CAVE5')
                cave_large = cave_large_wildlife or role.endswith('CAVE4')
                cave_wildlife = cave_large or role.endswith('CAVE3')
                cave_profile = cave_expansion or cave_wildlife or role.endswith('CAVE2')
                cave_capable = cave_profile or role.endswith('CAVE')
                if cave_expansion or cave_terrain:
                    role = role[:-6]
                elif cave_profile:
                    role = role[:-5]
                elif cave_capable:
                    role = role[:-4]
                peer32 = role.endswith('PEER32')
                peer16 = role.endswith('PEER16')
                if peer32 or peer16:
                    role = role[:-6]
                control = role == 'CONTROL'
                chat_capable = role in ('SOCIALCHAT', 'SOCIALTRAVELCHAT', 'SOCIALTRAVELCHATRALLY')
                travel = role in ('SOCIALTRAVEL', 'SOCIALTRAVELCHAT', 'SOCIALTRAVELRALLY', 'SOCIALTRAVELCHATRALLY')
                social = role in ('SOCIAL', 'SOCIALCHAT', 'SOCIALTRAVEL', 'SOCIALTRAVELCHAT', 'SOCIALTRAVELRALLY', 'SOCIALTRAVELCHATRALLY')
                link = role == 'LINK'
                if rules_capable and not social:
                    self._error(conn, 'AUTH')
                    return
                if region_capable and (not social or not cave_capable):
                    self._error(conn,'AUTH')
                    return
                if cave_capable and not social:
                    self._error(conn, 'AUTH')
                    return
                if ((len(fields) != 4 and not control and not social and not link)
                        or ((peer16 or peer32) and not social) or fields[:2] != ['HELLO', '1']):
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
                if not control and self.world_rules.requires_capability(rules_version):
                    self._error(conn, 'RULES_REQUIRED')
                    return
                rejection = self.host_controls.rejection(name)
                if rejection:
                    self._error(conn, rejection)
                    return
                if control:
                    controls = [c for c in self.connections.values() if c.get('control')]
                    if len(controls) >= self.max_controls or sum(c['id'] == name for c in controls) >= 2:
                        self._error(conn, 'FULL')
                        return
                    conn['id'], conn['control'], conn['busy'] = name, True, False
                    self._queue(conn, f'WELCOME 1 {name} {self.revision} CONTROL\n')
                    return
                if name in self.peers:
                    self._error(conn, 'DUPLICATE')
                    return
                if len(self.peers) >= self.max_players:
                    self._error(conn, 'FULL')
                    return
                conn['id'] = name
                conn['social'] = social
                conn['rules_capable'] = rules_capable
                conn['rules_version'] = rules_version
                conn['region_capable'] = region_capable
                conn['cave_capable'] = cave_capable
                conn['cave_profile'] = cave_profile
                conn['cave_wildlife'] = cave_wildlife
                conn['cave_large'] = cave_large
                conn['cave_large_wildlife'] = cave_large_wildlife
                conn['cave_wilds'] = cave_wilds
                conn['cave_guide'] = cave_guide
                conn['cave_cast'] = cave_cast
                conn['cave_events'] = cave_events
                conn['cave_terrain'] = cave_terrain
                conn['cave_geometry'] = cave_geometry
                conn['cave_large_terrain'] = cave_large_terrain
                conn['cave_xl'] = cave_xl
                conn['cave_expansion'] = cave_expansion
                conn['cave_expansion_large'] = cave_expansion_large
                conn['event_command_seq'] = 0
                conn['event_commands'] = {}
                conn['event_command_session'] = secrets.token_hex(8)
                conn['cave_offer'] = conn['cave_ack'] = None
                conn['cave_revoked'] = []
                conn['peer_limit'] = MAX_PEERS_EXTENDED if peer32 else MAX_PEERS_INTERMEDIATE if peer16 else MAX_PEERS
                conn['chat'] = chat_capable
                conn['travel'] = travel
                conn['chat_history'] = []
                conn['chat_status'] = 'ready'
                self.peers[name] = conn
                with self.db:
                    self._event('join', name)
                self._queue(conn, f'WELCOME 1 {name} {self.revision}\n')
                if region_capable:
                    self._queue(conn,'REGION READY 1\n')
                if social and rules_capable:
                    self._queue(conn, self.world_rules.line(rules_version))
                self._broadcast()
                return
            if conn.get('link'):
                self._link_line(conn, raw)
                return
            if conn.get('control'):
                self._control_line(conn, raw)
                return
            if fields and fields[0] == 'REGION':
                if len(fields)!=3 or fields[1]!='SELECT' or raw.decode('ascii')!=' '.join(fields):
                    self._error(conn,'REGION')
                    return
                try:
                    self._select_region(conn,fields[2])
                except ValueError:
                    self._queue(conn,'REGION REFUSED\n')
                return
            if fields and fields[0] == 'CAVE':
                if raw.decode('ascii') != ' '.join(fields):
                    self._error(conn, 'CAVE')
                    return
                if not conn.get('cave_capable') or self.peers.get(conn['id']) is not conn:
                    self._error(conn, 'CAVE')
                    return
                if len(fields)==5 and fields[1]=='TERRAINACK':
                    if not conn.get('cave_terrain') or not re.fullmatch(r'[0-9a-f]{64}',fields[2]) or fields[4] not in ('STAGED','APPLIED'):
                        self._error(conn,'CAVE');return
                    revision=bounded(fields[3],0,2147483647)
                    with self.lock:
                        cave=self._connection_cave(conn)
                        if cave and cave.version==9 and cave.identity==fields[2] and conn.get('cave_ack')==fields[2] and revision<=self._active_terrain()[0]:
                            old=conn.get('terrain_report');phase=fields[4].lower()
                            if not old or old['identity']!=fields[2] or revision>old['revision'] or (revision==old['revision'] and not (old['phase']=='applied' and phase=='staged')):
                                conn['terrain_report']={'identity':fields[2],'revision':revision,'phase':phase}
                    return
                if len(fields)==5 and fields[1]=='EVENTACK':
                    if not conn.get('cave_events') or not re.fullmatch(r'[0-9a-f]{64}',fields[2]) or fields[4] not in ('APPLIED','REJECTED'):
                        self._error(conn,'CAVE');return
                    seq=bounded(fields[3],1,2147483647);entry=conn.get('event_commands',{}).get(seq)
                    if entry and entry['identity']==fields[2] and entry['status']=='queued':entry['status']=fields[4].lower()
                    return
                if fields == ['CAVE', 'GET']:
                    with self.lock:
                        cave=self._connection_cave(conn)
                        if (cave is None
                                or (cave.version == 16 and not conn.get('cave_xl'))
                                or (cave.version == 9 and not conn.get('cave_events'))
                                or (cave.version == 9 and self._active_terrain()[1]!=b'\0' and not conn.get('cave_terrain'))
                                or (cave.version == 9 and self._terrain_requires_geometry() and not conn.get('cave_geometry'))
                                or (cave.version == 9 and self._terrain_requires_large() and not conn.get('cave_large_terrain'))
                                or (cave.version == 8 and not conn.get('cave_cast'))
                                or (cave.version == 7 and not conn.get('cave_guide'))
                                or (cave.version == 6 and not conn.get('cave_wilds'))
                                or (cave.version == 5 and (not conn.get('cave_large_wildlife') or conn.get('cave_expansion')))
                                or (cave.version == 10 and not conn.get('cave_expansion'))
                                or (cave.version == 11 and not conn.get('cave_expansion_large'))
                                or (cave.version == 4 and not conn.get('cave_large'))
                                or (cave.version == 3 and (not conn.get('cave_wildlife') or conn.get('cave_expansion')))
                                or (cave.profile is not None and not conn.get('cave_profile'))):
                            conn['cave_offer'] = None
                            self._queue(conn, 'CAVE NONE\n')
                            return
                        now = time.monotonic()
                        if now < conn.get('cave_next', 0):
                            self._queue(conn, 'CAVE BUSY\n')
                            return
                        conn['cave_next'] = now + .5
                        terrain = self._active_terrain() if cave.version==9 and conn.get('cave_terrain') else None
                        frames = cave.frames(terrain=terrain,terrain_large=bool(conn.get('cave_large_terrain')))
                        if len(conn['out']) + len(frames) > MAX_QUEUE:
                            self._queue(conn, 'CAVE BUSY\n')
                            return
                        conn['cave_offer'] = cave.identity
                        conn['cave_transfer_pending'] = True
                        conn['cave_offer_terrain_rev'] = self._active_terrain()[0] if cave.version==9 else 0
                        self._queue(conn, frames)
                        return
                if len(fields) == 3 and fields[1] == 'ACK' and re.fullmatch(r'[0-9a-f]{64}', fields[2]):
                    with self.lock:
                        cave=self._connection_cave(conn)
                        if (cave and conn.get('cave_offer') == cave.identity
                                and secrets.compare_digest(fields[2], cave.identity)
                                and cave.version==9 and conn.get('cave_offer_terrain_rev')!=self._active_terrain()[0]):
                            conn['cave_offer']=None;conn['cave_transfer_pending']=False;self._queue(conn,'CAVE RESET '+cave.identity+'\n');return
                        if (cave and conn.get('cave_offer') == cave.identity
                                and secrets.compare_digest(fields[2], cave.identity)):
                            conn['cave_ack'] = cave.identity
                            conn['terrain_report'] = None
                            conn['cave_transfer_pending'] = False
                            conn['cave_revoked'] = []
                            self._queue(conn, 'CAVE OK ' + cave.identity + '\n')
                        elif cave and fields[2] in conn.get('cave_revoked', ()):
                            self._queue(conn, 'CAVE RESET ' + cave.identity + '\n')
                        else:
                            self._error(conn, 'CAVE')
                        return
                self._error(conn, 'CAVE')
                return
            if bytes(raw) == b'CHAT_ENABLE' and conn.get('social'):
                conn['chat'] = True
                self._queue(conn, self._snapshot(conn))
                return
            if fields and fields[0] == 'RALLY':
                self.rally.process(conn, fields)
                self._broadcast()
                return
            if fields and fields[0] == 'CHAT':
                if raw.decode('ascii') != ' '.join(fields):
                    raise ValueError('noncanonical chat line')
                self._chat(conn, fields)
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
            with self.lock:
                # FIELD keeps a visible trainer on the map while walking or using
                # a menu. Its ready bit still gates every interaction. Legacy STATE
                # retains its canonical absent representation and validation.
                field = bool(fields and fields[0] == 'FIELD' and conn.get('social'))
                if len(fields) != 11 or (fields[0] != 'STATE' and not field):
                    raise ValueError('state shape')
                seq = bounded(fields[1], 0, 2**63 - 1)
                if seq <= conn['seq']:
                    self._error(conn, 'STALE')
                    return
                limits = [255, 255, 32767, 32767, 4, 65535, 1]
                state = [bounded(v, 0, limit) for v, limit in zip(fields[2:9], limits)]
                if tuple(state[:2]) in (self.cave_map, self.wilds_map):
                    cave=self._connection_cave(conn)
                    active_map = self.wilds_map if cave and cave.version in (6, 7, 8, 9, 16) else self.cave_map
                    if tuple(state[:2]) != active_map:
                        raise ValueError('wrong generated map')
                    if (cave and conn.get('cave_capable') and conn.get('cave_revoked')
                            and conn.get('cave_ack') != cave.identity):
                        self._queue(conn, 'CAVE RESET ' + cave.identity + '\n')
                        return
                    if (cave is None or conn.get('cave_ack') != cave.identity
                            or self.rally.current(conn) is not None
                            or not (cave.walkable(state[2],state[3]) if conn.get('region_cave') else self._active_walkable(state[2], state[3]))):
                        raise ValueError('unadmitted cave state')
                else:
                    validate_coords(*state[:4])
                if not 1 <= state[4] <= 4 or state[5] > 255:
                    raise ValueError('invalid peer facing or graphics')
                if not field and state[6] == 0 and state != [0, 0, 0, 0, 1, 7, 0]:
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
                now = time.monotonic()
                last_state = conn.get('state_time')
                # An identical report can revive a previously expired friend.
                became_fresh = (last_state is not None and
                                int((TRAVEL_FRESH_SECONDS - (now - last_state)) * 60) <= 0)
                changed = (conn.get('state') != state or bool(conn.get('field')) != field or hashes != previous or became_fresh)
                conn['seq'], conn['state'], conn['field'] = seq, state, field
                if tuple(state[:2]) in (self.cave_map, self.wilds_map):
                    conn['in_generated_cave'] = True
                elif state[6]:
                    conn['in_generated_cave'] = False
                conn['state_time'] = now
                self._deliver_links(self.link_protocol.update_presence(self._link_presence()))
                if changed or now - self.last_presence_broadcast >= PRESENCE_HEARTBEAT_INTERVAL:
                    self._schedule_presence(now)
                self.guild_chat.observe(conn, state)
        except (UnicodeError, ValueError):
            self._error(conn, 'MALFORMED')

    def _chat(self, conn, fields):
        # Session-only history. Private text never enters durable world events,
        # GM context, trainer files, or snapshots of non-recipients/legacy peers.
        if (not conn.get('chat') or len(fields) != 4
                or (fields[2] != '*' and not ID.fullmatch(fields[2]))
                or not re.fullmatch(r'(?:[0-9a-f]{2}){1,120}', fields[3])):
            raise ValueError('invalid chat')
        text = bytes.fromhex(fields[3])
        if any(c < 32 or c > 126 for c in text) or not text.strip():
            raise ValueError('invalid chat text')
        seq = bounded(fields[1], 0, 2**63-1)
        if seq <= conn['seq']:
            self._error(conn, 'STALE')
            return
        conn['seq'] = seq
        target = self.peers.get(fields[2])
        if fields[2] != '*' and (not target or not target.get('chat') or target.get('closing')):
            conn['chat_status'] = 'unavailable'
            self._queue(conn, self._snapshot(conn))
            return
        now = time.monotonic()
        credit = min(4, conn.get('chat_credit', 4) + now - conn.get('chat_time', now))
        conn['chat_time'] = now
        if credit < 1:
            conn['chat_credit'] = credit
            conn['chat_status'] = 'slow'
            self._queue(conn, self._snapshot(conn))
            return
        conn['chat_credit'] = credit - 1
        if fields[2] == '*' and self.guild_chat.handle(conn, text.decode('ascii')):
            return
        self.chat_serial += 1
        message = (self.chat_serial, conn['id'], fields[2], fields[3])
        recipients = self.peers.values() if fields[2] == '*' else (conn, target)
        for recipient in {id(c): c for c in recipients}.values():
            if recipient.get('chat') and not recipient.get('closing'):
                recipient['chat_history'] = (recipient['chat_history'] + [message])[-16:]
        conn['chat_status'] = 'sent'
        self._broadcast()

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
        if ((len(fields) == 4 and fields[:2] == [b'L', b'OFFER'])
                or (len(fields) == 3 and fields[:2] == [b'T', b'OFFER'])):
            try:
                target = fields[-1].decode('ascii')
            except UnicodeError:
                target = None
            other = self.link_channels.get(target)
            if (other is None or other.get('closing')
                    or self.peers.get(target) is not other.get('presence')):
                channel = 'T' if fields[0] == b'T' else 'L'
                self._queue(conn, f'{channel} ERROR UNAVAILABLE\n')
                return
            origin, destination = conn['presence'], other['presence']
            if origin.get('in_generated_cave') or destination.get('in_generated_cave'):
                same_instance = (self._region_scope(origin) is not None
                    and origin.get('in_generated_cave') and destination.get('in_generated_cave')
                    and self._region_scope(origin) == self._region_scope(destination))
                if not same_instance or (fields[0] == b'L' and fields[2] != b'4'):
                    channel = 'T' if fields[0] == b'T' else 'L'
                    self._queue(conn, f'{channel} ERROR UNAVAILABLE\n')
                    return
        self._deliver_links(self.link_protocol.process(conn['id'], bytes(raw), self._link_presence()))

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
        if state and tuple(state[:2]) in (self.cave_map, self.wilds_map):
            raise MeetingUnavailable('generated cave interactions unavailable')
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
        if state and tuple(state[:2]) in (self.cave_map, self.wilds_map):
            raise ValueError('generated cave interactions unavailable')
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

    def _persist_cave(self, blob, *, label=None, previous_revision=None, history_evidence=None):
        if not self.persist_generated_cave:
            return
        try:
            with self.db:
                previous = self.db.execute('SELECT template FROM generated_cave WHERE singleton=1').fetchone()
                identity = hashlib.sha256(blob).hexdigest()
                if previous_revision is not None:
                    if previous is None or hashlib.sha256(previous[0]).hexdigest() != previous_revision:
                        raise ValueError('active area revision changed')
                    place_id = self.memory.continue_place(previous_revision, identity)
                else:
                    place_id = self.memory.place(identity)
                self.db.execute('INSERT OR REPLACE INTO generated_cave (singleton, template) VALUES (1, ?)', (blob,))
                if self.archive_generated_areas:
                    identity = hashlib.sha256(blob).hexdigest()
                    kind = 'wilds' if blob[:8] in (b'EWGMAP06', b'EWGMAP07', b'EWGMAP08', b'EWGMAP09', b'EWGMAP0A') else 'cave'
                    prior_name = self.db.execute('SELECT label FROM generated_area_archive WHERE identity=?', (identity,)).fetchone()
                    display = label if label is not None else (prior_name[0] if prior_name else ('Outdoor area' if kind == 'wilds' else 'Cave'))
                    self.db.execute('INSERT OR IGNORE INTO generated_area_archive (identity,label,kind,template,created) VALUES (?,?,?,?,?)',
                                    (identity, display, kind, blob, int(time.time())))
                    if label is not None:
                        self.db.execute('UPDATE generated_area_archive SET label=? WHERE identity=?', (label, identity))
                        if prior_name and prior_name[0] != label:
                            self.memory.append('area_named', dict(place_id=place_id, revision=identity, before=prior_name[0], after=label))
                if previous is None or previous[0] != blob:
                    self.memory.append('area_activated', dict(place_id=place_id, revision=identity,
                                       label=display if self.archive_generated_areas else label,
                                       previous_revision=hashlib.sha256(previous[0]).hexdigest() if previous else None,
                                       continued=previous_revision is not None,
                                       **({'history_evidence':history_evidence} if history_evidence is not None else {})))
            self.revision = self.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0]
        except sqlite3.Error:
            raise ValueError('generated cave could not be persisted') from None

    def _replace_cave(self, blob, *, label=None, previous_revision=None, expected_world_id=None, expected_sequence=None, history_evidence=None):
        from .shared_cave import SharedCave
        candidate = SharedCave(blob)  # validate completely before mutating anything
        if previous_revision is not None and (not self.persist_generated_cave or type(previous_revision) is not str or not re.fullmatch(r'[0-9a-f]{64}', previous_revision)):
            raise ValueError('invalid previous area revision')
        if label is not None and (type(label) is not str or not label.strip() or len(label) > 80 or any(ord(c) < 32 or ord(c) == 127 for c in label)):
            raise ValueError('invalid generated area label')
        with self.lock:
            if expected_world_id is not None or expected_sequence is not None or history_evidence is not None:
                if (not self.archive_generated_areas or expected_world_id != self.memory.world_id
                        or type(expected_sequence) is not int
                        or expected_sequence != self.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0]):
                    raise ValueError('world changed; inspect before authoring again')
                if (type(history_evidence) is not list or len(history_evidence)>32
                        or any(type(seq) is not int or seq<=0 for seq in history_evidence)
                        or len(set(history_evidence))!=len(history_evidence)):
                    raise ValueError('invalid history evidence')
                for seq in history_evidence:
                    if self.db.execute("SELECT 1 FROM events WHERE seq=? AND kind='world_memory'",(seq,)).fetchone() is None:
                        raise ValueError('history evidence unavailable')
            if (self.wilds_map if candidate.version in (6, 7, 8, 9, 16) else self.cave_map) is None:
                raise ValueError('generated map missing from catalog')
            if self.shared_cave and candidate.identity == self.shared_cave.identity:
                self._persist_cave(blob, label=label, previous_revision=previous_revision, history_evidence=history_evidence)
                return candidate.identity
            peers = [peer for peer in self.peers.values() if not peer.get('closing') and not peer.get('region_cave')]
            if any(peer.get('in_generated_cave') or
                   (peer.get('state') is not None and tuple(peer['state'][:2]) in (self.cave_map, self.wilds_map))
                   for peer in peers):
                raise ValueError('generated cave is occupied')
            message = 'CAVE RESET ' + candidate.identity + '\n'
            recipients = [peer for peer in peers if peer.get('cave_capable')]
            if any(len(peer['out']) + len(message) > MAX_QUEUE for peer in recipients):
                raise ValueError('generated cave update is busy')
            old_id = self.shared_cave.identity if self.shared_cave else None
            self._persist_cave(blob, label=label, previous_revision=previous_revision, history_evidence=history_evidence)
            self.shared_cave = candidate
            self._terrain_walk_cache = None
            for peer in recipients:
                if old_id:
                    peer['cave_revoked'] = (peer.get('cave_revoked', []) + [old_id])[-4:]
                peer['cave_offer'] = peer['cave_ack'] = None
                peer['cave_transfer_pending'] = False
                self._queue(peer, message)
            return candidate.identity

    def list_generated_areas(self):
        if not self.archive_generated_areas:
            raise ValueError('generated area archive is not enabled')
        with self.lock:
            rows = self.db.execute('SELECT identity,label,kind,created FROM generated_area_archive ORDER BY created DESC, identity').fetchall()
            active = self.shared_cave.identity if self.shared_cave else None
            return [dict(identity=i, label=label, kind=kind, created=created, active=i == active)
                    for i, label, kind, created in rows]

    def activate_generated_area(self, identity):
        if not self.archive_generated_areas or type(identity) is not str or not re.fullmatch(r'[0-9a-f]{64}', identity):
            raise ValueError('invalid generated area')
        with self.lock:
            row = self.db.execute('SELECT template FROM generated_area_archive WHERE identity=?', (identity,)).fetchone()
            if row is None or type(row[0]) is not bytes or hashlib.sha256(row[0]).hexdigest() != identity:
                raise ValueError('generated area unavailable')
            return self._replace_cave(row[0])

    def _active_terrain(self):
        if not self.shared_cave or self.shared_cave.version!=9 or not self.archive_generated_areas:return (0,b'\0')
        from .shared_terrain import validate
        row=self.db.execute('SELECT revision,payload FROM generated_area_terrain WHERE identity=?',(self.shared_cave.identity,)).fetchone()
        if row is None:return (0,b'\0')
        revision,payload=row
        if type(revision) is not int or not 1<=revision<=2147483647:raise ValueError('invalid stored terrain revision')
        validate(self.shared_cave,payload);return revision,payload

    def _terrain_requires_geometry(self):
        from .shared_terrain import needs_geometry
        if not self.shared_cave or self.shared_cave.version!=9:return False
        revision,payload=self._active_terrain()
        return (revision>0 and payload==b'\0') or needs_geometry(self.shared_cave,payload)

    def _terrain_requires_large(self):
        from .shared_terrain import needs_large
        if not self.shared_cave or self.shared_cave.version!=9:return False
        return needs_large(self._active_terrain()[1])

    def _active_walkable(self, x, y):
        cave=self.shared_cave
        if not cave:return False
        if cave.version!=9 or not self.archive_generated_areas:return cave.walkable(x,y)
        if self._terrain_walk_cache is None or self._terrain_walk_cache[0]!=cave.identity:
            from .shared_terrain import project
            revision,payload=self._active_terrain();self._terrain_walk_cache=(cave.identity,revision,project(cave,payload))
        return (x,y) in self._terrain_walk_cache[2]

    def set_shared_terrain(self, identity, tiles):
        """Persist and broadcast a bounded shared walkable overlay snapshot."""
        from .shared_terrain import validate,encode
        if type(identity) is not str or not re.fullmatch(r'[0-9a-f]{64}',identity) or type(tiles) is not list or not 1<=len(tiles)<=64:raise ValueError('invalid shared terrain request')
        changes={}
        for tile in tiles:
            if type(tile) is not dict or set(tile)!={'x','y','terrain'}:raise ValueError('invalid shared terrain request')
            x,y,terrain=tile['x'],tile['y'],tile['terrain']
            if type(x) is not int or type(y) is not int or not 0<=x<63 or not 0<=y<63 or type(terrain) is not str or terrain not in ('grass','tall_grass') or (x,y) in changes:raise ValueError('invalid shared terrain request')
            changes[(x,y)]=0 if terrain=='grass' else 1
        with self.lock:
            cave=self.shared_cave
            if not self.archive_generated_areas or not cave or cave.version!=9 or cave.identity!=identity:raise ValueError('durable active event area required')
            stored=self.db.execute('SELECT template FROM generated_cave WHERE singleton=1').fetchone()
            if stored is None or type(stored[0]) is not bytes or hashlib.sha256(stored[0]).hexdigest()!=identity:raise ValueError('publish the active event area before editing terrain')
            revision,old=self._active_terrain();merged=validate(cave,old)
            if any(not self._active_walkable(x,y) for x,y in changes):raise ValueError('tile is not currently walkable')
            merged.update(changes);payload=encode(cave,merged)
            if payload==old:return {'ok':True,'identity':identity,'revision':revision,'tiles':len(merged),'changed':False}
            if revision>=2147483647:raise ValueError('terrain revision exhausted')
            peers=[p for p in self.peers.values() if not p.get('closing') and p.get('cave_capable') and not p.get('region_cave')]
            from .shared_terrain import needs_geometry,needs_large,frames as terrain_frames
            geometry=needs_geometry(cave,payload);large=needs_large(payload)
            def compatible(p):return bool(p.get('cave_terrain') and (not geometry or p.get('cave_geometry')) and (not large or p.get('cave_large_terrain')))
            if any((p.get('in_generated_cave') or (p.get('state') is not None and tuple(p['state'][:2]) in (self.cave_map,self.wilds_map))) and not compatible(p) for p in peers):raise ValueError('incompatible trainer is inside')
            revision+=1;reset=f'CAVE RESET {identity}\n'
            targets=[p for p in peers if p.get('cave_ack')==identity and compatible(p) and not p.get('cave_transfer_pending')]
            legacy=[p for p in peers if p.get('cave_ack')==identity and not compatible(p)]
            updates=[(p,terrain_frames(identity,revision,payload,bool(p.get('cave_large_terrain')))) for p in targets]
            if any(len(p['out'])+len(update)>MAX_QUEUE for p,update in updates) or any(len(p['out'])+len(reset)>MAX_QUEUE for p in legacy):raise ValueError('trainer connection is busy')
            try:
                with self.db:
                    self.db.execute('INSERT OR REPLACE INTO generated_area_terrain(identity,revision,payload) VALUES(?,?,?)',(identity,revision,payload))
                    self.memory.append('terrain_changed', dict(place_id=self.memory.place(identity),
                                       revision=identity, terrain_revision=revision,
                                       tiles=terrain_delta(cave, old, payload)))
                self.revision = self.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0]
            except sqlite3.Error:
                raise ValueError('shared terrain could not be persisted') from None
            from .shared_terrain import project
            self._terrain_walk_cache=(identity,revision,project(cave,payload))
            queued=0;delivery_failed=0
            for peer,update in updates:
                try:
                    self._queue(peer,update)
                    if peer.get('closing'):delivery_failed+=1
                    else:queued+=1
                except Exception:
                    delivery_failed+=1
                    try:self._drop(peer)
                    except Exception:peer['closing']=True
            for peer in legacy:
                peer['cave_revoked']=(peer.get('cave_revoked',[])+[identity])[-4:];peer['cave_offer']=peer['cave_ack']=None;peer['cave_transfer_pending']=False
                try:
                    self._queue(peer,reset)
                    if peer.get('closing'):delivery_failed+=1
                except Exception:
                    delivery_failed+=1
                    try:self._drop(peer)
                    except Exception:peer['closing']=True
            return {'ok':True,'identity':identity,'revision':revision,'tiles':len(merged),'changed':True,'queued':queued,'delivery_failed':delivery_failed}

    def set_shared_geometry(self, identity, tiles, replace=False, *, expected_world_id=None, expected_revision=None, history_evidence=None):
        """Commit connected terrain geometry only while the generated area is empty."""
        from .shared_terrain import validate,encode,project
        if type(identity) is not str or not re.fullmatch(r'[0-9a-f]{64}',identity) or type(tiles) is not list or type(replace) is not bool or len(tiles)>512 or (not tiles and not replace):raise ValueError('invalid shared geometry request')
        changes={}
        for tile in tiles:
            if type(tile) is not dict or set(tile)!={'x','y','terrain'}:raise ValueError('invalid shared geometry request')
            x,y,terrain=tile['x'],tile['y'],tile['terrain']
            if type(x) is not int or type(y) is not int or not 0<=x<63 or not 0<=y<63 or type(terrain) is not str or terrain not in ('grass','tall_grass','water','original') or (x,y) in changes:raise ValueError('invalid shared geometry request')
            changes[(x,y)]={'grass':0,'tall_grass':1,'water':2,'original':None}[terrain]
        with self.lock:
            cave=self.shared_cave
            if not self.archive_generated_areas or not cave or cave.version!=9 or cave.identity!=identity:raise ValueError('durable active event area required')
            stored=self.db.execute('SELECT template FROM generated_cave WHERE singleton=1').fetchone()
            if stored is None or type(stored[0]) is not bytes or hashlib.sha256(stored[0]).hexdigest()!=identity:raise ValueError('publish the active event area before editing geometry')
            peers=[p for p in self.peers.values() if not p.get('closing') and p.get('cave_capable') and not p.get('region_cave')]
            if any(p.get('in_generated_cave') or (p.get('state') is not None and tuple(p['state'][:2]) in (self.cave_map,self.wilds_map)) for p in peers):raise ValueError('all trainers must leave the generated area')
            revision,old=self._active_terrain();merged={} if replace else validate(cave,old)
            if expected_world_id is not None or expected_revision is not None or history_evidence is not None:
                if (expected_world_id != self.memory.world_id or type(expected_revision) is not int
                        or expected_revision != revision):
                    raise ValueError('world or terrain changed; inspect before authoring again')
                if (type(history_evidence) is not list or len(history_evidence)>16
                        or any(type(seq) is not int or seq<=0 for seq in history_evidence)
                        or len(set(history_evidence))!=len(history_evidence)):
                    raise ValueError('invalid history evidence')
                for seq in history_evidence:
                    if self.db.execute("SELECT 1 FROM events WHERE seq=? AND kind='world_memory'",(seq,)).fetchone() is None:
                        raise ValueError('history evidence unavailable')
            npcs={(cave.cast[2+61*i],cave.cast[3+61*i]) for i in range(cave.cast[0])}
            for (x,y),kind in changes.items():
                if not 0<x<62 or not 0<y<62 or (x,y) in npcs or (x,y) in ((1,1),(61,60),(61,61)):raise ValueError('protected geometry cell')
                if kind is None:merged.pop((x,y),None)
                else:merged[(x,y)]=kind
            payload=encode(cave,merged)
            if payload==old:return {'ok':True,'identity':identity,'revision':revision,'tiles':len(merged),'changed':False}
            if revision>=2147483647:raise ValueError('terrain revision exhausted')
            reset=f'CAVE RESET {identity}\n';recipients=[p for p in peers if p.get('cave_ack')==identity or p.get('cave_offer')==identity]
            if any(len(p['out'])+len(reset)>MAX_QUEUE for p in recipients):raise ValueError('trainer connection is busy')
            revision+=1
            try:
                with self.db:
                    self.db.execute('INSERT OR REPLACE INTO generated_area_terrain(identity,revision,payload) VALUES(?,?,?)',(identity,revision,payload))
                    self.memory.append('terrain_changed', dict(place_id=self.memory.place(identity),
                                       revision=identity, terrain_revision=revision,
                                       tiles=terrain_delta(cave, old, payload),
                                       **({'history_evidence':history_evidence} if history_evidence is not None else {})))
                self.revision = self.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0]
            except sqlite3.Error:raise ValueError('shared geometry could not be persisted') from None
            self._terrain_walk_cache=(identity,revision,project(cave,payload));queued=0;delivery_failed=0
            for peer in recipients:
                peer['cave_revoked']=(peer.get('cave_revoked',[])+[identity])[-4:];peer['cave_offer']=peer['cave_ack']=None;peer['cave_transfer_pending']=False
                try:
                    self._queue(peer,reset)
                    if peer.get('closing'):delivery_failed+=1
                    else:queued+=1
                except Exception:
                    delivery_failed+=1
                    try:self._drop(peer)
                    except Exception:peer['closing']=True
            return {'ok':True,'identity':identity,'revision':revision,'tiles':len(merged),'changed':True,'reset_queued':queued,'delivery_failed':delivery_failed}

    def inspect_shared_terrain(self, identity):
        """Owner-only world geometry, authoritative overlay and client reports."""
        from .shared_terrain import validate
        if type(identity) is not str or not re.fullmatch(r'[0-9a-f]{64}',identity):raise ValueError('invalid area identity')
        with self.lock:
            cave=self.shared_cave
            if not self.archive_generated_areas or not cave or cave.version!=9 or cave.identity!=identity:raise ValueError('active durable event area required')
            revision,payload=self._active_terrain();overlay=validate(cave,payload)
            tiles=[{'x':x,'y':y,'terrain':('grass','tall_grass','water')[kind]} for (x,y),kind in sorted(overlay.items())]
            cast=[{'npc':i+1,'x':cave.cast[2+i*61], 'y':cave.cast[3+i*61]} for i in range(cave.cast[0])]
            players=[]
            for name,peer in sorted(self.peers.items()):
                if peer.get('closing') or peer.get('cave_ack')!=identity:continue
                report=peer.get('terrain_report');current=report if report and report['identity']==identity and report['revision']==revision else None
                players.append({'trainer':name,'compatible':bool(peer.get('cave_terrain')),'geometry_capable':bool(peer.get('cave_geometry')),'inside':bool(peer.get('in_generated_cave')),
                                'reported_phase':current['phase'] if current else 'pending'})
            return {'ok':True,'identity':identity,'revision':revision,'rows':[row.decode('ascii') for row in cave._rows],
                    'effective_rows':[''.join('.' if self._active_walkable(x,y) else '#' for x in range(63)) for y in range(63)],
                    'characters':cast,'tiles':tiles,'players':players}

    def _queue_event_command(self, trainer, identity, verb, args, npc=None, tile=None, tiles=None):
        if type(trainer) is not str or not ID.fullmatch(trainer) or type(identity) is not str or not re.fullmatch(r'[0-9a-f]{64}',identity):
            raise ValueError('invalid event command')
        with self.lock:
            cave=self.shared_cave;peer=self.peers.get(trainer)
            if (not cave or cave.version!=9 or cave.identity!=identity or not peer or peer.get('closing')
                or not peer.get('cave_events') or peer.get('cave_ack')!=identity
                or not peer.get('in_generated_cave') or peer.get('state') is None
                or tuple(peer['state'][:2])!=self.wilds_map):
                raise ValueError('trainer is not in the requested event area')
            if npc is not None and npc>cave.cast[0]:raise ValueError('character not in area')
            for x,y in ([tile] if tile is not None else []) + (tiles or []):
                if not self._active_walkable(x,y) or (x,y) in ((1,1),(61,60),(61,61)):raise ValueError('tile cannot be painted')
            seq=peer.get('event_command_seq',0)+1
            if seq>2147483647:raise ValueError('event command sequence exhausted')
            message=f'CAVE {verb} {identity} {seq} {args}\n'
            if len(peer['out'])+len(message)>MAX_QUEUE:raise ValueError('trainer connection is busy')
            self._queue(peer,message);peer['event_command_seq']=seq
            commands=peer.setdefault('event_commands',{});commands[seq]={'identity':identity,'status':'queued'}
            while len(commands)>64:del commands[next(iter(commands))]
            return {'ok':True,'queued':True,'trainer':trainer,'identity':identity,'sequence':seq,'session':peer['event_command_session']}

    def set_event_state(self, trainer, identity, state):
        """Queue an owner-only, per-trainer state assignment; not delivery confirmation."""
        if type(state) is not int or not 0<=state<=15:raise ValueError('invalid event state command')
        result=self._queue_event_command(trainer,identity,'EVENTSET',str(state));result['state']=state;return result

    def set_event_rule(self, trainer, identity, state, npc, next_state, text):
        """Queue a literal per-trainer rule patch; native application is independent."""
        from .wilds_cast import _text
        if any(type(v) is not int for v in (state,npc,next_state)) or not 0<=state<=15 or not 1<=npc<=3 or not 0<=next_state<=15:
            raise ValueError('invalid event rule command')
        value=_text(text)
        return self._queue_event_command(trainer,identity,'EVENTRULE',f'{state} {npc} {next_state} {value.hex()}',npc=npc)

    def set_event_tile(self, trainer, identity, x, y, terrain):
        """Queue one walkable terrain paint for a named trainer only."""
        if type(x) is not int or type(y) is not int or not 0<=x<63 or not 0<=y<63 or type(terrain) is not str or terrain not in ('grass','tall_grass'):
            raise ValueError('invalid event tile command')
        kind=0 if terrain=='grass' else 1
        return self._queue_event_command(trainer,identity,'EVENTTILE',f'{x} {y} {kind}',tile=(x,y))

    def set_event_tiles(self, trainer, identity, tiles):
        """Queue an atomic, bounded per-trainer walkable terrain patch."""
        if type(tiles) is not list or not 1<=len(tiles)<=64:raise ValueError('invalid terrain patch')
        packed=bytearray([len(tiles)]);positions=[];seen=set()
        for tile in tiles:
            if type(tile) is not dict or set(tile)!={'x','y','terrain'}:raise ValueError('invalid terrain patch')
            x,y,terrain=tile['x'],tile['y'],tile['terrain']
            if type(x) is not int or type(y) is not int or not 0<=x<63 or not 0<=y<63 or type(terrain) is not str or terrain not in ('grass','tall_grass') or (x,y) in seen:raise ValueError('invalid terrain patch')
            seen.add((x,y));positions.append((x,y));packed.extend((x,y,0 if terrain=='grass' else 1))
        return self._queue_event_command(trainer,identity,'EVENTTILES',packed.hex(),tiles=positions)

    def event_command_status(self, trainer, identity, session, sequence):
        """Report a client-reported result or unknown; never infer delivery."""
        if type(trainer) is not str or not ID.fullmatch(trainer) or type(identity) is not str or not re.fullmatch(r'[0-9a-f]{64}',identity) or type(session) is not str or not re.fullmatch(r'[0-9a-f]{16}',session) or type(sequence) is not int or not 1<=sequence<=2147483647:
            raise ValueError('invalid event command status request')
        with self.lock:
            peer=self.peers.get(trainer);entry=peer.get('event_commands',{}).get(sequence) if peer and not peer.get('closing') and peer.get('event_command_session')==session else None
            status=entry['status'] if entry and entry['identity']==identity else 'unknown'
            return {'ok':True,'trainer':trainer,'identity':identity,'session':session,'sequence':sequence,'status':status}

    def _admin_line(self, conn, raw):
        conn['closing'] = True
        try:
            request = json.loads(raw)
            if request.get('command') == 'replace_cave':
                try:
                    if (not {'command', 'template'} <= set(request) or not set(request) <= {'command', 'template', 'label', 'previous_revision', 'expected_world_id', 'expected_sequence', 'history_evidence'}
                            or type(request['template']) is not str):
                        raise ValueError('invalid cave request')
                    try:
                        blob = base64.b64decode(request['template'], validate=True)
                    except (ValueError, binascii.Error):
                        raise ValueError('invalid cave encoding') from None
                    if base64.b64encode(blob).decode('ascii') != request['template']:
                        raise ValueError('noncanonical cave encoding')
                    guards={'expected_world_id','expected_sequence','history_evidence'}
                    if set(request)&guards and not guards<=set(request):
                        raise ValueError('incomplete world publication guard')
                    guard={key:request[key] for key in guards if key in request}
                    result = dict(ok=True, id=self._replace_cave(blob, label=request.get('label'), previous_revision=request.get('previous_revision'), **guard), persistent=self.persist_generated_cave)
                except ValueError as exc:
                    # Expected validation/occupancy refusal is not a mechanic error.
                    result = dict(ok=False, error=str(exc))
            elif request.get('command') == 'set_event_state':
                try:
                    if set(request)!={'command','trainer','identity','state'}:raise ValueError('invalid event state command')
                    result=self.set_event_state(request['trainer'],request['identity'],request['state'])
                except ValueError as exc:
                    result=dict(ok=False,error=str(exc))
            elif request.get('command') == 'set_event_tile':
                try:
                    if set(request)!={'command','trainer','identity','x','y','terrain'}:raise ValueError('invalid event tile command')
                    result=self.set_event_tile(request['trainer'],request['identity'],request['x'],request['y'],request['terrain'])
                except ValueError as exc:
                    result=dict(ok=False,error=str(exc))
            elif request.get('command') == 'set_shared_geometry_compact':
                try:
                    if set(request)!={'command','identity','data','replace'} or type(request['data']) is not str:raise ValueError('invalid compact geometry')
                    raw=base64.b64decode(request['data'],validate=True)
                    if base64.b64encode(raw).decode('ascii')!=request['data'] or len(raw)<2:raise ValueError('invalid compact geometry')
                    count=int.from_bytes(raw[:2],'little')
                    if count>512 or len(raw)!=2+3*count:raise ValueError('invalid compact geometry')
                    kinds=('grass','tall_grass','water','original');tiles=[]
                    for i in range(count):
                        x,y,kind=raw[2+3*i:5+3*i]
                        if kind>=len(kinds):raise ValueError('invalid compact geometry')
                        tiles.append({'x':x,'y':y,'terrain':kinds[kind]})
                    result=self.set_shared_geometry(request['identity'],tiles,request['replace'])
                except (ValueError,binascii.Error) as exc:
                    result=dict(ok=False,error=str(exc))
            elif request.get('command') == 'set_shared_geometry':
                try:
                    fields={'command','identity','tiles'}
                    guarded=fields|{'expected_world_id','expected_revision','history_evidence'}
                    if set(request) not in (fields,fields|{'replace'},guarded):raise ValueError('invalid shared geometry request')
                    guard={key:request[key] for key in ('expected_world_id','expected_revision','history_evidence') if key in request}
                    result=self.set_shared_geometry(request['identity'],request['tiles'],request.get('replace',False),**guard)
                except ValueError as exc:
                    result=dict(ok=False,error=str(exc))
            elif request.get('command') == 'inspect_shared_terrain':
                try:
                    if set(request)!={'command','identity'}:raise ValueError('invalid shared terrain inspection')
                    result=self.inspect_shared_terrain(request['identity'])
                except ValueError as exc:
                    result=dict(ok=False,error=str(exc))
            elif request.get('command') == 'set_shared_terrain':
                try:
                    if set(request)!={'command','identity','tiles'}:raise ValueError('invalid shared terrain request')
                    result=self.set_shared_terrain(request['identity'],request['tiles'])
                except ValueError as exc:
                    result=dict(ok=False,error=str(exc))
            elif request.get('command') == 'set_event_tiles':
                try:
                    if set(request)!={'command','trainer','identity','tiles'}:raise ValueError('invalid terrain patch')
                    result=self.set_event_tiles(request['trainer'],request['identity'],request['tiles'])
                except ValueError as exc:
                    result=dict(ok=False,error=str(exc))
            elif request.get('command') == 'event_command_status':
                try:
                    if set(request)!={'command','trainer','identity','session','sequence'}:raise ValueError('invalid event command status request')
                    result=self.event_command_status(request['trainer'],request['identity'],request['session'],request['sequence'])
                except ValueError as exc:
                    result=dict(ok=False,error=str(exc))
            elif request.get('command') == 'set_event_rule':
                try:
                    if set(request)!={'command','trainer','identity','state','npc','next_state','text'}:raise ValueError('invalid event rule command')
                    result=self.set_event_rule(request['trainer'],request['identity'],request['state'],request['npc'],request['next_state'],request['text'])
                except ValueError as exc:
                    result=dict(ok=False,error=str(exc))
            elif request.get('command') == 'invitation':
                if set(request) != {'command', 'trainer'} or self.sharing is None:
                    self._queue(conn, json.dumps(dict(ok=False, error='secure sharing required')) + '\n')
                    return
                identity = self.create_identity(request['trainer'])
                result = dict(ok=True, invitation=dict(self.sharing, trainer=identity['id'], token=identity['token']))
            elif request.get('command') == 'inspect':
                result = self.inspect()
            elif request.get('command') == 'world_rules':
                try:
                    action = request.get('action')
                    with self.lock:
                        if action == 'status' and set(request) == {'command', 'action'}:
                            result = self.world_rules.status()
                        elif action == 'replace' and set(request) == {'command', 'action', 'rules', 'expected_revision'}:
                            if any(not p.get('closing') for p in self.peers.values()):
                                raise ValueError('All players must leave before changing world rules.')
                            result = self.world_rules.replace(request['rules'], request['expected_revision'])
                        else:
                            raise ValueError('invalid world rules request')
                except ValueError as exc:
                    result = dict(ok=False, error=str(exc))
            elif request.get('command') == 'host_controls':
                try:
                    result = self.host_controls.request(request, self)
                except ValueError as exc:
                    # A busy activity or refused host action is not a failing
                    # mechanic module. Do not replace its persisted status.
                    result = dict(ok=False, error=str(exc))
            elif request.get('command') == 'open_region':
                try:
                    if set(request)!={'command','revision'}:
                        raise ValueError('invalid region request')
                    result=self.open_region(request['revision'])
                except ValueError as exc:
                    result=dict(ok=False,error=str(exc))
            elif request.get('command') == 'saved_places':
                try:
                    if not set(request) <= {'command','after','limit'}:
                        raise ValueError('invalid saved places request')
                    result = dict(ok=True, **self.memory.saved_places(self, **{k:v for k,v in request.items() if k!='command'}))
                except (ValueError, TypeError) as exc:
                    result = dict(ok=False,error=str(exc))
            elif request.get('command') == 'inspect_saved_place':
                try:
                    if set(request) != {'command','revision'}:
                        raise ValueError('invalid saved place inspection')
                    result = dict(ok=True, **self.memory.inspect_saved_place(self,request['revision']))
                except ValueError as exc:
                    result = dict(ok=False,error=str(exc))
            elif request.get('command') == 'world_recall':
                try:
                    if not {'command', 'through'} <= set(request) or not set(request) <= {'command', 'through', 'places', 'terms'}:
                        raise ValueError('invalid recall request')
                    result = dict(ok=True, **self.memory.recall(**{k:v for k,v in request.items() if k != 'command'}))
                    result['saved_places'] = self.memory.saved_places(self, places=result['places'], terms=result['terms'])
                except (ValueError, TypeError) as exc:
                    result = dict(ok=False, error=str(exc))
            elif request.get('command') == 'world_history':
                try:
                    if not set(request) <= {'command', 'after', 'limit', 'place_id', 'through'}:
                        raise ValueError('invalid history request')
                    result = dict(ok=True, world_id=self.memory.world_id,
                                  **self.memory.history(**{k:v for k,v in request.items() if k != 'command'}))
                except ValueError as exc:
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
                if conn.get('in_generated_cave') and self._region_scope(conn):
                    revision=self._region_scope(conn)
                    place=self.db.execute('SELECT place_id FROM world_places WHERE revision=?',(revision,)).fetchone()
                    player['generated_place']=dict(place_id=place[0] if place else None,revision=revision)
                player['meeting'] = conn.get('meeting')
                players.append(player)
            return dict(ok=True, revision=self.revision, players=players,
                        world_memory=self.memory.context(self),
                        sharing=(dict(endpoint=self.sharing['endpoint'], listen=getattr(self, 'sharing_listen', None))
                                 if self.sharing else None),
                        capacity=dict(players=self.max_players, controls=self.max_controls,
                                      connections=self.max_connections),
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
        objects = validate_objects(result.get('objects', []))
        from .build_catalog import catalog_maps
        reserved = {(g, n) for (g, n), item in catalog_maps().items()
                    if item.get('name') in ('GeneratedWorld_Cave', 'GeneratedWorld_Wilds')}
        if any((obj['group'], obj['num']) in reserved for obj in objects):
            raise ValueError('generated cave cannot have mutable objects')
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
            if tuple(values[:2]) in reserved:
                raise ValueError('generated cave cannot have mutable tiles')
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
                        if kind == 'deploy' or tiles != self.tiles or object_content(objects) != object_content(self.objects):
                            self.revision = self.memory.append('mechanic_changed', dict(
                                module_hash=candidate.sha256, previous_module_hash=self.candidate.sha256 if self.candidate else None,
                                cause=kind, interaction_cursor=cursor,
                                places=overlay_places(self.tiles + tiles, self.objects + objects),
                                before=dict(tiles=self.tiles, objects=self.objects),
                                after=dict(tiles=tiles, objects=objects)))
                        if kind == 'deploy':
                            self.db.execute('INSERT OR REPLACE INTO status VALUES(1,NULL)')
                    self.candidate, self.module_state, self.tiles = candidate, json.loads(state_json), tiles
                    self.objects, self.interaction_cursor = objects, cursor
                    if kind == 'deploy':
                        self.module_error = None
                    self._broadcast()
                response = dict(ok=True, revision=self.revision, module_hash=candidate.sha256)
            except Exception as exc:
                self.revision = self.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0]
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
                        # Public handshakes cannot consume the local admin reserve.
                        public_limit = self.max_connections - 2
                        if (len(self.connections) >= self.max_connections or
                                (key.data == 'listener' and sum(not c['admin'] for c in self.connections.values()) >= public_limit)):
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
                                limit = MAX_ADMIN_LINE if conn.get('admin') else MAX_CONTROL_LINE if conn.get('control') else MAX_LINE
                                if len(raw) > limit:
                                    self._error(conn, 'OVERSIZE')
                                else:
                                    if conn['admin']:
                                        self._admin_line(conn, raw)
                                    else:
                                        self._line(conn, raw)
                            limit = MAX_ADMIN_LINE if conn.get('admin') else MAX_CONTROL_LINE if conn.get('control') else MAX_LINE
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
                self._poll_presence(time.monotonic())
                self._deliver_links(self.link_protocol.tick())
                self.rally.tick()
                self._poll_controls()
                self._poll_mechanics()

    def close(self):
        if self._closed:
            return
        self._closed = True
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


def export_invitation(socket_path, trainer, destination, *, admin_path=None, state_dir=None):
    """Issue/reissue through the running private authority; never print tokens."""
    from .client import admin_request
    from .transport import validate_invitation
    socket_path = Path(socket_path).absolute()
    root = (Path(state_dir).absolute() if state_dir is not None else
            socket_path.parent.parent if socket_path.parent.name == 'transport' else socket_path.parent)
    destination = Path(destination).absolute()
    if any(destination.resolve().is_relative_to(root / part) for part in ('transport', 'trainers')):
        raise ValueError('keep invitations outside game-visible directories')
    # Exclusive creation also refuses a symlink, including dangling symlinks.
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'w') as output:
            result = admin_request(socket_path, dict(command='invitation', trainer=trainer), admin_path=admin_path)
            if not result.get('ok'):
                raise ValueError('invitation service unavailable')
            invitation = validate_invitation(result['invitation'])
            json.dump(invitation, output)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def main(argv=None):
    """Standalone authority; optionally own the existing TLS broker in-process."""
    from .transport import HostBroker, _endpoint, validate_invitation
    import signal
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--socket', help='default: STATE_DIR/transport/world.sock')
    parser.add_argument('--admin-socket')
    parser.add_argument('--state-dir', required=True, help='explicit persistent world directory; reused, never reset')
    parser.add_argument('--require-existing-state', action='store_true', help='refuse a missing database (deployment safety)')
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--create-identity', metavar='ID')
    action.add_argument('--invite', metavar='ID', help='issue/reissue invitation from the RUNNING private authority')
    parser.add_argument('--invitation-out', type=Path)
    parser.add_argument('--listen', type=_endpoint, help='enable TLS at HOST:PORT')
    parser.add_argument('--advertise', type=_endpoint, help='reachable invitation HOST:PORT (required with --listen)')
    parser.add_argument('--cert', type=Path, help='existing PEM certificate; never regenerated')
    parser.add_argument('--key', type=Path, help='existing PEM private key; never regenerated')
    parser.add_argument('--max-players', type=int, default=32)
    parser.add_argument('--max-controls', type=int, help='default: twice max-players; at most two per identity')
    parser.add_argument('--connection-headroom', type=int, default=8, help='includes two private admin slots')
    parser.add_argument('--generated-cave-template', type=Path, help='experimental startup shared cave template')
    parser.add_argument('--persist-generated-cave', action='store_true', help='opt in to retain published cave geometry in the world database')
    parser.add_argument('--timeout', type=float, default=120)
    args = parser.parse_args(argv)
    state = Path(args.state_dir).absolute()
    game_socket = args.socket or str(state/'transport/world.sock')
    if args.require_existing_state and not (state/'world.sqlite3').is_file():
        parser.error('existing world database required; refusing to create a new world')
    if bool(args.invite) != bool(args.invitation_out):
        parser.error('--invite and --invitation-out must be supplied together')
    if args.listen is not None:
        if args.advertise is None or args.cert is None or args.key is None:
            parser.error('--listen requires --advertise, --cert and --key')
        try:
            validate_invitation(dict(version=1, endpoint=dict(host=args.advertise[0], port=args.advertise[1]),
                                     pin='0'*64, trainer='validation', token='0'*64))
        except ValueError:
            parser.error('invalid advertised endpoint')
    elif any(value is not None for value in (args.advertise, args.cert, args.key)):
        parser.error('--advertise, --cert and --key require --listen')
    if args.invite is not None:
        try:
            export_invitation(game_socket, args.invite, args.invitation_out, admin_path=args.admin_socket, state_dir=state)
        except (OSError, ValueError, KeyError):
            parser.exit(1, 'world: could not export invitation (requires running TLS authority and a new private output path)\n')
        return 0
    if args.create_identity is not None:
        token = create_identity(args.state_dir, args.create_identity)
        print(json.dumps(dict(id=args.create_identity, token=token)))
        return 0
    stopped = threading.Event()
    previous = {}
    for signum in (signal.SIGTERM, signal.SIGINT):
        previous[signum] = signal.signal(signum, lambda *_: stopped.set())
    server = broker = None
    result = 0
    try:
        cave_template = None
        if args.generated_cave_template is not None:
            from .shared_cave import MAX_SIZE
            with args.generated_cave_template.open('rb') as stream:
                cave_template = stream.read(MAX_SIZE + 1)
        server = WorldServer(game_socket, state, admin_path=args.admin_socket,
                             max_players=args.max_players, max_controls=args.max_controls,
                             connection_headroom=args.connection_headroom, cave_template=cave_template,
                             persist_generated_cave=args.persist_generated_cave)
        server.start()
        if args.listen is not None:
            import ssl
            pin = hashlib.sha256(ssl.PEM_cert_to_DER_cert(args.cert.read_text())).hexdigest()
            broker = HostBroker(game_socket, args.cert, args.key, args.listen,
                                max_clients=server.max_connections-2, timeout=args.timeout)
            broker.start()
            with server.lock:
                server.sharing = dict(version=1, endpoint=dict(host=args.advertise[0], port=args.advertise[1]), pin=pin)
                server.sharing_listen = broker.address
        while not stopped.wait(.1):
            if not server.thread.is_alive() or (broker is not None and not broker._thread.is_alive()):
                result = 1
                break
    except (OSError, ValueError, RuntimeError):
        # No credential/path/network-supplied exception contents in service logs.
        print('world: configuration or listener failure', file=sys.stderr)
        result = 1
    finally:
        if broker is not None:
            broker.close()
        if server is not None:
            server.close()
        for signum, handler in previous.items():
            signal.signal(signum, handler)
    return result


if __name__ == '__main__':
    raise SystemExit(main())
