"""New-place mechanism compilation using the ordinary shared interaction validator."""
import copy,re
from .procedural_adventures import encode,placement


def prepare(server,actor,row,doc,network,trial):
    from .actor_population import prepare as population,population_step
    from .shared_cave import SharedCave
    from .object_networks import validate_program,project
    definitions=doc.get('mechanisms',[])
    if type(definitions) is not list or len(definitions)>2:raise ValueError('Use at most two new mechanisms')
    requests=[];programs=[];places=set()
    for definition in definitions:
        if (type(definition) is not dict or set(definition)!={'id','place','props','program'}
            or type(definition['id']) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',definition['id'])
            or type(definition['place']) is not int or not 0<=definition['place']<len(network['places'])):
            raise ValueError('New mechanism requires id, place, props and program')
        key=definition['id']
        if key in trial['state'].get('world_object_networks',{}):raise ValueError('Existing mechanism preserved')
        props=definition['props'];program=copy.deepcopy(definition['program'])
        if type(props) is not list or not 2<=len(props)<=4:raise ValueError('Two to four new anchored props required')
        revision=network['places'][definition['place']]['revision']
        cave=SharedCave(server.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(revision,)).fetchone()[0])
        anchors={}
        for prop in props:
            if type(prop) is not dict or set(prop)!={'id','gfx','text'}:raise ValueError('New props require id, gfx and initial text')
            x,y=placement(server,cave,revision,trial['objects'],doc['constraints']['seed'],prop['id'])
            p=population(server,actor,row,dict(revision=revision,definition=encode(dict(prop,kind='prop',portable=False,x=x,y=y))),state=trial['state'],objects=trial['objects'])
            trial=population_step(trial,p);requests.append(p);anchors[prop['id']]=(x,y)
        if type(program) is not dict or type(program.get('states')) is not dict:raise ValueError('Use a bounded mechanism state graph')
        for node in program['states'].values():
            if type(node) is not dict or type(node.get('objects')) is not dict or set(node['objects'])!=set(anchors):raise ValueError('Every phase describes each new prop')
            # Relative offsets bind authored appearances to the actual generated geometry.
            for identity,appearance in node['objects'].items():
                if type(appearance) is not dict or set(appearance)!={'dx','dy','gfx','text'} or any(type(appearance[k]) is not int for k in ('dx','dy')):raise ValueError('Use relative dx/dy appearances')
                x,y=anchors[identity];node['objects'][identity]=dict(x=x+appearance['dx'],y=y+appearance['dy'],gfx=appearance['gfx'],text=appearance['text'])
        request=dict(id=key,objects=list(anchors),program=program)
        preview=copy.copy(server);preview.module_state=trial['state'];preview.objects=trial['objects']
        validate_program(preview,request)
        initial=program['states'][program['initial']]['objects']
        for p in requests:
            if p['object']['id'] in anchors and any(p['object'][k]!=initial[p['object']['id']][k] for k in ('x','y','gfx','text')):
                raise ValueError('Initial phase must match new prop placement and appearance')
        trial['state'].setdefault('world_object_networks',{})[key]=request
        trial=project(trial);programs.append(request);places.add(definition['place'])
    return trial,requests,programs,places


def bind_campaign(server,campaign,programs):
    from .campaign_mechanisms import fingerprint
    campaign=copy.deepcopy(campaign);owned={p['id']:p for p in programs}
    for node in campaign['nodes'].values():
        for field in ('mechanism','expedition'):
            if field not in node:continue
            goal=node[field]
            if type(goal) is not dict or goal.get('network') not in owned or 'definition' in goal:raise ValueError('Reference a newly created mechanism without an invented digest')
            goal['definition']=fingerprint(server,owned[goal['network']])
    return campaign


def source(old,programs,suffix):
    import inspect
    from .object_networks import handler
    if not programs:return old
    helper=inspect.getsource(handler).replace('def handler(',f'def _adventure_handler_{suffix}(',1)
    fallback='actor_interact' if 'def actor_interact(' in old else 'None'
    return old+f'\n_adventure_fallback_{suffix}={fallback}\n'+helper+f'''
def actor_interact(identity,action,state):
    for request in {programs!r}:
        if identity in request['objects']:return _adventure_handler_{suffix}(identity,action,state,request)
    if _adventure_fallback_{suffix} is None:raise ValueError('Unknown object')
    return _adventure_fallback_{suffix}(identity,action,state)
'''
