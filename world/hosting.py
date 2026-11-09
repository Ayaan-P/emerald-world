"""Persistent private hosted-world authority. No game saves enter this API.

All game endpoints use the existing v1 invitation and WorldServer protocol.
The operator supplies a separate state root, existing TLS key/cert and port pool.
"""
import base64
import binascii
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import ssl
import threading

from .hosting_protocol import HostingError, _json_object
from .server import WorldServer
from .transport import HostBroker, validate_invitation, validate_invitation_host


def _secret(value):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value):
        raise HostingError(403, 'forbidden')
    return hashlib.sha256(value.encode('ascii')).hexdigest()


def _trainer(value):
    if type(value) is not str or not re.fullmatch('[A-Za-z0-9_-]{1,24}', value):
        raise HostingError()
    return value


class HostedWorldManager:
    """Own every registered authority until close(), including across client exits.

    Constructor restores ALL registered worlds or fails closed. An operator must
    keep the root, advertise name, certificate and allocated port pool stable.
    Credentials live only in private SQLite files. Methods are thread-safe.
    """
    def __init__(self, root, *, cert, key, advertise_host, listen_host='127.0.0.1',
                 port_start=9001, port_end=9016, max_worlds=16):
        validate_invitation_host(advertise_host)
        if (type(max_worlds) is not int or not 1 <= max_worlds <= 16
                or type(port_start) is not int or type(port_end) is not int
                or not 1 <= port_start <= port_end <= 65535
                or port_end-port_start+1 > 16 or max_worlds > port_end-port_start+1):
            raise ValueError('invalid hosting limits')
        self.root = Path(root).absolute()
        if len(os.fsencode(self.root/'worlds'/('f'*16)/'transport/world.sock')) >= 108:
            raise ValueError('hosting root too long for private sockets')
        self.cert, self.key = Path(cert), Path(key)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(self.cert, self.key)
        self.pin = hashlib.sha256(ssl.PEM_cert_to_DER_cert(self.cert.read_text())).hexdigest()
        self.advertise_host, self.listen_host = advertise_host, listen_host
        self.port_start, self.port_end, self.max_worlds = port_start, port_end, max_worlds
        self.lock = threading.RLock()
        self.running = {}
        self.db = None
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.root.chmod(0o700)
        self.authority_lock = (self.root/'hosting.lock').open('a+b')
        os.chmod(self.root/'hosting.lock', 0o600)
        try:
            fcntl.flock(self.authority_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.authority_lock.close()
            raise RuntimeError('hosting root already in use') from None
        try:
            path = self.root/'hosting.sqlite3'
            fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
            os.close(fd)
            path.chmod(0o600)
            self.db = sqlite3.connect(path, check_same_thread=False)
            self.db.row_factory = sqlite3.Row
            self.db.execute('PRAGMA foreign_keys=ON')
            self.db.executescript('''
                CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS accounts (
                    id TEXT PRIMARY KEY, enrollment TEXT UNIQUE NOT NULL, token TEXT UNIQUE);
                CREATE TABLE IF NOT EXISTS worlds (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES accounts(id),
                    name TEXT NOT NULL, trainer TEXT NOT NULL, port INTEGER UNIQUE NOT NULL,
                    request TEXT NOT NULL, UNIQUE(owner, request));
                CREATE TABLE IF NOT EXISTS members (
                    world TEXT NOT NULL REFERENCES worlds(id), trainer TEXT NOT NULL,
                    token TEXT NOT NULL, PRIMARY KEY(world, trainer));
                CREATE TABLE IF NOT EXISTS invites (
                    digest TEXT PRIMARY KEY, bearer TEXT NOT NULL,
                    world TEXT NOT NULL REFERENCES worlds(id), request TEXT NOT NULL,
                    trainer TEXT, UNIQUE(world, request));
                CREATE TABLE IF NOT EXISTS account_invites (
                    sponsor TEXT NOT NULL REFERENCES accounts(id), request TEXT NOT NULL,
                    bearer TEXT NOT NULL, PRIMARY KEY(sponsor, request));
            ''')
            # A restart must never silently change a published native endpoint.
            configuration = json.dumps([advertise_host, self.pin, port_start, port_end])
            old = self.db.execute("SELECT value FROM config WHERE key='endpoint'").fetchone()
            if old and old[0] != configuration:
                raise ValueError('hosting endpoint configuration changed')
            with self.db:
                self.db.execute("INSERT OR IGNORE INTO config VALUES ('endpoint', ?)", (configuration,))
            worlds = self.db.execute('SELECT * FROM worlds').fetchall()
            if len(worlds) > max_worlds:
                raise ValueError('registered worlds exceed limit')
            for row in worlds:
                self._start_world(row)
        except BaseException:
            self.close()
            raise

    def _start_world(self, row):
        if row['id'] in self.running:
            return self.running[row['id']][0]
        root = self.root/'worlds'/row['id']
        ready = self.db.execute('SELECT 1 FROM config WHERE key=?', ('world-ready:'+row['id'],)).fetchone()
        if ready and not (root/'world.sqlite3').is_file():
            raise RuntimeError('registered world database missing')
        root.parent.mkdir(mode=0o700, exist_ok=True)
        server = WorldServer(root/'transport/world.sock', root,
                             persist_generated_cave=True, archive_generated_areas=True)
        broker = None
        try:
            for member in self.db.execute('SELECT * FROM members WHERE world=?', (row['id'],)):
                server.create_identity(member['trainer'], member['token'])
            server.start()
            broker = HostBroker(server.socket_path, self.cert, self.key,
                                (self.listen_host, row['port']),
                                max_clients=server.max_connections-2, timeout=120)
            broker.start()
            with server.lock:
                server.sharing = dict(version=1, endpoint=dict(host=self.advertise_host, port=row['port']),
                                      pin=self.pin)
                server.sharing_listen = broker.address
            with self.db:
                self.db.execute('INSERT OR IGNORE INTO config VALUES (?, ?)',
                                ('world-ready:'+row['id'], '1'))
            self.running[row['id']] = (server, broker)
            return server
        except BaseException:
            if broker:
                broker.close()
            server.close()
            raise

    def _new_account(self, sponsor):
        if self.db.execute('SELECT count(*) FROM accounts').fetchone()[0] >= 1024:
            raise HostingError(503, 'capacity')
        token = secrets.token_hex(32)
        account = secrets.token_hex(16)
        self.db.execute('INSERT INTO accounts VALUES (?, ?, NULL)', (account, _secret(token)))
        if sponsor:
            self.db.execute('INSERT INTO config VALUES (?, ?)', ('account-sponsor:'+account, '1'))
        return dict(kind='host-access', version=1, token=token)

    def create_account(self):
        """Operator-only bootstrap. The resulting account can invite other owners."""
        with self.lock, self.db:
            return self._new_account(sponsor=True)

    def invite_account(self, token, request_id):
        """A bootstrap sponsor may remotely invite an independent ordinary owner."""
        with self.lock, self.db:
            account = self._account(token)
            if not self.db.execute('SELECT 1 FROM config WHERE key=?',
                                   ('account-sponsor:'+account,)).fetchone():
                raise HostingError(403, 'forbidden')
            if type(request_id) is not str or not re.fullmatch('[A-Za-z0-9_-]{1,64}', request_id):
                raise HostingError()
            row = self.db.execute('SELECT bearer FROM account_invites WHERE sponsor=? AND request=?',
                                  (account, request_id)).fetchone()
            if row:
                return dict(kind='host-access', version=1, token=row['bearer'])
            access = self._new_account(sponsor=False)
            self.db.execute('INSERT INTO account_invites VALUES (?, ?, ?)',
                            (account, request_id, access['token']))
            return access

    def enroll(self, invitation_token, account_token):
        with self.lock, self.db:
            row = self.db.execute('SELECT * FROM accounts WHERE enrollment=?',
                                  (_secret(invitation_token),)).fetchone()
            hashed = _secret(account_token)
            if row is None or (row['token'] is not None and row['token'] != hashed):
                raise HostingError(403, 'forbidden')
            try:
                self.db.execute('UPDATE accounts SET token=? WHERE id=?', (hashed, row['id']))
            except sqlite3.IntegrityError:
                raise HostingError(409, 'conflict') from None
            return dict(enrolled=True)

    def _account(self, token):
        row = self.db.execute('SELECT id FROM accounts WHERE token=?', (_secret(token),)).fetchone()
        if row is None:
            raise HostingError(403, 'forbidden')
        return row['id']

    @staticmethod
    def _public(row):
        return dict(id=row['id'], name=row['name'], trainer=row['trainer'])

    def _result(self, row, trainer):
        self._start_world(row)
        member = self.db.execute('SELECT token FROM members WHERE world=? AND trainer=?',
                                 (row['id'], trainer)).fetchone()
        invitation = validate_invitation(dict(version=1, trainer=trainer, token=member['token'],
                            endpoint=dict(host=self.advertise_host, port=row['port']), pin=self.pin))
        return dict(world=self._public(row), invitation=invitation)

    def _owned(self, token, world_id):
        account = self._account(token)
        if type(world_id) is not str:
            raise HostingError()
        row = self.db.execute('SELECT * FROM worlds WHERE id=? AND owner=?', (world_id, account)).fetchone()
        if row is None:
            raise HostingError(403, 'forbidden')
        return row

    def create_world(self, token, name, trainer, request_id):
        with self.lock:
            owner = self._account(token)
            _trainer(trainer)
            if (type(name) is not str or not 1 <= len(name.strip()) <= 80
                    or any(ord(c) < 32 for c in name)
                    or type(request_id) is not str
                    or not re.fullmatch('[A-Za-z0-9_-]{1,64}', request_id)):
                raise HostingError()
            row = self.db.execute('SELECT * FROM worlds WHERE owner=? AND request=?',
                                  (owner, request_id)).fetchone()
            if row:
                if (row['name'], row['trainer']) != (name, trainer):
                    raise HostingError(409, 'conflict')
                return self._result(row, trainer)
            used = {r[0] for r in self.db.execute('SELECT port FROM worlds')}
            if len(used) >= self.max_worlds:
                raise HostingError(503, 'capacity')
            port = next(p for p in range(self.port_start, self.port_end+1) if p not in used)
            world_id = secrets.token_hex(8)
            with self.db:
                self.db.execute('INSERT INTO worlds VALUES (?, ?, ?, ?, ?, ?)',
                                (world_id, owner, name, trainer, port, request_id))
                self.db.execute('INSERT INTO members VALUES (?, ?, ?)',
                                (world_id, trainer, secrets.token_hex(32)))
            row = self.db.execute('SELECT * FROM worlds WHERE id=?', (world_id,)).fetchone()
            return self._result(row, trainer)

    def list_worlds(self, token):
        with self.lock:
            account = self._account(token)
            return [self._public(row) for row in self.db.execute(
                'SELECT * FROM worlds WHERE owner=? ORDER BY rowid', (account,))]

    def resume(self, token, world_id):
        with self.lock:
            row = self._owned(token, world_id)
            return self._result(row, row['trainer'])

    @staticmethod
    def _adventure_result(value, world_id):
        # The consumer review needs its fixed recipe, guide and bound token, not
        # a second copy of 127x127 geometry, source plans or 100 history records.
        # Retain the existing 16 KiB HTTPS response boundary.
        fields = ('world_id', 'sequence', 'identity', 'version', 'residents',
                  'players', 'adventures', 'token', 'adventure', 'label', 'guide',
                  'prerequisites', 'validation', 'saved', 'already_installed',
                  'registered_revision')
        result = {key: value[key] for key in fields if key in value}
        # The owned hosting service, not the workshop helper, knows the exact
        # 16-hex world ID and its human label from the hosting registry.
        result['world'] = world_id
        if 'report' in value:
            result['proposed_revision'] = value['report']['revision']
        return result

    def read_adventures(self, token, world_id):
        """Owner-only built-in catalogue; never run a provider or create content."""
        with self.lock:
            server = self._start_world(self._owned(token, world_id))
            from .product_adventure import read_adventures
            with server.lock:
                return self._adventure_result(read_adventures(server), world_id)

    def preview_adventure(self, token, world_id, adventure):
        """Review a fixed built-in adventure, never arbitrary owner-supplied code."""
        from .session import SessionError
        with self.lock:
            server = self._start_world(self._owned(token, world_id))
            if type(adventure) is not str or not re.fullmatch('[a-z0-9-]{1,48}', adventure):
                raise HostingError()
            from .product_adventure import preview_adventure
            try:
                return self._adventure_result(preview_adventure(server, adventure), world_id)
            except (SessionError, ValueError):
                raise HostingError(409, 'conflict') from None

    def apply_adventure(self, token, world_id, review_token, confirmed):
        """Apply exactly one owner-reviewed built-in import through its sandbox."""
        from .session import SessionError
        with self.lock:
            server = self._start_world(self._owned(token, world_id))
            if (type(review_token) is not str or not re.fullmatch('[0-9a-f]{48}', review_token)
                    or confirmed is not True):
                raise HostingError()
            from .product_adventure import apply_adventure
            try:
                # The helper releases/rechecks its own authority lock while staging.
                # Do not hold an outer server lock across the sandbox operation.
                return self._adventure_result(apply_adventure(server, review_token, confirmed=True), world_id)
            except (SessionError, ValueError):
                raise HostingError(409, 'conflict') from None

    def generated_area_status(self, token, world_id):
        """Owner-only metadata. Never return templates, paths or provider state."""
        with self.lock:
            server = self._start_world(self._owned(token, world_id))
            with server.lock:
                kinds = {6: 'wilds', 7: 'guided_wilds', 8: 'cast_wilds',
                         9: 'event_wilds', 16: 'xl_wilds'}
                formats = {b'EWGMAP06': 'wilds', b'EWGMAP07': 'guided_wilds',
                           b'EWGMAP08': 'cast_wilds', b'EWGMAP09': 'event_wilds',
                           b'EWGMAP0A': 'xl_wilds'}
                headers = dict(server.db.execute(
                    'SELECT identity, substr(template, 1, 8) FROM generated_area_archive'))
                areas = [dict(area, kind=formats.get(headers.get(area['identity'], b''), area['kind']))
                         for area in server.list_generated_areas()]
                cave = server.shared_cave
                active = None
                if cave is not None:
                    archived = next((a for a in areas if a['identity'] == cave.identity), {})
                    occupants = sum(1 for peer in server.peers.values()
                        if not peer.get('closing') and (peer.get('in_generated_cave') or
                            (peer.get('state') is not None and
                             tuple(peer['state'][:2]) in (server.cave_map, server.wilds_map))))
                    active = dict(identity=cave.identity, kind=kinds.get(cave.version, 'cave'),
                                  side=cave.side, label=archived.get('label', 'Current generated area'),
                                  occupants=occupants)
                wilds = server.wilds_map is not None
                return dict(cave_authoring=server.cave_map is not None,
                            wilds_authoring=wilds, guided_wilds_authoring=wilds,
                            cast_wilds_authoring=wilds, xl_wilds_authoring=wilds,
                            cave_persistent=server.persist_generated_cave,
                            area_archive=server.archive_generated_areas,
                            generated_areas=areas, active_generated_area=active)

    def publish_generated_area(self, token, world_id, template, *, label):
        """Accept canonical base64 of inert SharedCave bytes, never source or paths."""
        from .shared_cave import SharedCave, MAX_SIZE
        with self.lock:
            server = self._start_world(self._owned(token, world_id))
            if type(template) is not str or len(template) > 4 * ((MAX_SIZE + 2) // 3):
                raise HostingError()
            try:
                blob = base64.b64decode(template, validate=True)
            except (ValueError, binascii.Error):
                raise HostingError() from None
            if len(blob) > MAX_SIZE or base64.b64encode(blob).decode('ascii') != template:
                raise HostingError()
            try:
                SharedCave(blob)
            except ValueError:
                raise HostingError() from None
            if (type(label) is not str or not label.strip() or len(label) > 80
                    or any(ord(c) < 32 or ord(c) == 127 for c in label)):
                raise HostingError()
            try:
                identity = server._replace_cave(blob, label=label)
            except ValueError:
                raise HostingError(409, 'conflict') from None
            return dict(identity=identity)

    def activate_generated_area(self, token, world_id, identity):
        with self.lock:
            server = self._start_world(self._owned(token, world_id))
            if type(identity) is not str or not re.fullmatch('[0-9a-f]{64}', identity):
                raise HostingError()
            try:
                return dict(identity=server.activate_generated_area(identity))
            except ValueError:
                raise HostingError(409, 'conflict') from None

    def invite(self, token, world_id, request_id):
        """Owner issues one private, single-identity bearer. Retry by request_id."""
        with self.lock, self.db:
            row = self._owned(token, world_id)
            if type(request_id) is not str or not re.fullmatch('[A-Za-z0-9_-]{1,64}', request_id):
                raise HostingError()
            invite = self.db.execute('SELECT bearer FROM invites WHERE world=? AND request=?',
                                     (world_id, request_id)).fetchone()
            if invite:
                bearer = invite['bearer']
            else:
                if self.db.execute('SELECT count(*) FROM invites WHERE world=?',
                                   (world_id,)).fetchone()[0] >= 128:
                    raise HostingError(503, 'capacity')
                bearer = secrets.token_hex(32)
                self.db.execute('INSERT INTO invites VALUES (?, ?, ?, ?, NULL)',
                                (_secret(bearer), bearer, row['id'], request_id))
            return dict(kind='world-join', version=1, token=bearer, world_id=world_id)

    def join(self, invitation_token, trainer):
        """Bind once, never return credentials for a different existing identity."""
        with self.lock:
            _trainer(trainer)
            invite = self.db.execute('SELECT * FROM invites WHERE digest=?',
                                     (_secret(invitation_token),)).fetchone()
            if invite is None:
                raise HostingError(403, 'forbidden')
            row = self.db.execute('SELECT * FROM worlds WHERE id=?', (invite['world'],)).fetchone()
            if invite['trainer'] is not None:
                if invite['trainer'] != trainer:
                    raise HostingError(409, 'conflict')
                return self._result(row, trainer)
            server = self._start_world(row)
            with server.lock:
                if (self.db.execute('SELECT 1 FROM members WHERE world=? AND trainer=?',
                                    (row['id'], trainer)).fetchone()
                        or server.db.execute('SELECT 1 FROM identities WHERE id=?', (trainer,)).fetchone()):
                    raise HostingError(409, 'conflict')
                if self.db.execute('SELECT count(*) FROM members WHERE world=?',
                                   (row['id'],)).fetchone()[0] >= 128:
                    raise HostingError(503, 'capacity')
                member_token = secrets.token_hex(32)
                with self.db:
                    self.db.execute('INSERT INTO members VALUES (?, ?, ?)', (row['id'], trainer, member_token))
                    self.db.execute('UPDATE invites SET trainer=? WHERE digest=?', (trainer, invite['digest']))
                # Registry first makes a crash recoverable with the exact same token.
                server.create_identity(trainer, member_token)
            return self._result(row, trainer)

    def close(self):
        with self.lock:
            for server, broker in self.running.values():
                broker.close()
                server.close()
            self.running.clear()
            if self.db is not None:
                self.db.close()
                self.db = None
            if not self.authority_lock.closed:
                self.authority_lock.close()


class HostingService:
    """Bounded pinned-HTTPS management listener, separate from all game ports.

    POST /v1/enroll {account_token}, enrollment bearer -> {enrolled:true}
    POST /v1/accounts/invites {request_id}, bootstrap sponsor bearer
      -> {kind:"host-access",version:1,endpoint,pin,token}, one-use enrollment
    GET /v1/worlds, account bearer -> {worlds:[{id,name,trainer}]}
    POST /v1/worlds {name,trainer,request_id}, account bearer
    POST /v1/worlds/ID/resume {}, account bearer
    POST /v1/worlds/ID/invites {request_id}, account bearer
    GET /v1/worlds/ID/generated-areas, owner bearer -> capabilities/current/archive
    POST /v1/worlds/ID/generated-areas {template,label}, owner bearer -> {identity}
      template is canonical base64 of production-validated inert SharedCave bytes.
    POST /v1/worlds/ID/generated-areas/activate {identity}, owner bearer -> {identity}
    POST /v1/join {trainer}, world-join bearer
    Create/resume/join -> {world:{id,name,trainer},invitation:<native v1>}.
    Errors are {error:<fixed code>}. No admin socket or private paths are served.
    """
    def __init__(self, manager, listen=('127.0.0.1', 8766), *, advertise=None, max_clients=16):
        from http.server import BaseHTTPRequestHandler, HTTPServer
        from socketserver import ThreadingMixIn
        if type(max_clients) is not int or not 1 <= max_clients <= 64:
            raise ValueError('invalid management client limit')
        self.manager = manager
        self.thread = None
        service = self

        class Server(ThreadingMixIn, HTTPServer):
            daemon_threads = False
            block_on_close = True
            allow_reuse_address = True
            request_queue_size = 16

            def __init__(self, address, handler):
                self.slots = threading.BoundedSemaphore(max_clients)
                super().__init__(address, handler)

            def process_request(self, request, address):
                if not self.slots.acquire(blocking=False):
                    self.shutdown_request(request)
                    return
                try:
                    super().process_request(request, address)
                except BaseException:
                    self.slots.release()
                    raise

            def process_request_thread(self, request, address):
                try:
                    super().process_request_thread(request, address)
                finally:
                    self.slots.release()

            def handle_error(self, *_):
                pass

        class Handler(BaseHTTPRequestHandler):
            server_version = 'HostedWorld'
            sys_version = ''
            timeout = 5

            def setup(self):
                self.request.settimeout(self.timeout)
                self.request.do_handshake()
                super().setup()

            def log_message(self, *_):
                pass

            def _reply(self, status, value):
                data = json.dumps(value, separators=(',', ':')).encode('utf-8')
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Connection', 'close')
                self.end_headers()
                self.wfile.write(data)
                self.close_connection = True

            def send_error(self, code, *args, **kwargs):
                self._reply(400, dict(error='invalid_request'))

            def _dispatch(self):
                try:
                    headers = self.headers
                    auth = headers.get_all('Authorization', [])
                    if len(auth) != 1 or not re.fullmatch('Bearer [0-9a-f]{64}', auth[0]):
                        raise HostingError(403, 'forbidden')
                    token = auth[0][7:]
                    lengths = headers.get_all('Content-Length', [])
                    if headers.get('Transfer-Encoding') is not None:
                        raise HostingError()
                    if self.command == 'POST':
                        from .shared_cave import MAX_SIZE
                        upload = re.fullmatch('/v1/worlds/[0-9a-f]{16}/generated-areas', self.path)
                        limit = 4 * ((MAX_SIZE + 2) // 3) + 1024 if upload else 4096
                        if (len(lengths) != 1 or not re.fullmatch('[0-9]{1,6}', lengths[0])
                                or not 2 <= int(lengths[0]) <= limit
                                or headers.get('Content-Type') != 'application/json'):
                            raise HostingError()
                        body = _json_object(self.rfile.read(int(lengths[0])))
                    else:
                        if lengths and lengths != ['0']:
                            raise HostingError()
                        body = {}
                    manager = service.manager
                    path = self.path
                    if self.command == 'GET' and path == '/v1/worlds':
                        result = dict(worlds=manager.list_worlds(token))
                    elif self.command == 'POST' and path == '/v1/enroll' and set(body) == {'account_token'}:
                        result = manager.enroll(token, body['account_token'])
                    elif self.command == 'POST' and path == '/v1/accounts/invites' and set(body) == {'request_id'}:
                        result = dict(manager.invite_account(token, body['request_id']),
                                      endpoint=service.endpoint, pin=manager.pin)
                    elif self.command == 'POST' and path == '/v1/worlds' and set(body) == {'name', 'trainer', 'request_id'}:
                        result = manager.create_world(token, body['name'], body['trainer'], body['request_id'])
                    elif self.command == 'POST' and path == '/v1/join' and set(body) == {'trainer'}:
                        result = manager.join(token, body['trainer'])
                    else:
                        adventure_match = re.fullmatch('/v1/worlds/([0-9a-f]{16})/adventure(/preview|/apply)?', path)
                        if adventure_match is not None:
                            world_id, action = adventure_match.groups()
                            if self.command == 'GET' and action is None:
                                result = manager.read_adventures(token, world_id)
                            elif self.command == 'POST' and action == '/preview' and set(body) == {'adventure'}:
                                result = manager.preview_adventure(token, world_id, body['adventure'])
                            elif self.command == 'POST' and action == '/apply' and set(body) == {'token', 'confirmed'}:
                                result = manager.apply_adventure(token, world_id, body['token'], body['confirmed'])
                            else:
                                raise HostingError()
                            self._reply(200, result)
                            return
                        area_match = re.fullmatch('/v1/worlds/([0-9a-f]{16})/generated-areas(/activate)?', path)
                        if area_match is not None:
                            world_id, activate = area_match.groups()
                            if self.command == 'GET' and not activate:
                                result = manager.generated_area_status(token, world_id)
                            elif self.command == 'POST' and not activate and set(body) == {'template', 'label'}:
                                result = manager.publish_generated_area(token, world_id, body['template'], label=body['label'])
                            elif self.command == 'POST' and activate and set(body) == {'identity'}:
                                result = manager.activate_generated_area(token, world_id, body['identity'])
                            else:
                                raise HostingError()
                            self._reply(200, result)
                            return
                        match = re.fullmatch('/v1/worlds/([0-9a-f]{16})/(resume|invites)', path)
                        if self.command != 'POST' or match is None:
                            raise HostingError()
                        world_id, action = match.groups()
                        if action == 'resume' and not body:
                            result = manager.resume(token, world_id)
                        elif action == 'invites' and set(body) == {'request_id'}:
                            result = dict(manager.invite(token, world_id, body['request_id']),
                                          endpoint=service.endpoint, pin=manager.pin)
                        else:
                            raise HostingError()
                    self._reply(200, result)
                except HostingError as exc:
                    self._reply(exc.status, dict(error=exc.code))
                except (ValueError, TypeError, RecursionError):
                    self._reply(400, dict(error='invalid_request'))
                except (OSError, RuntimeError, sqlite3.Error):
                    self._reply(503, dict(error='unavailable'))

            do_GET = do_POST = _dispatch

        self.httpd = Server(listen, Handler)
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(manager.cert, manager.key)
            self.httpd.socket = context.wrap_socket(self.httpd.socket, server_side=True,
                                                    do_handshake_on_connect=False)
            self.address = self.httpd.server_address
            host, port = advertise or (manager.advertise_host, self.address[1])
            validate_invitation_host(host)
            if type(port) is not int or not 1 <= port <= 65535:
                raise ValueError('invalid management endpoint')
            self.endpoint = dict(host=host, port=port)
        except BaseException:
            self.httpd.server_close()
            raise

    def start(self):
        if self.thread is not None:
            raise RuntimeError('already started')
        self.thread = threading.Thread(target=self.httpd.serve_forever, name='host-management', daemon=True)
        self.thread.start()
        return self

    def close(self):
        if self.thread is not None:
            self.httpd.shutdown()
            self.thread.join()
            self.thread = None
        self.httpd.server_close()


def main(argv=None):
    """Operator bootstrap and long-running management service. No secret stdout."""
    import argparse
    import signal
    import sys
    from .transport import _endpoint
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    for action in ('create-account', 'start'):
        command = actions.add_parser(action)
        command.add_argument('--root', required=True, type=Path,
                             help='explicit private persistent manager root, short enough for Unix sockets')
        command.add_argument('--cert', required=True, type=Path)
        command.add_argument('--key', required=True, type=Path)
        command.add_argument('--advertise-host', required=True)
        command.add_argument('--game-listen-host', default='127.0.0.1')
        command.add_argument('--port-start', type=int, default=9001)
        command.add_argument('--port-end', type=int, default=9016)
        command.add_argument('--max-worlds', type=int, default=16)
        command.add_argument('--management-advertise', type=_endpoint, required=True)
        if action == 'create-account':
            command.add_argument('--invitation-out', required=True, type=Path)
        else:
            command.add_argument('--listen', type=_endpoint, default=('127.0.0.1', 8766))
    args = parser.parse_args(argv)
    manager = service = None
    stopped = threading.Event()
    previous = {}
    try:
        if args.action == 'create-account' and args.invitation_out.exists():
            raise ValueError('output already exists')
        manager = HostedWorldManager(args.root, cert=args.cert, key=args.key,
                    advertise_host=args.advertise_host, listen_host=args.game_listen_host,
                    port_start=args.port_start, port_end=args.port_end, max_worlds=args.max_worlds)
        if args.action == 'create-account':
            from .hosting_client import write_private
            host, port = args.management_advertise
            validate_invitation_host(host)
            write_private(args.invitation_out, dict(manager.create_account(),
                          endpoint=dict(host=host, port=port), pin=manager.pin))
            return 0
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous[signum] = signal.signal(signum, lambda *_: stopped.set())
        service = HostingService(manager, args.listen, advertise=args.management_advertise).start()
        while not stopped.wait(.2):
            with manager.lock:
                if (not service.thread.is_alive()
                        or any(not server.thread.is_alive() or not broker._thread.is_alive()
                               for server, broker in manager.running.values())):
                    raise RuntimeError('authority stopped')
        return 0
    except (HostingError, OSError, ValueError, RuntimeError, sqlite3.Error):
        print('hosting: configuration, state or listener failure', file=sys.stderr)
        return 1
    finally:
        if service is not None:
            service.close()
        if manager is not None:
            manager.close()
        for signum, handler in previous.items():
            signal.signal(signum, handler)


if __name__ == '__main__':
    raise SystemExit(main())
