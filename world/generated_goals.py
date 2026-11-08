"""Stable-place/exact-revision goals over authenticated generated-map presence."""
import hashlib
import re
import time


def resolve_place(server, place_id, revision):
    from .guilds import GuildError
    from .shared_cave import SharedCave
    if (type(place_id) is not str or not re.fullmatch(r'area:[0-9a-f-]{36}',place_id)
            or type(revision) is not str or not re.fullmatch('[0-9a-f]{64}',revision)
            or not server.archive_generated_areas):
        raise GuildError('Generated expedition destination is unavailable.')
    row=server.db.execute('''SELECT a.template,a.label,r.place_id FROM generated_area_archive a
        JOIN world_places p ON p.revision=a.identity
        LEFT JOIN world_region_revisions r ON r.revision=a.identity
        WHERE p.place_id=? AND a.identity=?''',(place_id,revision)).fetchone()
    if row is None or hashlib.sha256(row[0]).hexdigest()!=revision:
        raise GuildError('Generated expedition destination is unavailable.')
    cave=SharedCave(row[0])
    if cave.version!=16 and not (cave.version==1 and row[2]==place_id):
        raise GuildError('This generated destination does not support expeditions.')
    label=''.join(c if c.isascii() and (c.isalnum() or c in " .,'!?-") else ' ' for c in (row[1] or 'Generated destination')).strip()[:40] or 'Generated destination'
    return dict(place_id=place_id,revision=revision,label=label)


def observed_place(server,conn,freshness=5):
    """No client-chosen place IDs: derive scope from the admitted template."""
    from .guilds import GuildError
    state=conn.get('state');stamp=conn.get('state_time')
    if (server.peers.get(conn.get('id')) is not conn or conn.get('closing') or not state or not state[6]
            or stamp is None or not 0<=time.monotonic()-stamp<=freshness):return None
    cave=server._connection_cave(conn)
    if cave is None or conn.get('cave_ack')!=cave.identity:return None
    expected=server.wilds_map if cave.version==16 else server.cave_map if cave.version==1 and conn.get('region_cave') else None
    if expected is None or tuple(state[:2])!=expected or not cave.walkable(state[2],state[3]):return None
    row=server.db.execute('SELECT place_id FROM world_places WHERE revision=?',(cave.identity,)).fetchone()
    if row is None:return None
    try:return resolve_place(server,row[0],cave.identity)
    except GuildError:return None
