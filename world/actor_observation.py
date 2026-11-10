"""Bounded authority-map sensing, not rendered sight or private player knowledge."""
from collections import deque
import hashlib


def observe(server, actor, row, args):
    from .characters import records
    from .shared_cave import SharedCave
    if set(args) != {'radius'} or type(args['radius']) is not int or not 1 <= args['radius'] <= 4:
        raise ValueError('Observation radius must be an integer from 1 to 4')
    current = records(server.module_state).get(actor)
    obj = next((o for o in server.objects if o['id'] == actor), None)
    if not current or current['status'] != 'active' or not obj or not obj.get('region_revision'):
        raise ValueError('Observation requires an active world actor on an exact generated map')
    revision = obj['region_revision']
    saved = server.db.execute('SELECT template FROM generated_area_archive WHERE identity=?', (revision,)).fetchone()
    if not saved or hashlib.sha256(saved[0]).hexdigest() != revision:
        raise ValueError('Exact authoritative geometry is unavailable')
    cave = SharedCave(saved[0]); origin = (obj['x'], obj['y'])
    if not cave.walkable(*origin):
        raise ValueError('Actor position is not on walkable geometry')
    # Explore only cardinally connected cells within a small path distance.
    # Solid boundary cells are reported, but never traversed to reveal behind them.
    distance = {origin: 0}; queue = deque([origin]); cells = {origin: True}
    while queue:
        x, y = queue.popleft()
        if distance[(x, y)] == args['radius']:continue
        for point in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            if not (0 <= point[0] < cave.side and 0 <= point[1] < cave.side):continue
            walkable = cave.walkable(*point); cells[point] = walkable
            if walkable and point not in distance:
                distance[point] = distance[(x,y)] + 1; queue.append(point)
    characters=records(server.module_state)
    entities = [dict(id=o['id'], x=o['x'], y=o['y'], **({'version':characters[o['id']]['version']} if o['id'] in characters else {})) for o in server.objects
                if o['id'] != actor and o.get('region_revision') == revision
                and (o['group'], o['num']) == (obj['group'], obj['num'])
                and (o['x'], o['y']) in distance]
    from .actor_objects import offers
    for entity in entities:
        obj=next(o for o in server.objects if o['id']==entity['id'])
        entity.update(gfx=obj['gfx'],text=obj['text'],kind=obj.get('kind','character' if obj['id'] in characters else 'object'))
        entity.update(offers(server,obj))
        if obj.get('kind')=='prop':
            from .actor_objects import digest
            entity['program_revision']=digest([obj,server.candidate.sha256 if server.candidate else None])
            from .actor_cave_travel import observed_link
            link=observed_link(server,obj)
            if link:entity['cave_link']=link
        if obj.get('kind')=='prop' and obj.get('portable') is True:
            from .actor_objects import digest
            entity['portable_revision']=digest(obj)
    from .actor_weather import current as current_weather
    return dict(weather=current_weather(server,revision),revision=revision, x=origin[0], y=origin[1], actor_version=current['version'],
                observed_revision=server.revision, radius=args['radius'],
                cells=[dict(x=x,y=y,walkable=cells[(x,y)]) for x,y in sorted(cells)],
                entities=sorted(entities,key=lambda o:o['id']),
                semantics='Connected local geometry and public objects at execution; not visual sight, player occupancy, encounters or lasting knowledge of current conditions.')
