"""Destination routing for world-owned actors on existing immutable generated maps."""
from collections import deque
import copy,hashlib,json


def route(server,actor,destination,revision,*,avoid=()):
    from .characters import records
    from .shared_cave import SharedCave
    from .character_walks import walking
    from .region_characters import validate_region_objects
    row=records(server.module_state).get(actor)
    obj=next((o for o in server.objects if o['id']==actor),None)
    if not row or row['status']!='active' or not obj or obj.get('region_revision')!=revision:raise ValueError('Actor is not active on that exact generated map')
    if walking(server.module_state,actor):raise ValueError('Actor already has an active movement')
    saved=server.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(revision,)).fetchone()
    if not saved or hashlib.sha256(saved[0]).hexdigest()!=revision:raise ValueError('Immutable geometry is unavailable')
    cave=SharedCave(saved[0]);start=(obj['x'],obj['y']);target=tuple(destination)
    if len(target)!=2 or any(type(v) is not int for v in target) or target==start:raise ValueError('Destination must be a different integer coordinate on this map')
    forbidden={(1,1),(cave.side-2,cave.side-2),(cave.side-2,cave.side-3)}
    forbidden|={(o['x'],o['y']) for o in server.objects if o['id']!=actor and o.get('region_revision')==revision}
    forbidden|={(p['x'],p['y']) for p in server.inspect()['players'] if p.get('ready') and p.get('generated_place',{}).get('revision')==revision}
    forbidden.update(avoid)
    queue=deque([start]);previous={start:None};depth={start:0}
    while queue:
        point=queue.popleft()
        if point==target:break
        if depth[point]>=64:continue
        for x,y in ((point[0]-1,point[1]),(point[0]+1,point[1]),(point[0],point[1]-1),(point[0],point[1]+1)):
            nxt=(x,y)
            if nxt in previous or nxt in forbidden or not cave.walkable(x,y):continue
            previous[nxt]=point;depth[nxt]=depth[point]+1;queue.append(nxt)
    if target not in previous:raise ValueError('Destination has no current route within 64 supported steps')
    path=[];at=target
    while at is not None:path.append(list(at));at=previous[at]
    path.reverse()
    for x,y in path:
        validate_region_objects(server,[dict(o,x=x,y=y) if o['id']==actor else o for o in server.objects],server.module_state)
    return row,obj,path


def start(server,actor,row,args):
    from .actor_runtime import Pending
    from .character_actions import compile_actions
    if set(args)!={'revision','x','y'}:raise ValueError('Navigation requires exact revision and destination x/y')
    current,obj,path=route(server,actor,[args['x'],args['y']],args['revision'])
    return stage(server,actor,current,obj,path,args['revision'])


def stage(server,actor,current,obj,path,revision):
    from .actor_runtime import Pending
    from .character_actions import compile_actions
    action=dict(id=actor,expected_version=current['version'],evidence=current['evidence'],reason='Execute this actor own destination-based navigation plan.',changes={},object=dict(obj,x=path[-1][0],y=path[-1][1]),journey=path)
    context=server.inspect();context['runtime']=dict(previous_source=server.candidate.source if server.candidate else '')
    # Recalled exact references were already admitted for the actor's plan.
    context['recalled_history']=dict(events=[dict(json.loads(server.db.execute("SELECT data FROM events WHERE seq=? AND kind='world_memory'",(seq,)).fetchone()[0]),seq=seq) for seq in current['evidence']])
    source=compile_actions([action],context);digest=hashlib.sha256(source.encode()).hexdigest()
    journey=hashlib.sha256(json.dumps([action],sort_keys=True).encode()).hexdigest()[:24]
    pathfile=server.runtime.candidates/('navigation_'+digest+'.py')
    try:
        with pathfile.open('x') as f:f.write(source)
    except FileExistsError:
        if pathfile.is_symlink() or pathfile.read_text()!=source:raise ValueError('Navigation candidate path conflict')
    def dispatch():server.deployment=(None,pathfile,None)
    return Pending(dict(journey=journey,revision=revision,destination=path[-1],candidate=digest,version=current['version']),dispatch)


def poll(server,actor,row,pending):
    control=server.module_state.get('world_character_controls',{}).get(actor,{})
    journey=control.get('journey')
    receipt=server.db.execute('SELECT seq FROM character_journey_receipts WHERE actor=? AND journey=?',(actor,pending['journey'])).fetchone()
    if receipt:return dict(arrival_receipt=receipt[0],revision=pending['revision'],x=pending['destination'][0],y=pending['destination'][1],outcome='authority_arrived')
    if not journey or journey['id']!=pending['journey']:raise ValueError('Navigation interrupted or staging was not admitted; inspect and replan')
    obj=control.get('object') or {}
    if obj.get('region_revision')!=pending['revision']:raise ValueError('Navigation scope changed')
    # Occupancy is handled by the existing movement reducer. Waiting is not a
    # failure or an arrival; no timeout manufactures either result.
    return None


def discover(server):
    from .characters import records
    return [dict(actor=o['id'],revision=o['region_revision'],x=o['x'],y=o['y'],max_steps=64,geometry_request=dict(command='inspect_saved_place',revision=o['region_revision']),
        limits='Same immutable generated map only; route is computed at execution. Occupancy can pause movement.')
        for o in server.objects if o.get('region_revision') and o['id'] in records(server.module_state)]
