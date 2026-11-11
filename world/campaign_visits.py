"""Voluntary campaign check-ins from fresh presence, not verified travel or lore."""
import time


def validate(server,node):
    from .build_catalog import validate_coords
    if set(node)-{'visit','next'} or not {'visit','next'}<=set(node):raise ValueError('Visit node requires visit and next routes')
    visit=node['visit']
    if type(visit) is not dict or set(visit) not in ({'label','point'},{'label','point','revision'},{'label','point','registry'}):raise ValueError('Visit requires label and point')
    if type(visit['label']) is not str or not 1<=len(visit['label'])<=40 or any(not 32<=ord(c)<127 for c in visit['label']):raise ValueError('Use a literal destination label')
    point=visit['point']
    if type(point) is not list or len(point)!=4 or any(type(v) is not int for v in point):raise ValueError('Use integer map group, map number, x and y')
    generated=tuple(point[:2]) in (tuple(server.cave_map),tuple(server.wilds_map))
    if generated:
        if 'registry' in visit:raise ValueError('Generated visits use their revision, not a registry')
        import hashlib
        from .shared_cave import SharedCave
        revision=visit.get('revision')
        if type(revision) is not str:raise ValueError('Generated visits require an immutable revision')
        saved=server.db.execute('SELECT a.template,r.place_id FROM generated_area_archive a LEFT JOIN world_region_revisions r ON r.revision=a.identity WHERE a.identity=?',(revision,)).fetchone()
        if not saved or hashlib.sha256(saved[0]).hexdigest()!=revision:raise ValueError('Generated visit geometry unavailable')
        cave=SharedCave(saved[0])
        if saved[1] is None and (cave.version!=16 or not server.archive_generated_areas):raise ValueError('Visit destination has not been opened')
        expected=server.cave_map if cave.version in (1,10) else server.wilds_map if cave.version==16 else None
        if expected is None or tuple(point[:2])!=tuple(expected) or not cave.walkable(*point[2:]):raise ValueError('Destination is not supported walkable geometry')
        if tuple(point[2:]) in ((1,1),(cave.side-2,cave.side-2),(cave.side-2,cave.side-3)):raise ValueError('Keep visit destinations off transit endpoints')
    else:
        if 'registry' in visit:
            from .combined_regions import DIGEST,coords
            if not getattr(server,'combined_regions',False) or visit['registry']!=DIGEST:raise ValueError('Visit requires its exact combined-world registry')
            coords(*point)
        else:
            validate_coords(*point)
        if 'revision' in visit:raise ValueError('Ordinary visits do not use generated revision aliases')


def describe(node):
    from .build_catalog import catalog_maps
    v=node['visit'];g,n,x,y=v['point']
    if 'registry' in v:
        from .combined_regions import DIGEST,catalog
        if v['registry']!=DIGEST:raise ValueError('Unsupported visit registry')
        maps=catalog()
    else:maps=catalog_maps()
    name=('Generated '+v['revision'][:12]) if 'revision' in v else maps[(g,n)]['name'].replace('_',' ')
    return ['Visit '+v['label'],f'{name} - tile {x} {y}.', 'Travel normally, then check in. Presence is client-reported, not proof of a journey.']


def check_in(server,conn,current):
    from .battle_campaigns import document,save,routes
    if not current or current[1]['status']!='ready':raise ValueError('No active visit stage ready for check-in')
    key,data=current
    from .parallel_campaigns import effective
    node=effective(server,key,data)
    if 'visit' not in node:raise ValueError('Current stage requires its normal battle')
    # Revalidate persisted authoring and live admission, not just cached board text.
    validate(server,node)
    if 'registry' in node['visit']:
        from .combined_regions import admitted
        if not admitted(server,conn):raise ValueError('Reconnect to the matching combined world before checking in')
    state=conn.get('state')
    if (server.peers.get(conn.get('id')) is not conn or conn.get('closing') or not state or not state[6]
        or not 0<=time.monotonic()-conn.get('state_time',0)<=5 or state[:4]!=node['visit']['point'] or conn.get('character_pending')):
        raise ValueError('Stand ready at the exact destination with a fresh world connection')
    if 'revision' in node['visit']:
        from .region_characters import scoped
        obj=dict(group=state[0],num=state[1],region_revision=node['visit']['revision'])
        if not scoped(server,conn,obj,node['visit']['revision']):raise ValueError('Check in only in the exact admitted generated revision')
    record=dict(node=data['node'],point=list(state[:4]),basis='voluntary_fresh_client_presence',outcome='checked_in')
    if 'revision' in node['visit']:record['revision']=node['visit']['revision']
    if 'registry' in node['visit']:record['registry']=node['visit']['registry']
    with server.db:
        if data.get('shared'):
            from .shared_campaigns import complete_stage
            complete_stage(server,conn,key,data,1,record)
        else:
            data['history'].append(record);choices=routes(node)
            data.update(choices=choices,status='choice' if choices else 'complete')
            save(server,conn,key,data)
