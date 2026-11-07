"""Session-only shared spawn identity and reservation authority.

This protocol prepares shared field encounters. A lease does not authorize a
battle, a catch, rewards or save writes. Native encounter admission must consume
it through the existing battle authority before those actions can be enabled.
"""
import hashlib
import json
from pathlib import Path
import re
import secrets

from .build_catalog import validate_coords

HEX = re.compile(r'[0-9a-f]{32}')
MAX_SPAWNS = 8
FRESH_SECONDS = 2.0
LEASE_SECONDS = 15.0


def catalogue():
    data = json.loads(Path(__file__).with_name('expansion_species.json').read_text())
    if data.get('cohort') != 'expansion-native':
        raise ValueError('Expansion species catalogue required')
    species = data['species']
    if type(species) is not dict or not species or any(type(v) is not int or not 1 <= v <= 65535 for v in species.values()):
        raise ValueError('invalid Expansion species catalogue')
    digest = hashlib.sha256(json.dumps(species, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return set(species.values()), digest


class SharedWildlife:
    def __init__(self):
        self.epoch = secrets.token_hex(16)
        self.revision = 0
        self.spawns = []
        self.claims = {}  # Spawn ID -> exact presence connection and lease ID.

    def replace(self, epoch, revision, rows, excluded_maps, occupied):
        if epoch != self.epoch or type(revision) is not int or revision != self.revision:
            raise ValueError('wildlife changed; reload before publishing')
        if self.claims:
            raise ValueError('wildlife has outstanding reservations')
        if type(rows) is not list or len(rows) > MAX_SPAWNS:
            raise ValueError('wildlife requires at most eight spawns')
        enabled, _ = catalogue()
        positions, result = set(), []
        for row in rows:
            if type(row) is not dict or set(row) != {'group', 'num', 'x', 'y', 'species', 'level'}:
                raise ValueError('invalid wildlife fields')
            if any(type(v) is not int for v in row.values()):
                raise ValueError('wildlife fields must be integers')
            position = tuple(row[k] for k in ('group', 'num', 'x', 'y'))
            validate_coords(*position)
            if position[:2] in excluded_maps or position in positions or position in occupied:
                raise ValueError('wildlife position unavailable')
            if row['species'] not in enabled or not 1 <= row['level'] <= 100:
                raise ValueError('invalid wildlife species or level')
            positions.add(position)
            result.append(dict(row, id=secrets.token_hex(16)))
        self.spawns = result
        self.revision += 1
        return self.view(None)

    def drop(self, conn):
        removed = [key for key, value in self.claims.items() if value[0] is conn]
        for key in removed:
            del self.claims[key]
        if removed:
            self.revision += 1
        return bool(removed)

    def expire(self, now):
        removed = [key for key, value in self.claims.items() if now >= value[2]]
        for key in removed:
            del self.claims[key]
        if removed:
            self.revision += 1
        return bool(removed)

    def claim(self, conn, epoch, spawn_id, now):
        self.expire(now)
        if epoch != self.epoch or not HEX.fullmatch(spawn_id):
            return False
        spawn = next((s for s in self.spawns if s['id'] == spawn_id), None)
        existing = self.claims.get(spawn_id)
        if existing:
            return existing[0] is conn
        if any(value[0] is conn for value in self.claims.values()):
            return False
        state, stamp = conn.get('state'), conn.get('state_time')
        if (spawn is None or state is None or stamp is None or not 0 <= now - stamp <= FRESH_SECONDS
                or not state[6] or tuple(state[:2]) != (spawn['group'], spawn['num'])):
            return False
        delta = {1: (0, 1), 2: (0, -1), 3: (-1, 0), 4: (1, 0)}.get(state[4])
        if delta is None or (state[2] + delta[0], state[3] + delta[1]) != (spawn['x'], spawn['y']):
            return False
        self.claims[spawn_id] = (conn, secrets.token_hex(16), now + LEASE_SECONDS)
        self.revision += 1
        return True

    def release(self, conn, epoch, spawn_id, lease):
        held = self.claims.get(spawn_id)
        if epoch != self.epoch or not held or held[0] is not conn or held[1] != lease:
            return False
        del self.claims[spawn_id]
        self.revision += 1
        return True

    def view(self, conn):
        state = conn.get('state') if conn is not None else None
        rows = [dict(row, status='reserved' if row['id'] in self.claims else 'available')
                for row in self.spawns if conn is None or (state and tuple(state[:2]) == (row['group'], row['num']))]
        lease = next((dict(id=key, lease=value[1]) for key, value in self.claims.items() if value[0] is conn), None)
        return dict(epoch=self.epoch, revision=self.revision, spawns=rows, lease=lease)

    def lines(self, conn):
        view = self.view(conn)
        lines = [f"WILDLIFE {self.epoch} {self.revision} {len(view['spawns'])}"]
        for row in view['spawns']:
            lines.append('WILDMON ' + row['id'] + ' ' + ' '.join(str(row[k]) for k in
                         ('group', 'num', 'x', 'y', 'species', 'level', 'status')))
        if view['lease']:
            lines.append('WILDLEASE ' + view['lease']['id'] + ' ' + view['lease']['lease'])
        return lines


def parse_snapshot(header, rows, lease):
    if (len(header) != 4 or not HEX.fullmatch(header[1]) or not header[2].isdigit()
            or not header[3].isdigit() or int(header[2]) > 2**63 - 1
            or int(header[3]) != len(rows) or len(rows) > MAX_SPAWNS):
        raise ValueError('invalid wildlife snapshot')
    parsed, seen, positions = [], set(), set()
    enabled, _ = catalogue()
    for fields in rows:
        if len(fields) != 9 or not HEX.fullmatch(fields[1]) or fields[1] in seen:
            raise ValueError('invalid wildlife spawn')
        if any(not v.isdigit() for v in fields[2:8]):
            raise ValueError('invalid wildlife numbers')
        values = list(map(int, fields[2:8])); position = tuple(values[:4])
        validate_coords(*position)
        if position in positions or values[4] not in enabled or not 1 <= values[5] <= 100 or fields[8] not in ('available', 'reserved'):
            raise ValueError('invalid wildlife content')
        parsed.append(dict(zip(('group', 'num', 'x', 'y', 'species', 'level'), values), id=fields[1], status=fields[8]))
        seen.add(fields[1]); positions.add(position)
    result = dict(epoch=header[1], revision=int(header[2]), spawns=parsed, lease=None)
    if lease:
        if (len(lease) != 3 or not HEX.fullmatch(lease[1]) or not HEX.fullmatch(lease[2])):
            raise ValueError('invalid wildlife lease')
        # The owner can have moved to another map; its held spawn need not be visible.
        result['lease'] = dict(id=lease[1], lease=lease[2])
    return result
