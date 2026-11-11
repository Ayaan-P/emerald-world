"""Resumable authored adventures: real places, original cast and private campaigns."""
import copy, hashlib, inspect, json
from collections import deque


def encode(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'))


def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS procedural_adventures(id TEXT PRIMARY KEY,actor TEXT,document TEXT,request TEXT,published INTEGER NOT NULL DEFAULT 0)')


def catalog(server):
    setup(server.db)
    result=[]
    for key,actor,raw,done in server.db.execute('SELECT id,actor,request,published FROM procedural_adventures ORDER BY id'):
        request=json.loads(raw);campaign=request['campaign']
        published=server.db.execute('SELECT actor,document FROM battle_campaigns WHERE id=?',(campaign['id'],)).fetchone()
        result.append(dict(id=key,actor=actor,places=request['network']['places'],campaign=campaign['id'],
                           published=bool(done) and published is not None and tuple(published)==(actor,encode(campaign))))
    return result


def project(result, request):
    result=apply_network(result,request['network'])
    for population in request['population']:
        result=population_step(result,population)
    return result


# These are the existing projectors, not parallel implementations.
from .region_networks import apply_network
from .actor_population import population_step


def placement(server,cave,revision,objects,seed,identity):
    blocked={(o['x'],o['y']) for o in objects if o.get('region_revision')==revision}
    floor={(x,y) for y in range(cave.side) for x in range(cave.side) if cave.walkable(x,y)}
    excluded={(1,1),(cave.side-2,cave.side-2),(cave.side-2,cave.side-3)}
    candidates=sorted(floor-blocked-excluded,key=lambda p:hashlib.sha256(encode([seed,identity,p]).encode()).digest())
    for point in candidates:
        # Keep every remaining floor tile and an adjacent interaction tile reachable.
        remaining=floor-blocked-{point};seen={(1,1)};queue=deque(seen)
        while queue:
            x,y=queue.popleft()
            for p in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if p in remaining and p not in seen:seen.add(p);queue.append(p)
        if seen==remaining and any((point[0]+dx,point[1]+dy) in seen for dx,dy in ((0,1),(0,-1),(1,0),(-1,0))):
            return point
    raise ValueError('No nonblocking reachable trainer placement; change layout constraints')


def start(server,actor,row,args):
    from .actor_runtime import Pending
    from .procedural_regions import generate
    from .region_networks import start as network_start
    from .actor_population import prepare,stage
    from .battle_campaigns import inspect_document
    from .shared_cave import SharedCave
    if set(args)!={'document'} or type(args['document']) is not str or len(args['document'])>6000:
        raise ValueError('Supply bounded authored adventure JSON')
    doc=json.loads(args['document'])
    if type(doc) is not dict or set(doc)!={'label','constraints','trainers','campaign'}:
        raise ValueError('Adventure requires label, procedural constraints, trainers and campaign')
    layout=generate(doc['label'],encode(doc['constraints']))
    trainers=doc['trainers'];campaign=doc['campaign']
    if type(trainers) is not list or not 2<=len(trainers)<=4 or type(campaign) is not dict:
        raise ValueError('Use two to four original trainers and an authored campaign')
    for trainer in trainers:
        if type(trainer) is not dict or set(trainer)!={'place','id','name','role','goals','team','gfx','text'} or type(trainer['place']) is not int or not 0<=trainer['place']<len(layout['places']):
            raise ValueError('Each original trainer selects an actual generated place index')
    ids=[t['id'] for t in trainers]
    if any(type(i) is not str for i in ids) or len(set(ids))!=len(ids) or set(t['place'] for t in trainers)!=set(range(len(layout['places']))):
        raise ValueError('Distinct trainers must populate every generated place')
    if type(campaign.get('nodes')) is not dict or any(type(n) is not dict or set(n)!={'opponent','win','loss'} or n['opponent'] not in ids for n in campaign['nodes'].values()):
        raise ValueError('Initial adventure graph uses only these original trainers and explicit win/loss routes')
    if {n['opponent'] for n in campaign['nodes'].values()}!=set(ids):raise ValueError('Every created trainer must have a campaign role')
    if type(campaign.get('id')) is not str:raise ValueError('Campaign requires a literal identity')
    setup(server.db)
    key=hashlib.sha256(encode([actor,doc]).encode()).hexdigest()
    old=server.db.execute('SELECT request,published FROM procedural_adventures WHERE id=?',(key,)).fetchone()
    if old:
        request=json.loads(old[0])
        if old[1]:return completion(request)
    else:
        if server.db.execute('SELECT 1 FROM battle_campaigns WHERE id=?',(campaign.get('id'),)).fetchone():raise ValueError('Campaign identity is already published')
        network=network_start(server,actor,row,dict(network=encode(layout))).data
        trial=apply_network(dict(state=copy.deepcopy(server.module_state),objects=copy.deepcopy(server.objects),tiles=[]),network)
        populations=[]
        for trainer in trainers:
            place=network['places'][trainer['place']];revision=place['revision']
            cave=SharedCave(server.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(revision,)).fetchone()[0])
            x,y=placement(server,cave,revision,trial['objects'],doc['constraints']['seed'],trainer['id'])
            definition={k:v for k,v in trainer.items() if k!='place'}
            definition.update(kind='character',x=x,y=y)
            population=prepare(server,actor,row,dict(revision=revision,definition=encode(definition)),state=trial['state'],objects=trial['objects'])
            trial=population_step(trial,population);populations.append(population)
        preview=copy.copy(server);preview.module_state=trial['state'];preview.objects=trial['objects']
        inspect_document(preview,dict(campaign=encode(campaign)))
        request=dict(id=key,network=network,population=populations,campaign=campaign)
        server.db.execute('INSERT INTO procedural_adventures(id,actor,document,request) VALUES(?,?,?,?)',(key,actor,encode(doc),encode(request)))
    # Once admitted, resumption only verifies and publishes; it never rewinds cast state.
    if server.module_state.get('world_region_networks',{}).get(request['network']['id'])==request['network']:
        return Pending(request,lambda:None)
    def projector(result,_):return project(result,request)
    def source_builder(old,_,state):
        suffix=key[:16]
        helpers='\n'.join(inspect.getsource(f).replace('def '+f.__name__+'(', 'def _adventure_'+f.__name__+'_'+suffix+'(') for f in (apply_network,population_step))
        body=f'''\n_adventure_previous_{suffix}=update
{helpers}
def update(context,state):
    if not state:
        import copy
        state=copy.deepcopy({state!r})
    result=_adventure_apply_network_{suffix}(_adventure_previous_{suffix}(context,state),{request['network']!r})
    for request in {request['population']!r}:
        result=_adventure_population_step_{suffix}(result,request)
    return result
'''
        return old+body
    pending=stage(server,actor,row,request['population'],projector=projector,source_builder=source_builder)
    return Pending(request,pending.dispatch)


def poll(server,actor,row,request):
    from .region_networks import poll as network_poll
    from .actor_population import poll as population_poll
    from .battle_campaigns import publish
    network_poll(server,actor,row,request['network'])
    population_poll(server,actor,row,request)
    publish(server,actor,row,dict(campaign=encode(request['campaign'])))
    server.db.execute('UPDATE procedural_adventures SET published=1 WHERE id=? AND actor=?',(request['id'],actor))
    return completion(request)


def completion(request):
    return dict(outcome='procedural_adventure_published',adventure=request['id'],campaign=request['campaign']['id'],
                places=request['network']['places'],trainers=[p['object']['id'] for p in request['population']],
                limits='Real selectable connected caves, original NPCs and optional native battle campaign. Player starts or hosts voluntarily. No victories, rewards, automatic travel or rendered playtest implied.')
