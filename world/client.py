"""Small blocking client helpers for the local world sockets."""
import json
from pathlib import Path
import socket
import time


def admin_request(socket_path, request, timeout=5, admin_path=None):
    if admin_path is None:
        path = Path(socket_path)
        admin_path = (path.parent.parent / 'admin.sock' if path.parent.name == 'transport'
                      else str(socket_path) + '.admin')
    deadline=time.monotonic()+timeout
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(str(admin_path))
        with sock.makefile('rb') as stream:
            def exchange(value):
                remaining=deadline-time.monotonic()
                if remaining<=0:raise TimeoutError('admin response timeout')
                sock.settimeout(remaining)
                sock.sendall(json.dumps(value,allow_nan=False).encode()+b'\n')
                raw=stream.readline(65537)
                if not raw.endswith(b'\n') or len(raw)>65536:raise ValueError('invalid admin response')
                return json.loads(raw)
            from .inspection_transfer import request as transfer_request
            return transfer_request(request,exchange)



class WorldClient:
    """A single authenticated session. Each snapshot replaces the previous one."""
    def __init__(self, socket_path, trainer_id, token, timeout=5, *, control=False, social=False, regions=False):
        from .server import ID, HEX
        if not ID.fullmatch(trainer_id) or not HEX.fullmatch(token):
            raise ValueError('invalid credentials')
        if regions and control:
            raise ValueError('regions require a presence connection')
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        self.stream = None
        self.control = control
        self.regions = regions
        self.social = social or regions
        self.trainer_id = trainer_id
        try:
            self.sock.connect(str(socket_path))
            self.stream = self.sock.makefile('rb')
            suffix = ' SOCIALCAVEREGION1' if regions else ' CONTROL' if control else (' SOCIAL' if social else '')
            self.sock.sendall(f'HELLO 1 {trainer_id} {token}{suffix}\n'.encode('ascii'))
            welcome = self._line().split()
            if (len(welcome) != (5 if control else 4) or welcome[:3] != ['WELCOME', '1', trainer_id]
                    or (control and welcome[4] != 'CONTROL')):
                raise ValueError('invalid welcome')
            self.revision = int(welcome[3])
            if regions and self._line() != 'REGION READY 1':
                raise ValueError('region capability unavailable')
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

    def snapshot(self, *, _begin=None):
        begin = (_begin if _begin is not None else self._line()).split()
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


class RegionClient(WorldClient):
    """Experimental protocol client, not a native warp or simulated movement."""
    def __init__(self, socket_path, trainer_id, token, timeout=5):
        super().__init__(socket_path,trainer_id,token,timeout,regions=True)
        self.last_snapshot=None

    def _region_response(self):
        for _ in range(64):
            line=self._line()
            if line.startswith('BEGIN '):
                self.last_snapshot=self.snapshot(_begin=line)
            else:
                return line
        raise ValueError('too many snapshots while waiting for region response')

    def select_region(self, place_id):
        import re
        from .shared_cave import SharedCave
        if type(place_id) is not str or not re.fullmatch(r'area:[0-9a-f-]{36}',place_id):
            raise ValueError('invalid place identity')
        self.sock.sendall(('REGION SELECT '+place_id+'\n').encode('ascii'))
        response=self._region_response().split()
        if len(response)!=4 or response[:3]!=['REGION','SELECTED',place_id]:
            raise ValueError('region selection refused')
        revision=response[3]
        if not re.fullmatch('[0-9a-f]{64}',revision):
            raise ValueError('invalid region revision')
        self.sock.sendall(b'CAVE GET\n')
        if self._region_response()!='CAVE BEGIN '+revision:
            raise ValueError('region template unavailable')
        rows=[]
        for index in range(31):
            row=self._line().split()
            if len(row)!=5 or row[:4]!=['CAVE','ROW',revision,str(index)]:
                raise ValueError('invalid region row')
            rows.append(row[4])
        if self._line()!='CAVE END '+revision:
            raise ValueError('invalid region end')
        blob=b'EWGMAP01'+''.join(rows).encode('ascii')
        cave=SharedCave(blob)
        if cave.identity!=revision:
            raise ValueError('region template digest mismatch')
        self.sock.sendall(('CAVE ACK '+revision+'\n').encode('ascii'))
        if self._region_response()!='CAVE OK '+revision:
            raise ValueError('region admission rejected')
        return dict(place_id=place_id,revision=revision,template=blob)


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
