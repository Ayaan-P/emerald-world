"""Reviewed local-owner UI for the existing durable geometry authority."""
import hashlib
import re
import sqlite3

from .session import SessionError
from .shared_terrain import encode, validate
from .shared_cave import EVENT_SIZE


def _scope(session, worlds, payload, fields):
    if (type(payload) is not dict or set(payload) != fields
            or type(payload.get('world')) is not str or type(payload.get('identity')) is not str
            or not re.fullmatch('[0-9a-f]{64}', payload['identity'])):
        raise SessionError('Choose an active interactive area from this local world.')
    server = session.server
    if (payload['world'] not in {item['key'] for item in worlds} or session.state is None
            or session.state.name != payload['world'] or server is None
            or getattr(server, '_closed', True)):
        raise SessionError('Reopen the local world before editing terrain.')
    return server


def _read(server, payload):
    cave = server.shared_cave
    if (server._closed or not server.archive_generated_areas or not server.persist_generated_cave
            or cave is None or cave.version != 9 or cave.identity != payload['identity']):
        raise SessionError('Terrain editing requires the active, saved 63 × 63 interactive area.')
    stored = server.db.execute('SELECT template FROM generated_cave WHERE singleton=1 AND length(template)<=?', (EVENT_SIZE,)).fetchone()
    if stored is None or type(stored[0]) is not bytes or hashlib.sha256(stored[0]).hexdigest() != cave.identity:
        raise SessionError('The active area is not saved. Reopen it before editing.')
    row = server.db.execute('SELECT revision,length(payload) FROM generated_area_terrain WHERE identity=?', (cave.identity,)).fetchone()
    if row is not None and (type(row[0]) is not int or not 1 <= row[0] <= 2147483647 or type(row[1]) is not int or not 1 <= row[1] <= 1539):
        raise ValueError('invalid stored terrain')
    revision, raw = server._active_terrain()
    tiles = validate(cave, raw)
    return dict(world=payload['world'], identity=cave.identity, revision=revision,
                rows=[row.decode('ascii') for row in cave._rows],
                characters=[dict(x=cave.cast[2 + i * 61], y=cave.cast[3 + i * 61]) for i in range(cave.cast[0])],
                tiles=[dict(x=x, y=y, terrain=('grass', 'tall_grass', 'water')[kind]) for (x, y), kind in sorted(tiles.items())],
                players=sum(not peer.get('closing') for peer in server.peers.values()))


def _draft(server, payload, current):
    if type(payload['expected_revision']) is not int or payload['expected_revision'] != current['revision']:
        raise SessionError('Terrain changed. Reload before reviewing a new draft.')
    tiles = payload['tiles']
    if type(tiles) is not list or len(tiles) > 512:
        raise SessionError('Use at most 512 terrain overrides.')
    values = {}
    for tile in tiles:
        if (type(tile) is not dict or set(tile) != {'x', 'y', 'terrain'}
                or type(tile['x']) is not int or type(tile['y']) is not int
                or not 0 <= tile['x'] < 63 or not 0 <= tile['y'] < 63
                or type(tile['terrain']) is not str or tile['terrain'] not in ('grass', 'tall_grass', 'water')
                or (tile['x'], tile['y']) in values):
            raise SessionError('Choose valid, distinct terrain cells.')
        values[(tile['x'], tile['y'])] = ('grass', 'tall_grass', 'water').index(tile['terrain'])
    try:
        encode(server.shared_cave, values)
    except ValueError:
        raise SessionError('Keep all land connected and every character reachable. Entrance, exit, characters and map edges are protected.') from None
    return [dict(x=x, y=y, terrain=('grass', 'tall_grass', 'water')[kind]) for (x, y), kind in sorted(values.items())]


def terrain_action(session, worlds, action, payload):
    fields = {'world', 'identity'}
    if action in ('terrain_review', 'terrain_apply'):
        fields |= {'expected_revision', 'tiles'}
    if action == 'terrain_apply':
        fields.add('confirmed')
        if type(payload) is not dict or payload.get('confirmed') is not True:
            raise SessionError('Review the terrain changes before applying them.')
    if action not in ('terrain_read', 'terrain_review', 'terrain_apply'):
        raise SessionError('Unknown terrain action.')
    server = _scope(session, worlds, payload, fields)
    try:
        # The same reentrant lock protects admin changes, admission and the
        # compare-and-apply operation. Never check a revision outside this lock.
        with server.lock:
            current = _read(server, payload)
            if action == 'terrain_read':
                return current
            tiles = _draft(server, payload, current)
            if action == 'terrain_review':
                return dict(current, proposed_tiles=tiles)
            # Geometry's CLI permits an empty area. This UI deliberately requires
            # no connected players, so a reviewed edit cannot race an entry offer.
            if current['players']:
                raise SessionError('Save and close all connected games before applying terrain. No one is disconnected automatically.')
            result = server.set_shared_geometry(payload['identity'], tiles, replace=True)
            if not result.get('ok'):
                raise SessionError('The terrain save was not confirmed. Reload before trying again.')
            return dict(_read(server, payload), saved=True, changed=result['changed'])
    except SessionError:
        raise
    except (ValueError, TypeError, KeyError, OSError, sqlite3.Error):
        raise SessionError('Terrain could not be read or the save confirmed. Reload before trying again.') from None
