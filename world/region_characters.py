"""Exact-revision character scope for immutable regions and archived shared XL maps."""
import hashlib


def validate_region_objects(server, objects, state):
    from .characters import records
    from .npc_absence import validate_objects as validate_absence
    validate_absence(server,objects,state)
    from .shared_cave import SharedCave
    from .native_resident_population import validate as validate_residents
    validate_residents(server,objects,state)
    cast=records(state)
    placements={}
    for obj in objects:
        revision=obj.get('region_revision')
        if revision is None:continue
        if obj['id'] not in {o['id'] for o in server.objects} and any(not p.get('closing') and p.get('state') and p['state'][6] and server._region_scope(p)==revision and p['state'][2:4]==[obj['x'],obj['y']] for p in server.peers.values()):
            raise ValueError('New population overlaps a ready player')
        if obj['id'] in state.get('world_pushables',{}):
            if any(not p.get('closing') and p.get('state') and server._region_scope(p)==revision and p['state'][2:4]==[obj['x'],obj['y']] for p in server.peers.values()):
                raise ValueError('Pushable destination overlaps a player, including menus')
        if obj.get('kind')=='prop':
            if obj['id'] in cast:raise ValueError('Props cannot be characters')
            if any(not p.get('closing') and p.get('state') and p['state'][6] and server._region_scope(p)==revision and p['state'][2:4]==[obj['x'],obj['y']] for p in server.peers.values()):
                raise ValueError('Prop placement overlaps a ready player')
            for peer in server.peers.values():
                if not peer.get('closing') and not peer.get('world_props_capable') and peer.get('state') and tuple(peer['state'][:2]) in (server.cave_map,server.wilds_map) and server._region_scope(peer)==revision:
                    raise ValueError('Legacy player must leave before props are admitted')
        elif obj['id'] not in cast:raise ValueError('region objects must be persistent characters')
        row=server.db.execute('''SELECT a.template,r.place_id FROM generated_area_archive a
            LEFT JOIN world_region_revisions r ON r.revision=a.identity WHERE a.identity=?''',(revision,)).fetchone()
        if row is None or hashlib.sha256(row[0]).hexdigest()!=revision:
            raise ValueError('character region must be an opened immutable revision')
        cave=SharedCave(row[0])
        if row[1] is None and (cave.version not in (16,17) or not server.archive_generated_areas):
            raise ValueError('only archived XL maps may host shared-slot characters')
        placements.setdefault(revision,(cave,set()))[1].add((obj['x'],obj['y']))
        expected=server.cave_map if cave.version in (1,10) else server.wilds_map if cave.version in (16,17) else None
        if expected is None or (obj['group'],obj['num'])!=expected:
            raise ValueError('unsupported character region geometry')
        x,y=obj['x'],obj['y']
        if (not cave.walkable(x,y) or (x,y) in ((1,1),(cave.side-2,cave.side-2),(cave.side-2,cave.side-3))
                or not any(cave.walkable(x+dx,y+dy) for dx,dy in ((0,1),(0,-1),(1,0),(-1,0)))):
            raise ValueError('character needs a walkable region interaction tile outside entry and exit')

    # NPC collision must not collectively seal a corridor or isolate an exit.
    # Shared XL geometry is immutable; mutable terrain/cast formats are excluded.
    for cave,blocked in placements.values():
        available={(x,y) for y in range(cave.side) for x in range(cave.side) if cave.walkable(x,y)}-blocked
        seen={(1,1)};frontier=[(1,1)]
        while frontier:
            x,y=frontier.pop()
            for step in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if step in available and step not in seen:
                    seen.add(step);frontier.append(step)
        if seen!=available:
            raise ValueError('character placement blocks region routes')


def scoped(server,conn,obj,revision=None):
    """Generated requests must name the exact selected region or active archived shared XL revision."""
    if obj is None:return False
    generated=(obj['group'],obj['num']) in (server.cave_map,server.wilds_map)
    if not generated:return revision is None and 'region_revision' not in obj
    cave=conn.get('region_cave')
    if cave is None:
        cave=server.shared_cave
        if cave is None or cave.version not in (16,17) or not server.archive_generated_areas:return False
    state=conn.get('state')
    return bool(conn.get('character_region_capable') and cave and revision==obj.get('region_revision')
                and revision==cave.identity and conn.get('cave_ack')==revision
                and state and state[:2]==[obj['group'],obj['num']])
