"""Small blocking client helpers for the local world sockets."""
import json
from pathlib import Path
import socket


def installed_content_id():
    """Read the manifest packaged beside this library, never the world directory."""
    import re
    value = json.loads(Path(__file__).with_name('content_compat.json').read_text('ascii'))
    if (type(value) is not dict or set(value) != {'schema', 'content_id'}
            or type(value['schema']) is not int or value['schema'] != 1
            or not isinstance(value['content_id'], str)
            or not re.fullmatch(r'[0-9a-f]{64}', value['content_id'])):
        raise ValueError('invalid installed content manifest')
    return value['content_id']


def admin_request(socket_path, request, timeout=5, admin_path=None):
    if admin_path is None:
        path = Path(socket_path)
        admin_path = (path.parent.parent / 'admin.sock' if path.parent.name == 'transport'
                      else str(socket_path) + '.admin')
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(str(admin_path))
        sock.sendall(json.dumps(request, allow_nan=False).encode() + b'\n')
        with sock.makefile('rb') as stream:
            raw = stream.readline(65537)
            if not raw.endswith(b'\n') or len(raw) > 65536:
                raise ValueError('invalid admin response')
            return json.loads(raw)


_INSTALLED_CONTENT = object()


class WorldClient:
    """A single authenticated session. Each snapshot replaces the previous one.

    content_id=None explicitly emulates a legacy native client without DATA.
    """
    def __init__(self, socket_path, trainer_id, token, timeout=5, *, control=False, social=False,
                 rules=None, content_id=_INSTALLED_CONTENT):
        from .server import ID, HEX
        if not ID.fullmatch(trainer_id) or not HEX.fullmatch(token):
            raise ValueError('invalid credentials')
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        self.stream = None
        self.control = control
        self.social = social
        self.trainer_id = trainer_id
        self.rules = rules
        try:
            self.sock.connect(str(socket_path))
            self.stream = self.sock.makefile('rb')
            suffix = ' CONTROL' if control else (' SOCIAL' if social else '')
            if rules is not None and not control:
                from .rules import wire
                suffix += ' RULES ' + wire(rules)
            if not control:
                import re
                if content_id is _INSTALLED_CONTENT:
                    content_id = installed_content_id()
                if content_id is not None:
                    if not isinstance(content_id, str) or not re.fullmatch(r'[0-9a-f]{64}', content_id):
                        raise ValueError('invalid content ID')
                    suffix += ' DATA ' + content_id
            self.sock.sendall(f'HELLO 1 {trainer_id} {token}{suffix}\n'.encode('ascii'))
            welcome = self._line().split()
            if (len(welcome) != (5 if control else 4) or welcome[:3] != ['WELCOME', '1', trainer_id]
                    or (control and welcome[4] != 'CONTROL')):
                raise ValueError('invalid welcome')
            self.revision = int(welcome[3])
        except BaseException:
            self.close()
            raise

    def _line(self):
        limit = 16384 if self.control else 1024
        raw = self.stream.readline(limit+2)
        if not raw.endswith(b'\n') or len(raw) > limit+1:
            raise ValueError('truncated or oversized server line')
        text = raw.decode('ascii').rstrip('\n')
        if text.startswith('ERROR '):
            raise ValueError(text)
        return text

    def send_state(self, seq, group, num, x, y, facing, gfx, ready, party_hash, bag_hash):
        from .server import bounded, HASH
        values = (seq, group, num, x, y, facing, gfx, ready)
        for value, limit in zip(values, (2**63-1, 255, 255, 32767, 32767, 4, 65535, 1)):
            if type(value) is not int:
                raise ValueError('state values must be integers')
            bounded(str(value), 0, limit)
        if not HASH.fullmatch(party_hash) or not HASH.fullmatch(bag_hash):
            raise ValueError('invalid ownership hashes')
        self.sock.sendall(('STATE ' + ' '.join(map(str, values)) + ' ' + party_hash + ' ' + bag_hash + '\n').encode('ascii'))

    def interact(self, seq, object_id):
        """Use the shared STATE sequence, with an adjacent ready facing position."""
        from .server import ID, bounded
        if type(seq) is not int or type(object_id) is not str or not ID.fullmatch(object_id):
            raise ValueError('invalid interaction')
        bounded(str(seq), 0, 2**63-1)
        self.sock.sendall(f'INTERACT {seq} {object_id}\n'.encode('ascii'))

    def meet(self, seq, trainer_id):
        """Signal 'explore together' to a ready adjacent trainer. SOCIAL only."""
        from .server import ID, bounded
        if not self.social or type(seq) is not int or type(trainer_id) is not str or not ID.fullmatch(trainer_id):
            raise ValueError('invalid trainer interaction')
        bounded(str(seq), 0, 2**63-1)
        self.sock.sendall(f'MEET {seq} {trainer_id}\n'.encode('ascii'))

    def snapshot(self):
        begin = self._line().split()
        if len(begin) != 2 or begin[0] != 'BEGIN':
            raise ValueError('missing BEGIN')
        peers, tiles, objects = {}, [], []
        meeting = None
        total = 0
        while True:
            text = self._line()
            total += len(text) + 1
            if total > 65536:
                raise ValueError('snapshot too large')
            if text == 'END':
                break
            fields = text.split()
            if fields and fields[0] == 'PEER' and len(fields) == 9 and len(peers) < 8:
                peers[fields[1]] = dict(zip(('group','num','x','y','facing','gfx','ready'), map(int, fields[2:])))
            elif fields and fields[0] == 'TILE' and len(fields) == 7 and len(tiles) < 128:
                tiles.append(list(map(int, fields[1:])))
            elif fields and fields[0] == 'OBJECT' and len(fields) == 8 and len(objects) < 8:
                obj = dict(zip(('group','num','x','y','gfx'), map(int, fields[2:7])))
                obj.update(id=fields[1], text=bytes.fromhex(fields[7]).decode('ascii'))
                objects.append(obj)
                from .mechanics import validate_objects
                validate_objects(objects)
            elif fields and fields[0] == 'MEET' and len(fields) == 9 and self.social and meeting is None:
                from .server import ID, bounded
                if (not ID.fullmatch(fields[2]) or not ID.fullmatch(fields[3]) or fields[2] == fields[3]
                        or self.trainer_id not in fields[2:4] or fields[8] != 'explore'):
                    raise ValueError('invalid meeting')
                values = [bounded(v,0,limit) for v,limit in zip(
                    [fields[1]]+fields[4:8], (2**63-1,255,255,32767,32767))]
                from .build_catalog import validate_coords
                validate_coords(*values[1:])
                if values[0] > int(begin[1]):
                    raise ValueError('future meeting')
                meeting = dict(zip(('seq','group','num','x','y'),values), player=fields[2],target=fields[3],signal='explore')
            else:
                raise ValueError('invalid snapshot entry')
        self.revision = int(begin[1])
        result = dict(revision=self.revision, peers=peers, tiles=tiles, objects=objects)
        if self.social:
            result['meeting'] = meeting
        return result

    def close(self):
        if self.stream is not None:
            self.stream.close()
        self.sock.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class IntentClient(WorldClient):
    """An authenticated role that never occupies or evicts native presence.

    Connect through the same local socket/TLS broker as the native client.
    The host must explicitly enable its GM worker to process queued requests.
    """
    def __init__(self, socket_path, trainer_id, token, timeout=5):
        super().__init__(socket_path, trainer_id, token, timeout, control=True)

    def _request(self, request):
        wire = json.dumps(request, allow_nan=False, ensure_ascii=True, separators=(',', ':')).encode('ascii')
        if len(wire) > 16384:
            raise ValueError('control request too large')
        self.sock.sendall(wire+b'\n')
        result = json.loads(self._line())
        if type(result) is not dict or type(result.get('ok')) is not bool:
            raise ValueError('invalid control response')
        return result

    def submit_intent(self, text, request_id=None):
        import uuid
        return self._request(dict(command='intent', text=text,
                                  request_id=uuid.uuid4().hex if request_id is None else request_id))

    def intent_status(self, identifier):
        return self._request(dict(command='intent_status', id=identifier))
