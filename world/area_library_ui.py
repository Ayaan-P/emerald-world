"""Read-only, bounded views of the selected local owner's generated archive."""
import hashlib
import re
import sqlite3

from .session import SessionError
from .shared_cave import MAX_SIZE, SharedCave
from .species_cohort import catalogue

KINDS = {6: 'wilds', 7: 'guided_wilds', 8: 'cast_wilds', 9: 'event_wilds', 16: 'xl_wilds', 17: 'painted_xl_wilds'}


def inspect_area(session, worlds, payload):
    if (type(payload) is not dict or set(payload) != {'world', 'identity'}
            or type(payload['world']) is not str or type(payload['identity']) is not str
            or not re.fullmatch(r'[0-9a-f]{64}', payload['identity'])):
        raise SessionError('Choose a saved area from this local world.')
    world, identity = payload['world'], payload['identity']
    server = session.server
    if (world not in {item['key'] for item in worlds} or session.state is None
            or session.state.name != world or server is None or getattr(server, '_closed', True)
            or not getattr(server, 'archive_generated_areas', False)):
        raise SessionError('Open the local world that owns this area before previewing it.')
    try:
        with server.lock:
            if server._closed or not server.archive_generated_areas:
                raise ValueError('host closed')
            # Bound the database read before materializing a potentially corrupt
            # template or label. Never return dialogue, event graphs or raw blobs.
            row = server.db.execute(
                "SELECT label,template FROM generated_area_archive "
                "WHERE identity=? AND typeof(label)='text' AND length(CAST(label AS BLOB))<=320 "
                "AND typeof(template)='blob' AND length(template)<=?",
                (identity, MAX_SIZE)).fetchone()
            if row is None or type(row[0]) is not str or not 1 <= len(row[0]) <= 80:
                raise ValueError('invalid archive entry')
            label, blob = row
            if not label.strip() or any(ord(char) < 32 or ord(char) == 127 for char in label):
                raise ValueError('invalid area label')
            if type(blob) is not bytes or hashlib.sha256(blob).hexdigest() != identity:
                raise ValueError('archive identity mismatch')
            cave = SharedCave(blob)
        characters = []
        if cave.guide is not None:
            characters.append(dict(number=1, x=2, y=1, role='Guide'))
        elif cave.cast is not None:
            for index in range(cave.cast[0]):
                start = 1 + index * 61
                characters.append(dict(number=index + 1, x=cave.cast[start + 1], y=cave.cast[start + 2], role='Character'))
        wildlife = []
        if cave.wildlife is not None:
            names = {value: name.replace('_', ' ').title() for name, value in catalogue(cave.cohort).items()}
            levels = {}
            for index in range(12):
                start = 1 + index * 3
                species = int.from_bytes(cave.wildlife[start:start + 2], 'little')
                levels.setdefault(species, set()).add(cave.wildlife[start + 2])
            wildlife = [dict(species=species, name=names[species], levels=sorted(values)) for species, values in levels.items()]
        return dict(world=world, identity=identity, label=label, kind=KINDS.get(cave.version, 'cave'),
                    side=cave.side, rows=[row.decode('ascii') for row in cave._rows],
                    entrance=[1, 1], exit=[cave.side - 2, cave.side - 2], characters=characters,
                    wildlife=wildlife, wildlife_cohort=cave.cohort if wildlife else None,
                    floor_tiles=sum(row.count(b'.') for row in cave._rows),
                    interactive=cave.events is not None, layout='saved_base')
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
        raise SessionError('This saved area could not be previewed. Its stored layout or catalogue is unavailable. Nothing was changed.') from None
