"""Immutable-region scope for agent characters; no mutable geometry or shared-cave NPCs."""
import hashlib


def validate_region_objects(server, objects, state):
    from .characters import records
    from .shared_cave import SharedCave
    cast=records(state)
    for obj in objects:
        revision=obj.get('region_revision')
        if revision is None:continue
        if obj['id'] not in cast:raise ValueError('region objects must be persistent characters')
        row=server.db.execute('''SELECT a.template FROM world_region_revisions r
            JOIN generated_area_archive a ON a.identity=r.revision WHERE r.revision=?''',(revision,)).fetchone()
        if row is None or hashlib.sha256(row[0]).hexdigest()!=revision:
            raise ValueError('character region must be an opened immutable revision')
        cave=SharedCave(row[0])
        expected=server.cave_map if cave.version==1 else server.wilds_map if cave.version==16 else None
        if expected is None or (obj['group'],obj['num'])!=expected:
            raise ValueError('unsupported character region geometry')
        x,y=obj['x'],obj['y']
        if (not cave.walkable(x,y) or (x,y) in ((1,1),(cave.side-2,cave.side-2),(cave.side-2,cave.side-3))
                or not any(cave.walkable(x+dx,y+dy) for dx,dy in ((0,1),(0,-1),(1,0),(-1,0)))):
            raise ValueError('character needs a walkable region interaction tile outside entry and exit')


def scoped(server,conn,obj,revision=None):
    """Generated requests must name the exact selected, acknowledged immutable region."""
    if obj is None:return False
    generated=(obj['group'],obj['num']) in (server.cave_map,server.wilds_map)
    if not generated:return revision is None and 'region_revision' not in obj
    cave=conn.get('region_cave')
    state=conn.get('state')
    return bool(conn.get('character_region_capable') and cave and revision==obj.get('region_revision')
                and revision==cave.identity and conn.get('cave_ack')==revision
                and state and state[:2]==[obj['group'],obj['num']])
