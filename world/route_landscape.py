"""Compile custom clearings and reserved terrain into connected native XL maps.

This is geometry generation, not a quest/portal or biome-art system. Reserved
cells remain impassable under the existing native XL palette.
"""
import argparse
from collections import deque
import hashlib
import heapq
import json
from pathlib import Path
import re

from .map_store import write_map
from .shared_cave import SharedCave
from .xl_wilds import encode

SIDE=127
MAX_INPUT=16384


def _distance(a,b):
    return abs(a[0]-b[0])+abs(a[1]-b[1])


def compile_plan(plan):
    """Return ordinary EWGMAP0A bytes and a derived route report.

Routes go around reservations, rather than drawing L-shaped lines through them.
The spanning network connects every clearing and both native return endpoints.
Requested additional routes must use new terrain outside their endpoint areas.
"""
    if type(plan) is not dict or set(plan)!={'seed','landmarks','reservations','loops'}:
        raise ValueError('expected seed, landmarks, reservations and loops')
    seed=plan['seed'];loops=plan['loops'];landmarks=plan['landmarks'];reservations=plan['reservations']
    if type(seed) is not int or not 0<=seed<2**32 or type(loops) is not int or not 0<=loops<=4:
        raise ValueError('invalid seed or loop count')
    if type(landmarks) is not list or not 2<=len(landmarks)<=12 or type(reservations) is not list or len(reservations)>32:
        raise ValueError('use 2..12 landmarks and at most 32 reservations')
    sites=[dict(id='entry',x=1,y=1,radius=0)]
    ids={'entry','exit'}
    blocked={(x,y) for x in range(SIDE) for y in (0,SIDE-1)}|{(x,y) for y in range(SIDE) for x in (0,SIDE-1)}
    for rect in reservations:
        if type(rect) is not list or len(rect)!=4 or any(type(v) is not int for v in rect):
            raise ValueError('reservation must be [x,y,width,height]')
        x,y,w,h=rect
        if x<1 or y<1 or w<1 or h<1 or x+w>126 or y+h>126:
            raise ValueError('reservation outside interior')
        blocked.update((xx,yy) for xx in range(x,x+w) for yy in range(y,y+h))
    for item in landmarks:
        if type(item) is not dict or not {'id','x','y','radius'}<=set(item) or set(item)-{'id','x','y','radius','landform','facing'}:
            raise ValueError('landmark needs id, x, y and radius')
        name=item['id'];x=item['x'];y=item['y'];r=item['radius']
        form=item.get('landform','round');facing=item.get('facing','east')
        if form not in ('round','lagoon','cove','headland') or facing not in ('east','south','west','north'):
            raise ValueError('invalid coastal landform or facing')
        if type(name) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',name) or name in ids:
            raise ValueError('landmark identities must be unique bounded names')
        if any(type(v) is not int for v in (x,y,r)) or not (2 if form=='round' else 6)<=r<=20 or min(x-r,y-r)<1 or max(x+r,y+r)>125:
            raise ValueError('landmark outside interior')
        ids.add(name);sites.append(dict(item))
    sites.append(dict(id='exit',x=125,y=125,radius=1))
    walk=set();centers=[];coastal_water=set();footprints=set()
    for site in sites:
        x,y,r=site['x'],site['y'],site['radius'];centers.append((x,y))
        clearing={(xx,yy) for xx in range(max(1,x-r),min(126,x+r+1))
                  for yy in range(max(1,y-r),min(126,y+r+1)) if (xx-x)**2+(yy-y)**2<=r*r}
        if clearing&blocked:raise ValueError('reserved terrain overlaps a landmark or native endpoint')
        if site['id'] not in ('entry','exit') and clearing&footprints:
            raise ValueError('landmark clearings overlap')
        footprints.update(clearing)
        form=site.get('landform','round');facing=site.get('facing','east')
        def local(point):
            dx,dy=point[0]-x,point[1]-y
            return {'east':(dx,dy),'south':(dy,-dx),'west':(-dx,-dy),'north':(-dy,dx)}[facing]
        water=set()
        for point in clearing:
            u,v=local(point)
            if form=='lagoon' and (u-r//2)**2+v*v<=(r//3)**2:
                water.add(point)
            elif form=='cove' and (u-r)**2+v*v<=(r*2//3)**2:
                water.add(point)
            elif form=='headland' and u>r//3 and abs(v)>max(1,(r-u)//3):
                water.add(point)
        clearing-=water
        coastal_water.update(water)
        walk.update(clearing)
    # Water cuts are semantic geography, not cheap empty space for route carving.
    blocked.update(coastal_water)
    # Seed affects route preference, not global process randomness or save state.
    costs={(x,y):10+hashlib.sha256(f'{seed}:{x//4}:{y//4}'.encode('ascii')).digest()[0]%7
           for x in range(1,126) for y in range(1,126)}

    def route(a,b,extra=False):
        start,goal=centers[a],centers[b]
        avoid=set(blocked)
        if extra:
            for p in walk:
                if all(_distance(p,centers[i])>sites[i]['radius']+3 for i in (a,b)):
                    avoid.add(p)
        queue=[(_distance(start,goal),0,start)];best={start:0};prev={}
        while queue:
            _,cost,p=heapq.heappop(queue)
            if best.get(p)!=cost:continue
            if p==goal:
                path=[p]
                while p!=start:p=prev[p];path.append(p)
                return path[::-1]
            x,y=p
            for q in ((x,y-1),(x+1,y),(x,y+1),(x-1,y)):
                if not 1<=q[0]<=125 or not 1<=q[1]<=125 or q in avoid:continue
                nxt=cost+(1 if q in walk else costs[q])
                if nxt<best.get(q,10**12):
                    best[q]=nxt;prev[q]=p
                    heapq.heappush(queue,(nxt+_distance(q,goal),nxt,q))
        return None

    # Prim's connection order keeps the plan compact while A* handles terrain.
    connected={0};edges=[];records=[]
    def add(a,b,path,kind):
        new=len(set(path)-walk);walk.update(path);edges.append(tuple(sorted((a,b))))
        records.append(dict(source=sites[a]['id'],target=sites[b]['id'],kind=kind,
                            steps=len(path)-1,new_tiles=new,path=[list(p) for p in path]))
    while len(connected)<len(sites):
        candidates=sorted((_distance(centers[a],centers[b]),a,b) for a in connected for b in range(len(sites)) if b not in connected)
        for _,a,b in candidates:
            path=route(a,b)
            if path is not None:add(a,b,path,'connection');connected.add(b);break
        else:raise ValueError('reservations disconnect required landmarks')
    added=0
    candidates=sorted((_distance(centers[a],centers[b]),a,b) for a in range(1,len(sites)-1) for b in range(a+1,len(sites)-1) if (a,b) not in edges)
    for _,a,b in candidates:
        if added==loops:break
        path=route(a,b,True)
        if path is not None and len(set(path)-walk)>4:
            add(a,b,path,'alternate');added+=1
    if added!=loops:raise ValueError('cannot fit requested alternate routes around reservations')
    rows=[''.join('.' if (x,y) in walk else '#' for x in range(SIDE)) for y in range(SIDE)]
    blob=encode(dict(rows=rows,spawn=[1,1],exit=[125,125]));cave=SharedCave(blob)
    distance={(1,1):0};queue=deque(distance)
    while queue:
        x,y=queue.popleft()
        for p in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            if p in walk and p not in distance:distance[p]=distance[x,y]+1;queue.append(p)
    return blob,dict(schema=1,generator='reserved-terrain-routes-1',revision=cave.identity,
        landmarks=sites,routes=records,protected_coastal_water=[list(p) for p in sorted(coastal_water)],walkable_tiles=len(walk),entry_to_exit_steps=distance[125,125],
        limitations='Geometry uses the existing grass/water palette. No elevation, new biome art, quests or inter-map portals.')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args(argv)
    with args.plan.open('rb') as stream:raw=stream.read(MAX_INPUT+1)
    if len(raw)>MAX_INPUT:parser.error('plan too large')
    try:blob,report=compile_plan(json.loads(raw))
    except (ValueError,UnicodeError) as error:parser.error(str(error))
    if args.report is not None and args.report.exists():parser.error('report already exists')
    write_map(args.output,blob)
    if args.report is not None:
        with args.report.open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(revision=report['revision'],walkable_tiles=report['walkable_tiles'],routes=len(report['routes']))))

if __name__=='__main__':main()
