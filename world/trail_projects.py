"""Turn explicitly shared surveys into previewable, additive walking shortcuts."""
import argparse
from collections import deque
import json
from .shared_cave import SharedCave


def _path(start, goal, allowed):
    queue=deque([start]);previous={start:None}
    while queue:
        point=queue.popleft()
        if point==goal:
            path=[]
            while point is not None:path.append(point);point=previous[point]
            return path[::-1]
        x,y=point
        for step in ((x,y-1),(x+1,y),(x,y+1),(x-1,y)):
            if 1<=step[0]<=125 and 1<=step[1]<=125 and step not in previous and allowed(step):
                previous[step]=point;queue.append(step)
    raise ValueError('protected terrain prevents a connecting trail')


def compile_trail(blob, plan):
    cave=SharedCave(blob)
    if cave.version not in (16,17):raise ValueError('trail requires an XL outdoor map')
    if type(plan) is not dict or set(plan)!={'kind','start','end','protected','sites'} or plan['kind']!='survey_trail':
        raise ValueError('invalid trail recipe')
    for point in (plan['start'],plan['end']):
        if type(point) is not list or len(point)!=2 or any(type(n) is not int or not 1<=n<=125 for n in point):
            raise ValueError('invalid trail endpoint')
    start,end=tuple(plan['start']),tuple(plan['end'])
    if start==end or not cave.walkable(*start) or not cave.walkable(*end):raise ValueError('trail endpoints must be distinct walkable sites')
    if type(plan['protected']) is not list or len(plan['protected'])>16129:raise ValueError('invalid protected terrain')
    protected=set()
    for point in plan['protected']:
        if type(point) is not list or len(point)!=2 or any(type(n) is not int or not 0<=n<=126 for n in point):
            raise ValueError('invalid protected terrain point')
        protected.add(tuple(point))
    if type(plan['sites']) is not list or len(plan['sites'])!=2 or any(type(n) is not str or not 1<=len(n)<=32 for n in plan['sites']):
        raise ValueError('invalid trail landmark names')
    old=_path(start,end,lambda p:cave.walkable(*p))
    path=_path(start,end,lambda p:cave.walkable(*p) or p not in protected)
    additions={p for p in path if not cave.walkable(*p)}
    if not additions or len(old)-len(path)<4:raise ValueError('trail must save at least four walking steps')
    if len(additions)>128:raise ValueError('trail requires more than 128 new walking tiles')
    rows=[bytearray(row) for row in cave._rows]
    for x,y in additions:rows[y][x]=ord('.')
    from .xl_wilds import encode
    result=encode(dict(rows=[row.decode('ascii') for row in rows],spawn=[1,1],exit=[125,125]))
    if cave.version==17:
        from .route_encounters import MAGIC,validate_table
        result=MAGIC+validate_table(cave.wildlife)+result[8:]
    return result,dict(previous_revision=cave.identity,revision=SharedCave(result).identity,
                       sites=plan['sites'],old_steps=len(old)-1,new_steps=len(path)-1,
                       saved_steps=len(old)-len(path),added_walkable_tiles=len(additions),
                       path=[list(p) for p in path])


def _recipe(server, revision, names):
    from .route_artifacts import load
    artifact=load(server,revision);root=artifact
    while root['schema']==2:root=load(server,root['parent'])
    # Preserve a designed mandatory-passage expedition rather than silently
    # relaxing its graph contract with an opportunistic shortcut.
    if root['report'].get('required_passages'):raise ValueError('mandatory-passage routes need deliberate route redesign')
    sites={p['id']:p for p in artifact['report']['landmarks'] if p['id'] not in ('entry','exit')}
    if any(name not in sites for name in names):raise ValueError('choose two named landmarks in this place')
    protected={tuple(p) for p in root['report'].get('protected_coastal_water',[])}
    for x,y,w,h in root['plan']['reservations']:
        protected.update((xx,yy) for xx in range(x,x+w) for yy in range(y,y+h))
    # Never carve inside a recorded clearing or an existing outpost's walls.
    for site in sites.values():
        r=site['radius']
        protected.update((x,y) for x in range(max(0,site['x']-r),min(127,site['x']+r+1))
                         for y in range(max(0,site['y']-r),min(127,site['y']+r+1)))
    return dict(kind='survey_trail',start=[sites[names[0]]['x'],sites[names[0]]['y']],
                end=[sites[names[1]]['x'],sites[names[1]]['y']],sites=names,
                protected=[list(p) for p in sorted(protected)])


def construct(server, request):
    required={'command','sites','label','previous_revision','expected_world_id','expected_sequence'}
    if set(request)!=required or request['command'] not in ('preview_trail','construct_trail'):
        raise ValueError('invalid surveyed trail request')
    names=request['sites']
    if type(names) is not list or len(names)!=2 or any(type(n) is not str for n in names) or names[0]==names[1]:
        raise ValueError('choose two distinct surveyed landmarks')
    if type(request['label']) is not str or not 1<=len(request['label'])<=80:raise ValueError('trail label must be 1 to 80 characters')
    with server.lock:
        cave=server.shared_cave
        if (not server.archive_generated_areas or cave is None or cave.identity!=request['previous_revision']
                or request['expected_world_id']!=server.memory.world_id
                or type(request['expected_sequence']) is not int
                or request['expected_sequence']!=server.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0]):
            raise ValueError('world changed; inspect this destination again')
        evidence=[]
        for name in names:
            row=server.db.execute('SELECT seq FROM survey_publications WHERE revision=? AND landmark=?',(cave.identity,name)).fetchone()
            if row is None:raise ValueError('both landmarks need explicitly shared discoveries in this exact revision')
            evidence.append(row[0])
        recipe=_recipe(server,cave.identity,names)
        stored=server.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(cave.identity,)).fetchone()
        blob,report=compile_trail(stored[0],recipe)
        if request['command']=='preview_trail':return dict(ok=True,applied=False,construction=report,history_evidence=evidence)
        from .route_artifacts import derive
        from .character_rebinding import prepare
        artifact=derive(server,cave.identity,blob,recipe)
        continuation=prepare(server,cave.identity,report['revision'])
        revision=server._replace_cave(blob,label=request['label'],previous_revision=cave.identity,
            expected_world_id=request['expected_world_id'],expected_sequence=request['expected_sequence'],
            history_evidence=evidence,character_continuation=continuation,route_artifact=artifact)
        return dict(ok=True,applied=True,revision=revision,construction=report,history_evidence=evidence,
                    rebound_characters=continuation['ids'] if continuation else [])


def main(argv=None):
    from .client import admin_request
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('start');parser.add_argument('end');parser.add_argument('--label',required=True)
    parser.add_argument('--admin-socket',required=True);parser.add_argument('--apply',action='store_true')
    args=parser.parse_args(argv)
    def call(request):
        result=admin_request('',request,admin_path=args.admin_socket)
        if not result.get('ok'):raise ValueError(result.get('error','trail request refused'))
        return result
    try:
        inspection=call(dict(command='inspect'));memory=inspection['world_memory']
        result=call(dict(command='construct_trail' if args.apply else 'preview_trail',sites=[args.start,args.end],
                         label=args.label,previous_revision=memory['active_area']['revision'],
                         expected_world_id=memory['world_id'],expected_sequence=memory['through']))
        print(json.dumps(result,indent=2))
    except (ValueError,KeyError,TypeError,OSError) as error:parser.exit(1,str(error)+'\n')
    return 0

if __name__=='__main__':main()
