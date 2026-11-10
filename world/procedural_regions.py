"""Constraint-driven region geometry, compiled by existing native cave admission.

No LLM, world simulation, executable input or predetermined story is involved.
"""
import hashlib,itertools,json,re


def number(seed,*parts):
    return int.from_bytes(hashlib.sha256(json.dumps([seed,*parts],separators=(',',':')).encode()).digest()[:8],'big')


def graph(count,loops,degree,seed):
    edges=list(itertools.combinations(range(count),2));size=count-1+loops
    candidates=[]
    for selected in itertools.combinations(edges,size):
        if any(sum(i in edge for edge in selected)>degree for i in range(count)):continue
        seen={0}
        for _ in range(count):
            for a,b in selected:
                if a in seen or b in seen:seen.update((a,b))
        if len(seen)==count:candidates.append(selected)
    if not candidates:raise ValueError('No connected graph satisfies these loop and branching constraints')
    return [list(e) for e in min(candidates,key=lambda es:number(seed,'graph',es))]


def rooms(count,seed):
    pieces=[(2,2,27,27)]
    while len(pieces)<count:
        eligible=[r for r in pieces if max(r[2:])>=12]
        if not eligible:raise ValueError('Cannot pack requested rooms')
        rect=max(eligible,key=lambda r:(r[2]*r[3],number(seed,'piece',r)));pieces.remove(rect)
        x,y,w,h=rect;axes=[a for a,span in enumerate((w,h)) if span>=12]
        axis=axes[number(seed,'axis',rect)%len(axes)];span=(w,h)[axis]
        split=5+number(seed,'split',rect)%(span-11)
        if axis==0:pieces.extend([(x,y,split,h),(x+split+2,y,w-split-2,h)])
        else:pieces.extend([(x,y,w,split),(x,y+split+2,w,h-split-2)])
    result=[]
    for i,(x,y,w,h) in enumerate(sorted(pieces)):
        left=number(seed,'left',i)%2;top=number(seed,'top',i)%2
        right=number(seed,'right',i)%2;bottom=number(seed,'bottom',i)%2
        result.append([x+left,y+top,w-left-right,h-top-bottom])
    return result


def generate(label,raw):
    if type(label) is not str or not re.fullmatch('[A-Za-z][A-Za-z0-9 -]{0,11}',label):raise ValueError('Use a literal region label prefix of 1..12 characters')
    if type(raw) is not str or len(raw)>400:raise ValueError('Use bounded generation constraints JSON')
    try:spec=json.loads(raw)
    except ValueError:raise ValueError('Invalid generation constraints') from None
    keys={'places','rooms','loops','branching','style','seed','corridor_width'}
    if type(spec) is not dict or set(spec)!=keys:raise ValueError('Supply places, rooms, loops, branching, style, seed and corridor_width')
    for key,lo,hi in [('places',2,4),('rooms',2,4),('loops',0,1),('branching',1,3),('seed',0,2**32-1),('corridor_width',1,3)]:
        if type(spec[key]) is not int or not lo<=spec[key]<=hi:raise ValueError('Invalid '+key+' constraint')
    if spec['style'] not in ('rooms','rounded','organic','maze'):raise ValueError('Unsupported cave style')
    links=graph(spec['places'],spec['loops'],spec['branching'],spec['seed'])
    from .cave_blueprint import proposal_from_blueprint
    from .shared_cave import SharedCave
    places=[];identities=set()
    for i in range(spec['places']):
        seed=number(spec['seed'],'place',i)%2**32
        blueprint=dict(rooms=rooms(spec['rooms'],seed),links=graph(spec['rooms'],0,3,seed),entrance_room=0,exit_room=spec['rooms']-1,style=spec['style'],seed=seed,corridor_width=spec['corridor_width'])
        proposal=proposal_from_blueprint(blueprint)
        cave=SharedCave(b'EWGMAP01'+''.join(proposal['rows']).encode())
        if cave.identity in identities:raise ValueError('Generated duplicate geometry; choose another seed')
        identities.add(cave.identity);places.append(dict(label=label+' '+str(i+1),blueprint=blueprint))
    result=dict(places=places,links=links)
    encoded=json.dumps(result,separators=(',',':'))
    if len(encoded)>850:raise ValueError('Generated blueprint exceeds existing network budget; use fewer rooms or places')
    return result


def start(server,actor,row,args):
    if set(args)!={'label','constraints'}:raise ValueError('Supply label and generation constraints')
    from .region_networks import start as publish
    doc=generate(args['label'],args['constraints'])
    # All archive, topology, object, capacity, rollback and resume ownership is
    # retained by the existing real publication transaction and its poller.
    return publish(server,actor,row,dict(network=json.dumps(doc,separators=(',',':'))))
