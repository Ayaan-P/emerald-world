"""Opt-in, persistent grass succession driven by accepted player footsteps.

No wall-clock growth or client-provided ecology commands. Rest is measured in
steps elsewhere in the same area, so empty worlds do not change on their own.
"""
import copy
import hashlib
import json
import re
import sqlite3
import time


class Habitats:
    def __init__(self, server):
        self.server = server
        self.db = server.db
        self.db.execute('CREATE TABLE IF NOT EXISTS habitats (identity TEXT PRIMARY KEY, data TEXT NOT NULL)')
        self.db.commit()
        self.records = {identity: json.loads(data) for identity, data in
                        self.db.execute('SELECT identity,data FROM habitats')}
        self.errors = {}
        self.next_poll = 0

    def _save(self, identity, record):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO habitats VALUES (?,?)',
                            (identity, json.dumps(record, sort_keys=True)))
        self.records[identity] = record

    def request(self, request):
        identity = request.get('identity')
        if type(identity) is not str or not re.fullmatch(r'[0-9a-f]{64}', identity):
            raise ValueError('invalid habitat identity')
        action = request.get('action')
        basic = {'command', 'identity', 'action'}
        with self.server.lock:
            if action == 'status' and set(request) == basic:
                return self.status(identity)
            if action == 'disable' and set(request) == basic:
                with self.db:
                    self.db.execute('DELETE FROM habitats WHERE identity=?', (identity,))
                self.records.pop(identity, None)
                self.errors.pop(identity, None)
                return dict(ok=True, identity=identity, enabled=False, terrain_preserved=True)
            if action != 'configure' or set(request) != basic | {'tiles', 'wear_steps', 'rest_steps'}:
                raise ValueError('invalid habitat request')
            wear, rest, tiles = request['wear_steps'], request['rest_steps'], request['tiles']
            if type(wear) is not int or not 2 <= wear <= 100 or type(rest) is not int or not wear <= rest <= 10000:
                raise ValueError('wear_steps must be 2..100 and rest_steps must be wear_steps..10000')
            if type(tiles) is not list or not 1 <= len(tiles) <= 64:
                raise ValueError('a habitat needs 1..64 tiles')
            seen = set()
            for tile in tiles:
                if type(tile) is not dict or set(tile) != {'x', 'y'} or any(type(tile[k]) is not int or not 0 < tile[k] < 62 for k in ('x', 'y')):
                    raise ValueError('invalid habitat tile')
                point = (tile['x'], tile['y'])
                if point in seen:
                    raise ValueError('duplicate habitat tile')
                seen.add(point)
            # Reuse terrain validation without publishing or changing the map.
            server = self.server
            server.inspect_shared_terrain(identity)
            from .shared_terrain import validate, encode
            cave = server.shared_cave
            stored = self.db.execute('SELECT template FROM generated_cave WHERE singleton=1').fetchone()
            if stored is None or hashlib.sha256(stored[0]).hexdigest() != identity:
                raise ValueError('publish the active event area before configuring habitat')
            overlay = validate(cave, server._active_terrain()[1])
            if any(not server._active_walkable(*point) for point in seen):
                raise ValueError('habitat tile is not currently walkable')
            overlay.update({point: 1 for point in seen})
            encode(cave, overlay)
            old = self.records.get(identity)
            if old and old['wear_steps'] == wear and old['rest_steps'] == rest and {(c['x'], c['y']) for c in old['cells']} == seen:
                return self.status(identity)
            record = dict(wear_steps=wear, rest_steps=rest, steps=0, pending=True,
                          cells=[dict(x=x, y=y, wear=0, rest=0, tall=True) for x, y in sorted(seen)])
            self._save(identity, record)
            self.flush(force=True)
            return self.status(identity)

    def status(self, identity):
        record = self.records.get(identity)
        return dict(ok=True, identity=identity, enabled=record is not None,
                    habitat=copy.deepcopy(record), error=self.errors.get(identity),
                    growth_clock='accepted adjacent ready steps in this area',
                    delivery=('disabled' if record is None else 'pending' if record['pending'] else
                              'terrain committed; client application requires TERRAINACK'))

    def observe(self, conn, previous, state):
        server = self.server
        cave = server.shared_cave
        identity = cave.identity if cave else None
        record = self.records.get(identity)
        if (record is None or conn.get('cave_ack') != identity or not previous
                or tuple(state[:2]) != server.wilds_map or previous[:2] != state[:2]
                or not previous[6] or not state[6]
                or abs(previous[2] - state[2]) + abs(previous[3] - state[3]) != 1):
            return
        updated = copy.deepcopy(record)
        updated['steps'] += 1
        for cell in updated['cells']:
            before = cell['tall']
            if (cell['x'], cell['y']) == tuple(state[2:4]):
                cell['wear'] = min(updated['wear_steps'], cell['wear'] + 1)
                cell['rest'] = 0
                if cell['wear'] == updated['wear_steps']:
                    cell['tall'] = False
            else:
                cell['rest'] = min(updated['rest_steps'], cell['rest'] + 1)
                if cell['rest'] == updated['rest_steps']:
                    cell['wear'] = 0
                    cell['tall'] = True
            updated['pending'] |= before != cell['tall']
        try:
            self._save(identity, updated)
        except sqlite3.Error:
            # Ecology storage failures must not reject an otherwise valid move.
            self.errors[identity] = 'habitat progress could not be persisted'

    def flush(self, force=False):
        now = time.monotonic()
        if not force and now < self.next_poll:
            return
        self.next_poll = now + 1
        cave = self.server.shared_cave
        identity = cave.identity if cave else None
        record = self.records.get(identity)
        if record is None or not record['pending']:
            return
        try:
            result = self.server.set_shared_terrain(identity, [dict(x=c['x'], y=c['y'], terrain='tall_grass' if c['tall'] else 'grass') for c in record['cells']])
            updated = copy.deepcopy(record)
            updated['pending'] = False
            updated['terrain_revision'] = result['revision']
            self._save(identity, updated)
            self.errors.pop(identity, None)
        except (ValueError, sqlite3.Error) as exc:
            # Durable desired state remains pending; replay is idempotent after
            # a crash between terrain commit and this acknowledgement.
            self.errors[identity] = str(exc)
